# -*- coding: utf-8 -*-
"""
PDF前処理モジュール（強化版）

OCR精度向上のための前処理:
1. 回転補正（4方向: 0/90/180/270度の全自動判定）
2. 傾き補正（Hough変換 + PCA併用）
3. 影除去（背景推定・除去）
4. 画像最適化（コントラスト強調等）

Updated: 2026-01-14 - Document AI廃止対応

Usage:
    from pdf_preprocess import PDFPreprocessor

    preprocessor = PDFPreprocessor()
    result = preprocessor.preprocess("input.pdf", "output_dir/")
"""
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple
import tempfile

sys.path.insert(0, str(Path(__file__).parent))

import fitz
import cv2
import numpy as np
from PIL import Image
import io

from common.logger import get_logger
from pdf_rotation_detect import PDFRotationDetector


@dataclass
class PreprocessResult:
    """前処理結果"""
    output_path: Path
    rotated: bool = False
    rotation_angle: int = 0
    deskewed: bool = False
    skew_angle: float = 0.0
    shadow_removed: bool = False
    enhanced: bool = False
    success: bool = True
    error: str = ""


# 傾き補正閾値（度）
SKEW_THRESHOLD_DEFAULT = 0.5

# アップスケール設定
UPSCALE_MIN_WIDTH = 1000   # この幅以下ならアップスケール
UPSCALE_MIN_HEIGHT = 1000  # この高さ以下ならアップスケール
UPSCALE_FACTOR = 2.0       # アップスケール倍率


