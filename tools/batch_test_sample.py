# -*- coding: utf-8 -*-
"""
サンプルPDFバッチテスト
"""
import sys
import io
from pathlib import Path

# Windows対応: UTF-8出力
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))

from pdf_ocr_smart import SmartOCRProcessor, CONFIDENCE_THRESHOLD

SAMPLE_DIR = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\sample PDF")


def main():
    # 不明瞭PDFサブフォルダを除外してメインフォルダのPDFのみ取得
    # _preproc_で始まるファイルも除外（前処理済みファイル）
    pdf_files = [f for f in SAMPLE_DIR.glob("*.pdf") if f.is_file() and not f.name.startswith("_preproc_")]
    pdf_files.sort()

    print("=" * 120)
    print(f"サンプルPDFバッチテスト - {len(pdf_files)}ファイル")
    print(f"信頼度閾値: {CONFIDENCE_THRESHOLD}")
    print("=" * 120)

    processor = SmartOCRProcessor(use_gpu=False, lite_mode=True)

    results = []
    success_count = 0
    fail_count = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] {pdf_path.name}")

        try:
            result = processor.process(pdf_path, auto_queue=False)

            status = "OK" if result.success else "NG"
            ocr_engine = result.preprocess_info.get("ocr_engine", "yomitoku")

            if result.success:
                success_count += 1
            else:
                fail_count += 1

            results.append({
                "path": str(pdf_path),
                "name": pdf_path.name,
                "success": result.success,
                "confidence": result.confidence,
                "vendor": result.vendor_name,
                "date": result.issue_date,
                "amount": result.amount,
                "invoice": result.invoice_number,
                "engine": ocr_engine,
                "error": result.error
            })

            print(f"  [{status}] conf={result.confidence:.2f} engine={ocr_engine}")
            print(f"      vendor={result.vendor_name or '(なし)'}")
            print(f"      date={result.issue_date or '(なし)'}")
            print(f"      amount={result.amount}")
            print(f"      invoice={result.invoice_number or '(なし)'}")

        except Exception as e:
            fail_count += 1
            results.append({
                "path": str(pdf_path),
                "name": pdf_path.name,
                "success": False,
                "confidence": 0,
                "vendor": "",
                "date": "",
                "amount": 0,
                "invoice": "",
                "engine": "error",
                "error": str(e)
            })
            print(f"  [ERROR] {e}")

    # サマリー
    print("\n" + "=" * 120)
    print("サマリー")
    print("=" * 120)
    total = len(results)
    print(f"成功: {success_count}/{total} ({100*success_count/total:.1f}%)")
    print(f"失敗: {fail_count}/{total} ({100*fail_count/total:.1f}%)")

    # 失敗一覧
    failed = [r for r in results if not r["success"]]
    if failed:
        print("\n" + "=" * 120)
        print("失敗PDFの一覧")
        print("=" * 120)
        print(f"{'ファイル名':<50} {'信頼度':>8} {'取引先':<20} {'日付':<10} {'金額':>12} {'登録番号':<16}")
        print("-" * 120)
        for r in failed:
            print(f"{r['name']:<50} {r['confidence']:>8.2f} {r['vendor'] or '(なし)':<20} {r['date'] or '(なし)':<10} {r['amount']:>12} {r['invoice'] or '(なし)':<16}")
            print(f"  フルパス: {r['path']}")

    # 成功一覧
    succeeded = [r for r in results if r["success"]]
    if succeeded:
        print("\n" + "=" * 120)
        print("成功PDFの一覧")
        print("=" * 120)
        print(f"{'ファイル名':<50} {'信頼度':>8} {'取引先':<20} {'日付':<10} {'金額':>12} {'登録番号':<16} {'エンジン':<10}")
        print("-" * 120)
        for r in succeeded:
            print(f"{r['name']:<50} {r['confidence']:>8.2f} {r['vendor'] or '(なし)':<20} {r['date'] or '(なし)':<10} {r['amount']:>12} {r['invoice'] or '(なし)':<16} {r['engine']:<10}")


if __name__ == "__main__":
    main()
