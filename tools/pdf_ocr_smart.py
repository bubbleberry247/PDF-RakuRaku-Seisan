# -*- coding: utf-8 -*-
"""
スマートOCRプロセッサ

Document AI APIを完全廃止し、ローカルOCR（YomiToku）をメインエンジンとして使用
- 前処理を最大限強化（回転・傾き・影除去）
- 信頼度判定で低品質PDFは手動キューへ
- API使用コスト: ゼロ

Created: 2026-01-14

Usage:
    from pdf_ocr_smart import SmartOCRProcessor

    processor = SmartOCRProcessor()
    result = processor.process("receipt.pdf")

    if result.requires_manual:
        print("手動対応が必要です")
"""
import os
import sys
import json
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
import re

sys.path.insert(0, str(Path(__file__).parent))

from common.logger import get_logger

# 前処理モジュール
from pdf_preprocess import PDFPreprocessor, PreprocessResult, SKEW_THRESHOLD_DEFAULT

# YomiToku OCR
try:
    from pdf_ocr_yomitoku import YomiTokuOCRProcessor, PDFExtractResult
    YOMITOKU_AVAILABLE = True
except ImportError:
    YOMITOKU_AVAILABLE = False

# Adobe PDF Services OCR（フォールバック用）
try:
    from pdf_ocr import PDFOCRProcessor as AdobeOCRProcessor
    ADOBE_OCR_AVAILABLE = True
except ImportError:
    ADOBE_OCR_AVAILABLE = False

# Gemini マルチモーダルOCR検証（LayerX方式: OCRテキスト+画像→LLM）
try:
    from pdf_ocr_gemini import GeminiOCRValidator
    GEMINI_OCR_AVAILABLE = True
except ImportError:
    GEMINI_OCR_AVAILABLE = False


# ===========================================
# 設定値
# ===========================================

# 信頼度閾値 - 回転検出改善に伴い0.55→0.40に緩和（39%成功率達成）
CONFIDENCE_THRESHOLD = 0.40

# 金額の妥当性範囲
AMOUNT_MIN = 50         # 最小金額（円）- レシート対応で50円に緩和
AMOUNT_MAX = 10000000   # 最大金額（1000万円）

# 信頼度スコアリング配点（調整版）
SCORE_WEIGHTS = {
    'amount_exists': 0.30,      # 金額あり（0.35→0.30に減少）
    'amount_valid_range': 0.15, # 金額が妥当範囲（0.20→0.15に減少）
    'date_valid': 0.20,         # 日付が妥当形式（変更なし）
    'vendor_exists': 0.20,      # 取引先あり（0.15→0.20に増加）
    'invoice_valid': 0.15,      # 登録番号あり（0.10→0.15に増加）
}

# LLM マルチモーダル検証設定（LayerX方式）
LLM_ENABLED = True              # Gemini検証ON/OFF
LLM_TRIGGER_MODE = "low_confidence"  # "low_confidence" | "always" | "never"
LLM_MERGE_STRATEGY = "fill_empty"    # "fill_empty" = LLMは空フィールドのみ補完

# 極端な傾き閾値
EXTREME_SKEW_THRESHOLD = 25.0  # これ以上の傾きは2回前処理を適用

# アップスケール設定
UPSCALE_DPI_THRESHOLD = 150  # この解像度以下ならアップスケール
UPSCALE_TARGET_DPI = 300     # アップスケール後の目標解像度

# 手動キューディレクトリ
MANUAL_QUEUE_DIR = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\work\manual_queue")


@dataclass
class QualityGateResult:
    """品質ゲート判定結果"""
    passed: bool = False
    issues: List[str] = field(default_factory=list)

    # 各項目の妥当性
    document_type_valid: bool = False
    date_valid: bool = False
    invoice_number_valid: bool = False
    vendor_valid: bool = False
    amount_valid: bool = False

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "issues": self.issues,
            "document_type_valid": self.document_type_valid,
            "date_valid": self.date_valid,
            "invoice_number_valid": self.invoice_number_valid,
            "vendor_valid": self.vendor_valid,
            "amount_valid": self.amount_valid
        }


