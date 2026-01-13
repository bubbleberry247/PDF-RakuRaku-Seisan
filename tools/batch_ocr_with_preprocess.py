# -*- coding: utf-8 -*-
"""
全PDFを前処理付きでOCR実行し、成功率を検証

1. 全サンプルPDFに前処理（回転補正）を適用
2. Adobe PDF Services API (OCR-JA) でOCR
3. 結果を抽出して成功率を計算
"""
import sys
import shutil
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding='utf-8')

from common.logger import setup_logger, get_logger
from pdf_ocr import PDFOCRProcessor
from pdf_preprocess import PDFPreprocessor


def batch_ocr_all_pdfs():
    """全PDFを前処理付きでOCR"""
    setup_logger("batch_ocr")
    logger = get_logger()

    sample_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\sample PDF")
    preproc_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data\batch_preproc")
    preproc_dir.mkdir(parents=True, exist_ok=True)

    preprocessor = PDFPreprocessor(dpi=200)
    ocr_processor = PDFOCRProcessor()

    # 全PDFを取得
    pdf_files = sorted(sample_dir.glob("*.pdf"))

    print("=" * 90)
    print(f"バッチOCR処理: 前処理（回転補正）+ Adobe PDF Services API")
    print(f"対象: {len(pdf_files)}ファイル")
    print("=" * 90)

    results = []

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] {pdf_path.name}")

        try:
            # 1. 前処理（回転補正）
            preproc_result = preprocessor.preprocess(
                pdf_path,
                preproc_dir,
                do_deskew=False,  # 傾き補正は今回スキップ（回転のみ）
                skew_threshold=2.0
            )

            if preproc_result.rotated:
                print(f"  → 回転補正: {preproc_result.rotation_angle}度")

            # 2. OCR実行（前処理済みPDFを使用）
            if preproc_result.rotated:
                # 前処理済みPDFをOCR-JAのinputにコピー
                ocr_input = ocr_processor.input_dir / pdf_path.name
                shutil.copy2(preproc_result.output_path, ocr_input)

                # OCR実行
                ocr_output = ocr_processor.run_ocr(pdf_path)

                if ocr_output:
                    # OCR済みPDFからテキスト抽出→データ抽出
                    text = ocr_processor.extract_text(ocr_output)
                    extract_result = ocr_processor.parse_invoice_data(text)

                    # ファイル名からの補完
                    filename_info = ocr_processor.extract_from_filename(pdf_path.name)
                    if not extract_result.vendor_name and filename_info['vendor']:
                        extract_result.vendor_name = filename_info['vendor']
                    if not extract_result.issue_date and filename_info['date']:
                        extract_result.issue_date = filename_info['date']
                    if extract_result.amount == 0 and filename_info['amount'] > 0:
                        extract_result.amount = filename_info['amount']

                    if extract_result.vendor_name or extract_result.amount > 0:
                        extract_result.success = True

                    results.append({
                        'name': pdf_path.name,
                        'vendor': extract_result.vendor_name,
                        'date': extract_result.issue_date,
                        'amount': extract_result.amount,
                        'invoice': extract_result.invoice_number,
                        'success': extract_result.success,
                        'rotated': True,
                    })
                    print(f"  → OCR成功: vendor={extract_result.vendor_name}, date={extract_result.issue_date}, amount={extract_result.amount}")
                else:
                    results.append({
                        'name': pdf_path.name,
                        'vendor': '',
                        'date': '',
                        'amount': 0,
                        'invoice': '',
                        'success': False,
                        'rotated': True,
                    })
                    print(f"  → OCR失敗")
            else:
                # 回転不要 = 既存のOCR結果を使用
                extract_result = ocr_processor.process_pdf(pdf_path, skip_ocr=True)
                results.append({
                    'name': pdf_path.name,
                    'vendor': extract_result.vendor_name,
                    'date': extract_result.issue_date,
                    'amount': extract_result.amount,
                    'invoice': extract_result.invoice_number,
                    'success': extract_result.success,
                    'rotated': False,
                })
                print(f"  → 既存OCR使用: vendor={extract_result.vendor_name}, date={extract_result.issue_date}, amount={extract_result.amount}")

        except Exception as e:
            logger.error(f"処理エラー: {pdf_path.name} - {e}")
            results.append({
                'name': pdf_path.name,
                'vendor': '',
                'date': '',
                'amount': 0,
                'invoice': '',
                'success': False,
                'rotated': False,
            })
            print(f"  → エラー: {e}")

    # 結果サマリー
    print("\n" + "=" * 90)
    print("結果サマリー")
    print("=" * 90)

    total = len(results)
    success_count = sum(1 for r in results if r['success'])
    vendor_count = sum(1 for r in results if r['vendor'])
    date_count = sum(1 for r in results if r['date'])
    amount_count = sum(1 for r in results if r['amount'] > 0)
    invoice_count = sum(1 for r in results if r['invoice'])
    rotated_count = sum(1 for r in results if r['rotated'])

    print(f"  総ファイル数:     {total}")
    print(f"  回転補正適用:     {rotated_count}")
    print(f"  成功（何か抽出）: {success_count}/{total} ({success_count/total*100:.0f}%)")
    print(f"  取引先抽出:       {vendor_count}/{total} ({vendor_count/total*100:.0f}%)")
    print(f"  日付抽出:         {date_count}/{total} ({date_count/total*100:.0f}%)")
    print(f"  金額抽出:         {amount_count}/{total} ({amount_count/total*100:.0f}%)")
    print(f"  登録番号抽出:     {invoice_count}/{total} ({invoice_count/total*100:.0f}%)")

    return results


if __name__ == "__main__":
    batch_ocr_all_pdfs()
