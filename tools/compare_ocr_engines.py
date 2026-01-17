# -*- coding: utf-8 -*-
"""
OCRエンジン精度比較スクリプト

Adobe PDF Services vs YomiToku vs Adobe Acrobat Pro
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz  # PyMuPDF
from common.logger import get_logger

logger = get_logger()

# Adobe PDF Services OCR済みファイルのパス
ADOBE_OCR_OUTPUT = Path(r"C:\ProgramData\RK10\Tools\OCR-JA\output")

# テスト対象ファイル（低信頼度だったファイル）
TEST_FILES = [
    "(株)ニトリ",
    "0109セリア(百均)買物",
    "2025,12,27名鉄協商400",
    "ごとう歯科打合せ駐車場代",
    "東京インテリア家具",
    "領収証2025.12.26",
    "鶴舞クリニック消防打合せ駐車場代",
]

# 元PDFフォルダ
ORIGINAL_PDF_DIR = Path(r"c:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\data\MOCK_FAX")


def extract_text_from_pdf(pdf_path: Path) -> str:
    """PDFからテキストを抽出"""
    try:
        doc = fitz.open(str(pdf_path))
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text.strip()
    except Exception as e:
        return f"Error: {e}"


def analyze_text_quality(text: str, filename: str) -> dict:
    """テキスト品質を分析"""
    import re

    result = {
        "char_count": len(text),
        "has_vendor": False,
        "has_date": False,
        "has_amount": False,
        "has_invoice": False,
    }

    # 取引先名（日本語が含まれているか）
    japanese_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+')
    if japanese_pattern.search(text):
        result["has_vendor"] = True

    # 日付パターン
    date_patterns = [
        r'\d{4}[年/\-\.]\d{1,2}[月/\-\.]\d{1,2}',
        r'\d{8}',
        r'令和\s*\d+\s*年',
    ]
    for pattern in date_patterns:
        if re.search(pattern, text):
            result["has_date"] = True
            break

    # 金額パターン
    amount_patterns = [
        r'¥[\d,]+',
        r'[\d,]+円',
        r'合計[^\d]*[\d,]+',
    ]
    for pattern in amount_patterns:
        if re.search(pattern, text):
            result["has_amount"] = True
            break

    # 登録番号パターン
    if re.search(r'T\d{13}', text):
        result["has_invoice"] = True

    return result


def main():
    # Windows対応: UTF-8出力に設定
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 80)
    print("OCRエンジン精度比較 - Adobe PDF Services OCR済みファイル分析")
    print("=" * 80)

    results = []

    for name in TEST_FILES:
        # Adobe OCR済みファイルを探す
        ocr_file = ADOBE_OCR_OUTPUT / f"{name}_ocr.pdf"
        if not ocr_file.exists():
            # v2_ プレフィックス版を試す
            ocr_file = ADOBE_OCR_OUTPUT / f"v2_{name}_ocr.pdf"
        if not ocr_file.exists():
            # preproc_ プレフィックス版を試す
            ocr_file = ADOBE_OCR_OUTPUT / f"preproc_{name}_ocr.pdf"

        print(f"\n{'─' * 60}")
        print(f"ファイル: {name}")

        if ocr_file.exists():
            text = extract_text_from_pdf(ocr_file)
            quality = analyze_text_quality(text, name)

            print(f"  Adobe OCR済み: {ocr_file.name}")
            print(f"  文字数: {quality['char_count']}")
            print(f"  取引先: {'✓' if quality['has_vendor'] else '✗'}")
            print(f"  日付:   {'✓' if quality['has_date'] else '✗'}")
            print(f"  金額:   {'✓' if quality['has_amount'] else '✗'}")
            print(f"  登録番号: {'✓' if quality['has_invoice'] else '✗'}")

            # 抽出されたテキストの一部を表示
            preview = text[:200].replace('\n', ' ') if text else "(empty)"
            print(f"  テキストプレビュー: {preview}...")

            results.append({
                "name": name,
                "ocr_file": str(ocr_file),
                "quality": quality,
                "text_preview": text[:500] if text else ""
            })
        else:
            print(f"  [!] Adobe OCR済みファイルが見つかりません")
            results.append({
                "name": name,
                "ocr_file": None,
                "quality": None,
                "text_preview": ""
            })

    # サマリー
    print("\n" + "=" * 80)
    print("サマリー")
    print("=" * 80)

    success_count = 0
    for r in results:
        if r["quality"]:
            q = r["quality"]
            fields_ok = sum([q["has_vendor"], q["has_date"], q["has_amount"]])
            if fields_ok >= 2:
                success_count += 1
                status = "✓ 成功"
            else:
                status = "✗ 失敗"
        else:
            status = "- 未処理"
        print(f"  {r['name']}: {status}")

    total = len(results)
    processed = sum(1 for r in results if r["quality"])
    print(f"\n処理済み: {processed}/{total}")
    print(f"成功率: {success_count}/{processed} ({100*success_count/processed:.1f}%)" if processed > 0 else "N/A")


if __name__ == "__main__":
    main()