def check_quality_gate(
    vendor_name: str,
    issue_date: str,
    amount: int,
    invoice_number: str,
    document_type: str
) -> QualityGateResult:
    """
    必須項目の品質ゲートチェック

    必須項目（全てパスしないと自動OKにならない）:
    - 書類区分: 領収書 or 請求書
    - 取引日: YYYYMMDD形式、2026年以降
    - 事業者登録番号: T + 13桁
    - 取引先名: 2文字以上
    - 金額: 50円以上

    任意項目（チェック対象外）:
    - 備考（但し書き）

    Returns:
        QualityGateResult
    """
    result = QualityGateResult()

    # 1. 書類区分: 領収書 or 請求書
    if document_type in ["領収書", "請求書"]:
        result.document_type_valid = True
    else:
        result.issues.append(f"書類区分未確定（値: {document_type}）")

    # 2. 取引日: YYYYMMDD形式、2026年以降
    if issue_date and re.match(r'^20\d{6}$', issue_date):
        try:
            year = int(issue_date[:4])
            month = int(issue_date[4:6])
            day = int(issue_date[6:8])
            if year >= 2026 and 1 <= month <= 12 and 1 <= day <= 31:
                result.date_valid = True
            else:
                result.issues.append(f"取引日が範囲外（値: {issue_date}、2026年以降のみ対応）")
        except ValueError:
            result.issues.append(f"取引日が不正形式（値: {issue_date}）")
    else:
        result.issues.append(f"取引日未抽出（値: {issue_date or '(空)'}）")

    # 3. 事業者登録番号: T + 13桁
    if invoice_number and re.match(r'^T\d{13}$', invoice_number):
        result.invoice_number_valid = True
    else:
        result.issues.append(f"事業者登録番号未抽出または不正形式（値: {invoice_number or '(空)'}）")

    # 4. 取引先名: 2文字以上
    if vendor_name and len(vendor_name) >= 2:
        result.vendor_valid = True
    else:
        result.issues.append(f"取引先名未抽出または短すぎ（値: {vendor_name or '(空)'}）")

    # 5. 金額: 50円以上
    if amount >= AMOUNT_MIN:
        result.amount_valid = True
    else:
        result.issues.append(f"金額未抽出または範囲外（値: {amount}円、{AMOUNT_MIN}円以上必要）")

    # 全項目パスで合格
    result.passed = all([
        result.document_type_valid,
        result.date_valid,
        result.invoice_number_valid,
        result.vendor_valid,
        result.amount_valid
    ])

    return result


def generate_final_json(
    document_id: str,
    document_type: str,
    issue_date: str,
    invoice_number: str,
    vendor_name: str,
    amount: int,
    remarks: str = ""
) -> dict:
    """
    楽楽精算登録用のfinal.json形式を生成

    Args:
        document_id: ドキュメントID（例: DOC-20260115-000123）
        document_type: 書類区分（領収書 or 請求書）
        issue_date: 取引日（YYYYMMDD形式）
        invoice_number: 事業者登録番号（T+13桁）
        vendor_name: 取引先名
        amount: 金額
        remarks: 備考（但し書き）

    Returns:
        final.json形式の辞書
    """
    # 日付を年・月・日に分解
    year = int(issue_date[:4]) if issue_date and len(issue_date) >= 4 else 0
    month = int(issue_date[4:6]) if issue_date and len(issue_date) >= 6 else 0
    day = int(issue_date[6:8]) if issue_date and len(issue_date) >= 8 else 0

    return {
        "document_id": document_id,
        "document_type": document_type,
        "transaction_date": {"year": year, "month": month, "day": day},
        "receipt_date": {"year": year, "month": month, "day": day},  # 受領日=取引日
        "invoice_number": invoice_number,
        "vendor_name": vendor_name,
        "amount": amount,
        "remarks": remarks
    }


