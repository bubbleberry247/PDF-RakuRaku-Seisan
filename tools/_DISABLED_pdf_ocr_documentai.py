# -*- coding: utf-8 -*-
"""
PDF OCR処理モジュール（Document AI版）

Google Document AI Expense Parserを使用してPDFから経費データを抽出

Usage:
    from pdf_ocr_documentai import DocumentAIOCRProcessor

    processor = DocumentAIOCRProcessor()
    result = processor.process_pdf("receipt.pdf")
    print(result)
    # {'vendor_name': 'セリア',
    #  'issue_date': '20260105',
    #  'amount': 330,
    #  'invoice_number': 'T4200001013662'}
"""
import os
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List

# Google Cloud Document AI
try:
    from google.cloud import documentai_v1 as documentai
    from google.api_core.client_options import ClientOptions
    DOCUMENTAI_AVAILABLE = True
except ImportError:
    DOCUMENTAI_AVAILABLE = False

# 共通モジュール
sys.path.insert(0, str(Path(__file__).parent))
from common.logger import get_logger


# ===========================================
# Document AI 設定
# ===========================================
PROJECT_ID = "robotic-catwalk-464100-m3"
LOCATION = "us"
PROCESSOR_ID = "2b0290fe788d2b94"
CREDENTIALS_PATH = r"C:\Users\masam\Desktop\AI\robotic-catwalk-464100-m3-8078ccd716ce.json"


@dataclass
class PDFExtractResult:
    """PDF抽出結果"""
    vendor_name: str = ""
    issue_date: str = ""  # YYYYMMDD
    amount: int = 0
    invoice_number: str = ""  # 事業者登録番号
    raw_text: str = ""  # 抽出した生テキスト
    confidence: float = 0.0  # 信頼度
    success: bool = False
    error: str = ""


