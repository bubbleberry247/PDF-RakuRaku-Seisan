# -*- coding: utf-8 -*-
"""
PDF OCR処理モジュール（YomiToku版）

日本語特化ローカルOCRエンジン YomiToku を使用
- 7000文字以上の日本語対応
- 縦書き・手書き対応
- GPU/CPU両対応

Usage:
    from pdf_ocr_yomitoku import YomiTokuOCRProcessor

    processor = YomiTokuOCRProcessor()
    result = processor.process_pdf("receipt.pdf")
"""
import os
import sys
import re
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# YomiToku
try:
    from yomitoku import DocumentAnalyzer
    from yomitoku.data.functions import load_image
    YOMITOKU_AVAILABLE = True
except ImportError:
    YOMITOKU_AVAILABLE = False

# PyMuPDF（PDF→画像変換用）
try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

# 共通モジュール
sys.path.insert(0, str(Path(__file__).parent))
from common.logger import get_logger


@dataclass
class PDFExtractResult:
    """PDF抽出結果"""
    vendor_name: str = ""
    issue_date: str = ""  # YYYYMMDD
    amount: int = 0
    invoice_number: str = ""
    raw_text: str = ""
    confidence: float = 0.0
    success: bool = False
    error: str = ""


class YomiTokuOCRProcessor:
    """YomiToku OCR処理クラス"""

    def __init__(self, use_gpu: bool = True, lite_mode: bool = False):
        """
        Args:
            use_gpu: GPU使用（Falseの場合CPU）
            lite_mode: 軽量モード（CPU向け）
        """
        self.logger = get_logger()

        if not YOMITOKU_AVAILABLE:
            raise ImportError(
                "YomiTokuがインストールされていません: pip install yomitoku"
            )

        if not FITZ_AVAILABLE:
            raise ImportError(
                "PyMuPDFがインストールされていません: pip install PyMuPDF"
            )

        self.use_gpu = use_gpu
        self.lite_mode = lite_mode
        self._analyzer = None

    @property
    def analyzer(self):
        """DocumentAnalyzerの遅延初期化"""
        if self._analyzer is None:
            device = "cuda" if self.use_gpu else "cpu"
            self.logger.info(f"YomiToku初期化: device={device}, lite={self.lite_mode}")

            configs = {}
            if self.lite_mode:
                configs = {
                    "ocr": {"model_name": "lite"},
                    "layout_analyzer": {"model_name": "lite"},
                }

            self._analyzer = DocumentAnalyzer(
                configs=configs,
                device=device
            )
        return self._analyzer

    def pdf_to_image(self, pdf_path: Path, dpi: int = 300) -> Path:
        """PDFを画像に変換"""
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # 一時ファイルに保存
        temp_path = Path(tempfile.mktemp(suffix=".png"))
        pix.save(str(temp_path))

        doc.close()
        return temp_path

    def extract_text(self, image_path: Path) -> str:
        """画像からテキストを抽出"""
        img = load_image(str(image_path))
        result, _, _ = self.analyzer(img)

        # 全テキストを結合
        text_parts = []
        for element in result.paragraphs:
            text_parts.append(element.contents)

        return "\n".join(text_parts)

    def parse_expense_data(self, text: str) -> dict:
        """テキストから経費データを抽出"""
        data = {
            "vendor_name": "",
            "issue_date": "",
            "amount": 0,
            "invoice_number": ""
        }

        # 事業者登録番号
        invoice_patterns = [
            r'[TＴ][\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'登録番号[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
        ]
        for pattern in invoice_patterns:
            match = re.search(pattern, text)
            if match:
                raw_num = re.sub(r'[\s\-]', '', match.group(1))
                if len(raw_num) == 13 and raw_num.isdigit():
                    data["invoice_number"] = f"T{raw_num}"
                    break

        # 金額（優先度順のパターン - レシート対応強化）
        amount_patterns_priority = [
            # 最優先: 明示的な合計・小計
            (r'(?:合計|小計|総額|総計)[金額]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', True),
            (r'(?:税込|税込合計)[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', True),
            (r'(?:お買上|お買い上げ|お支払)[金額]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', True),
            # 中優先: 円記号付き
            (r'[¥\\￥]\s*([\d,，]+)', False),
            # 低優先: 円マーク
            (r'([\d,，]+)\s*円', False),
            # レシート用: 数字のみ（最後の手段）
            (r'\s(\d{2,7})\s*$', False),
        ]

        amounts = []
        priority_amounts = []  # 優先パターンで見つかった金額

        for pattern, is_priority in amount_patterns_priority:
            matches = re.findall(pattern, text, re.MULTILINE)
            for m in matches:
                try:
                    amount = int(re.sub(r'[,，\.]', '', m))
                    if 50 <= amount <= 10000000:  # 50円以上に緩和
                        amounts.append(amount)
                        if is_priority:
                            priority_amounts.append(amount)
                except ValueError:
                    pass

        # 優先パターンがあればそれを使用、なければ最大値
        if priority_amounts:
            data["amount"] = max(priority_amounts)
        elif amounts:
            data["amount"] = max(amounts)

        # 日付（パターン強化 - 様々な形式に対応）
        date_patterns = [
            # 標準形式: 2026年1月10日
            (r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
             lambda m: f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
            # スラッシュ区切り: 2026/01/10
            (r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})',
             lambda m: f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
            # 和暦: 令和8年1月10日
            (r'令和\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
             lambda m: f"{2018 + int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
            # 省略形: R8.1.10
            (r'[RＲ]\s*(\d{1,2})\s*[\.・]\s*(\d{1,2})\s*[\.・]\s*(\d{1,2})',
             lambda m: f"{2018 + int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
            # レシート用: 26/01/10 (年が2桁)
            (r'(\d{2})[/\-](\d{1,2})[/\-](\d{1,2})',
             lambda m: f"20{int(m.group(1)):02d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
            # ドット区切り: 2026.01.10
            (r'(\d{4})\s*[\.・]\s*(\d{1,2})\s*[\.・]\s*(\d{1,2})',
             lambda m: f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
        ]

        for pattern, converter in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    date_str = converter(match)
                    # 日付の妥当性チェック
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                        data["issue_date"] = date_str
                        break
                except (ValueError, IndexError):
                    continue

        # 取引先名（パターン強化 - 店舗名・会社名対応）
        vendor_patterns = [
            # 会社形式（先頭）
            r'^((?:株式会社|有限会社|合同会社|一般社団法人).+?)(?:\s|$)',
            # 会社形式（末尾）
            r'^(.+?(?:株式会社|有限会社|㈱|㈲|LLC))(?:\s|$)',
            # よくある店舗名（レシート対応）
            r'(セリア|ニトリ|東京インテリア|ダイソー|セブンイレブン|ローソン|ファミリーマート|イオン|ヤマダ電機|ビックカメラ|ヨドバシカメラ|コジマ|ケーズデンキ|エディオン|ノジマ|ドン・キホーテ|ユニクロ|GU|無印良品|MUJI|しまむら|西松屋|スシロー|くら寿司|ガスト|サイゼリヤ|マクドナルド|ミスタードーナツ|スターバックス|ドトール|タリーズ)',
            # ○○店・○○支店形式
            r'^(.+?(?:店|支店|営業所|事業所))(?:\s|$)',
            # ○○ガス・○○電力等
            r'^(.+?(?:ガス|電力|電気|水道|通信))(?:\s|$)',
        ]

        for pattern in vendor_patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                vendor = match.group(1).strip()
                # ノイズ除去
                vendor = re.sub(r'[\r\n\t]', '', vendor)
                vendor = vendor[:50]  # 50文字まで
                if len(vendor) >= 2 and '御中' not in vendor and '様' not in vendor:
                    data["vendor_name"] = vendor
                    break

        return data

    def process_pdf(self, pdf_path: Path) -> PDFExtractResult:
        """PDFを処理してデータを抽出"""
        pdf_path = Path(pdf_path)
        result = PDFExtractResult()

        if not pdf_path.exists():
            result.error = f"ファイルが存在しません: {pdf_path}"
            return result

        try:
            self.logger.info(f"YomiToku処理開始: {pdf_path.name}")

            # PDF→画像変換
            image_path = self.pdf_to_image(pdf_path)

            # OCR実行
            text = self.extract_text(image_path)
            result.raw_text = text

            # 一時ファイル削除
            image_path.unlink()

            # データ抽出
            expense_data = self.parse_expense_data(text)
            result.vendor_name = expense_data["vendor_name"]
            result.issue_date = expense_data["issue_date"]
            result.amount = expense_data["amount"]
            result.invoice_number = expense_data["invoice_number"]

            # 成功判定
            if result.vendor_name or result.amount > 0 or result.issue_date:
                result.success = True
                result.confidence = 0.8  # YomiTokuは信頼度を返さないため固定値

            self.logger.info(
                f"抽出結果: vendor={result.vendor_name}, "
                f"date={result.issue_date}, amount={result.amount}"
            )

        except Exception as e:
            result.error = str(e)
            self.logger.error(f"YomiToku処理エラー: {e}")
            import traceback
            traceback.print_exc()

        return result


def main():
    """テスト実行"""
    import argparse

    parser = argparse.ArgumentParser(description="PDF OCR処理（YomiToku版）")
    parser.add_argument("pdf", help="PDFファイルパス")
    parser.add_argument("--cpu", action="store_true", help="CPUモード")
    parser.add_argument("--lite", action="store_true", help="軽量モード")

    args = parser.parse_args()

    from common.logger import setup_logger
    setup_logger("pdf_ocr_yomitoku")

    processor = YomiTokuOCRProcessor(
        use_gpu=not args.cpu,
        lite_mode=args.lite
    )
    result = processor.process_pdf(Path(args.pdf))

    print("\n=== 抽出結果（YomiToku）===")
    print(f"取引先名: {result.vendor_name}")
    print(f"発行日: {result.issue_date}")
    print(f"金額: {result.amount:,}円" if result.amount else "金額: -")
    print(f"事業者登録番号: {result.invoice_number}")
    print(f"成功: {result.success}")
    if result.error:
        print(f"エラー: {result.error}")

    print("\n--- 抽出テキスト（先頭500文字）---")
    print(result.raw_text[:500])


if __name__ == "__main__":
    main()
