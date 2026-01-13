# -*- coding: utf-8 -*-
"""
全テストPDFのOCR抽出テスト
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding='utf-8')

from common.logger import setup_logger
from pdf_ocr import PDFOCRProcessor

# テストデータ（期待値）
EXPECTED = [
    ("20251117183719001.pdf", "ソニービズネットワークス株式会社", "20241107", 22803, "T1010701026820"),
    ("20251117183719002.pdf", "株式会社三菱UFJ銀行", "20241115", 7612, "T8010001008346"),
    ("20251117183719003.pdf", "エヌ・ティ・ティ・スマートコネクト株式会社", "20241110", 26400, ""),
    ("20251117183719004.pdf", "ラディックス株式会社", "20241108", 4045, "T5010001089333"),
    ("20251117183719005.pdf", "税理士法人TFC", "20241120", 104500, "T3180005006900"),
    ("20251117183719006.pdf", "東海スマート企業グループ株式会社", "20241105", 2970, "T8180301014312"),
    ("20251117183719007.pdf", "東海スマート企業グループ株式会社", "20241112", 2488420, "T8180301014312"),
    ("20251117183719008.pdf", "東海スマート企業グループ株式会社", "20241118", 28432, "T8180301014312"),
    ("20251117183719009.pdf", "刈谷税務署", "20241125", 14600, ""),
    ("20251117183719010.pdf", "楽天市場(マンツウオンラインショップ)", "20241103", 10768, ""),
    ("20251117183719011.pdf", "楽天市場(花の専門店 行きつけのお花屋さん)", "20241122", 3998, "T6013201013227"),
]

def main():
    setup_logger("test_ocr")
    processor = PDFOCRProcessor()

    pdf_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data\MOCK_FAX")

    print("=" * 80)
    print("OCR抽出テスト")
    print("=" * 80)

    success = 0
    failed = 0

    for filename, exp_vendor, exp_date, exp_amount, exp_invoice in EXPECTED:
        pdf_path = pdf_dir / filename
        result = processor.process_pdf(pdf_path, skip_ocr=True)

        # 検証
        vendor_ok = exp_vendor in result.vendor_name or result.vendor_name in exp_vendor
        date_ok = result.issue_date == exp_date
        amount_ok = result.amount == exp_amount
        invoice_ok = result.invoice_number == exp_invoice or (not exp_invoice and not result.invoice_number)

        all_ok = vendor_ok and date_ok and amount_ok and invoice_ok

        status = "OK" if all_ok else "NG"
        if all_ok:
            success += 1
        else:
            failed += 1

        print(f"\n[{status}] {filename}")
        print(f"  取引先: {result.vendor_name}")
        if not vendor_ok:
            print(f"    期待値: {exp_vendor}")
        print(f"  日付: {result.issue_date} {'OK' if date_ok else f'NG (期待: {exp_date})'}")
        print(f"  金額: {result.amount:,} {'OK' if amount_ok else f'NG (期待: {exp_amount:,})'}")
        print(f"  登録番号: {result.invoice_number} {'OK' if invoice_ok else f'NG (期待: {exp_invoice})'}")

    print("\n" + "=" * 80)
    print(f"結果: {success}/{len(EXPECTED)} 成功, {failed} 失敗")
    print("=" * 80)

if __name__ == "__main__":
    main()