class DocumentAIOCRProcessor:
    """Document AI OCR処理クラス"""

    def __init__(self):
        self.logger = get_logger()

        if not DOCUMENTAI_AVAILABLE:
            raise ImportError(
                "google-cloud-documentaiがインストールされていません: "
                "pip install google-cloud-documentai"
            )

        # 認証情報を設定
        if os.path.exists(CREDENTIALS_PATH):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH
        else:
            raise FileNotFoundError(f"認証ファイルが見つかりません: {CREDENTIALS_PATH}")

    def process_document(self, file_path: Path) -> documentai.Document:
        """Document AI でPDFを処理

        Args:
            file_path: PDFファイルパス

        Returns:
            Document AIのDocumentオブジェクト
        """
        # クライアントオプション設定
        opts = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
        client = documentai.DocumentProcessorServiceClient(client_options=opts)

        # プロセッサのフルパス
        name = client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

        # PDFファイルを読み込み
        with open(file_path, "rb") as f:
            pdf_content = f.read()

        # MIMEタイプを判定
        suffix = Path(file_path).suffix.lower()
        mime_types = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
            '.gif': 'image/gif',
        }
        mime_type = mime_types.get(suffix, 'application/pdf')

        # リクエスト作成
        raw_document = documentai.RawDocument(content=pdf_content, mime_type=mime_type)
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)

        # 処理実行
        self.logger.info(f"Document AI処理開始: {file_path.name}")
        result = client.process_document(request=request)
        self.logger.info(f"Document AI処理完了: {file_path.name}")

        return result.document

    def extract_expense_data(self, document: documentai.Document) -> dict:
        """Expense Parser の結果から経費データを抽出

        Args:
            document: Document AIのDocumentオブジェクト

        Returns:
            抽出データの辞書
        """
        expense_data = {
            "full_text": document.text,
            "entities": [],
            "total_amount": None,
            "total_amount_confidence": 0.0,
            "supplier_name": None,
            "supplier_name_confidence": 0.0,
            "receipt_date": None,
            "receipt_date_confidence": 0.0,
            "invoice_number": None,
            "line_items": []
        }

        for entity in document.entities:
            entity_info = {
                "type": entity.type_,
                "mention_text": entity.mention_text,
                "confidence": entity.confidence
            }
            expense_data["entities"].append(entity_info)

            # 主要フィールドを抽出
            if entity.type_ == "total_amount":
                expense_data["total_amount"] = entity.mention_text
                expense_data["total_amount_confidence"] = entity.confidence
            elif entity.type_ == "supplier_name":
                expense_data["supplier_name"] = entity.mention_text
                expense_data["supplier_name_confidence"] = entity.confidence
            elif entity.type_ == "receipt_date":
                expense_data["receipt_date"] = entity.mention_text
                expense_data["receipt_date_confidence"] = entity.confidence
            elif entity.type_ == "line_item":
                line_item = {"description": None, "amount": None}
                for prop in entity.properties:
                    if prop.type_ == "line_item/description":
                        line_item["description"] = prop.mention_text
                    elif prop.type_ == "line_item/amount":
                        line_item["amount"] = prop.mention_text
                expense_data["line_items"].append(line_item)

        # 事業者登録番号を全文から抽出
        invoice_patterns = [
            r'[TＴ][\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'登録番号[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
        ]
        for pattern in invoice_patterns:
            match = re.search(pattern, document.text)
            if match:
                raw_num = re.sub(r'[\s\-]', '', match.group(1))
                if len(raw_num) == 13 and raw_num.isdigit():
                    expense_data["invoice_number"] = f"T{raw_num}"
                    break

        return expense_data

    def parse_date(self, date_str: str) -> str:
        """日付文字列をYYYYMMDD形式に変換

        Args:
            date_str: Document AIが抽出した日付文字列

        Returns:
            YYYYMMDD形式の日付（変換失敗時は空文字）
        """
        if not date_str:
            return ""

        # 様々な形式に対応
        patterns = [
            # 2026年1月5日 / 2026年01月05日
            (r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
             lambda m: f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
            # 2026/1/5 / 2026/01/05
            (r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})',
             lambda m: f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
            # 令和8年1月5日
            (r'令和\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
             lambda m: f"{2018 + int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
            # R8/1/5 / R8.1.5
            (r'[RrＲ]\s*(\d{1,2})[/\.\-](\d{1,2})[/\.\-](\d{1,2})',
             lambda m: f"{2018 + int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
        ]

        for pattern, converter in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    return converter(match)
                except (ValueError, IndexError):
                    continue

        return ""

    def parse_amount(self, amount_str: str) -> int:
        """金額文字列を整数に変換

        Args:
            amount_str: Document AIが抽出した金額文字列

        Returns:
            金額（整数）
        """
        if not amount_str:
            return 0

        # 数字以外を除去
        clean = re.sub(r'[^\d]', '', amount_str)

        try:
            return int(clean)
        except ValueError:
            return 0

    def extract_from_filename(self, filename: str) -> dict:
        """ファイル名から情報を抽出（フォールバック用）

        Args:
            filename: ファイル名

        Returns:
            抽出情報の辞書
        """
        info = {'vendor': '', 'date': '', 'amount': 0}
        name = Path(filename).stem

        # 日付パターン: YYYY,MM,DD or YYYY.MM.DD
        date_match = re.search(r'(\d{4})[,\.](\d{1,2})[,\.](\d{1,2})', name)
        if date_match:
            year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            if 2000 <= year <= 2100:
                info['date'] = f"{year:04d}{month:02d}{day:02d}"

        # MMDDで始まるパターン
        if not info['date']:
            date_match = re.match(r'^(\d{2})(\d{2})', name)
            if date_match:
                month, day = int(date_match.group(1)), int(date_match.group(2))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    import datetime
                    current_year = datetime.datetime.now().year
                    info['date'] = f"{current_year:04d}{month:02d}{day:02d}"

        # 取引先パターン
        vendor_patterns = [
            (r'ニトリ', 'ニトリ'),
            (r'名鉄協商', '名鉄協商株式会社'),
            (r'セリア', 'セリア'),
            (r'東京インテリア', '東京インテリア家具'),
            (r'日本郵便', '日本郵便株式会社'),
            (r'もち吉', 'もち吉'),
        ]
        for pattern, vendor_name in vendor_patterns:
            if re.search(pattern, name):
                info['vendor'] = vendor_name
                break

        return info

    def process_pdf(self, pdf_path: Path, skip_ocr: bool = False) -> PDFExtractResult:
        """PDFを処理してデータを抽出

        Args:
            pdf_path: 入力PDFパス
            skip_ocr: 未使用（互換性のため残す）

        Returns:
            抽出結果
        """
        pdf_path = Path(pdf_path)
        result = PDFExtractResult()

        if not pdf_path.exists():
            result.error = f"ファイルが存在しません: {pdf_path}"
            return result

        try:
            # Document AI で処理
            document = self.process_document(pdf_path)

            # 経費データを抽出
            expense_data = self.extract_expense_data(document)

            # 結果を設定
            result.raw_text = expense_data["full_text"]
            result.vendor_name = expense_data["supplier_name"] or ""
            result.issue_date = self.parse_date(expense_data["receipt_date"])
            result.amount = self.parse_amount(expense_data["total_amount"])
            result.invoice_number = expense_data["invoice_number"] or ""
            result.confidence = expense_data["total_amount_confidence"]

            # ファイル名からフォールバック補完
            filename_info = self.extract_from_filename(pdf_path.name)
            if not result.vendor_name and filename_info['vendor']:
                result.vendor_name = filename_info['vendor']
                self.logger.info(f"ファイル名から取引先補完: {result.vendor_name}")
            if not result.issue_date and filename_info['date']:
                result.issue_date = filename_info['date']
                self.logger.info(f"ファイル名から日付補完: {result.issue_date}")

            # 成功判定
            if result.vendor_name or result.amount > 0 or result.issue_date:
                result.success = True
            else:
                result.error = "データを抽出できませんでした"

            self.logger.info(
                f"抽出結果: vendor={result.vendor_name}, "
                f"date={result.issue_date}, amount={result.amount}, "
                f"invoice={result.invoice_number}, confidence={result.confidence:.2f}"
            )

        except Exception as e:
            result.error = str(e)
            self.logger.error(f"Document AI処理エラー: {e}")
            import traceback
            traceback.print_exc()

        return result


# エイリアス（既存コードとの互換性のため）
PDFOCRProcessor = DocumentAIOCRProcessor


def main():
    """テスト実行"""
    import argparse

    parser = argparse.ArgumentParser(description="PDF OCR処理（Document AI版）")
    parser.add_argument("pdf", help="PDFファイルパス")

    args = parser.parse_args()

    # ロガー設定
    from common.logger import setup_logger
    setup_logger("pdf_ocr_documentai")

    processor = DocumentAIOCRProcessor()
    result = processor.process_pdf(Path(args.pdf))

    print("\n=== 抽出結果 ===")
    print(f"取引先名: {result.vendor_name}")
    print(f"発行日: {result.issue_date}")
    print(f"金額: {result.amount:,}円" if result.amount else "金額: -")
    print(f"事業者登録番号: {result.invoice_number}")
    print(f"信頼度: {result.confidence:.2%}")
    print(f"成功: {result.success}")
    if result.error:
        print(f"エラー: {result.error}")


if __name__ == "__main__":
    main()
