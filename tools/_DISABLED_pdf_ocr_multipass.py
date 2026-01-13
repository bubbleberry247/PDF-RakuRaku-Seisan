# -*- coding: utf-8 -*-
"""
PDF OCRマルチパス処理

通常読取で精度が出ない場合、複数の前処理組み合わせを試して最良結果を選択
目標: 精度30%アップ

組み合わせパターン:
1. 原画像そのまま
2. 解像度アップのみ（300dpi）
3. 解像度アップ + コントラスト強調
4. 解像度アップ + CLAHE（局所コントラスト）
5. 解像度アップ + 影除去
6. 解像度アップ + 二値化（適応的）
7. 解像度アップ + ネガポジ反転
8. 高解像度（600dpi）
9. 回転90度
10. 回転180度
11. 回転270度

Usage:
    from pdf_ocr_multipass import MultiPassOCR

    ocr = MultiPassOCR()
    result = ocr.process("receipt.pdf")
"""
import os
import sys
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# OpenCV
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# 共通モジュール
sys.path.insert(0, str(Path(__file__).parent))
from common.logger import get_logger


@dataclass
class OCRResult:
    """OCR結果"""
    pattern_name: str = ""
    vendor_name: str = ""
    issue_date: str = ""
    amount: int = 0
    invoice_number: str = ""
    confidence: float = 0.0
    raw_text: str = ""
    success: bool = False
    error: str = ""

    def score(self) -> float:
        """結果のスコアを計算"""
        s = self.confidence * 100
        if self.amount > 0:
            s += 30
        if self.issue_date:
            s += 20
        if self.vendor_name:
            s += 15
        if self.invoice_number:
            s += 10
        return s


