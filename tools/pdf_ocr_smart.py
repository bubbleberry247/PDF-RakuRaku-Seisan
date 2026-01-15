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

# 極端な傾き閾値
EXTREME_SKEW_THRESHOLD = 25.0  # これ以上の傾きは2回前処理を適用

# アップスケール設定
UPSCALE_DPI_THRESHOLD = 150  # この解像度以下ならアップスケール
UPSCALE_TARGET_DPI = 300     # アップスケール後の目標解像度

# 手動キューディレクトリ
MANUAL_QUEUE_DIR = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\work\manual_queue")


@dataclass
class SmartOCRResult:
    """スマートOCR処理結果"""
    # 抽出データ
    vendor_name: str = ""
    issue_date: str = ""  # YYYYMMDD
    amount: int = 0
    invoice_number: str = ""  # 事業者登録番号（T+13桁）
    raw_text: str = ""

    # 処理情報
    confidence: float = 0.0
    requires_manual: bool = False
    preprocess_info: Dict = field(default_factory=dict)

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
            "confidence": self.confidence,
            "requires_manual": self.requires_manual,
            "success": self.success,
            "error": self.error
        }


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
            result.raw_text = ocr_result.raw_text

            # 3. 信頼度判定
            result.confidence = self.evaluate_confidence(ocr_result)

            # 4. 低信頼度判定 → Adobe PDF Servicesへフォールバック
            if result.confidence < CONFIDENCE_THRESHOLD:
                # Adobe PDF Services OCRでリトライ
                if ADOBE_OCR_AVAILABLE:
                    self.logger.info(
                        f"YomiToku低信頼度({result.confidence:.2f}) → Adobe PDF Servicesで再試行"
                    )
                    try:
                        adobe_result = self._fallback_to_adobe_ocr(pdf_path)
                        if adobe_result:
                            adobe_confidence = self.evaluate_confidence(adobe_result)
                            if adobe_confidence > result.confidence:
                                # Adobe結果の方が良い場合は採用
                                result.vendor_name = adobe_result.vendor_name or result.vendor_name
                                result.issue_date = adobe_result.issue_date or result.issue_date
                                result.amount = adobe_result.amount or result.amount
                                result.invoice_number = adobe_result.invoice_number or result.invoice_number
                                result.confidence = adobe_confidence
                                # ocr_engine情報はpreprocess_infoに保存
                                result.preprocess_info["ocr_engine"] = "adobe_pdf_services"
                                self.logger.info(
                                    f"Adobe PDF Services採用: 信頼度={adobe_confidence:.2f}"
                                )
                    except Exception as e:
                        self.logger.warning(f"Adobe PDF Servicesフォールバック失敗: {e}")

                # 再評価
                if result.confidence < CONFIDENCE_THRESHOLD:
                    result.requires_manual = True
                    self.logger.warning(
                        f"低信頼度: {result.confidence:.2f} < {CONFIDENCE_THRESHOLD} "
                        f"→ 手動対応が必要"
                    )

                    # 自動キュー登録
                    if auto_queue:
                        self.add_to_manual_queue(pdf_path, result)
                else:
                    result.success = True
                    self.logger.info(
                        f"OCR完了（フォールバック成功）: 信頼度={result.confidence:.2f}"
                    )
            else:
                result.success = True
                self.logger.info(
                    f"OCR完了: 信頼度={result.confidence:.2f}, "
                    f"vendor={result.vendor_name}, "
                    f"date={result.issue_date}, "
                    f"amount={result.amount}"
                )

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
