# -*- coding: utf-8 -*-
"""
PDF前処理モジュール（テンプレート版）

OCR精度向上のための前処理:
1. 回転補正（4方向: 0/90/180/270度の全自動判定）
2. 傾き補正（Hough変換 + PCA併用）
3. 影除去（背景推定・除去）
4. 画像最適化（コントラスト強調等）

Usage:
    from pdf_preprocess import PDFPreprocessor

    preprocessor = PDFPreprocessor()
    result = preprocessor.preprocess("input.pdf", "output_dir/")
"""
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple
import logging

import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image


# ロガー（プロジェクトに合わせて変更）
def get_logger():
    return logging.getLogger(__name__)


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
UPSCALE_MIN_WIDTH = 1000
UPSCALE_MIN_HEIGHT = 1000
UPSCALE_FACTOR = 2.0


class PDFRotationDetector:
    """PDF回転方向検出クラス"""

    ROTATION_MIN_DIFF = 0.1

    def __init__(self, dpi: int = 150):
        self.dpi = dpi
        self.logger = get_logger()

    def pdf_to_image(self, pdf_path: Path) -> np.ndarray:
        """PDFを画像に変換"""
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        zoom = self.dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        elif pix.n == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

        doc.close()
        return img

    def rotate_image(self, img: np.ndarray, angle: int) -> np.ndarray:
        """画像を回転（90度単位）"""
        if angle == 90:
            return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            return cv2.rotate(img, cv2.ROTATE_180)
        elif angle == 270:
            return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return img

    def detect_text_score(self, img: np.ndarray) -> float:
        """テキストの「読みやすさ」スコアを計算"""
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        h, w = gray.shape

        # 水平エッジの検出
        sobel_h = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        sobel_v = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)

        h_score = np.sum(np.abs(sobel_h))
        v_score = np.sum(np.abs(sobel_v))
        edge_ratio = h_score / (v_score + 1)

        # 上部のテキスト密度
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        top_half = binary[:h//2, :]
        bottom_half = binary[h//2:, :]

        top_density = np.sum(top_half) / top_half.size
        bottom_density = np.sum(bottom_half) / bottom_half.size
        position_score = top_density / (bottom_density + 0.01)

        # テキスト領域の連続性
        h_projection = np.sum(binary, axis=1)
        v_projection = np.sum(binary, axis=0)

        h_var = np.var(h_projection)
        v_var = np.var(v_projection)
        projection_score = h_var / (v_var + 1)

        total_score = edge_ratio * 0.4 + position_score * 0.2 + projection_score * 0.4
        return total_score

    def detect_best_rotation(self, pdf_path: Path) -> int:
        """最適な回転角度を検出"""
        img = self.pdf_to_image(pdf_path)
        h, w = img.shape[:2]
        is_landscape = w > h

        if is_landscape:
            rotations = [90, 270]
        else:
            rotations = [0, 180]

        scores = []
        for angle in rotations:
            if angle == 0:
                rotated = img
            else:
                rotated = self.rotate_image(img, angle)

            score = self.detect_text_score(rotated)
            scores.append(score)
            self.logger.debug(f"回転 {angle}度: スコア {score:.4f}")

        best_idx = np.argmax(scores)
        best_angle = rotations[best_idx]

        score_diff = abs(scores[0] - scores[1])
        if score_diff < self.ROTATION_MIN_DIFF:
            default_angle = 90 if is_landscape else 0
            return default_angle

        return best_angle

    def detect_orientation_for_landscape(self, pdf_path: Path) -> int:
        """横長PDFの正しい向きを検出"""
        img = self.pdf_to_image(pdf_path)

        img_90 = self.rotate_image(img, 90)
        img_270 = self.rotate_image(img, 270)

        score_90 = self.detect_text_score(img_90)
        score_270 = self.detect_text_score(img_270)

        return 90 if score_90 > score_270 else 270


class PDFPreprocessor:
    """PDF前処理クラス"""

    def __init__(self, dpi: int = 200):
        self.dpi = dpi
        self.logger = get_logger()

    def pdf_to_image(self, pdf_path: Path) -> np.ndarray:
        """PDFを画像に変換"""
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        zoom = self.dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        elif pix.n == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

        doc.close()
        return img

    def image_to_pdf(self, img: np.ndarray, output_path: Path) -> Path:
        """画像をPDFに変換"""
        pil_img = Image.fromarray(img)
        pil_img.save(str(output_path), "PDF", resolution=self.dpi)
        return output_path

    def detect_page_orientation(self, pdf_path: Path, force_4way: bool = True) -> Tuple[bool, int]:
        """ページの向きを検出"""
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        width = page.rect.width
        height = page.rect.height

        needs_rotation = False
        rotation_angle = 0

        detector = PDFRotationDetector(dpi=150)

        if width > height:
            rotation_angle = detector.detect_orientation_for_landscape(pdf_path)
            needs_rotation = True
            self.logger.info(f"横長ページ検出 ({width:.0f}x{height:.0f}) → {rotation_angle}度回転")
        elif force_4way:
            rotation_angle = detector.detect_best_rotation(pdf_path)
            if rotation_angle != 0:
                needs_rotation = True
                self.logger.info(f"4方向検出: {rotation_angle}度回転が必要")

        doc.close()
        return needs_rotation, rotation_angle

    def detect_skew_angle_hough(self, img: np.ndarray) -> float:
        """Hough変換による傾き角度検出"""
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        edges = cv2.Canny(enhanced, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 80)

        if lines is None or len(lines) == 0:
            return 0.0

        angles = []
        for line in lines:
            theta = line[0][1]
            angle_deg = np.degrees(theta) - 90

            if -20 <= angle_deg <= 20:
                angles.append(angle_deg)

        if not angles:
            return 0.0

        return np.median(angles)

    def detect_skew_angle_pca(self, img: np.ndarray) -> float:
        """PCA法による傾き角度検出"""
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(binary > 0))

        if len(coords) < 500:
            return 0.0

        mean = np.mean(coords, axis=0)
        centered = coords - mean
        cov = np.cov(centered.T)

        eigenvalues, eigenvectors = np.linalg.eig(cov)
        idx = np.argmax(eigenvalues)
        angle = np.arctan2(eigenvectors[1, idx], eigenvectors[0, idx]) * 180 / np.pi

        while angle > 45:
            angle -= 90
        while angle < -45:
            angle += 90

        return angle

    def detect_skew_angle(self, img: np.ndarray) -> float:
        """傾き角度を検出（Hough法優先）"""
        angle_hough = self.detect_skew_angle_hough(img)

        if abs(angle_hough) >= 0.1:
            return angle_hough

        angle_pca = self.detect_skew_angle_pca(img)

        if abs(angle_pca) >= 25:
            return 0.0

        if abs(angle_pca) >= 0.5:
            return angle_pca

        return 0.0

    def deskew_image(self, img: np.ndarray, angle: float, threshold: float = SKEW_THRESHOLD_DEFAULT) -> np.ndarray:
        """画像の傾きを補正"""
        if abs(angle) < threshold:
            return img

        h, w = img.shape[:2]
        center = (w // 2, h // 2)

        M = cv2.getRotationMatrix2D(center, angle, 1.0)

        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int(h * sin + w * cos)
        new_h = int(h * cos + w * sin)

        M[0, 2] += (new_w - w) / 2
        M[1, 2] += (new_h - h) / 2

        rotated = cv2.warpAffine(
            img, M, (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)
        )

        return rotated

    def enhance_image(self, img: np.ndarray) -> np.ndarray:
        """OCR向けの画像強調"""
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
        result = cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)

        return result

    def upscale_image(self, img: np.ndarray) -> np.ndarray:
        """低解像度画像をアップスケール"""
        h, w = img.shape[:2]

        if w >= UPSCALE_MIN_WIDTH and h >= UPSCALE_MIN_HEIGHT:
            return img

        scale = UPSCALE_FACTOR
        if w < UPSCALE_MIN_WIDTH:
            scale = max(scale, UPSCALE_MIN_WIDTH / w)
        if h < UPSCALE_MIN_HEIGHT:
            scale = max(scale, UPSCALE_MIN_HEIGHT / h)

        scale = min(scale, 3.0)

        new_w = int(w * scale)
        new_h = int(h * scale)

        upscaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        self.logger.info(f"アップスケール実行: {w}x{h} → {new_w}x{new_h} ({scale:.1f}倍)")

        return upscaled

    def detect_shadow(self, img: np.ndarray) -> bool:
        """影の存在を検出"""
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        h, w = gray.shape
        block_h, block_w = h // 4, w // 4

        brightnesses = []
        for i in range(4):
            for j in range(4):
                block = gray[i*block_h:(i+1)*block_h, j*block_w:(j+1)*block_w]
                brightnesses.append(np.mean(block))

        std_brightness = np.std(brightnesses)
        has_shadow = std_brightness > 30

        return has_shadow

    def remove_shadow(self, img: np.ndarray) -> np.ndarray:
        """影を除去"""
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        kernel_size = max(gray.shape[0], gray.shape[1]) // 10
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel_size = max(kernel_size, 51)

        background = cv2.GaussianBlur(gray, (kernel_size, kernel_size), 0)

        mean_bg = np.mean(background)
        with np.errstate(divide='ignore', invalid='ignore'):
            normalized = gray.astype(np.float32) * (mean_bg / background.astype(np.float32))
            normalized = np.clip(normalized, 0, 255).astype(np.uint8)

        min_val, max_val = np.percentile(normalized, [2, 98])
        if max_val > min_val:
            stretched = np.clip(
                (normalized - min_val) * 255.0 / (max_val - min_val),
                0, 255
            ).astype(np.uint8)
        else:
            stretched = normalized

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
        """PDF前処理のメイン関数"""
        pdf_path = Path(pdf_path)
        if output_dir is None:
            output_dir = pdf_path.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        result = PreprocessResult(output_path=pdf_path)

        try:
            img_modified = False
            img = self.pdf_to_image(pdf_path)

            # 1. 傾き補正（回転前に実行）
            if do_deskew:
                skew_angle = self.detect_skew_angle(img)

                if abs(skew_angle) >= skew_threshold:
                    self.logger.info(f"傾き検出: {skew_angle:.2f}度 → 補正")
                    img = self.deskew_image(img, skew_angle, threshold=skew_threshold)
                    result.deskewed = True
                    result.skew_angle = skew_angle
                    img_modified = True

            # 2. 回転補正
            temp_pdf = None
            if img_modified:
                temp_pdf = output_dir / f"_temp_{pdf_path.name}"
                self.image_to_pdf(img, temp_pdf)
                detect_path = temp_pdf
            else:
                detect_path = pdf_path

            needs_rotation, rotation_angle = self.detect_page_orientation(
                detect_path, force_4way=force_4way_rotation
            )

            if needs_rotation:
                if rotation_angle == 90:
                    img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                elif rotation_angle == 180:
                    img = cv2.rotate(img, cv2.ROTATE_180)
                elif rotation_angle == 270:
                    img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                result.rotated = True
                result.rotation_angle = rotation_angle
                img_modified = True

            if temp_pdf and temp_pdf.exists():
                temp_pdf.unlink()

            # 3. アップスケール
            h, w = img.shape[:2]
            if w < UPSCALE_MIN_WIDTH or h < UPSCALE_MIN_HEIGHT:
                img = self.upscale_image(img)
                img_modified = True

            # 4. 影除去
            if do_shadow_removal:
                has_shadow = self.detect_shadow(img)
                if has_shadow:
                    img = self.remove_shadow(img)
                    result.shadow_removed = True
                    img_modified = True

            # 5. 画像強調
            if do_enhance:
                img = self.enhance_image(img)
                result.enhanced = True
                img_modified = True

            # 出力
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


if __name__ == "__main__":
    # テスト実行
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="PDF前処理")
    parser.add_argument("pdf", help="入力PDFファイルパス")
    parser.add_argument("--output-dir", "-o", help="出力ディレクトリ")
    parser.add_argument("--no-deskew", action="store_true", help="傾き補正をスキップ")
    parser.add_argument("--enhance", action="store_true", help="画像強調を有効化")

    args = parser.parse_args()

    preprocessor = PDFPreprocessor(dpi=200)
    result = preprocessor.preprocess(
        Path(args.pdf),
        Path(args.output_dir) if args.output_dir else None,
        do_deskew=not args.no_deskew,
        do_enhance=args.enhance
    )

    print(f"\n=== 前処理結果 ===")
    print(f"出力: {result.output_path}")
    print(f"回転: {result.rotated} ({result.rotation_angle}度)")
    print(f"傾き補正: {result.deskewed} ({result.skew_angle:.1f}度)")
    print(f"影除去: {result.shadow_removed}")
    print(f"画像強調: {result.enhanced}")
    print(f"成功: {result.success}")
    if result.error:
        print(f"エラー: {result.error}")
