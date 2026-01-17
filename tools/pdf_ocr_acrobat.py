# -*- coding: utf-8 -*-
"""
Adobe Acrobat Pro OCRモジュール

Acrobat DCのアクション機能を使用してOCR処理を行う
- 高精度な日本語OCR
- ローカル処理（API課金なし）
- バッチ処理対応

Usage:
    from pdf_ocr_acrobat import AcrobatOCRProcessor

    processor = AcrobatOCRProcessor()
    result = processor.process_pdf("input.pdf")
"""
import os
import sys
import shutil
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import re

sys.path.insert(0, str(Path(__file__).parent))

# PyMuPDFでテキスト抽出
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

from common.logger import get_logger


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


class AcrobatOCRProcessor:
    """Adobe Acrobat Pro OCR処理クラス"""

    # Acrobatのパス
    ACROBAT_PATH = Path(r"C:\Program Files (x86)\Adobe\Acrobat DC\Acrobat\Acrobat.exe")

    # OCR用フォルダ
    OCR_INPUT_DIR = Path(r"C:\OCR\input")
    OCR_OUTPUT_DIR = Path(r"C:\OCR\output")

    # アクション名
    ACTION_NAME = "searchable PDFへ変換"

    def __init__(self):
        self.logger = get_logger()

        # フォルダ作成
        self.OCR_INPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.OCR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Acrobatの確認
        if not self.ACROBAT_PATH.exists():
            raise FileNotFoundError(f"Adobe Acrobat DCが見つかりません: {self.ACROBAT_PATH}")

    def run_ocr(self, pdf_path: Path, timeout: int = 120) -> Optional[Path]:
        """
        AcrobatアクションでOCRを実行

        Args:
            pdf_path: 入力PDF
            timeout: タイムアウト秒数

        Returns:
            OCR済みPDFパス（失敗時はNone）
        """
        filename = pdf_path.name
        input_file = self.OCR_INPUT_DIR / filename
        output_file = self.OCR_OUTPUT_DIR / filename

        try:
            # 入力フォルダにコピー
            if pdf_path != input_file:
                shutil.copy2(pdf_path, input_file)

            # 既存の出力ファイルを削除
            if output_file.exists():
                output_file.unlink()

            # Acrobatアクションを実行
            # /A オプションでアクションを指定
            cmd = [
                str(self.ACROBAT_PATH),
                "/A", f'Workflow:{self.ACTION_NAME}',
                str(input_file)
            ]

            self.logger.info(f"Acrobat OCR開始: {filename}")

            # Acrobatプロセス起動
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False
            )

            # 出力ファイルが生成されるまで待機
            start_time = time.time()
            while not output_file.exists():
                if time.time() - start_time > timeout:
                    proc.kill()
                    self.logger.error(f"Acrobat OCRタイムアウト: {filename}")
                    return None
                time.sleep(1)

            # ファイルが書き込み完了するまで少し待機
            time.sleep(2)

            self.logger.info(f"Acrobat OCR完了: {filename}")
            return output_file

        except Exception as e:
            self.logger.error(f"Acrobat OCRエラー: {e}")
            return None
        finally:
            # 入力ファイルをクリーンアップ
            if input_file.exists() and input_file != pdf_path:
                try:
                    input_file.unlink()
                except:
                    pass

    def extract_text(self, pdf_path: Path) -> str:
        """PDFからテキストを抽出"""
        if not PYMUPDF_AVAILABLE:
            return ""

        try:
            doc = fitz.open(str(pdf_path))
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            self.logger.error(f"テキスト抽出エラー: {e}")
            return ""

    def parse_invoice_data(self, text: str, filename: str = "") -> PDFExtractResult:
        """OCRテキストから請求書データを抽出"""
        result = PDFExtractResult(raw_text=text)

        if not text.strip():
            result.error = "テキストが空"
            return result

        # 金額パターン
        amount_patterns = [
            r'[¥￥]\s*([0-9,]+)\s*[-－]',  # ¥1,234-
            r'合\s*計[^\d]*([0-9,]+)',     # 合計 1,234
            r'金\s*額[^\d]*([0-9,]+)',     # 金額 1,234
            r'([0-9,]+)\s*円',              # 1,234円
        ]

        for pattern in amount_patterns:
            match = re.search(pattern, text)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    result.amount = int(amount_str)
                    break
                except ValueError:
                    continue

        # 日付パターン
        date_patterns = [
            r'(\d{4})[年/.-](\d{1,2})[月/.-](\d{1,2})',  # 2026年1月15日
            r'(\d{4})(\d{2})(\d{2})',                      # 20260115
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                year, month, day = match.groups()
                result.issue_date = f"{year}{int(month):02d}{int(day):02d}"
                break

        # 登録番号パターン（T+13桁）
        invoice_match = re.search(r'[TＴ]\s*(\d{13})', text)
        if invoice_match:
            result.invoice_number = f"T{invoice_match.group(1)}"

        # 取引先パターン（株式会社など）
        vendor_patterns = [
            r'(株式会社[^\s\n]{2,20})',
            r'([^\s\n]{2,10}株式会社)',
            r'(有限会社[^\s\n]{2,20})',
        ]

        for pattern in vendor_patterns:
            match = re.search(pattern, text)
            if match:
                result.vendor_name = match.group(1).strip()
                break

        # ファイル名からの補完
        if not result.vendor_name and filename:
            # ファイル名から取引先を推測
            known_vendors = {
                'ニトリ': 'ニトリ',
                'セリア': 'セリア',
                '名鉄協商': '名鉄協商株式会社',
                '日本郵便': '日本郵便株式会社',
            }
            for key, vendor in known_vendors.items():
                if key in filename:
                    result.vendor_name = vendor
                    break

        result.success = bool(result.amount or result.vendor_name or result.issue_date)
        return result

    def process_pdf(self, pdf_path: Path) -> PDFExtractResult:
        """
        PDFをOCR処理してデータを抽出

        Args:
            pdf_path: 入力PDF

        Returns:
            抽出結果
        """
        pdf_path = Path(pdf_path)
        filename = pdf_path.name

        # OCR実行
        ocr_pdf = self.run_ocr(pdf_path)

        if ocr_pdf is None or not ocr_pdf.exists():
            return PDFExtractResult(error="OCR処理に失敗")

        # テキスト抽出
        text = self.extract_text(ocr_pdf)

        # データ解析
        result = self.parse_invoice_data(text, filename)

        return result


def test_acrobat_ocr():
    """テスト"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_ocr_acrobat.py <pdf_path>")
        return

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"ファイルが見つかりません: {pdf_path}")
        return

    processor = AcrobatOCRProcessor()
    result = processor.process_pdf(pdf_path)

    print(f"=== OCR結果: {pdf_path.name} ===")
    print(f"取引先: {result.vendor_name}")
    print(f"日付: {result.issue_date}")
    print(f"金額: {result.amount:,}円" if result.amount else "金額: -")
    print(f"登録番号: {result.invoice_number}")
    print(f"成功: {result.success}")
    if result.error:
        print(f"エラー: {result.error}")


if __name__ == "__main__":
    test_acrobat_ocr()