class PDFPreprocessor:
    """PDF前処理クラス"""

    def __init__(self, dpi: int = 200):
        """
        Args:
            dpi: 画像変換時の解像度
        """
        self.dpi = dpi
        self.logger = get_logger()

    def pdf_to_image(self, pdf_path: Path) -> np.ndarray:
        """PDFを画像に変換"""
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        zoom = self.dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # numpy配列に変換
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        elif pix.n == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

        doc.close()
        return img

    def image_to_pdf(self, img: np.ndarray, output_path: Path) -> Path:
        """画像をPDFに変換"""
        # numpy → PIL
        pil_img = Image.fromarray(img)

        # PDFとして保存
        pil_img.save(str(output_path), "PDF", resolution=self.dpi)

        return output_path

    def detect_page_orientation(self, pdf_path: Path, force_4way: bool = True) -> Tuple[bool, int]:
        """
        ページの向きを検出（4方向全自動判定対応）

        Args:
            pdf_path: 入力PDF
            force_4way: 縦長でも4方向検出を行うか（デフォルト: True）

        Returns:
            (回転が必要か, 回転角度)
        """
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        width = page.rect.width
        height = page.rect.height

        needs_rotation = False
        rotation_angle = 0

        # 回転検出器を使用（強化版）
        detector = PDFRotationDetector(dpi=150)

        # 横長ページの場合
        if width > height:
            # テキスト方向を解析して90度か270度かを判定
            rotation_angle = detector.detect_orientation_for_landscape(pdf_path)
            needs_rotation = True
            self.logger.info(f"横長ページ検出 ({width:.0f}x{height:.0f}) → {rotation_angle}度回転")
        elif force_4way:
            # 縦長でも4方向検出を実行（180度反転チェック含む）
            rotation_angle = detector.detect_best_rotation(pdf_path, use_enhanced=True)
            if rotation_angle != 0:
                needs_rotation = True
                self.logger.info(f"4方向検出: {rotation_angle}度回転が必要")

        # 縦長だが画像が横長の場合（force_4wayがTrueの場合は既に検出済み）
        if not force_4way:
            images = page.get_images()
            if images and not needs_rotation:
                xref = images[0][0]
                base_image = doc.extract_image(xref)
                img_w, img_h = base_image['width'], base_image['height']

                if img_w > img_h:
                    # 画像が横長 = 90度か270度の回転が必要
                    rotation_angle = detector.detect_orientation_for_landscape(pdf_path)
                    needs_rotation = True
                    self.logger.info(f"横長画像検出 ({img_w}x{img_h}) → {rotation_angle}度回転")

        doc.close()
        return needs_rotation, rotation_angle

    def rotate_pdf(self, pdf_path: Path, rotation: int, output_path: Path) -> Path:
        """PDFを回転"""
        doc = fitz.open(str(pdf_path))

        for page in doc:
            page.set_rotation(rotation)

        doc.save(str(output_path))
        doc.close()

        return output_path

    def detect_skew_angle_pca(self, img: np.ndarray) -> float:
        """
        PCA法による傾き角度検出

        主成分分析（PCA）でテキスト行の傾きを推定

        Returns:
            傾き角度（度）、-45〜+45の範囲
        """
        # グレースケール
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        # 二値化（Otsu）
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # テキスト領域の座標を取得
        coords = np.column_stack(np.where(binary > 0))

        if len(coords) < 500:
            # テキストが少なすぎる場合はスキップ
            return 0.0

        # 主成分分析
        mean = np.mean(coords, axis=0)
        centered = coords - mean
        cov = np.cov(centered.T)

        eigenvalues, eigenvectors = np.linalg.eig(cov)

        # 最大固有値に対応する角度
        idx = np.argmax(eigenvalues)
        angle = np.arctan2(eigenvectors[1, idx], eigenvectors[0, idx]) * 180 / np.pi

        # -45〜45度に正規化
        while angle > 45:
            angle -= 90
        while angle < -45:
            angle += 90

        return angle

    def detect_skew_angle_hough(self, img: np.ndarray) -> float:
        """
        Hough変換による傾き角度検出

        直線検出から主要な傾き角度を推定

        Returns:
            傾き角度（度）、-45〜+45の範囲
        """
        # グレースケール
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        # エッジ検出
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        # Hough変換で直線検出
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

        if lines is None or len(lines) == 0:
            return 0.0

        # 角度を収集（水平線に近いもののみ）
        angles = []
        for line in lines[:100]:  # 最大100本
            theta = line[0][1]
            angle_deg = np.degrees(theta) - 90  # 水平を0度に

            # -45〜45度の範囲のみ
            if -45 <= angle_deg <= 45:
                angles.append(angle_deg)

        if not angles:
            return 0.0

        # 中央値を使用（外れ値に強い）
        return np.median(angles)

    def detect_skew_angle(self, img: np.ndarray) -> float:
        """
        傾き角度を検出（Hough変換 + PCA併用）

        両手法の結果を組み合わせて精度向上

        Returns:
            傾き角度（度）、-45〜+45の範囲
        """
        # PCA法
        angle_pca = self.detect_skew_angle_pca(img)

        # Hough変換法
        angle_hough = self.detect_skew_angle_hough(img)

        # 両方の結果を考慮
        if abs(angle_pca) < 0.1 and abs(angle_hough) < 0.1:
            # 両方とも0に近い → 傾きなし
            return 0.0

        if abs(angle_hough) < 0.1:
            # Houghが検出できない → PCAを採用
            return angle_pca

        if abs(angle_pca) < 0.1:
            # PCAが検出できない → Houghを採用
            return angle_hough

        # 両方検出できた場合
        # 差が5度以内なら平均、そうでなければHoughを優先
        if abs(angle_pca - angle_hough) < 5.0:
            return (angle_pca + angle_hough) / 2
        else:
            # Hough変換の方が直線検出に特化しているため優先
            self.logger.debug(
                f"傾き検出差異: PCA={angle_pca:.2f}, Hough={angle_hough:.2f} → Hough採用"
            )
            return angle_hough

    def deskew_image(self, img: np.ndarray, angle: float, threshold: float = SKEW_THRESHOLD_DEFAULT) -> np.ndarray:
        """
        画像の傾きを補正

        Args:
            img: 入力画像
            angle: 傾き角度（度）
            threshold: 補正を行う最小角度（デフォルト: 0.5度）

        Returns:
            補正後の画像
        """
        if abs(angle) < threshold:
            # 閾値未満は補正しない
            return img

        h, w = img.shape[:2]
        center = (w // 2, h // 2)

        # 回転行列
        M = cv2.getRotationMatrix2D(center, angle, 1.0)

        # 回転後のサイズ計算
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int(h * sin + w * cos)
        new_h = int(h * cos + w * sin)

        # 平行移動を調整
        M[0, 2] += (new_w - w) / 2
        M[1, 2] += (new_h - h) / 2

        # 回転実行（白で埋める）
        rotated = cv2.warpAffine(
            img, M, (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)
        )

        return rotated

    def enhance_image(self, img: np.ndarray) -> np.ndarray:
        """
        OCR向けの画像強調

        - コントラスト強調
        - ノイズ除去
        """
        # グレースケール変換
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        # CLAHE（適応的ヒストグラム均等化）
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # 軽いノイズ除去
        denoised = cv2.fastNlMeansDenoising(enhanced, h=10)

        # RGBに戻す
        result = cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)

        return result

    def upscale_image(self, img: np.ndarray) -> np.ndarray:
        """
        低解像度画像をアップスケール

        小さい画像は文字認識精度が低下するため拡大

        Returns:
            アップスケール後の画像
        """
        h, w = img.shape[:2]

        # アップスケールが必要か判定
        if w >= UPSCALE_MIN_WIDTH and h >= UPSCALE_MIN_HEIGHT:
            return img

        # アップスケール倍率を計算
        scale = UPSCALE_FACTOR
        if w < UPSCALE_MIN_WIDTH:
            scale = max(scale, UPSCALE_MIN_WIDTH / w)
        if h < UPSCALE_MIN_HEIGHT:
            scale = max(scale, UPSCALE_MIN_HEIGHT / h)

        # 最大3倍まで
        scale = min(scale, 3.0)

        new_w = int(w * scale)
        new_h = int(h * scale)

        # INTER_CUBICで高品質アップスケール
        upscaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

        self.logger.info(f"アップスケール実行: {w}x{h} → {new_w}x{new_h} ({scale:.1f}倍)")

        return upscaled

    def detect_shadow(self, img: np.ndarray) -> bool:
        """
        影の存在を検出

        明度のばらつきから影の有無を判定

        Returns:
            影が検出されたか
        """
        # グレースケール
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        # 画像を複数領域に分割して明度を比較
        h, w = gray.shape
        block_h, block_w = h // 4, w // 4

        brightnesses = []
        for i in range(4):
            for j in range(4):
                block = gray[i*block_h:(i+1)*block_h, j*block_w:(j+1)*block_w]
                brightnesses.append(np.mean(block))

        # 明度の標準偏差が大きい = 影がある可能性
        std_brightness = np.std(brightnesses)

        # 閾値（経験則: 30以上で影あり）
        has_shadow = std_brightness > 30

        if has_shadow:
            self.logger.debug(f"影検出: 明度標準偏差={std_brightness:.1f}")

        return has_shadow

    def remove_shadow(self, img: np.ndarray) -> np.ndarray:
        """
        影を除去

        背景推定により影を除去してOCR精度を向上

        Returns:
            影除去後の画像
        """
        # グレースケール
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        # 背景推定（大きなカーネルでぼかす）
        # 背景 = 影を含む大局的な明るさ
        kernel_size = max(gray.shape[0], gray.shape[1]) // 10
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel_size = max(kernel_size, 51)  # 最小51

        background = cv2.GaussianBlur(gray, (kernel_size, kernel_size), 0)

        # 背景で割って正規化（影を除去）
        # 公式: result = gray * (mean_bg / background)
        mean_bg = np.mean(background)
        with np.errstate(divide='ignore', invalid='ignore'):
            normalized = gray.astype(np.float32) * (mean_bg / background.astype(np.float32))
            normalized = np.clip(normalized, 0, 255).astype(np.uint8)

        # コントラスト補正
        # ヒストグラムストレッチ
        min_val, max_val = np.percentile(normalized, [2, 98])
        if max_val > min_val:
            stretched = np.clip(
                (normalized - min_val) * 255.0 / (max_val - min_val),
                0, 255
            ).astype(np.uint8)
        else:
            stretched = normalized

        # RGBに戻す
        result = cv2.cvtColor(stretched, cv2.COLOR_GRAY2RGB)

        self.logger.info("影除去処理を実行")
        return result

    def preprocess(
        self,
        pdf_path: Path,
        output_dir: Path = None,
        do_deskew: bool = True,
        do_enhance: bool = False,
        do_shadow_removal: bool = True,
        skew_threshold: float = SKEW_THRESHOLD_DEFAULT,
        force_4way_rotation: bool = True
    ) -> PreprocessResult:
        """
        PDF前処理のメイン関数

        Args:
            pdf_path: 入力PDF
            output_dir: 出力ディレクトリ（Noneなら同じディレクトリ）
            do_deskew: 傾き補正を行うか
            do_enhance: 画像強調を行うか
            do_shadow_removal: 影除去を行うか（Trueなら影検出時のみ実行）
            skew_threshold: 傾き補正を行う閾値（度）デフォルト: 0.5度
            force_4way_rotation: 縦長でも4方向検出を行うか

        Returns:
            前処理結果
        """
        pdf_path = Path(pdf_path)
        if output_dir is None:
            output_dir = pdf_path.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        result = PreprocessResult(output_path=pdf_path)

        try:
            current_path = pdf_path
            img_modified = False  # 画像が変更されたか

            # 1. 回転補正（4方向対応）
            needs_rotation, rotation_angle = self.detect_page_orientation(
                current_path,
                force_4way=force_4way_rotation
            )

            if needs_rotation:
                rotated_path = output_dir / f"_preproc_{pdf_path.name}"
                current_path = self.rotate_pdf(current_path, rotation_angle, rotated_path)
                result.rotated = True
                result.rotation_angle = rotation_angle

            # 画像を読み込み（傾き補正・影除去・画像強調で共有）
            img = self.pdf_to_image(current_path)

            # 1.5. 低解像度の場合はアップスケール
            h, w = img.shape[:2]
            if w < UPSCALE_MIN_WIDTH or h < UPSCALE_MIN_HEIGHT:
                img = self.upscale_image(img)
                img_modified = True

            # 2. 影除去（オプション、影検出時のみ実行）
            if do_shadow_removal:
                has_shadow = self.detect_shadow(img)
                if has_shadow:
                    img = self.remove_shadow(img)
                    result.shadow_removed = True
                    img_modified = True

            # 3. 傾き補正（オプション）
            if do_deskew:
                skew_angle = self.detect_skew_angle(img)

                if abs(skew_angle) >= skew_threshold:
                    self.logger.info(f"傾き検出: {skew_angle:.2f}度 → 補正")
                    img = self.deskew_image(img, skew_angle, threshold=skew_threshold)
                    result.deskewed = True
                    result.skew_angle = skew_angle
                    img_modified = True

            # 4. 画像強調（オプション）
            if do_enhance:
                img = self.enhance_image(img)
                result.enhanced = True
                img_modified = True

            # 画像が変更された場合のみPDFを再生成
            if img_modified:
                if not result.rotated:
                    output_path = output_dir / f"_preproc_{pdf_path.name}"
                else:
                    output_path = current_path
                current_path = self.image_to_pdf(img, output_path)

            result.output_path = current_path
            result.success = True

            self.logger.info(
                f"前処理完了: rotated={result.rotated} ({result.rotation_angle}度), "
                f"deskewed={result.deskewed} ({result.skew_angle:.1f}度), "
                f"shadow_removed={result.shadow_removed}, "
                f"enhanced={result.enhanced}"
            )

        except Exception as e:
            result.success = False
            result.error = str(e)
            self.logger.error(f"前処理エラー: {e}")

        return result


