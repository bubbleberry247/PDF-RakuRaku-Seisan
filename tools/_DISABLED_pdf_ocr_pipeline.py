# -*- coding: utf-8 -*-
"""
PDF OCRパイプライン（C案：項目抽出最適化）

設計思想:
- Document AI Expense Parserの項目抽出精度を最大化
- 前処理は非破壊を原則、必要な時だけ重処理
- confidenceベースの自動分岐
- 後処理で整合性チェック

パイプライン:
Step0: 入力分類（テキスト層の有無）
Step1: 軽量前処理（トリミング・透視補正・deskew）
Step2: Document AI 1回目
Step3: 失敗時のみ重処理（影補正・CLAHE）
Step4: Document AI 2回目（必要時）
Step5: 後処理（整合性ルール・アンサンブル）

Usage:
    from pdf_ocr_pipeline import OCRPipeline

    pipeline = OCRPipeline()
    result = pipeline.process("receipt.pdf")
"""
import os
import sys
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
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
class ExtractionResult:
    """項目抽出結果"""
    vendor_name: str = ""
    issue_date: str = ""  # YYYYMMDD
    amount: int = 0
    tax_amount: int = 0
    invoice_number: str = ""

    # メタ情報
    confidence: float = 0.0
    pass_number: int = 1  # 1回目 or 2回目
    preprocessing_applied: List[str] = field(default_factory=list)
    quality_issues: List[str] = field(default_factory=list)

    success: bool = False
    error: str = ""
    raw_text: str = ""


@dataclass
class QualityMetrics:
    """画像品質メトリクス"""
    estimated_dpi: float = 0.0
    has_text_layer: bool = False
    is_landscape: bool = False
    blur_score: float = 0.0  # 高いほどぼやけている
    contrast_score: float = 0.0  # 低いほどコントラスト不足
    shadow_detected: bool = False
    skew_angle: float = 0.0
    needs_perspective: bool = False