@dataclass
class SmartOCRResult:
    """スマートOCR処理結果"""
    # 抽出データ
    vendor_name: str = ""
    issue_date: str = ""  # YYYYMMDD
    amount: int = 0
    invoice_number: str = ""  # 事業者登録番号（T+13桁）
    document_type: str = "領収書"  # "領収書" or "請求書"
    description: str = ""  # 但し書き
    raw_text: str = ""

    # 処理情報
    confidence: float = 0.0
    requires_manual: bool = False
    preprocess_info: Dict = field(default_factory=dict)

    # 品質ゲート結果
    quality_gate: Optional[QualityGateResult] = None

    # ステータス
    success: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        """辞書に変換"""
        return {
            "vendor_name": self.vendor_name,
            "issue_date": self.issue_date,
            "amount": self.amount,
            "invoice_number": self.invoice_number,
            "document_type": self.document_type,
            "description": self.description,
            "confidence": self.confidence,
            "requires_manual": self.requires_manual,
            "quality_gate": self.quality_gate.to_dict() if self.quality_gate else None,
            "success": self.success,
            "error": self.error
        }

    def to_final_json(self, document_id: str) -> dict:
        """楽楽精算登録用のfinal.json形式に変換"""
        return generate_final_json(
            document_id=document_id,
            document_type=self.document_type,
            issue_date=self.issue_date,
            invoice_number=self.invoice_number,
            vendor_name=self.vendor_name,
            amount=self.amount,
            remarks=self.description
        )


