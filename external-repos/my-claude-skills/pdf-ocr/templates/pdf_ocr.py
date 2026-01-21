# -*- coding: utf-8 -*-
"""
PDF OCR処理モジュール（テンプレート版）

PDFからテキストを抽出して取引先名・日付・金額を取得する

Usage:
    from pdf_ocr import PDFOCRProcessor, PDFExtractResult

    processor = PDFOCRProcessor()
    result = processor.process_pdf("invoice.pdf")
    print(result)
    # {'vendor_name': '株式会社サンプル',
    #  'issue_date': '20251107',
    #  'amount': 22803,
    #  'invoice_number': 'T1010701026820'}
"""
import re
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# PyMuPDFでテキスト抽出
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


# ロガー（プロジェクトに合わせて変更）
def get_logger():
    return logging.getLogger(__name__)


@dataclass
class PDFExtractResult:
    """PDF抽出結果"""
    vendor_name: str = ""
    issue_date: str = ""  # YYYYMMDD
    amount: int = 0
    invoice_number: str = ""  # 事業者登録番号
    raw_text: str = ""  # 抽出した生テキスト
    success: bool = False
    error: str = ""


class PDFOCRProcessor:
    """PDF OCR処理クラス"""

    def __init__(self):
        self.logger = get_logger()

    def extract_text(self, pdf_path: Path) -> str:
        """PDFからテキストを抽出"""
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDFがインストールされていません: pip install PyMuPDF")

        text = ""
        try:
            doc = fitz.open(str(pdf_path))
            for page in doc:
                text += page.get_text()
            doc.close()
        except Exception as e:
            self.logger.error(f"テキスト抽出エラー: {e}")

        return text

    def normalize_cjk(self, text: str) -> str:
        """CJK互換漢字を通常の漢字に正規化"""
        replacements = {
            '\u2F46': '日',
            '\u2F51': '日',
            '\u2F49': '月',
            '\u2F4B': '年',
            '⽇': '日',
            '⽉': '月',
            '⾦': '金',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def reiwa_to_seireki(self, reiwa_year: int) -> int:
        """令和年を西暦に変換 (令和1年 = 2019年)"""
        return 2018 + reiwa_year

    def parse_invoice_data(self, text: str) -> PDFExtractResult:
        """テキストから請求書データを抽出"""
        result = PDFExtractResult(raw_text=text)

        if not text.strip():
            result.error = "テキストが空です"
            return result

        # CJK互換漢字を正規化
        text = self.normalize_cjk(text)

        # --- 事業者登録番号を抽出 ---
        invoice_patterns = [
            r'[TＴ][\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'登録番号[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'インボイス[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
        ]
        for pattern in invoice_patterns:
            match = re.search(pattern, text)
            if match:
                raw_num = re.sub(r'[\s\-]', '', match.group(1))
                if len(raw_num) == 13 and raw_num.isdigit():
                    result.invoice_number = f"T{raw_num}"
                    break

        # --- 金額を抽出 ---
        # OCR誤認識のクリーニング
        cleaned_text = text
        cleaned_text = re.sub(r'[¥￥\\]\s*(\d)\s+(\d)\s+([0a-zA-Z])',
                              lambda m: '¥' + m.group(1) + m.group(2) + ('0' if m.group(3).lower() in ['o', 'a'] else m.group(3)),
                              cleaned_text)
        cleaned_text = re.sub(r'([¥￥\\][\d,]+),\s+(\d)', r'\1,\2', cleaned_text)
        cleaned_text = re.sub(r'(\d)\s+(\d{3})\s*[-\-ー円]', r'\1\2', cleaned_text)

        amount_patterns = [
            r'合計[金額]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?',
            r'請求金額[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?',
            r'ご請求額[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?',
            r'税込[金額合計]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?',
            r'[¥\\￥]\s*([\d,，\.]+)\s*[-\-ー]*',
            r'([\d,，\.]+)\s*円',
            r'[¥￥\\]([\d,，\.]+)',
            r'現計[:\s：]*[¥\\￥]?\s*([\d,，\.]+)',
            r'通行料金[:\s：]*[¥\\￥]?\s*([\d,，\.]+)',
            r'駐車料金[:\s：（(]*[一般]*[）):\s：]*\s*([\d,，\.]+)',
            r'クレジット支払[:\s：]*\s*([\d,，\.]+)',
            r'料金計[:\s：]*\s*([\d,，\.]+)',
            r'小計[:\s：]*[¥\\￥]?\s*([\d,，\.]+)',
            r'支払[い]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)',
            r'お買[い]?上[げ]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)',
            r'領収[金額]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)',
        ]
        amounts = []
        for pattern in amount_patterns:
            matches = re.findall(pattern, cleaned_text, re.MULTILINE)
            for m in matches:
                try:
                    amount = int(re.sub(r'[,，\.]', '', m))
                    if amount >= 100:
                        amounts.append(amount)
                except ValueError:
                    pass

        if amounts:
            result.amount = max(amounts)

        # --- 日付を抽出 ---
        lines = text.split('\n')
        filtered_lines = [l for l in lines if not re.search(r'TEL|FAX|電話', l, re.IGNORECASE)]
        filtered_text = '\n'.join(filtered_lines)

        date_found = False

        # 「請求日」「発行日」ラベルの近くにある日付
        for i, line in enumerate(filtered_lines):
            if '請求日' in line or '発行日' in line:
                # 令和形式
                match = re.search(r'令和\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', line)
                if match:
                    year = self.reiwa_to_seireki(int(match.group(1)))
                    month, day = int(match.group(2)), int(match.group(3))
                    result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                    date_found = True
                    break

                # 西暦形式
                match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', line)
                if match:
                    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                    date_found = True
                    break

                # 次の行を確認
                for j in range(i+1, min(i+3, len(filtered_lines))):
                    next_line = filtered_lines[j].strip()
                    match = re.search(r'令和\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', next_line)
                    if match:
                        year = self.reiwa_to_seireki(int(match.group(1)))
                        month, day = int(match.group(2)), int(match.group(3))
                        result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                        date_found = True
                        break

                    match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', next_line)
                    if match:
                        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                        date_found = True
                        break
                if date_found:
                    break

        # 西暦年月日形式
        if not date_found:
            for match in re.finditer(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', filtered_text):
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                    date_found = True
                    break

        # YYYY/MM/DD形式
        if not date_found:
            for match in re.finditer(r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', filtered_text):
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                    date_found = True
                    break

        # 和暦短縮形式 / 西暦下2桁形式
        if not date_found:
            normalized_text = re.sub(r'[\r\n\s]+', ' ', text)
            for match in re.finditer(r'[Il1|]?(\d{1,2})\s*年\s+(\d{1,2})\s*月\s+(\d{1,2})\s*日', normalized_text):
                year_num, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    if 1 <= year_num <= 20:
                        year = self.reiwa_to_seireki(year_num)
                    else:
                        year = 2000 + year_num
                    result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                    date_found = True
                    break

        # R7/1/9形式（令和短縮）
        if not date_found:
            for match in re.finditer(r'[RrＲ]\s*(\d{1,2})[/\.\-](\d{1,2})[/\.\-](\d{1,2})', filtered_text):
                year_num, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 1 <= year_num <= 20 and 1 <= month <= 12 and 1 <= day <= 31:
                    year = self.reiwa_to_seireki(year_num)
                    result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                    break

        # --- 取引先名を抽出 ---
        lines = text.split('\n')
        company_patterns = [
            r'^((?:株式会社|有限会社|合同会社|一般社団法人|税理士法人).+)$',
            r'^(.+(?:株式会社|有限会社|合同会社|㈱|㈲))$',
            r'^(税理士法人.+)$',
            r'^(.+税務署)$',
            r'^([ァ-ヶー・a-zA-Z]+株式会社.*)$',
            r'^(.+店)$',
            r'^(.+パーキング.*)$',
        ]

        # 「御請求書」「請求書」の直前の会社名を探す
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if '請求書' in line_stripped or '御請求書' in line_stripped:
                for j in range(max(0, i-5), i):
                    prev_line = lines[j].strip()
                    if '御中' in prev_line:
                        continue
                    for pattern in company_patterns:
                        match = re.match(pattern, prev_line)
                        if match:
                            vendor = match.group(1).strip()
                            if len(vendor) >= 2:
                                result.vendor_name = vendor
                                break
                    if result.vendor_name:
                        break
                break

        # 最初に見つかる会社名
        if not result.vendor_name:
            for line in lines:
                line = line.strip()
                if '御中' in line:
                    continue
                for pattern in company_patterns:
                    match = re.match(pattern, line)
                    if match:
                        vendor = match.group(1).strip()
                        if len(vendor) >= 2:
                            result.vendor_name = vendor
                            break
                if result.vendor_name:
                    break

        # 特定キーワードから取引先を推定
        # ★ここをプロジェクトに合わせてカスタマイズ★
        if not result.vendor_name:
            special_vendors = [
                (r'オートバックス|AUTOBACS', 'オートバックス'),
                (r'セリア|Seria', 'セリア'),
                (r'ニトリ|NITORI', 'ニトリ'),
                (r'東京インテリア', '東京インテリア家具'),
                (r'ダイソー|DAISO', 'ダイソー'),
                (r'キャンドゥ|Can.*Do', 'キャンドゥ'),
                (r'ドン[・]?キホーテ|ドンキ', 'ドン・キホーテ'),
                (r'スギ薬局', 'スギ薬局'),
                (r'マツモトキヨシ', 'マツモトキヨシ'),
                (r'イオン|AEON', 'イオン'),
                (r'コメダ珈琲', 'コメダ珈琲'),
                (r'スターバックス|STARBUCKS', 'スターバックス'),
                (r'マクドナルド|McDonald', 'マクドナルド'),
                (r'ENEOS|エネオス', 'ENEOS'),
                (r'出光|idemitsu', '出光'),
                (r'セブン[−-]?イレブン|7-ELEVEN', 'セブン-イレブン'),
                (r'ファミリーマート|FamilyMart', 'ファミリーマート'),
                (r'ローソン|LAWSON', 'ローソン'),
                (r'タイムズ|Times', 'タイムズ'),
                (r'三井のリパーク', '三井のリパーク'),
            ]
            for pattern, vendor_name in special_vendors:
                if re.search(pattern, text, re.IGNORECASE):
                    result.vendor_name = vendor_name
                    break

        # 抽出成功判定
        if result.vendor_name or result.amount > 0:
            result.success = True
        else:
            result.error = "データを抽出できませんでした"

        return result

    def extract_from_filename(self, filename: str) -> dict:
        """ファイル名から情報を抽出（フォールバック用）"""
        info = {'vendor': '', 'date': '', 'amount': 0}
        name = Path(filename).stem

        # 日付パターン: YYYY,MM,DD or YYYY.MM.DD
        date_match = re.search(r'(\d{4})[,\.](\d{1,2})[,\.](\d{1,2})', name)
        if date_match:
            year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            if 2000 <= year <= 2100:
                info['date'] = f"{year:04d}{month:02d}{day:02d}"

        # MMDD形式
        if not info['date']:
            date_match = re.match(r'^(\d{2})(\d{2})', name)
            if date_match:
                month, day = int(date_match.group(1)), int(date_match.group(2))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    import datetime
                    current_year = datetime.datetime.now().year
                    info['date'] = f"{current_year:04d}{month:02d}{day:02d}"

        # YYYYMMDD形式
        if not info['date']:
            date_match = re.search(r'_(\d{4})(\d{2})(\d{2})_', name)
            if date_match:
                year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    info['date'] = f"{year:04d}{month:02d}{day:02d}"

        # 末尾のYYYYMMDD
        if not info['date']:
            date_match = re.search(r'(\d{4})(\d{2})(\d{2})\d*\.pdf$', filename, re.IGNORECASE)
            if date_match:
                year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    info['date'] = f"{year:04d}{month:02d}{day:02d}"

        # 金額パターン: 末尾の数字
        amount_match = re.search(r'(\d+)$', name)
        if amount_match:
            amount = int(amount_match.group(1))
            if 100 <= amount <= 1000000:
                info['amount'] = amount

        return info

    def process_pdf(self, pdf_path: Path, skip_ocr: bool = False) -> PDFExtractResult:
        """PDFを処理してデータを抽出"""
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            return PDFExtractResult(error=f"ファイルが存在しません: {pdf_path}")

        # テキスト抽出
        text = self.extract_text(pdf_path)

        # データ抽出
        result = self.parse_invoice_data(text)

        # OCR結果が不十分な場合、ファイル名から補完
        filename_info = self.extract_from_filename(pdf_path.name)
        if not result.vendor_name and filename_info['vendor']:
            result.vendor_name = filename_info['vendor']
            self.logger.info(f"ファイル名から取引先補完: {result.vendor_name}")
        if not result.issue_date and filename_info['date']:
            result.issue_date = filename_info['date']
            self.logger.info(f"ファイル名から日付補完: {result.issue_date}")
        if result.amount == 0 and filename_info['amount'] > 0:
            result.amount = filename_info['amount']
            self.logger.info(f"ファイル名から金額補完: {result.amount}")

        # 再判定
        if result.vendor_name or result.amount > 0:
            result.success = True

        self.logger.info(
            f"抽出結果: vendor={result.vendor_name}, date={result.issue_date}, "
            f"amount={result.amount}, invoice={result.invoice_number}"
        )

        return result


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="PDF OCR処理")
    parser.add_argument("pdf", help="PDFファイルパス")

    args = parser.parse_args()

    processor = PDFOCRProcessor()
    result = processor.process_pdf(Path(args.pdf))

    print("\n=== 抽出結果 ===")
    print(f"取引先名: {result.vendor_name}")
    print(f"発行日: {result.issue_date}")
    print(f"金額: {result.amount:,}円" if result.amount else "金額: -")
    print(f"事業者登録番号: {result.invoice_number}")
    print(f"成功: {result.success}")
    if result.error:
        print(f"エラー: {result.error}")
