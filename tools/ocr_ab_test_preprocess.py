# -*- coding: utf-8 -*-
"""
OCR ABテスト - 前処理あり/なし比較

前処理（回転補正・傾き補正）の効果を検証
"""
import os
import sys
import shutil
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding='utf-8')

from common.logger import setup_logger, get_logger
from pdf_ocr import PDFOCRProcessor, PDFExtractResult
from pdf_preprocess import PDFPreprocessor, PreprocessResult


@dataclass
class ABTestResult:
    """ABテスト結果"""
    filename: str
    # 前処理なし
    baseline_vendor: str = ""
    baseline_date: str = ""
    baseline_amount: int = 0
    baseline_invoice: str = ""
    baseline_success: bool = False
    # 前処理あり
    preproc_vendor: str = ""
    preproc_date: str = ""
    preproc_amount: int = 0
    preproc_invoice: str = ""
    preproc_success: bool = False
    # 前処理情報
    rotated: bool = False
    deskewed: bool = False
    skew_angle: float = 0.0


def run_ab_test(pdf_files: List[Path], output_dir: Path) -> List[ABTestResult]:
    """ABテスト実行"""
    logger = get_logger()
    preprocessor = PDFPreprocessor(dpi=200)
    ocr_processor = PDFOCRProcessor()

    # 一時ディレクトリ
    preproc_dir = output_dir / "preprocessed"
    preproc_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for pdf_path in pdf_files:
        logger.info(f"テスト: {pdf_path.name}")
        result = ABTestResult(filename=pdf_path.name)

        try:
            # === ベースライン（前処理なし） ===
            # OCR-JAのoutputに既存のOCR済みファイルがあれば使う
            ocr_output = ocr_processor.output_dir / f"{pdf_path.stem}_ocr.pdf"

            if ocr_output.exists():
                baseline_result = ocr_processor.process_pdf(pdf_path, skip_ocr=True)
            else:
                baseline_result = ocr_processor.process_pdf(pdf_path, skip_ocr=False)

            result.baseline_vendor = baseline_result.vendor_name
            result.baseline_date = baseline_result.issue_date
            result.baseline_amount = baseline_result.amount
            result.baseline_invoice = baseline_result.invoice_number
            result.baseline_success = baseline_result.success

            # === 前処理あり ===
            preproc_result = preprocessor.preprocess(
                pdf_path,
                preproc_dir,
                do_deskew=True,
                do_enhance=False,
                skew_threshold=2.0
            )

            result.rotated = preproc_result.rotated
            result.deskewed = preproc_result.deskewed
            result.skew_angle = preproc_result.skew_angle

            if preproc_result.success and (preproc_result.rotated or preproc_result.deskewed):
                # 前処理済みPDFでOCR
                preproc_ocr_result = ocr_processor.process_pdf(
                    preproc_result.output_path, skip_ocr=False
                )

                result.preproc_vendor = preproc_ocr_result.vendor_name
                result.preproc_date = preproc_ocr_result.issue_date
                result.preproc_amount = preproc_ocr_result.amount
                result.preproc_invoice = preproc_ocr_result.invoice_number
                result.preproc_success = preproc_ocr_result.success
            else:
                # 前処理なし = ベースラインと同じ
                result.preproc_vendor = result.baseline_vendor
                result.preproc_date = result.baseline_date
                result.preproc_amount = result.baseline_amount
                result.preproc_invoice = result.baseline_invoice
                result.preproc_success = result.baseline_success

        except Exception as e:
            logger.error(f"エラー: {pdf_path.name} - {e}")

        results.append(result)

    return results


