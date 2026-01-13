# -*- coding: utf-8 -*-
"""
PDF前処理モジュール（OCR精度向上用）

前処理内容:
1. 解像度向上（300dpi以上に統一）
2. コントラスト/シャープネス強調
3. 傾き補正（自動検出）
4. ノイズ除去
5. 余白トリミング

Usage:
    from pdf_preprocess_enhance import PDFPreprocessor

    preprocessor = PDFPreprocessor()
    enhanced_pdf = preprocessor.enhance("input.pdf")
"""
import os
import sys
from pathlib import Path
from typing import Optional, Tuple
import tempfile

# PyMuPDF
try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

# PIL/Pillow
try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# OpenCV（オプション）
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class PDFPreprocessor:
    """PDF前処理クラス"""

    # 目標解像度
    TARGET_DPI = 300

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Args:
            output_dir: 出力ディレクトリ（指定なしの場合は元ファイルと同じ場所）
        """
        if not FITZ_AVAILABLE:
            raise ImportError("PyMuPDFが必要です: pip install PyMuPDF")
        if not PIL_AVAILABLE:
            raise ImportError("Pillowが必要です: pip install Pillow")

        self.output_dir = output_dir

    def analyze_pdf(self, pdf_path: Path) -> dict:
        """PDFの状態を分析

        Args:
            pdf_path: PDFファイルパス

        Returns:
            分析結果の辞書
        """
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        info = {
            "page_width": page.rect.width,
            "page_height": page.rect.height,
            "rotation": page.rotation,
            "is_landscape": page.rect.width > page.rect.height,
            "images": [],
            "estimated_dpi": 0,
            "needs_enhancement": False,
            "enhancement_reasons": []
        }

        # 埋め込み画像を分析
        images = page.get_images()
        for img in images:
            xref = img[0]
            base = doc.extract_image(xref)
            img_info = {
                "width": base["width"],
                "height": base["height"],
                "format": base["ext"]
            }
            info["images"].append(img_info)

            # DPI推定（画像サイズ / ページサイズ * 72）
            if info["page_width"] > 0:
                dpi_x = base["width"] / info["page_width"] * 72
                dpi_y = base["height"] / info["page_height"] * 72
                info["estimated_dpi"] = max(info["estimated_dpi"], min(dpi_x, dpi_y))

        doc.close()

        # 改善が必要かどうかを判定
        if info["estimated_dpi"] < 250:
            info["needs_enhancement"] = True
            info["enhancement_reasons"].append(f"低解像度 ({info['estimated_dpi']:.0f} dpi)")

        if info["is_landscape"]:
            info["needs_enhancement"] = True
            info["enhancement_reasons"].append("横向き")

        return info

    def extract_image_from_pdf(self, pdf_path: Path, dpi: int = 300) -> Image.Image:
        """PDFからページ画像を抽出

        Args:
            pdf_path: PDFファイルパス
            dpi: 出力解像度

        Returns:
            PIL Image
        """
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        # 高解像度でレンダリング
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # PIL Imageに変換
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        doc.close()
        return img

    def enhance_contrast(self, img: Image.Image, factor: float = 1.5) -> Image.Image:
        """コントラストを強調

        Args:
            img: 入力画像
            factor: 強調係数（1.0で変化なし、1.5で50%強調）

        Returns:
            強調後の画像
        """
        enhancer = ImageEnhance.Contrast(img)
        return enhancer.enhance(factor)

    def enhance_sharpness(self, img: Image.Image, factor: float = 1.5) -> Image.Image:
        """シャープネスを強調

        Args:
            img: 入力画像
            factor: 強調係数

        Returns:
            強調後の画像
        """
        enhancer = ImageEnhance.Sharpness(img)
        return enhancer.enhance(factor)

    def auto_contrast(self, img: Image.Image) -> Image.Image:
        """自動コントラスト調整（ヒストグラム均等化）

        Args:
            img: 入力画像

        Returns:
            調整後の画像
        """
        return ImageOps.autocontrast(img, cutoff=1)

    def denoise(self, img: Image.Image) -> Image.Image:
        """ノイズ除去（軽いぼかし後にシャープ化）

        Args:
            img: 入力画像

        Returns:
            ノイズ除去後の画像
        """
        # 軽いメディアンフィルタでノイズ除去
        img = img.filter(ImageFilter.MedianFilter(size=3))
        # シャープ化で文字を鮮明に
        img = img.filter(ImageFilter.SHARPEN)
        return img

    def detect_skew_angle(self, img: Image.Image) -> float:
        """傾き角度を検出（OpenCV使用）

        Args:
            img: 入力画像

        Returns:
            傾き角度（度）
        """
        if not CV2_AVAILABLE:
            return 0.0

        # PIL → OpenCV
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)

        # エッジ検出
        edges = cv2.Canny(cv_img, 50, 150, apertureSize=3)

        # ハフ変換で直線検出
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

        if lines is None:
            return 0.0

        # 角度の中央値を取得
        angles = []
        for line in lines[:20]:  # 最大20本
            rho, theta = line[0]
            angle = (theta * 180 / np.pi) - 90
            if -10 < angle < 10:  # -10〜10度の範囲のみ
                angles.append(angle)

        if angles:
            return float(np.median(angles))
        return 0.0

    def deskew(self, img: Image.Image, angle: Optional[float] = None) -> Image.Image:
        """傾き補正

        Args:
            img: 入力画像
            angle: 補正角度（Noneの場合は自動検出）

        Returns:
            補正後の画像
        """
        if angle is None:
            angle = self.detect_skew_angle(img)

        if abs(angle) < 0.5:  # 0.5度未満は無視
            return img

        # 回転（白背景で埋める）
        return img.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))

    def trim_whitespace(self, img: Image.Image, threshold: int = 250) -> Image.Image:
        """余白をトリミング

        Args:
            img: 入力画像
            threshold: 白判定の閾値

        Returns:
            トリミング後の画像
        """
        # グレースケール変換
        gray = img.convert('L')

        # 白以外の領域を検出
        bbox = gray.point(lambda x: 0 if x > threshold else 255).getbbox()

        if bbox:
            # マージンを追加（10ピクセル）
            margin = 10
            x1 = max(0, bbox[0] - margin)
            y1 = max(0, bbox[1] - margin)
            x2 = min(img.width, bbox[2] + margin)
            y2 = min(img.height, bbox[3] + margin)
            return img.crop((x1, y1, x2, y2))

        return img

    def image_to_pdf(self, img: Image.Image, output_path: Path) -> Path:
        """画像をPDFに変換

        Args:
            img: PIL Image
            output_path: 出力パス

        Returns:
            出力PDFパス
        """
        # RGBモードに変換（PDFはRGBが必要）
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # PDFとして保存
        img.save(str(output_path), 'PDF', resolution=self.TARGET_DPI)
        return output_path

    def enhance(
        self,
        pdf_path: Path,
        output_path: Optional[Path] = None,
        dpi: int = 300,
        contrast: float = 1.3,
        sharpness: float = 1.2,
        denoise: bool = True,
        deskew: bool = True,
        trim: bool = True,
        auto_contrast: bool = True
    ) -> Path:
        """PDFを前処理して品質向上

        Args:
            pdf_path: 入力PDFパス
            output_path: 出力パス（Noneの場合は自動生成）
            dpi: 出力解像度
            contrast: コントラスト強調係数
            sharpness: シャープネス強調係数
            denoise: ノイズ除去を行うか
            deskew: 傾き補正を行うか
            trim: 余白トリミングを行うか
            auto_contrast: 自動コントラスト調整を行うか

        Returns:
            出力PDFパス
        """
        pdf_path = Path(pdf_path)

        # 出力パスを決定
        if output_path is None:
            if self.output_dir:
                output_path = self.output_dir / f"enhanced_{pdf_path.name}"
            else:
                output_path = pdf_path.parent / f"enhanced_{pdf_path.name}"

        print(f"  前処理開始: {pdf_path.name}")

        # PDFから画像を抽出
        img = self.extract_image_from_pdf(pdf_path, dpi=dpi)
        print(f"    画像抽出: {img.width}x{img.height} @ {dpi}dpi")

        # 余白トリミング
        if trim:
            img = self.trim_whitespace(img)
            print(f"    トリミング: {img.width}x{img.height}")

        # 傾き補正
        if deskew:
            angle = self.detect_skew_angle(img)
            if abs(angle) >= 0.5:
                img = self.deskew(img, angle)
                print(f"    傾き補正: {angle:.1f}度")

        # 自動コントラスト
        if auto_contrast:
            img = self.auto_contrast(img)
            print("    自動コントラスト調整")

        # コントラスト強調
        if contrast != 1.0:
            img = self.enhance_contrast(img, contrast)
            print(f"    コントラスト強調: x{contrast}")

        # シャープネス強調
        if sharpness != 1.0:
            img = self.enhance_sharpness(img, sharpness)
            print(f"    シャープネス強調: x{sharpness}")

        # ノイズ除去
        if denoise:
            img = self.denoise(img)
            print("    ノイズ除去")

        # PDFに変換して保存
        self.image_to_pdf(img, output_path)
        print(f"  前処理完了: {output_path.name}")

        return output_path


def test_enhancement(pdf_path: str, output_dir: Optional[str] = None):
    """前処理テスト

    Args:
        pdf_path: 入力PDFパス
        output_dir: 出力ディレクトリ
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir) if output_dir else pdf_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    preprocessor = PDFPreprocessor(output_dir)

    # 分析
    print("\n=== PDF分析 ===")
    info = preprocessor.analyze_pdf(pdf_path)
    print(f"ページサイズ: {info['page_width']:.0f} x {info['page_height']:.0f}")
    print(f"推定DPI: {info['estimated_dpi']:.0f}")
    print(f"画像数: {len(info['images'])}")
    for i, img_info in enumerate(info['images']):
        print(f"  画像{i+1}: {img_info['width']}x{img_info['height']} ({img_info['format']})")
    print(f"改善推奨: {'はい' if info['needs_enhancement'] else 'いいえ'}")
    if info['enhancement_reasons']:
        print(f"理由: {', '.join(info['enhancement_reasons'])}")

    # 前処理実行
    print("\n=== 前処理実行 ===")
    enhanced_path = preprocessor.enhance(pdf_path)

    # 前処理後の分析
    print("\n=== 前処理後の分析 ===")
    info_after = preprocessor.analyze_pdf(enhanced_path)
    print(f"推定DPI: {info_after['estimated_dpi']:.0f}")

    return enhanced_path


def main():
    """メイン関数"""
    import argparse

    parser = argparse.ArgumentParser(description="PDF前処理（OCR精度向上）")
    parser.add_argument("pdf", help="入力PDFパス")
    parser.add_argument("--output-dir", "-o", help="出力ディレクトリ")
    parser.add_argument("--dpi", type=int, default=300, help="出力解像度")
    parser.add_argument("--analyze-only", action="store_true", help="分析のみ（前処理なし）")

    args = parser.parse_args()

    pdf_path = Path(args.pdf)

    if args.analyze_only:
        preprocessor = PDFPreprocessor()
        info = preprocessor.analyze_pdf(pdf_path)
        print(f"\n=== {pdf_path.name} ===")
        print(f"推定DPI: {info['estimated_dpi']:.0f}")
        print(f"改善推奨: {'はい' if info['needs_enhancement'] else 'いいえ'}")
        if info['enhancement_reasons']:
            print(f"理由: {', '.join(info['enhancement_reasons'])}")
    else:
        enhanced_path = test_enhancement(args.pdf, args.output_dir)
        print(f"\n出力: {enhanced_path}")


if __name__ == "__main__":
    main()
