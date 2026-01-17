# -*- coding: utf-8 -*-
"""
OCRエンジン精度比較スクリプト（完全版）

Adobe PDF Services vs YomiToku の抽出精度を比較
"""
import sys
import io
from pathlib import Path

# Windows対応: UTF-8出力
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))

import fitz  # PyMuPDF
from common.logger import get_logger

# YomiToku
try:
    from pdf_ocr_yomitoku import YomiTokuOCRProcessor
    YOMITOKU_AVAILABLE = True
except ImportError:
    YOMITOKU_AVAILABLE = False

# Adobe PDF Services
try:
    from pdf_ocr import PDFOCRProcessor as AdobeOCRProcessor
    ADOBE_AVAILABLE = True
except ImportError:
    ADOBE_AVAILABLE = False

logger = get_logger()

# Adobe PDF Services OCR済みファイルのパス
ADOBE_OCR_OUTPUT = Path(r"C:\ProgramData\RK10\Tools\OCR-JA\output")

# 元PDFフォルダ
ORIGINAL_PDF_DIR = Path(r"c:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\data\MOCK_FAX")

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


def evaluate_extraction(result) -> dict:
    """抽出結果を評価"""
    score = 0
    details = {}

    if result.vendor_name:
        score += 1
        details["vendor"] = result.vendor_name
    else:
        details["vendor"] = "(なし)"

    if result.issue_date:
        score += 1
        details["date"] = result.issue_date
    else:
        details["date"] = "(なし)"

    if result.amount > 0:
        score += 1
        details["amount"] = result.amount
    else:
        details["amount"] = 0

    if result.invoice_number:
        score += 1
        details["invoice"] = result.invoice_number
    else:
        details["invoice"] = "(なし)"

    return {
        "score": score,
        "max_score": 4,
        "details": details,
        "success": score >= 2  # 2項目以上取れたら成功
    }