def print_results(results: List[ABTestResult]):
    """結果を表示"""
    print("\n" + "=" * 100)
    print("ABテスト結果")
    print("=" * 100)

    # ヘッダー
    print(f"\n{'ファイル名':<30} | {'ベースライン':^40} | {'前処理あり':^40}")
    print(f"{'':<30} | {'取引先':<15} {'日付':<10} {'金額':>8} | {'取引先':<15} {'日付':<10} {'金額':>8}")
    print("-" * 100)

    baseline_scores = {'vendor': 0, 'date': 0, 'amount': 0, 'invoice': 0}
    preproc_scores = {'vendor': 0, 'date': 0, 'amount': 0, 'invoice': 0}
    improved = []
    degraded = []

    for r in results:
        # スコア計算
        b_score = sum([
            1 if r.baseline_vendor else 0,
            1 if r.baseline_date else 0,
            1 if r.baseline_amount > 0 else 0,
            1 if r.baseline_invoice else 0
        ])
        p_score = sum([
            1 if r.preproc_vendor else 0,
            1 if r.preproc_date else 0,
            1 if r.preproc_amount > 0 else 0,
            1 if r.preproc_invoice else 0
        ])

        # 集計
        if r.baseline_vendor:
            baseline_scores['vendor'] += 1
        if r.baseline_date:
            baseline_scores['date'] += 1
        if r.baseline_amount > 0:
            baseline_scores['amount'] += 1
        if r.baseline_invoice:
            baseline_scores['invoice'] += 1

        if r.preproc_vendor:
            preproc_scores['vendor'] += 1
        if r.preproc_date:
            preproc_scores['date'] += 1
        if r.preproc_amount > 0:
            preproc_scores['amount'] += 1
        if r.preproc_invoice:
            preproc_scores['invoice'] += 1

        # 改善/悪化の判定
        if p_score > b_score:
            improved.append(r.filename)
        elif p_score < b_score:
            degraded.append(r.filename)

        # 表示
        preproc_info = ""
        if r.rotated:
            preproc_info += "R"
        if r.deskewed:
            preproc_info += f"D({r.skew_angle:.0f})"

        print(
            f"{r.filename[:28]:<30} | "
            f"{r.baseline_vendor[:13]:<15} {r.baseline_date:<10} {r.baseline_amount:>8} | "
            f"{r.preproc_vendor[:13]:<15} {r.preproc_date:<10} {r.preproc_amount:>8} "
            f"{preproc_info}"
        )

    # サマリー
    total = len(results)
    print("\n" + "=" * 100)
    print("サマリー")
    print("=" * 100)
    print(f"{'項目':<15} | {'ベースライン':>12} | {'前処理あり':>12} | {'差分':>8}")
    print("-" * 60)

    for key in ['vendor', 'date', 'amount', 'invoice']:
        b = baseline_scores[key]
        p = preproc_scores[key]
        diff = p - b
        label = {'vendor': '取引先', 'date': '日付', 'amount': '金額', 'invoice': '登録番号'}[key]
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"{label:<15} | {b:>10}/{total} | {p:>10}/{total} | {diff_str:>8}")

    print()
    if improved:
        print(f"改善: {len(improved)}件")
        for f in improved[:5]:
            print(f"  - {f}")
    if degraded:
        print(f"悪化: {len(degraded)}件")
        for f in degraded[:5]:
            print(f"  - {f}")


def main():
    """メイン"""
    setup_logger("ocr_ab_test")

    sample_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\sample PDF")
    output_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data\ab_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 問題がありそうなPDFを優先テスト（少数でまずテスト）
    priority_files = [
        "(株)ニトリ.pdf",
        "東京インテリア家具.pdf",
        "0109セリア(百均)買物.pdf",
        "領収証2025.12.26.pdf",
        "doc06562520260108152210.pdf",
    ]

    pdf_files = []
    for name in priority_files:
        path = sample_dir / name
        if path.exists():
            pdf_files.append(path)

    if not pdf_files:
        print("テストファイルがありません")
        return

    print("=" * 100)
    print("OCR ABテスト - 前処理の効果検証")
    print(f"テスト対象: {len(pdf_files)}ファイル")
    print("=" * 100)

    results = run_ab_test(pdf_files, output_dir)
    print_results(results)


if __name__ == "__main__":
    main()
