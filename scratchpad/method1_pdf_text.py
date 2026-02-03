"""Method 1: PDF埋め込みテキスト抽出

テキスト埋め込みPDFはOCR不要。pymupdfで直接テキスト取得し、
parse_expense_data相当のロジックでamount/date/vendorを抽出。

Usage:
    from method1_pdf_text import process_pdf
    result = process_pdf("receipt.pdf")
"""
import os, sys, re, unicodedata
from pathlib import Path

# PyMuPDF
import fitz

# 既存のparse_expense_dataを再利用するためEasyOCRProcessorをインポート
TOOLS_DIR = r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools"
sys.path.insert(0, TOOLS_DIR)


# テキスト埋め込み判定の最小文字数
MIN_TEXT_CHARS = 30


def extract_text_from_pdf(pdf_path: str) -> tuple:
    """PDFからテキストを直接抽出（全ページ）。

    Returns:
        (text, is_text_pdf): テキストとテキスト埋め込みPDFかどうか
    """
    doc = fitz.open(pdf_path)
    all_text = []
    for page in doc:
        text = page.get_text("text")
        if text:
            all_text.append(text.strip())
    doc.close()

    combined = "\n".join(all_text)
    # NFKC正規化
    combined = unicodedata.normalize('NFKC', combined)

    # テキスト埋め込み判定: 日本語/英数字の実質文字数
    content_chars = re.sub(r'\s+', '', combined)
    is_text_pdf = len(content_chars) >= MIN_TEXT_CHARS

    return combined, is_text_pdf


def parse_expense_data_standalone(text: str) -> dict:
    """テキストから経費データを抽出（EasyOCRProcessorのparse_expense_dataと同等ロジック）。

    EasyOCRProcessor.parse_expense_dataを直接呼び出すとEasyOCR初期化が走るため、
    ここではparse_expense_dataのロジックだけを使用する。
    """
    # EasyOCRProcessorをインスタンス化せずにparse_expense_dataを呼ぶ
    # __new__でインスタンスだけ作り、__init__は呼ばない
    from pdf_ocr_easyocr import EasyOCRProcessor
    dummy = EasyOCRProcessor.__new__(EasyOCRProcessor)
    # loggerだけ設定
    from common.logger import get_logger
    dummy.logger = get_logger()

    return dummy.parse_expense_data(text)


def process_pdf(pdf_path: str) -> dict:
    """Method 1: PDF埋め込みテキストからデータ抽出。

    Returns:
        dict with keys: amount, issue_date, vendor_name, raw_text, confidence,
                        is_text_pdf, text_chars
    """
    pdf_path = str(pdf_path)
    text, is_text_pdf = extract_text_from_pdf(pdf_path)

    result = {
        "amount": 0,
        "issue_date": "",
        "vendor_name": "",
        "raw_text": text,
        "confidence": 0.0,
        "is_text_pdf": is_text_pdf,
        "text_chars": len(re.sub(r'\s+', '', text)),
    }

    if not is_text_pdf:
        # テキスト不足 → OCR必要
        result["confidence"] = 0.0
        return result

    # テキストからデータ抽出（parse_expense_dataと同じロジック）
    data = parse_expense_data_standalone(text)
    result["amount"] = data.get("amount", 0)
    result["issue_date"] = data.get("issue_date", "")
    result["vendor_name"] = data.get("vendor_name", "")
    result["invoice_number"] = data.get("invoice_number", "")

    # ファイル名からvendor/amount補完（EasyOCRProcessorのprocess_pdf内ロジックと同等）
    stem = Path(pdf_path).stem
    if stem.startswith('【') and '】' in stem:
        stem = stem.split('】', 1)[1]
    stem_clean = re.sub(r'【.*?】', '', stem)
    parts = stem_clean.split('_')

    # vendor from filename
    if len(parts) >= 1 and parts[0]:
        filename_vendor = parts[0]
        exclude_prefixes = ['東海インプル建設', '御請求書']
        is_numeric_start = re.match(r'^\d{4,}', filename_vendor)
        if (not filename_vendor.isdigit() and
            not is_numeric_start and
            not any(ep in filename_vendor for ep in exclude_prefixes)):
            legal_entities = ['株式会社', '有限会社', '合同会社', '一般社団法人', '一般財団法人',
                              '社会福祉法人', '医療法人', '社会保険労務士法人']
            ocr_has_legal = result["vendor_name"] and any(le in result["vendor_name"] for le in legal_entities)
            ocr_contains_filename = result["vendor_name"] and filename_vendor in result["vendor_name"]
            if ocr_has_legal and ocr_contains_filename:
                pass  # Keep OCR vendor (has legal entity)
            elif result["vendor_name"] and result["vendor_name"] != filename_vendor:
                result["vendor_name"] = filename_vendor
            elif not result["vendor_name"]:
                result["vendor_name"] = filename_vendor

    # amount from filename
    if len(parts) >= 3:
        amount_part = parts[2].strip()
        if not re.match(r'^\d{8}$', amount_part):
            amount_part_clean = amount_part.replace(',', '')
            amount_match = re.match(r'^(\d+)', amount_part_clean)
            if amount_match:
                filename_amount = int(amount_match.group(1))
                if filename_amount > 0:
                    if result["amount"] > 0 and result["amount"] != filename_amount:
                        ratio = result["amount"] / filename_amount
                        is_tax_inclusive = (abs(ratio - 1.10) < 0.015 or abs(ratio - 1.08) < 0.015)
                        if not is_tax_inclusive:
                            result["amount"] = filename_amount
                    elif result["amount"] == 0:
                        result["amount"] = filename_amount

    # Confidence: based on how many fields we extracted
    filled = sum([
        bool(result["amount"] > 0),
        bool(result["issue_date"]),
        bool(result["vendor_name"]),
    ])
    result["confidence"] = filled / 3.0

    return result


# ── CLI test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, glob, json

    parser = argparse.ArgumentParser(description="Method 1: PDF text extraction test")
    parser.add_argument("pdf", nargs="?", help="Single PDF to test")
    parser.add_argument("--scan", action="store_true", help="Scan all PDFs and report text/non-text split")
    args = parser.parse_args()

    PDF_DIR = r"C:\ProgramData\RK10\Tools\PDF-Rename-Tool\2025年12月支払依頼サンプルPDF"

    if args.scan:
        pdfs = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
        text_pdfs = 0
        scan_pdfs = 0
        for p in pdfs:
            text, is_text = extract_text_from_pdf(p)
            chars = len(re.sub(r'\s+', '', text))
            label = "TEXT" if is_text else "SCAN"
            if is_text:
                text_pdfs += 1
            else:
                scan_pdfs += 1
            print(f"[{label}] {chars:>5}chars  {os.path.basename(p)[:60]}")
        print(f"\nTotal: {len(pdfs)} PDFs, TEXT={text_pdfs}, SCAN={scan_pdfs}")
    elif args.pdf:
        result = process_pdf(args.pdf)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Usage: method1_pdf_text.py <pdf> or --scan")