def test_preprocess():
    """テスト実行"""
    from common.logger import setup_logger
    setup_logger("preprocess_test")

    sample_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\sample PDF")
    output_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data\preprocess_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    preprocessor = PDFPreprocessor(dpi=200)

    # テスト対象
    test_files = [
        "(株)ニトリ.pdf",
        "20260108192522.pdf",
        "東京インテリア家具.pdf",
        "doc06562520260108152210.pdf",
        "0109セリア(百均)買物.pdf",
    ]

    print("=" * 80)
    print("PDF前処理テスト（強化版）")
    print("=" * 80)
    print(f"傾き補正閾値: {SKEW_THRESHOLD_DEFAULT}度")
    print("=" * 80)

    for pdf_name in test_files:
        pdf_path = sample_dir / pdf_name
        if not pdf_path.exists():
            print(f"\n[SKIP] {pdf_name}")
            continue

        print(f"\n--- {pdf_name} ---")

        result = preprocessor.preprocess(
            pdf_path,
            output_dir,
            do_deskew=True,
            do_enhance=False,  # 画像強調はOCRエンジン側に任せる
            do_shadow_removal=True,  # 影除去を有効化
            skew_threshold=SKEW_THRESHOLD_DEFAULT,  # 0.5度以上で傾き補正
            force_4way_rotation=True  # 4方向検出有効
        )

        if result.success:
            print(f"  出力: {result.output_path.name}")
            print(f"  回転: {result.rotated} ({result.rotation_angle}度)")
            print(f"  傾き補正: {result.deskewed} ({result.skew_angle:.1f}度)")
            print(f"  影除去: {result.shadow_removed}")
        else:
            print(f"  [ERROR] {result.error}")

    print("\n" + "=" * 80)
    print(f"出力先: {output_dir}")


if __name__ == "__main__":
    test_preprocess()