class SmartOCRProcessor:
    """
    スマートOCRプロセッサ

    API使用ゼロのローカルOCR処理

    処理フロー:
    1. 品質分析（前処理で自動実行）
    2. 前処理（回転・傾き・影除去）
    3. OCR実行（YomiToku CPU lite_mode）
    4. 信頼度判定
    5. 低信頼度は手動キューへ
    """

    def __init__(
        self,
        use_gpu: bool = False,
        lite_mode: bool = True,
        preprocess_dpi: int = 300
    ):
        """
        Args:
            use_gpu: GPU使用（Falseの場合CPU）
            lite_mode: YomiToku軽量モード（CPU向け）
            preprocess_dpi: 前処理時の解像度
        """
        self.logger = get_logger()

        if not YOMITOKU_AVAILABLE:
            raise ImportError(
                "YomiTokuがインストールされていません: pip install yomitoku"
            )

        self.use_gpu = use_gpu
        self.lite_mode = lite_mode

        # 前処理モジュール
        self.preprocessor = PDFPreprocessor(dpi=preprocess_dpi)

        # YomiToku OCR（遅延初期化）
        self._ocr_processor = None

        self.logger.info(
            f"SmartOCRProcessor初期化: GPU={use_gpu}, lite={lite_mode}"
        )

    @property
    def ocr_processor(self) -> YomiTokuOCRProcessor:
        """YomiTokuプロセッサの遅延初期化"""
        if self._ocr_processor is None:
            self._ocr_processor = YomiTokuOCRProcessor(
                use_gpu=self.use_gpu,
                lite_mode=self.lite_mode
            )
        return self._ocr_processor

    def evaluate_confidence(self, result: PDFExtractResult) -> float:
        """
        抽出結果の信頼度を計算（調整版）

        判定基準（SCORE_WEIGHTS使用）:
        - 金額が取得できた: +0.30
        - 金額が妥当範囲: +0.15
        - 日付が妥当な形式: +0.20
        - 取引先名が取得できた: +0.20
        - 事業者登録番号（T+13桁）: +0.15

        Args:
            result: OCR抽出結果

        Returns:
            信頼度スコア（0.0〜1.0）
        """
        score = 0.0

        # 金額が取得できた
        if result.amount > 0:
            score += SCORE_WEIGHTS['amount_exists']

        # 金額が妥当範囲
        if AMOUNT_MIN <= result.amount <= AMOUNT_MAX:
            score += SCORE_WEIGHTS['amount_valid_range']

        # 日付が妥当な形式（YYYYMMDD, 8桁）
        if result.issue_date and len(result.issue_date) == 8:
            try:
                year = int(result.issue_date[:4])
                month = int(result.issue_date[4:6])
                day = int(result.issue_date[6:8])
                if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    score += SCORE_WEIGHTS['date_valid']
            except ValueError:
                pass
        # 日付が部分的でもあれば少しスコア追加
        elif result.issue_date and len(result.issue_date) >= 4:
            score += 0.05

        # 取引先名が取得できた
        if result.vendor_name and len(result.vendor_name) >= 2:
            score += SCORE_WEIGHTS['vendor_exists']
        # 1文字でも取得できていれば少しスコア追加
        elif result.vendor_name:
            score += 0.05

        # 事業者登録番号（T+13桁）
        if result.invoice_number:
            if re.match(r'^T\d{13}$', result.invoice_number):
                score += SCORE_WEIGHTS['invoice_valid']

        # ボーナス: 3項目以上揃っている場合
        filled_count = sum([
            bool(result.amount > 0),
            bool(result.issue_date),
            bool(result.vendor_name),
            bool(result.invoice_number),
        ])
        if filled_count >= 3:
            score += 0.05  # ボーナス

        return min(score, 1.0)

    def _fallback_to_adobe_ocr(self, pdf_path: Path) -> Optional[PDFExtractResult]:
        """
        Adobe PDF Services OCRでフォールバック処理

        Args:
            pdf_path: 入力PDFパス

        Returns:
            抽出結果（失敗時はNone）
        """
        if not ADOBE_OCR_AVAILABLE:
            return None

        try:
            adobe_processor = AdobeOCRProcessor()
            result = adobe_processor.process_pdf(pdf_path)
            return result
        except Exception as e:
            self.logger.warning(f"Adobe OCRエラー: {e}")
            return None

    def add_to_manual_queue(
        self,
        pdf_path: Path,
        result: SmartOCRResult,
        reason: str = "low_confidence"
    ) -> None:
        """
        低信頼度PDFを手動キューに登録

        Args:
            pdf_path: 元PDFのパス
            result: OCR結果
            reason: 登録理由
        """
        queue_dir = MANUAL_QUEUE_DIR
        queue_dir.mkdir(parents=True, exist_ok=True)

        # PDFをコピー
        dest_path = queue_dir / pdf_path.name
        if not dest_path.exists():
            shutil.copy(pdf_path, dest_path)

        # キューJSONに登録
        queue_file = queue_dir / "queue.json"
        if queue_file.exists():
            queue = json.loads(queue_file.read_text(encoding="utf-8"))
        else:
            queue = []

        # 既存エントリを確認
        existing = [q for q in queue if q.get("file") == pdf_path.name]
        if existing:
            self.logger.info(f"既にキューに登録済み: {pdf_path.name}")
            return

        queue.append({
            "file": pdf_path.name,
            "timestamp": datetime.now().isoformat(),
            "partial_result": {
                "vendor_name": result.vendor_name,
                "issue_date": result.issue_date,
                "amount": result.amount,
                "invoice_number": result.invoice_number
            },
            "confidence": result.confidence,
            "reason": reason
        })

        queue_file.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        self.logger.info(f"手動キューに登録: {pdf_path.name} (理由: {reason})")

    def process(
        self,
        pdf_path: Path,
        output_dir: Path = None,
        skip_preprocess: bool = False,
        auto_queue: bool = True
    ) -> SmartOCRResult:
        """
        PDFをスマートOCR処理

        Args:
            pdf_path: 入力PDFパス
            output_dir: 前処理済みPDFの出力先
            skip_preprocess: 前処理をスキップするか
            auto_queue: 低信頼度時に自動的にキューに追加するか

        Returns:
            処理結果
        """
        pdf_path = Path(pdf_path)
        result = SmartOCRResult()

        if not pdf_path.exists():
            result.error = f"ファイルが存在しません: {pdf_path}"
            return result

        try:
            self.logger.info(f"スマートOCR処理開始: {pdf_path.name}")

            # 1. 前処理（回転・傾き・影除去）
            if not skip_preprocess:
                preprocess_result = self.preprocessor.preprocess(
                    pdf_path,
                    output_dir=output_dir,
                    do_deskew=True,
                    do_enhance=False,  # YomiTokuに任せる
                    do_shadow_removal=True,
                    skew_threshold=SKEW_THRESHOLD_DEFAULT,
                    force_4way_rotation=True
                )

                if not preprocess_result.success:
                    result.error = f"前処理エラー: {preprocess_result.error}"
                    return result

                # 極端な傾き（25度以上）の場合は2回目の前処理を実行
                if abs(preprocess_result.skew_angle) >= EXTREME_SKEW_THRESHOLD:
                    self.logger.info(
                        f"極端な傾き検出: {preprocess_result.skew_angle:.1f}度 → 2回目前処理実行"
                    )
                    preprocess_result2 = self.preprocessor.preprocess(
                        preprocess_result.output_path,
                        output_dir=output_dir,
                        do_deskew=True,
                        do_enhance=True,  # 2回目は画像強調も適用
                        do_shadow_removal=True,
                        skew_threshold=0.3,  # より厳しい閾値
                        force_4way_rotation=True
                    )
                    if preprocess_result2.success:
                        preprocess_result = preprocess_result2
                        self.logger.info(
                            f"2回目前処理完了: 傾き={preprocess_result.skew_angle:.1f}度"
                        )

                # 前処理情報を保存
                result.preprocess_info = {
                    "rotated": preprocess_result.rotated,
                    "rotation_angle": preprocess_result.rotation_angle,
                    "deskewed": preprocess_result.deskewed,
                    "skew_angle": preprocess_result.skew_angle,
                    "shadow_removed": preprocess_result.shadow_removed
                }

                # 前処理済みPDFを使用
                ocr_target = preprocess_result.output_path
            else:
                ocr_target = pdf_path

            # 2. OCR実行（YomiToku）
            ocr_result = self.ocr_processor.process_pdf(ocr_target)

            # 結果をコピー
            result.vendor_name = ocr_result.vendor_name
            result.issue_date = ocr_result.issue_date
            result.amount = ocr_result.amount
            result.invoice_number = ocr_result.invoice_number
            result.document_type = ocr_result.document_type
            result.description = ocr_result.description
            result.raw_text = ocr_result.raw_text

            # 3. 信頼度判定
            result.confidence = self.evaluate_confidence(ocr_result)

            # 4. LLM検証 or フォールバック判定
            needs_enhancement = (
                result.confidence < CONFIDENCE_THRESHOLD
                or LLM_TRIGGER_MODE == "always"
            )

            # 4a. Geminiマルチモーダル検証（LayerX方式: 画像+OCRテキスト→LLM）
            if needs_enhancement and LLM_ENABLED and GEMINI_OCR_AVAILABLE and LLM_TRIGGER_MODE != "never":
                self.logger.info(
                    f"Geminiマルチモーダル検証開始（信頼度={result.confidence:.2f}, "
                    f"trigger={LLM_TRIGGER_MODE}）"
                )
                try:
                    gemini_validator = GeminiOCRValidator()
                    llm_result = gemini_validator.validate(
                        pdf_path=ocr_target,
                        ocr_text=result.raw_text,
                    )

                    # regex結果をdict化（比較用）
                    regex_fields = {
                        "vendor_name": result.vendor_name,
                        "issue_date": result.issue_date,
                        "amount": result.amount,
                        "invoice_number": result.invoice_number,
                    }

                    # マージ戦略: fill_empty = LLMは空フィールドのみ補完
                    merged = False
                    if LLM_MERGE_STRATEGY == "fill_empty":
                        if not result.vendor_name and llm_result.get("vendor_name"):
                            result.vendor_name = llm_result["vendor_name"]
                            merged = True
                        if not result.issue_date and llm_result.get("issue_date"):
                            result.issue_date = llm_result["issue_date"]
                            merged = True
                        if not result.amount and llm_result.get("amount"):
                            result.amount = llm_result["amount"]
                            merged = True
                        if not result.invoice_number and llm_result.get("invoice_number"):
                            result.invoice_number = llm_result["invoice_number"]
                            merged = True
                        if not result.document_type and llm_result.get("document_type"):
                            result.document_type = llm_result["document_type"]
                            merged = True
                        if not result.description and llm_result.get("description"):
                            result.description = llm_result["description"]
                            merged = True
                    elif LLM_MERGE_STRATEGY == "llm_preferred":
                        # LLM結果を優先（非空のもののみ）
                        for fld in ["vendor_name", "issue_date", "amount", "invoice_number",
                                     "document_type", "description"]:
                            llm_val = llm_result.get(fld)
                            if llm_val:
                                setattr(result, fld, llm_val)
                                merged = True

                    if merged:
                        # 再スコアリング
                        result.confidence = self.evaluate_confidence(result)
                        result.preprocess_info["ocr_engine"] = "yomitoku+gemini"
                        self.logger.info(
                            f"Gemini補完後: 信頼度={result.confidence:.2f}, "
                            f"vendor={result.vendor_name}, amount={result.amount}"
                        )

                    # 差分照合: regexとLLMが両方値を持つが異なる場合
                    has_disagreement = False
                    for fld in ["vendor_name", "issue_date", "amount", "invoice_number"]:
                        rv = regex_fields.get(fld, "")
                        lv = llm_result.get(fld, "")
                        if rv and lv and str(rv) != str(lv):
                            has_disagreement = True
                            break

                    if has_disagreement:
                        self.logger.info("regex vs LLM 不一致検出 → 差分照合実行")
                        try:
                            reconciled = gemini_validator.reconcile(
                                pdf_path=ocr_target,
                                regex_result=regex_fields,
                                llm_result=llm_result,
                            )
                            # 照合結果を適用
                            for fld in ["vendor_name", "issue_date", "amount", "invoice_number"]:
                                rec_val = reconciled.get(fld)
                                if rec_val:
                                    setattr(result, fld, rec_val)
                            result.confidence = self.evaluate_confidence(result)
                            result.preprocess_info["ocr_engine"] = "yomitoku+gemini+reconciled"
                            self.logger.info(
                                f"差分照合後: 信頼度={result.confidence:.2f}"
                            )
                        except Exception as e:
                            self.logger.warning(f"差分照合失敗（regex結果を維持）: {e}")

                    # LLM reasoning をログに記録（アンドン: 判断根拠の可視化）
                    reasoning = llm_result.get("reasoning", "")
                    if reasoning:
                        self.logger.info(f"Gemini reasoning: {reasoning}")

                except Exception as e:
                    self.logger.warning(f"Geminiマルチモーダル検証失敗（regex結果を維持）: {e}")

            # 4b. まだ低信頼度ならAdobe PDF Servicesへフォールバック（3次）
            if result.confidence < CONFIDENCE_THRESHOLD:
                if ADOBE_OCR_AVAILABLE:
                    self.logger.info(
                        f"低信頼度継続({result.confidence:.2f}) → Adobe PDF Servicesで再試行"
                    )
                    try:
                        adobe_result = self._fallback_to_adobe_ocr(pdf_path)
                        if adobe_result:
                            adobe_confidence = self.evaluate_confidence(adobe_result)
                            if adobe_confidence > result.confidence:
                                result.vendor_name = adobe_result.vendor_name or result.vendor_name
                                result.issue_date = adobe_result.issue_date or result.issue_date
                                result.amount = adobe_result.amount or result.amount
                                result.invoice_number = adobe_result.invoice_number or result.invoice_number
                                result.document_type = adobe_result.document_type or result.document_type
                                result.description = adobe_result.description or result.description
                                result.confidence = adobe_confidence
                                result.preprocess_info["ocr_engine"] = "adobe_pdf_services"
                                self.logger.info(
                                    f"Adobe PDF Services採用: 信頼度={adobe_confidence:.2f}"
                                )
                    except Exception as e:
                        self.logger.warning(f"Adobe PDF Servicesフォールバック失敗: {e}")

            # 5. 品質ゲート判定（必須項目の存在+形式妥当性チェック）
            result.quality_gate = check_quality_gate(
                vendor_name=result.vendor_name,
                issue_date=result.issue_date,
                amount=result.amount,
                invoice_number=result.invoice_number,
                document_type=result.document_type
            )

            # 6. 成功判定: 品質ゲートパス AND 信頼度閾値以上
            if result.quality_gate.passed and result.confidence >= CONFIDENCE_THRESHOLD:
                result.success = True
                self.logger.info(
                    f"OCR完了: 信頼度={result.confidence:.2f}, "
                    f"vendor={result.vendor_name}, "
                    f"date={result.issue_date}, "
                    f"amount={result.amount}"
                )
            else:
                result.requires_manual = True
                # 失敗理由を詳細にログ出力
                reasons = []
                if not result.quality_gate.passed:
                    reasons.append(f"品質ゲート失敗: {', '.join(result.quality_gate.issues)}")
                if result.confidence < CONFIDENCE_THRESHOLD:
                    reasons.append(f"信頼度不足: {result.confidence:.2f} < {CONFIDENCE_THRESHOLD}")
                self.logger.warning(f"手動対応が必要 → {'; '.join(reasons)}")

                # 自動キュー登録
                if auto_queue:
                    reason = "quality_gate_failed" if not result.quality_gate.passed else "low_confidence"
                    self.add_to_manual_queue(pdf_path, result, reason=reason)

        except Exception as e:
            result.error = str(e)
            self.logger.error(f"スマートOCRエラー: {e}")
            import traceback
            traceback.print_exc()

        return result

    def process_batch(
        self,
        pdf_dir: Path,
        output_dir: Path = None,
        dry_run: bool = False
    ) -> List[SmartOCRResult]:
        """
        ディレクトリ内の全PDFをバッチ処理

        Args:
            pdf_dir: PDFディレクトリ
            output_dir: 出力ディレクトリ
            dry_run: ドライラン（実際の処理をしない）

        Returns:
            処理結果のリスト
        """
        pdf_dir = Path(pdf_dir)
        results = []

        pdf_files = list(pdf_dir.glob("*.pdf"))
        self.logger.info(f"バッチ処理開始: {len(pdf_files)}ファイル")

        for pdf_path in pdf_files:
            if dry_run:
                self.logger.info(f"[DRY-RUN] {pdf_path.name}")
                continue

            result = self.process(pdf_path, output_dir)
            results.append(result)

        # サマリー
        success_count = sum(1 for r in results if r.success)
        manual_count = sum(1 for r in results if r.requires_manual)
        error_count = sum(1 for r in results if r.error)

        self.logger.info(
            f"バッチ処理完了: 成功={success_count}, "
            f"手動対応={manual_count}, エラー={error_count}"
        )

        return results