class OCRPipeline:
    """OCRパイプライン（C案実装）"""

    # 閾値設定
    CONFIDENCE_THRESHOLD = 0.75  # これ未満は重処理へ
    MIN_DPI = 250
    TARGET_DPI = 300
    MAX_DPI = 600  # 40MP制限対策

    def __init__(self):
        self.logger = get_logger()

        if not FITZ_AVAILABLE:
            raise ImportError("PyMuPDFが必要: pip install PyMuPDF")
        if not PIL_AVAILABLE:
            raise ImportError("Pillowが必要: pip install Pillow")

        # Document AI プロセッサ（遅延初期化）
        self._docai_processor = None

    @property
    def docai_processor(self):
        """Document AIプロセッサの遅延初期化"""
        if self._docai_processor is None:
            from pdf_ocr_documentai import DocumentAIOCRProcessor
            self._docai_processor = DocumentAIOCRProcessor()
        return self._docai_processor

    # =========================================
    # Step 0: 入力分類
    # =========================================

    def analyze_pdf(self, pdf_path: Path) -> QualityMetrics:
        """PDFの品質を分析"""
        metrics = QualityMetrics()

        doc = fitz.open(str(pdf_path))
        page = doc[0]

        # テキスト層の確認
        text = page.get_text()
        metrics.has_text_layer = len(text.strip()) > 50

        # ページサイズと向き
        metrics.is_landscape = page.rect.width > page.rect.height

        # 埋め込み画像の解像度推定
        images = page.get_images()
        if images:
            xref = images[0][0]
            base = doc.extract_image(xref)
            if page.rect.width > 0:
                dpi_x = base["width"] / page.rect.width * 72
                dpi_y = base["height"] / page.rect.height * 72
                metrics.estimated_dpi = min(dpi_x, dpi_y)

        doc.close()

        # 画像として詳細分析（OpenCV利用可能時）
        if CV2_AVAILABLE:
            img = self._pdf_to_image(pdf_path)
            if img is not None:
                metrics.blur_score = self._detect_blur(img)
                metrics.contrast_score = self._detect_contrast(img)
                metrics.skew_angle = self._detect_skew(img)
                metrics.shadow_detected = self._detect_shadow(img)
                metrics.needs_perspective = self._detect_perspective_distortion(img)

        return metrics

    def _pdf_to_image(self, pdf_path: Path, dpi: int = 150) -> Optional[np.ndarray]:
        """PDFをOpenCV画像に変換（分析用）"""
        try:
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            doc.close()
            return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        except Exception:
            return None

    def _detect_blur(self, img: np.ndarray) -> float:
        """ブレ検出（Laplacian variance）"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def _detect_contrast(self, img: np.ndarray) -> float:
        """コントラスト検出"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return gray.std()

    def _detect_skew(self, img: np.ndarray) -> float:
        """傾き検出"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

        if lines is None:
            return 0.0

        angles = []
        for line in lines[:20]:
            theta = line[0][1]
            angle = (theta * 180 / np.pi) - 90
            if -15 < angle < 15:
                angles.append(angle)

        return float(np.median(angles)) if angles else 0.0

    def _detect_shadow(self, img: np.ndarray) -> bool:
        """影検出（明度のばらつき）"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 画像を4x4に分割して明度の差をチェック
        h, w = gray.shape
        blocks = []
        for i in range(4):
            for j in range(4):
                block = gray[i*h//4:(i+1)*h//4, j*w//4:(j+1)*w//4]
                blocks.append(block.mean())

        return (max(blocks) - min(blocks)) > 80

    def _detect_perspective_distortion(self, img: np.ndarray) -> bool:
        """透視歪み検出（四角形検出）"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) == 4:
                # 四角形が見つかった場合、歪みをチェック
                pts = approx.reshape(4, 2)
                widths = [np.linalg.norm(pts[i] - pts[(i+1)%4]) for i in range(4)]
                if max(widths) / (min(widths) + 1) > 1.2:  # 20%以上の差
                    return True

        return False

    # =========================================
    # Step 1: 軽量前処理
    # =========================================

    def light_preprocess(self, pdf_path: Path, metrics: QualityMetrics) -> Tuple[Path, List[str]]:
        """軽量前処理（非破壊原則）"""
        applied = []

        # テキスト層がある場合はそのまま
        if metrics.has_text_layer:
            return pdf_path, ["skip_has_text"]

        # 画像として処理
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        # DPIを決定（低すぎる場合は上げる）
        target_dpi = self.TARGET_DPI
        if metrics.estimated_dpi < self.MIN_DPI:
            target_dpi = self.TARGET_DPI
            applied.append(f"upscale_{int(metrics.estimated_dpi)}_to_{target_dpi}")

        zoom = target_dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # PIL Imageに変換
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()

        # トリミング（余白除去）
        img_trimmed = self._trim_whitespace(img)
        if img_trimmed.size != img.size:
            img = img_trimmed
            applied.append("trim")

        # 傾き補正（小角度のみ）
        if abs(metrics.skew_angle) >= 0.5:
            img = img.rotate(metrics.skew_angle, resample=Image.BICUBIC,
                           expand=True, fillcolor=(255, 255, 255))
            applied.append(f"deskew_{metrics.skew_angle:.1f}")

        # 透視補正（OpenCV利用可能かつ必要な場合）
        if CV2_AVAILABLE and metrics.needs_perspective:
            img_corrected = self._perspective_correction(img)
            if img_corrected is not None:
                img = img_corrected
                applied.append("perspective")

        # 一時ファイルに保存
        output_path = Path(tempfile.mktemp(suffix=".pdf"))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(str(output_path), 'PDF', resolution=target_dpi)

        return output_path, applied

    def _trim_whitespace(self, img: Image.Image, threshold: int = 250) -> Image.Image:
        """余白トリミング"""
        gray = img.convert('L')
        bbox = gray.point(lambda x: 0 if x > threshold else 255).getbbox()
        if bbox:
            margin = 10
            x1 = max(0, bbox[0] - margin)
            y1 = max(0, bbox[1] - margin)
            x2 = min(img.width, bbox[2] + margin)
            y2 = min(img.height, bbox[3] + margin)
            return img.crop((x1, y1, x2, y2))
        return img

    def _perspective_correction(self, img: Image.Image) -> Optional[Image.Image]:
        """透視補正（四隅検出）"""
        if not CV2_AVAILABLE:
            return None

        # PIL → OpenCV
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

        # エッジ検出
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 最大の四角形を探す
        best_contour = None
        best_area = 0

        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) == 4:
                area = cv2.contourArea(approx)
                if area > best_area and area > (img.width * img.height * 0.3):
                    best_area = area
                    best_contour = approx

        if best_contour is None:
            return None

        # 四隅を並び替え（左上、右上、右下、左下）
        pts = best_contour.reshape(4, 2).astype(np.float32)
        rect = self._order_points(pts)

        # 出力サイズを計算
        width = max(
            np.linalg.norm(rect[0] - rect[1]),
            np.linalg.norm(rect[2] - rect[3])
        )
        height = max(
            np.linalg.norm(rect[0] - rect[3]),
            np.linalg.norm(rect[1] - rect[2])
        )

        dst = np.array([
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1]
        ], dtype=np.float32)

        # 透視変換
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(cv_img, M, (int(width), int(height)))

        # OpenCV → PIL
        return Image.fromarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))

    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """四隅を左上、右上、右下、左下の順に並び替え"""
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # 左上
        rect[2] = pts[np.argmax(s)]  # 右下
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # 右上
        rect[3] = pts[np.argmax(diff)]  # 左下
        return rect

    # =========================================
    # Step 2 & 4: Document AI処理
    # =========================================

    def run_document_ai(self, pdf_path: Path) -> ExtractionResult:
        """Document AIで項目抽出"""
        result = self.docai_processor.process_pdf(pdf_path)

        extraction = ExtractionResult(
            vendor_name=result.vendor_name,
            issue_date=result.issue_date,
            amount=result.amount,
            invoice_number=result.invoice_number,
            confidence=result.confidence,
            success=result.success,
            error=result.error,
            raw_text=result.raw_text
        )

        return extraction

    # =========================================
    # Step 3: 重処理
    # =========================================

    def heavy_preprocess(self, pdf_path: Path, metrics: QualityMetrics) -> Tuple[Path, List[str]]:
        """重処理（影補正・CLAHE等）"""
        applied = []

        # 高解像度で画像化
        doc = fitz.open(str(pdf_path))
        page = doc[0]
        zoom = 400 / 72  # 400dpi
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        applied.append("render_400dpi")

        if CV2_AVAILABLE:
            cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

            # 影補正（背景除去）
            if metrics.shadow_detected:
                cv_img = self._remove_shadow(cv_img)
                applied.append("shadow_removal")

            # CLAHE（局所コントラスト）
            cv_img = self._apply_clahe(cv_img)
            applied.append("clahe")

            # 軽いシャープ
            kernel = np.array([[-0.5, -0.5, -0.5],
                              [-0.5,  5,   -0.5],
                              [-0.5, -0.5, -0.5]])
            cv_img = cv2.filter2D(cv_img, -1, kernel)
            applied.append("sharpen")

            # OpenCV → PIL
            img = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
        else:
            # PIL only: 自動コントラスト + シャープ
            img = ImageOps.autocontrast(img, cutoff=2)
            img = ImageEnhance.Sharpness(img).enhance(1.5)
            applied.append("autocontrast_sharpen")

        # 一時ファイルに保存
        output_path = Path(tempfile.mktemp(suffix=".pdf"))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(str(output_path), 'PDF', resolution=400)

        return output_path, applied

    def _remove_shadow(self, img: np.ndarray) -> np.ndarray:
        """影除去（背景推定→除去）"""
        # 大きくぼかして背景を推定
        rgb_planes = cv2.split(img)
        result_planes = []

        for plane in rgb_planes:
            dilated = cv2.dilate(plane, np.ones((7, 7), np.uint8))
            bg = cv2.medianBlur(dilated, 21)
            diff = 255 - cv2.absdiff(plane, bg)
            norm = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
            result_planes.append(norm)

        return cv2.merge(result_planes)

    def _apply_clahe(self, img: np.ndarray) -> np.ndarray:
        """CLAHE（局所コントラスト強調）"""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)

        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # =========================================
    # Step 5: 後処理（整合性チェック）
    # =========================================

    def validate_result(self, result: ExtractionResult) -> ExtractionResult:
        """結果の整合性チェック"""
        issues = []

        # 金額チェック
        if result.amount > 0:
            # 現実的な範囲（1円〜1000万円）
            if result.amount < 1 or result.amount > 10000000:
                issues.append(f"amount_out_of_range_{result.amount}")

        # 日付チェック
        if result.issue_date:
            try:
                year = int(result.issue_date[:4])
                month = int(result.issue_date[4:6])
                day = int(result.issue_date[6:8])

                # 未来日チェック
                from datetime import datetime
                date = datetime(year, month, day)
                if date > datetime.now():
                    issues.append("future_date")

                # 古すぎる日付チェック
                if year < 2020:
                    issues.append("old_date")

            except (ValueError, IndexError):
                issues.append("invalid_date_format")

        # 事業者番号チェック（T + 13桁）
        if result.invoice_number:
            if not re.match(r'^T\d{13}$', result.invoice_number):
                issues.append("invalid_invoice_number")

        result.quality_issues = issues
        return result

    def select_best_result(self, result1: ExtractionResult, result2: ExtractionResult) -> ExtractionResult:
        """2つの結果から最良を選択（アンサンブル）"""

        # スコアリング
        def score(r: ExtractionResult) -> float:
            s = r.confidence * 100

            # 必須項目の有無
            if r.amount > 0:
                s += 20
            if r.issue_date:
                s += 15
            if r.vendor_name:
                s += 10

            # 品質問題でペナルティ
            s -= len(r.quality_issues) * 10

            return s

        score1 = score(result1)
        score2 = score(result2)

        self.logger.info(f"Result1 score: {score1:.1f}, Result2 score: {score2:.1f}")

        return result1 if score1 >= score2 else result2

    # =========================================
    # メインパイプライン
    # =========================================

    def process(self, pdf_path: Path) -> ExtractionResult:
        """メインパイプライン実行"""
        pdf_path = Path(pdf_path)
        self.logger.info(f"パイプライン開始: {pdf_path.name}")

        # Step 0: 入力分析
        metrics = self.analyze_pdf(pdf_path)
        self.logger.info(f"品質分析: DPI={metrics.estimated_dpi:.0f}, "
                        f"text_layer={metrics.has_text_layer}, "
                        f"shadow={metrics.shadow_detected}, "
                        f"skew={metrics.skew_angle:.1f}")

        # Step 1: 軽量前処理
        light_path, light_applied = self.light_preprocess(pdf_path, metrics)
        self.logger.info(f"軽量前処理: {light_applied}")

        # Step 2: Document AI 1回目
        result1 = self.run_document_ai(light_path)
        result1.pass_number = 1
        result1.preprocessing_applied = light_applied
        result1 = self.validate_result(result1)

        self.logger.info(f"1回目結果: amount={result1.amount}, "
                        f"confidence={result1.confidence:.2%}, "
                        f"issues={result1.quality_issues}")

        # 信頼度が十分なら終了
        if result1.confidence >= self.CONFIDENCE_THRESHOLD and not result1.quality_issues:
            self.logger.info("信頼度OK → 1回目結果を採用")
            # 一時ファイル削除
            if light_path != pdf_path and light_path.exists():
                light_path.unlink()
            return result1

        # Step 3: 重処理
        self.logger.info("信頼度不足 → 重処理実行")
        heavy_path, heavy_applied = self.heavy_preprocess(pdf_path, metrics)

        # Step 4: Document AI 2回目
        result2 = self.run_document_ai(heavy_path)
        result2.pass_number = 2
        result2.preprocessing_applied = heavy_applied
        result2 = self.validate_result(result2)

        self.logger.info(f"2回目結果: amount={result2.amount}, "
                        f"confidence={result2.confidence:.2%}, "
                        f"issues={result2.quality_issues}")

        # Step 5: 最良結果を選択
        best = self.select_best_result(result1, result2)
        self.logger.info(f"採用: {best.pass_number}回目")

        # 一時ファイル削除
        for p in [light_path, heavy_path]:
            if p != pdf_path and p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

        return best


def main():
    """テスト実行"""
    import argparse

    parser = argparse.ArgumentParser(description="OCRパイプライン（C案）")
    parser.add_argument("pdf", help="入力PDFパス")
    parser.add_argument("--analyze-only", action="store_true", help="分析のみ")

    args = parser.parse_args()

    from common.logger import setup_logger
    setup_logger("ocr_pipeline")

    pipeline = OCRPipeline()

    if args.analyze_only:
        metrics = pipeline.analyze_pdf(Path(args.pdf))
        print(f"\n=== 品質分析: {Path(args.pdf).name} ===")
        print(f"推定DPI: {metrics.estimated_dpi:.0f}")
        print(f"テキスト層: {'あり' if metrics.has_text_layer else 'なし'}")
        print(f"横向き: {'はい' if metrics.is_landscape else 'いいえ'}")
        print(f"ブレスコア: {metrics.blur_score:.1f}")
        print(f"コントラスト: {metrics.contrast_score:.1f}")
        print(f"影検出: {'あり' if metrics.shadow_detected else 'なし'}")
        print(f"傾き: {metrics.skew_angle:.1f}度")
        print(f"透視歪み: {'あり' if metrics.needs_perspective else 'なし'}")
    else:
        result = pipeline.process(Path(args.pdf))

        print(f"\n=== 抽出結果 ===")
        print(f"取引先: {result.vendor_name}")
        print(f"日付: {result.issue_date}")
        print(f"金額: {result.amount:,}円" if result.amount else "金額: -")
        print(f"事業者番号: {result.invoice_number}")
        print(f"信頼度: {result.confidence:.2%}")
        print(f"採用パス: {result.pass_number}回目")
        print(f"前処理: {result.preprocessing_applied}")
        print(f"品質問題: {result.quality_issues}")
        print(f"成功: {result.success}")


if __name__ == "__main__":
    main()
