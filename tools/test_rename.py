# -*- coding: utf-8 -*-
"""
リネーム処理テスト（自動モードをシミュレート）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding='utf-8')

from common.config_loader import load_config
from common.logger import setup_logger, get_logger
from pdf_ocr import PDFOCRProcessor
from pdf_renamer import PDFRenamer, PDFInfo

def main():
    setup_logger("test_rename")
    logger = get_logger()

    config = load_config()
    renamer = PDFRenamer(config)
    processor = PDFOCRProcessor()

    pdfs = renamer.get_pdf_list()

    print("=" * 80)
    print("リネーム処理テスト")
    print("=" * 80)
    print(f"対象: {len(pdfs)}件")
    print("-" * 80)

    results = []
    for i, pdf_path in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] {pdf_path.name}")

        # OCR/テキスト抽出
        ocr_result = processor.process_pdf(pdf_path, skip_ocr=True)

        if not ocr_result.success:
            print(f"  抽出失敗: {ocr_result.error}")
            continue

        print(f"  取引先: {ocr_result.vendor_name}")
        print(f"  日付: {ocr_result.issue_date}")
        print(f"  金額: {ocr_result.amount:,}円")

        # リネーム後ファイル名を計算
        info = PDFInfo(
            original_path=pdf_path,
            vendor_name=ocr_result.vendor_name,
            issue_date=ocr_result.issue_date,
            amount=ocr_result.amount,
            invoice_number=ocr_result.invoice_number
        )

        new_filename = info.new_filename
        print(f"  新ファイル名: {new_filename}")
        results.append((pdf_path.name, new_filename))

    print("\n" + "=" * 80)
    print("リネーム結果サマリー")
    print("=" * 80)
    for old, new in results:
        print(f"  {old}")
        print(f"    -> {new}")
    print("-" * 80)
    print(f"完了: {len(results)}件")

if __name__ == "__main__":
    main()