class MultiPassOCR:
    """マルチパスOCR処理"""

    def __init__(self, max_parallel: int = 3):
        """
        Args:
            max_parallel: 並列実行数（API制限に注意）
        """
        self.logger = get_logger()
        self.max_parallel = max_parallel
        self._docai = None

        if not FITZ_AVAILABLE:
            raise ImportError("PyMuPDFが必要: pip install PyMuPDF")
        if not PIL_AVAILABLE:
            raise ImportError("Pillowが必要: pip install Pillow")

    @property
    def docai(self):
        """Document AIプロセッサ（遅延初期化）"""
        if self._docai is None:
            from pdf_ocr_documentai import DocumentAIOCRProcessor
            self._docai = DocumentAIOCRProcessor()
        return self._docai

    # =========================================
    # 前処理パターン定義
    # =========================================

    def get_preprocessing_patterns(self) -> List[Tuple[str, Callable]]:
        """前処理パターンのリスト"""
        patterns = [
            ("01_original", lambda img: img),
            ("02_upscale_300", lambda img: self._upscale(img, 300)),
            ("03_contrast_1.5", lambda img: self._contrast(self._upscale(img, 300), 1.5)),
            ("04_contrast_2.0", lambda img: self._contrast(self._upscale(img, 300), 2.0)),
            ("05_clahe", lambda img: self._clahe(self._upscale(img, 300))),
            ("06_shadow_removal", lambda img: self._shadow_removal(self._upscale(img, 300))),
            ("07_adaptive_threshold", lambda img: self._adaptive_threshold(self._upscale(img, 300))),
            ("08_otsu_threshold", lambda img: self._otsu_threshold(self._upscale(img, 300))),
            ("09_invert", lambda img: self._invert(self._upscale(img, 300))),
            ("10_upscale_600", lambda img: self._upscale(img, 600)),
            ("11_rotate_90", lambda img: self._rotate(self._upscale(img, 300), 90)),
            ("12_rotate_180", lambda img: self._rotate(self._upscale(img, 300), 180)),
            ("13_rotate_270", lambda img: self._rotate(self._upscale(img, 300), 270)),
            ("14_sharpen", lambda img: self._sharpen(self._upscale(img, 300))),
            ("15_denoise_sharpen", lambda img: self._sharpen(self._denoise(self._upscale(img, 300)))),
            ("16_clahe_sharpen", lambda img: self._sharpen(self._clahe(self._upscale(img, 300)))),
        ]
        return patterns

    # =========================================
    # 前処理関数
    # =========================================

    def _pdf_to_pil(self, pdf_path: Path, dpi: int = 150) -> Image.Image:
        """PDFをPIL Imageに変換"""
        doc = fitz.open(str(pdf_path))
        page = doc[0]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        return img

    def _upscale(self, img: Image.Image, target_dpi: int) -> Image.Image:
        """解像度アップ"""
        # 現在の解像度を推定（A4基準）
        current_dpi = img.width / 8.27  # A4幅 = 8.27インチ
        if current_dpi >= target_dpi:
            return img

        scale = target_dpi / max(current_dpi, 72)
        new_size = (int(img.width * scale), int(img.height * scale))
        return img.resize(new_size, Image.LANCZOS)

    def _contrast(self, img: Image.Image, factor: float) -> Image.Image:
        """コントラスト強調"""
        enhancer = ImageEnhance.Contrast(img)
        return enhancer.enhance(factor)

    def _sharpen(self, img: Image.Image) -> Image.Image:
        """シャープ化"""
        enhancer = ImageEnhance.Sharpness(img)
        return enhancer.enhance(2.0)

    def _denoise(self, img: Image.Image) -> Image.Image:
        """ノイズ除去"""
        return img.filter(ImageFilter.MedianFilter(size=3))

    def _invert(self, img: Image.Image) -> Image.Image:
        """ネガポジ反転"""
        return ImageOps.invert(img.convert('RGB'))

    def _rotate(self, img: Image.Image, angle: int) -> Image.Image:
        """回転"""
        return img.rotate(angle, expand=True, fillcolor=(255, 255, 255))

    def _clahe(self, img: Image.Image) -> Image.Image:
        """CLAHE（局所コントラスト強調）"""
        if not CV2_AVAILABLE:
            return ImageOps.autocontrast(img)

        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        lab = cv2.cvtColor(cv_img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)

        lab = cv2.merge([l, a, b])
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))

    def _shadow_removal(self, img: Image.Image) -> Image.Image:
        """影除去"""
        if not CV2_AVAILABLE:
            return ImageOps.autocontrast(img)

        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        rgb_planes = cv2.split(cv_img)
        result_planes = []

        for plane in rgb_planes:
            dilated = cv2.dilate(plane, np.ones((7, 7), np.uint8))
            bg = cv2.medianBlur(dilated, 21)
            diff = 255 - cv2.absdiff(plane, bg)
            norm = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
            result_planes.append(norm)

        result = cv2.merge(result_planes)
        return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))

    def _adaptive_threshold(self, img: Image.Image) -> Image.Image:
        """適応的二値化"""
        if not CV2_AVAILABLE:
            return img.convert('L').point(lambda x: 0 if x < 128 else 255).convert('RGB')

        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        binary = cv2.adaptiveThreshold(
            cv_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        return Image.fromarray(binary).convert('RGB')

    def _otsu_threshold(self, img: Image.Image) -> Image.Image:
        """大津の二値化"""
        if not CV2_AVAILABLE:
            return img.convert('L').point(lambda x: 0 if x < 128 else 255).convert('RGB')

        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(cv_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return Image.fromarray(binary).convert('RGB')

    # =========================================
    # OCR実行
    # =========================================

    def _run_single_pattern(
        self,
        pdf_path: Path,
        pattern_name: str,
        preprocess_func: Callable
    ) -> OCRResult:
        """単一パターンでOCR実行"""
        result = OCRResult(pattern_name=pattern_name)

        try:
            # PDFを画像に変換
            img = self._pdf_to_pil(pdf_path, dpi=150)

            # 前処理適用
            processed = preprocess_func(img)

            # 一時PDFに保存
            temp_path = Path(tempfile.mktemp(suffix=".pdf"))
            if processed.mode != 'RGB':
                processed = processed.convert('RGB')
            processed.save(str(temp_path), 'PDF', resolution=300)

            # Document AI実行
            docai_result = self.docai.process_pdf(temp_path)

            # 結果を設定
            result.vendor_name = docai_result.vendor_name
            result.issue_date = docai_result.issue_date
            result.amount = docai_result.amount
            result.invoice_number = docai_result.invoice_number
            result.confidence = docai_result.confidence
            result.raw_text = docai_result.raw_text
            result.success = docai_result.success

            # 一時ファイル削除
            temp_path.unlink()

        except Exception as e:
            result.error = str(e)
            result.success = False

        return result

    def process(
        self,
        pdf_path: Path,
        quick_mode: bool = False,
        target_amount: Optional[int] = None
    ) -> OCRResult:
        """マルチパスOCR実行

        Args:
            pdf_path: 入力PDFパス
            quick_mode: Trueの場合、良い結果が出たら早期終了
            target_amount: 期待する金額（検証用）

        Returns:
            最良のOCR結果
        """
        pdf_path = Path(pdf_path)
        self.logger.info(f"マルチパスOCR開始: {pdf_path.name}")

        patterns = self.get_preprocessing_patterns()
        results: List[OCRResult] = []

        # まず原画像で試す
        self.logger.info("パターン01: 原画像")
        original_result = self._run_single_pattern(pdf_path, "01_original", lambda x: x)
        results.append(original_result)

        self.logger.info(f"  → amount={original_result.amount}, conf={original_result.confidence:.2%}")

        # 信頼度が高ければ終了
        if original_result.confidence >= 0.90 and original_result.amount > 0:
            self.logger.info("原画像で十分な精度 → 終了")
            return original_result

        # 各パターンを試す
        for name, func in patterns[1:]:  # 原画像はスキップ
            self.logger.info(f"パターン{name}")

            result = self._run_single_pattern(pdf_path, name, func)
            results.append(result)

            self.logger.info(f"  → amount={result.amount}, conf={result.confidence:.2%}")

            # quick_modeで良い結果が出たら終了
            if quick_mode:
                if result.confidence >= 0.85 and result.amount > 0:
                    self.logger.info(f"良い結果を検出 → 早期終了")
                    break

                # target_amountが指定されていて一致したら終了
                if target_amount and result.amount == target_amount:
                    self.logger.info(f"期待金額と一致 → 早期終了")
                    break

        # 最良結果を選択
        best = max(results, key=lambda r: r.score())

        self.logger.info(f"最良結果: {best.pattern_name}, score={best.score():.1f}")

        # 全結果をログ
        self.logger.info("=== 全パターン結果 ===")
        for r in sorted(results, key=lambda x: x.score(), reverse=True)[:5]:
            self.logger.info(f"  {r.pattern_name}: amount={r.amount}, conf={r.confidence:.2%}, score={r.score():.1f}")

        return best

    def process_with_report(self, pdf_path: Path) -> Tuple[OCRResult, List[OCRResult]]:
        """全パターンを試して詳細レポートを返す"""
        pdf_path = Path(pdf_path)
        patterns = self.get_preprocessing_patterns()
        results: List[OCRResult] = []

        for name, func in patterns:
            print(f"  処理中: {name}...", end=" ", flush=True)
            result = self._run_single_pattern(pdf_path, name, func)
            results.append(result)
            print(f"amount={result.amount}, conf={result.confidence:.2%}")

        best = max(results, key=lambda r: r.score())
        return best, results


def main():
    """テスト実行"""
    import argparse

    parser = argparse.ArgumentParser(description="マルチパスOCR")
    parser.add_argument("pdf", help="入力PDFパス")
    parser.add_argument("--quick", action="store_true", help="高速モード")
    parser.add_argument("--report", action="store_true", help="全パターンレポート")
    parser.add_argument("--target", type=int, help="期待金額（検証用）")

    args = parser.parse_args()

    from common.logger import setup_logger
    setup_logger("multipass_ocr")

    ocr = MultiPassOCR()

    if args.report:
        print(f"\n=== マルチパスOCR（全パターン）: {Path(args.pdf).name} ===\n")
        best, all_results = ocr.process_with_report(Path(args.pdf))

        print(f"\n=== 結果ランキング ===")
        for i, r in enumerate(sorted(all_results, key=lambda x: x.score(), reverse=True), 1):
            print(f"{i:2d}. {r.pattern_name}: amount={r.amount:,}, conf={r.confidence:.2%}, score={r.score():.1f}")

        print(f"\n=== 最良結果 ===")
        print(f"パターン: {best.pattern_name}")
        print(f"取引先: {best.vendor_name}")
        print(f"日付: {best.issue_date}")
        print(f"金額: {best.amount:,}円" if best.amount else "金額: -")
        print(f"事業者番号: {best.invoice_number}")
        print(f"信頼度: {best.confidence:.2%}")
    else:
        result = ocr.process(Path(args.pdf), quick_mode=args.quick, target_amount=args.target)

        print(f"\n=== 最良結果 ===")
        print(f"パターン: {result.pattern_name}")
        print(f"取引先: {result.vendor_name}")
        print(f"日付: {result.issue_date}")
        print(f"金額: {result.amount:,}円" if result.amount else "金額: -")
        print(f"事業者番号: {result.invoice_number}")
        print(f"信頼度: {result.confidence:.2%}")
        print(f"スコア: {result.score():.1f}")


if __name__ == "__main__":
    main()
