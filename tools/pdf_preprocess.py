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

# アップスケール設定（Phase1改善: 1000→1200px）
UPSCALE_MIN_WIDTH = 1200   # この幅以下ならアップスケール
UPSCALE_MIN_HEIGHT = 1200  # この高さ以下ならアップスケール
UPSCALE_FACTOR = 2.0       # アップスケール倍率

# Sauvola二値化用（オプション）
try:
    from skimage.filters import threshold_sauvola
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False


class PDFPreprocessor:
    """PDF前処理クラス"""

    def __init__(self, dpi: int = 300):
        """
        Args:
            dpi: 画像変換時の解像度（デフォルト300dpi推奨）
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
            # テキスト方向を解析して90度か270度かを判定（0の場合は回転不要）
            rotation_angle = detector.detect_orientation_for_landscape(pdf_path)
            if rotation_angle != 0:
                needs_rotation = True
                self.logger.info(f"横長ページ検出 ({width:.0f}x{height:.0f}) → {rotation_angle}度回転")
            else:
                self.logger.info(f"横長ページ検出 ({width:.0f}x{height:.0f}) → 回転スキップ（スコア条件未達）")
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
                    # 画像が横長 = 90度か270度の回転が必要（0の場合は回転不要）
                    rotation_angle = detector.detect_orientation_for_landscape(pdf_path)
                    if rotation_angle != 0:
                        needs_rotation = True
                        self.logger.info(f"横長画像検出 ({img_w}x{img_h}) → {rotation_angle}度回転")
                    else:
                        self.logger.info(f"横長画像検出 ({img_w}x{img_h}) → 回転スキップ（スコア条件未達）")

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
        Hough変換による傾き角度検出（改善版）

        CLAHE前処理 + 低閾値でコントラストの弱い画像でも直線検出可能

        Returns:
            傾き角度（度）、-20〜+20の範囲（それ以外は0.0）
        """
        # グレースケール
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        # CLAHE（適応的ヒストグラム均等化）でコントラスト強調
        # 薄い印刷やスキャン画像でもエッジを検出しやすくなる
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # エッジ検出
        edges = cv2.Canny(enhanced, 50, 150, apertureSize=3)

        # Hough変換で直線検出（閾値80: 薄い画像でも検出可能）
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 80)

        if lines is None or len(lines) == 0:
            return 0.0

        # 角度を収集（水平に近い線のみ: -20〜+20度）
        angles = []
        for line in lines:
            theta = line[0][1]
            angle_deg = np.degrees(theta) - 90  # 水平を0度に

            # -20〜+20度の範囲のみ（レシートの傾きは通常この範囲内）
            if -20 <= angle_deg <= 20:
                angles.append(angle_deg)

        if not angles:
            return 0.0

        # 中央値を使用（外れ値に強い）
        return np.median(angles)

    def detect_skew_angle(self, img: np.ndarray) -> float:
        """
        傾き角度を検出（改善Hough法優先）

        改善Hough法は33サンプルで異常検出0%を達成したため優先使用
        Houghが検出できない場合のみPCA法をフォールバックとして使用

        Returns:
            傾き角度（度）、-20〜+20の範囲
        """
        # 改善Hough法（CLAHE + 閾値80）
        angle_hough = self.detect_skew_angle_hough(img)

        # Houghが有効な角度を検出した場合はそれを使用
        if abs(angle_hough) >= 0.1:
            self.logger.debug(f"傾き検出(Hough): {angle_hough:.2f}度")
            return angle_hough

        # Houghが0に近い場合、PCA法でダブルチェック
        angle_pca = self.detect_skew_angle_pca(img)

        # PCAが極端な値（25度以上）の場合は信頼しない
        if abs(angle_pca) >= 25:
            self.logger.debug(f"傾き検出(PCA): {angle_pca:.2f}度 → 異常値のため0を返す")
            return 0.0

        # PCAが妥当な範囲の場合
        if abs(angle_pca) >= 0.5:
            self.logger.debug(f"傾き検出(PCA fallback): {angle_pca:.2f}度")
            return angle_pca

        # 両方とも0に近い → 傾きなし
        return 0.0

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

        # CLAHE（適応的ヒストグラム均等化）- 強化版
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
        enhanced = clahe.apply(gray)

        # 軽いノイズ除去
        denoised = cv2.fastNlMeansDenoising(enhanced, h=10)

        # RGBに戻す
        result = cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)

        return result

    def adaptive_binarize_sauvola(self, img: np.ndarray, window_size: int = 25, k: float = 0.2) -> np.ndarray:
        """
        Sauvola法による適応的二値化（FAX画像に効果的）

        局所的な閾値を計算するため、明暗差のある画像でも効果的

        Args:
            img: 入力画像
            window_size: 局所閾値計算のウィンドウサイズ（奇数）
            k: Sauvolaパラメータ（0.2が標準）

        Returns:
            二値化された画像
        """
        if not SKIMAGE_AVAILABLE:
            self.logger.warning("scikit-image未インストール: Sauvola二値化スキップ")
            return img

        # グレースケール変換
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        # Sauvola閾値計算
        thresh = threshold_sauvola(gray, window_size=window_size, k=k)

        # 二値化
        binary = (gray > thresh).astype(np.uint8) * 255

        # RGBに戻す
        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)

        self.logger.debug(f"Sauvola二値化実行: window={window_size}, k={k}")
        return result

    def denoise_bilateral(self, img: np.ndarray, d: int = 9, sigma_color: float = 75, sigma_space: float = 75) -> np.ndarray:
        """
        バイラテラルフィルタによるノイズ除去

        エッジを保持しながらノイズを除去（FAX/スキャン画像に効果的）

        Args:
            img: 入力画像
            d: フィルタサイズ（-1で自動）
            sigma_color: 色空間のシグマ
            sigma_space: 座標空間のシグマ

        Returns:
            ノイズ除去後の画像
        """
        result = cv2.bilateralFilter(img, d=d, sigmaColor=sigma_color, sigmaSpace=sigma_space)
        self.logger.debug(f"バイラテラルフィルタ実行: d={d}")
        return result

    def remove_moire(self, img: np.ndarray, kernel_size: int = 3) -> np.ndarray:
        """
        モアレパターン除去

        FAX画像特有の縞模様ノイズを軽減

        Args:
            img: 入力画像
            kernel_size: ガウシアンカーネルサイズ（奇数）

        Returns:
            モアレ除去後の画像
        """
        # グレースケール変換
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        # ガウシアンぼかしで高周波ノイズ（モアレ）を除去
        blurred = cv2.GaussianBlur(gray, (kernel_size, kernel_size), 0)

        # RGBに戻す
        result = cv2.cvtColor(blurred, cv2.COLOR_GRAY2RGB)

        self.logger.debug(f"モアレ除去実行: kernel={kernel_size}")
        return result

    def add_border(self, img: np.ndarray, border_size: int = 10) -> np.ndarray:
        """
        画像に白ボーダーを追加（OCR認識向上）

        Tesseract公式推奨: 画像端に文字があると認識失敗しやすいため
        10px以上の白ボーダーを追加

        Args:
            img: 入力画像
            border_size: ボーダーサイズ（ピクセル）

        Returns:
            ボーダー追加後の画像
        """
        result = cv2.copyMakeBorder(
            img, border_size, border_size, border_size, border_size,
            cv2.BORDER_CONSTANT, value=(255, 255, 255)
        )
        self.logger.debug(f"白ボーダー追加: {border_size}px")
        return result

    def adjust_character_thickness(self, img: np.ndarray, mode: str = 'auto') -> np.ndarray:
        """
        文字の太さを調整（膨張/収縮）

        細すぎる文字は膨張、太すぎる文字は収縮で調整
        レシートの薄い印字に効果的

        Args:
            img: 入力画像
            mode: 'dilate'（膨張=太く）, 'erode'（収縮=細く）, 'auto'（自動判定）, 'none'

        Returns:
            調整後の画像
        """
        # グレースケール変換
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        kernel = np.ones((2, 2), np.uint8)

        if mode == 'auto':
            # 黒ピクセル密度で判定
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            black_ratio = np.sum(binary > 0) / binary.size
            # 薄い印字（黒が少ない）なら膨張
            if black_ratio < 0.03:
                mode = 'dilate'
                self.logger.debug(f"自動判定: 薄い印字検出（黒比率{black_ratio:.1%}）→ 膨張")
            elif black_ratio > 0.15:
                mode = 'erode'
                self.logger.debug(f"自動判定: 太い文字検出（黒比率{black_ratio:.1%}）→ 収縮")
            else:
                mode = 'none'

        if mode == 'dilate':
            processed = cv2.dilate(gray, kernel, iterations=1)
            self.logger.debug("文字膨張処理を実行")
        elif mode == 'erode':
            processed = cv2.erode(gray, kernel, iterations=1)
            self.logger.debug("文字収縮処理を実行")
        else:
            processed = gray

        # RGBに戻す
        return cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB)

    def sharpen_unsharp_mask(self, img: np.ndarray, sigma: float = 1.0, strength: float = 1.5) -> np.ndarray:
        """
        アンシャープマスクで文字エッジを強調

        ぼやけた文字のエッジを強調してOCR精度向上

        Args:
            img: 入力画像
            sigma: ガウシアンぼかしのシグマ
            strength: シャープ化の強度（1.0-2.0推奨）

        Returns:
            シャープ化後の画像
        """
        blurred = cv2.GaussianBlur(img, (0, 0), sigma)
        sharpened = cv2.addWeighted(img, 1 + strength, blurred, -strength, 0)
        result = np.clip(sharpened, 0, 255).astype(np.uint8)
        self.logger.debug(f"アンシャープマスク実行: sigma={sigma}, strength={strength}")
        return result

    def stretch_contrast(self, img: np.ndarray, percentile: tuple = (2, 98)) -> np.ndarray:
        """
        パーセンタイルベースのコントラストストレッチ

        全体的に薄い/暗い画像を自動補正

        Args:
            img: 入力画像
            percentile: 正規化に使用するパーセンタイル範囲

        Returns:
            コントラスト補正後の画像
        """
        # グレースケール変換
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        p_low, p_high = np.percentile(gray, percentile)

        if p_high > p_low:
            stretched = np.clip(
                (gray.astype(np.float32) - p_low) * 255.0 / (p_high - p_low),
                0, 255
            ).astype(np.uint8)
        else:
            stretched = gray

        self.logger.debug(f"コントラストストレッチ実行: range=[{p_low:.0f}, {p_high:.0f}]")

        # RGBに戻す
        return cv2.cvtColor(stretched, cv2.COLOR_GRAY2RGB)

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
        do_binarize: bool = False,
        do_denoise: bool = False,
        do_moire_removal: bool = False,
        do_border: bool = True,
        do_sharpen: bool = False,
        do_stretch: bool = True,
        do_thickness_adjust: bool = True,
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
            do_binarize: Sauvola適応的二値化を行うか（FAX画像に効果的）
            do_denoise: バイラテラルフィルタでノイズ除去を行うか
            do_moire_removal: モアレパターン除去を行うか
            do_border: 白ボーダーを追加するか（OCR端文字認識向上）
            do_sharpen: アンシャープマスクでエッジ強調するか
            do_stretch: コントラストストレッチを行うか
            do_thickness_adjust: 文字太さの自動調整を行うか（薄い印字対応）
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
            img_modified = False  # 画像が変更されたか

            # 0. 元画像を読み込み（傾き検出は回転前に行う必要がある）
            img = self.pdf_to_image(pdf_path)

            # 1. 傾き補正（回転前に実行！）
            # 重要: Hough変換による傾き検出は水平線を基準にするため、
            #       回転後（縦向き）では正しく検出できない。
            #       そのため、元の向きで傾き検出・補正を行う。
            if do_deskew:
                skew_angle = self.detect_skew_angle(img)

                if abs(skew_angle) >= skew_threshold:
                    self.logger.info(f"傾き検出: {skew_angle:.2f}度 → 補正")
                    img = self.deskew_image(img, skew_angle, threshold=skew_threshold)
                    result.deskewed = True
                    result.skew_angle = skew_angle
                    img_modified = True

            # 2. 回転補正（4方向対応）
            # 傾き補正後の画像で回転方向を判定
            # 一時PDFに保存して回転検出
            temp_pdf = None
            if img_modified:
                temp_pdf = output_dir / f"_temp_{pdf_path.name}"
                self.image_to_pdf(img, temp_pdf)
                detect_path = temp_pdf
            else:
                detect_path = pdf_path

            needs_rotation, rotation_angle = self.detect_page_orientation(
                detect_path,
                force_4way=force_4way_rotation
            )

            if needs_rotation:
                # 画像を回転（OpenCVで直接回転）
                if rotation_angle == 90:
                    img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                elif rotation_angle == 180:
                    img = cv2.rotate(img, cv2.ROTATE_180)
                elif rotation_angle == 270:
                    img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                result.rotated = True
                result.rotation_angle = rotation_angle
                img_modified = True

            # 一時ファイル削除
            if temp_pdf and temp_pdf.exists():
                temp_pdf.unlink()

            # 3. 低解像度の場合はアップスケール
            h, w = img.shape[:2]
            if w < UPSCALE_MIN_WIDTH or h < UPSCALE_MIN_HEIGHT:
                img = self.upscale_image(img)
                img_modified = True

            # 3.5 超低解像度（900x700未満）の場合はenhanceも強制適用
            is_very_low_res = (w < 900 or h < 700)
            if is_very_low_res and not do_enhance:
                img = self.enhance_image(img)
                result.enhanced = True
                img_modified = True
                self.logger.info(f"超低解像度のため強制enhance適用: {w}x{h}")

            # 4. 影除去（オプション、影検出時のみ実行）
            if do_shadow_removal:
                has_shadow = self.detect_shadow(img)
                if has_shadow:
                    img = self.remove_shadow(img)
                    result.shadow_removed = True
                    img_modified = True

            # 5. 画像強調（オプション）
            if do_enhance:
                img = self.enhance_image(img)
                result.enhanced = True
                img_modified = True

            # 6. バイラテラルフィルタでノイズ除去（オプション）
            if do_denoise:
                img = self.denoise_bilateral(img)
                img_modified = True

            # 7. モアレ除去（オプション）
            if do_moire_removal:
                img = self.remove_moire(img)
                img_modified = True

            # 8. Sauvola適応的二値化（オプション、FAX画像向け）
            if do_binarize:
                img = self.adaptive_binarize_sauvola(img)
                img_modified = True

            # 9. コントラストストレッチ（薄い/暗い画像対応）
            if do_stretch:
                img = self.stretch_contrast(img)
                img_modified = True

            # 10. 文字太さ自動調整（薄い印字対応）
            if do_thickness_adjust:
                img = self.adjust_character_thickness(img, mode='auto')
                img_modified = True

            # 11. アンシャープマスク（ぼやけた文字対応）
            if do_sharpen:
                img = self.sharpen_unsharp_mask(img)
                img_modified = True

            # 12. 白ボーダー追加（最後に実行）
            if do_border:
                img = self.add_border(img)
                img_modified = True

            # 画像が変更された場合のみPDFを再生成
            output_path = output_dir / f"_preproc_{pdf_path.name}"
            if img_modified:
                self.image_to_pdf(img, output_path)
                result.output_path = output_path
            else:
                result.output_path = pdf_path

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