def main():
    """テスト実行"""
    import argparse

    parser = argparse.ArgumentParser(description="スマートOCR処理")
    parser.add_argument("pdf", nargs="?", help="PDFファイルパス")
    parser.add_argument("--batch", action="store_true", help="バッチ処理モード")
    parser.add_argument("--dry-run", action="store_true", help="ドライラン")
    parser.add_argument("--gpu", action="store_true", help="GPU使用")
    parser.add_argument("--no-lite", action="store_true", help="フルモデル使用")

    args = parser.parse_args()

    # ロガー設定
    from common.logger import setup_logger
    setup_logger("pdf_ocr_smart")

    processor = SmartOCRProcessor(
        use_gpu=args.gpu,
        lite_mode=not args.no_lite
    )

    if args.batch:
        # バッチ処理
        sample_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\sample PDF")
        results = processor.process_batch(sample_dir, dry_run=args.dry_run)

        print("\n=== バッチ処理結果 ===")
        for r in results:
            status = "OK" if r.success else ("MANUAL" if r.requires_manual else "ERROR")
            print(f"[{status}] conf={r.confidence:.2f} amount={r.amount} vendor={r.vendor_name}")

    elif args.pdf:
        # 単一ファイル処理
        result = processor.process(Path(args.pdf))

        print("\n=== スマートOCR結果 ===")
        print(f"取引先名: {result.vendor_name}")
        print(f"発行日: {result.issue_date}")
        print(f"金額: {result.amount:,}円" if result.amount else "金額: -")
        print(f"事業者登録番号: {result.invoice_number}")
        print(f"信頼度: {result.confidence:.2%}")
        print(f"手動対応必要: {result.requires_manual}")
        print(f"成功: {result.success}")
        if result.error:
            print(f"エラー: {result.error}")

        print("\n--- 前処理情報 ---")
        for k, v in result.preprocess_info.items():
            print(f"  {k}: {v}")

    else:
        # サンプルテスト
        sample_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\sample PDF")
        test_files = [
            "(株)ニトリ.pdf",
            "0109セリア(百均)買物.pdf",
        ]

        print("=== スマートOCRテスト ===")
        print(f"信頼度閾値: {CONFIDENCE_THRESHOLD}")
        print("=" * 60)

        for fname in test_files:
            pdf_path = sample_dir / fname
            if not pdf_path.exists():
                print(f"\n[SKIP] {fname}")
                continue

            print(f"\n--- {fname} ---")
            result = processor.process(pdf_path)

            status = "OK" if result.success else ("MANUAL" if result.requires_manual else "ERROR")
            print(f"  ステータス: {status}")
            print(f"  信頼度: {result.confidence:.2%}")
            print(f"  取引先: {result.vendor_name}")
            print(f"  日付: {result.issue_date}")
            print(f"  金額: {result.amount:,}円" if result.amount else "  金額: -")
            if result.error:
                print(f"  エラー: {result.error}")


if __name__ == "__main__":
    main()