def main():
    print("=" * 100)
    print("OCRエンジン精度比較 - Adobe PDF Services vs YomiToku")
    print("=" * 100)

    if not YOMITOKU_AVAILABLE:
        print("[WARNING] YomiTokuがインポートできません")
    if not ADOBE_AVAILABLE:
        print("[WARNING] Adobe PDF Servicesがインポートできません")

    adobe_results = []
    yomitoku_results = []

    # YomiTokuプロセッサ初期化
    yomitoku_proc = None
    if YOMITOKU_AVAILABLE:
        try:
            yomitoku_proc = YomiTokuOCRProcessor()
        except Exception as e:
            print(f"[ERROR] YomiToku初期化エラー: {e}")

    for name in TEST_FILES:
        print(f"\n{'─' * 80}")
        print(f"ファイル: {name}")
        print(f"{'─' * 80}")

        # 元PDFを探す
        original_pdf = ORIGINAL_PDF_DIR / f"{name}.pdf"
        if not original_pdf.exists():
            print(f"  [!] 元PDFが見つかりません: {original_pdf}")
            continue

        # === Adobe PDF Services (既にOCR済みのファイルから抽出) ===
        ocr_file = ADOBE_OCR_OUTPUT / f"{name}_ocr.pdf"
        if not ocr_file.exists():
            ocr_file = ADOBE_OCR_OUTPUT / f"v2_{name}_ocr.pdf"

        adobe_eval = None
        if ocr_file.exists():
            # OCR済みPDFからテキスト抽出してパース
            text = extract_text_from_pdf(ocr_file)

            # Adobe OCRプロセッサでパース
            if ADOBE_AVAILABLE:
                try:
                    adobe_proc = AdobeOCRProcessor()
                    # テキストからデータを抽出（parse_invoice_dataを使用）
                    result = adobe_proc.parse_invoice_data(text)
                    adobe_eval = evaluate_extraction(result)

                    print(f"  [Adobe PDF Services]")
                    print(f"    取引先: {adobe_eval['details']['vendor']}")
                    print(f"    日付:   {adobe_eval['details']['date']}")
                    print(f"    金額:   {adobe_eval['details']['amount']}")
                    print(f"    登録番号: {adobe_eval['details']['invoice']}")
                    print(f"    スコア: {adobe_eval['score']}/{adobe_eval['max_score']} {'OK' if adobe_eval['success'] else 'NG'}")
                except Exception as e:
                    print(f"  [Adobe PDF Services] エラー: {e}")
        else:
            print(f"  [Adobe PDF Services] OCR済みファイルなし")

        adobe_results.append({"name": name, "eval": adobe_eval})

        # === YomiToku ===
        yomitoku_eval = None
        if yomitoku_proc:
            try:
                result = yomitoku_proc.process_pdf(original_pdf)
                yomitoku_eval = evaluate_extraction(result)

                print(f"  [YomiToku]")
                print(f"    取引先: {yomitoku_eval['details']['vendor']}")
                print(f"    日付:   {yomitoku_eval['details']['date']}")
                print(f"    金額:   {yomitoku_eval['details']['amount']}")
                print(f"    登録番号: {yomitoku_eval['details']['invoice']}")
                print(f"    スコア: {yomitoku_eval['score']}/{yomitoku_eval['max_score']} {'OK' if yomitoku_eval['success'] else 'NG'}")
            except Exception as e:
                print(f"  [YomiToku] エラー: {e}")
        else:
            print(f"  [YomiToku] 利用不可")

        yomitoku_results.append({"name": name, "eval": yomitoku_eval})

    # サマリー
    print("\n" + "=" * 100)
    print("サマリー")
    print("=" * 100)

    adobe_success = sum(1 for r in adobe_results if r["eval"] and r["eval"]["success"])
    adobe_total = sum(1 for r in adobe_results if r["eval"])

    yomitoku_success = sum(1 for r in yomitoku_results if r["eval"] and r["eval"]["success"])
    yomitoku_total = sum(1 for r in yomitoku_results if r["eval"])

    print(f"\nAdobe PDF Services: {adobe_success}/{adobe_total} ({100*adobe_success/adobe_total:.1f}%)" if adobe_total > 0 else "Adobe: N/A")
    print(f"YomiToku: {yomitoku_success}/{yomitoku_total} ({100*yomitoku_success/yomitoku_total:.1f}%)" if yomitoku_total > 0 else "YomiToku: N/A")

    # 詳細比較テーブル
    print("\n" + "─" * 100)
    print(f"{'ファイル名':<40} {'Adobe':^15} {'YomiToku':^15} {'勝者':^15}")
    print("─" * 100)

    for i, name in enumerate(TEST_FILES):
        adobe_eval = adobe_results[i]["eval"] if i < len(adobe_results) else None
        yomitoku_eval = yomitoku_results[i]["eval"] if i < len(yomitoku_results) else None

        adobe_score = adobe_eval["score"] if adobe_eval else 0
        yomitoku_score = yomitoku_eval["score"] if yomitoku_eval else 0

        if adobe_score > yomitoku_score:
            winner = "Adobe"
        elif yomitoku_score > adobe_score:
            winner = "YomiToku"
        else:
            winner = "引き分け"

        adobe_str = f"{adobe_score}/4" if adobe_eval else "N/A"
        yomitoku_str = f"{yomitoku_score}/4" if yomitoku_eval else "N/A"

        print(f"{name:<40} {adobe_str:^15} {yomitoku_str:^15} {winner:^15}")

    print("─" * 100)

    # 結論
    print("\n" + "=" * 100)
    print("結論")
    print("=" * 100)
    if adobe_total > 0 and yomitoku_total > 0:
        adobe_rate = adobe_success / adobe_total
        yomitoku_rate = yomitoku_success / yomitoku_total

        if adobe_rate > yomitoku_rate:
            print(f">> Adobe PDF Services の精度が高い ({adobe_rate*100:.1f}% vs {yomitoku_rate*100:.1f}%)")
            print(">> 推奨: Adobe PDF Services をメインOCRとして使用")
        elif yomitoku_rate > adobe_rate:
            print(f">> YomiToku の精度が高い ({yomitoku_rate*100:.1f}% vs {adobe_rate*100:.1f}%)")
            print(">> 推奨: YomiToku をメインOCRとして使用")
        else:
            print(f">> 両者同等の精度 ({adobe_rate*100:.1f}%)")
            print(">> 推奨: コスト面でYomiToku（ローカル）を優先、失敗時はAdobe PDF Servicesでフォールバック")


if __name__ == "__main__":
    main()
