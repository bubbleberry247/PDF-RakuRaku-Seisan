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
from ocr_dictionary import correct_ocr_text


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

        # OCR誤認識補正（辞書ベース）
        text = correct_ocr_text(text)

        # 事業者登録番号（パターン拡張）
        invoice_patterns = [
            # 基本パターン
            r'[TＴ][\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'登録番号[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'インボイス[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            # 追加パターン
            r'事業者[登録]*番号[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'適格請求書[発行]*事業者[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'適格[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            # OCR誤認識対応（Tが7や1に誤認識される場合）- ラベル直後のみ
            r'登録番号[:\s：]*[7１1][\s\-]*(\d[\d\s\-]{11,17}\d)',
            # 先頭1の後に13桁が続くパターン（1XXXXXXXXXXXX形式 - Tが1に誤認識）
            r'登録番号[:\s：\n]*[1](\d{13})',
            # 14桁の数字（先頭1がTの誤認識）の後に登録番号ラベルがあるパターン
            r'[1](\d{13})\s*\n?\s*登録番号',
            # 単独の14桁数字（先頭1がTの誤認識、会社名の後にある）
            r'株式会社\s*\n?\s*[1](\d{13})',
        ]
        for pattern in invoice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_num = re.sub(r'[\s\-]', '', match.group(1))
                if len(raw_num) == 13 and raw_num.isdigit():
                    data["invoice_number"] = f"T{raw_num}"
                    break

        # 金額（優先度順のパターン - レシート対応強化）
        # (パターン, 優先度) - 優先度が高いパターンで見つかった金額を優先
        amount_patterns_priority = [
            # 最優先: 明示的な合計・請求金額（優先度10）
            (r'(?:合計金額|ご請求金額|請求金額)[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 10),
            (r'(?:税込合計|税込金額)[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 10),
            # 高優先: 一般的な合計表現（優先度8）
            (r'(?:合計|総額|総計)[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 8),
            (r'(?:お買上|お買い上げ|お支払)[金額計]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 8),
            # 中優先: 業種別表現（優先度7）
            (r'通行料金[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 7),
            (r'駐車料金[:\s：（(]*[一般]*[）):\s：]*\s*([\d,，\.]+)', 7),
            (r'現計[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 7),
            (r'領収[金額]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 7),
            # 中低優先: 汎用パターン（優先度6）
            (r'税込[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 6),
            (r'支払[い]?[金額計]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 6),
            # 低優先: 小計・¥記号（優先度5）
            (r'小計[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 5),
            (r'[¥\\￥]\s*([\d,，\.]+)\s*[-\-ー]*', 5),  # ¥3,400- 形式対応
            # 最低優先: 単独の円表記（優先度4）
            (r'([\d,，]+)\s*円', 4),
            # 除外: 「お預り」は採用しない（受取金額であり請求額ではない）
        ]

        best_amount = 0
        best_priority = 0

        for pattern, priority in amount_patterns_priority:
            matches = re.findall(pattern, text, re.MULTILINE)
            for m in matches:
                try:
                    amount = int(re.sub(r'[,，\.]', '', m))
                    if 50 <= amount <= 10000000:  # 50円以上に緩和
                        # 優先度が高い、または同じ優先度で金額が大きい場合に更新
                        if priority > best_priority or (priority == best_priority and amount > best_amount):
                            best_amount = amount
                            best_priority = priority
                except ValueError:
                    pass

        if best_amount > 0:
            data["amount"] = best_amount

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

        # 全ての日付候補を収集して、最も妥当なものを選択
        date_candidates = []
        for pattern, converter in date_patterns:
            for match in re.finditer(pattern, text):
                try:
                    date_str = converter(match)
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                        date_candidates.append(date_str)
                except (ValueError, IndexError):
                    continue

        if date_candidates:
            # 2026年以降の日付のみ有効（それ以前の領収書は処理対象外）
            valid_dates = [d for d in date_candidates if int(d[:4]) >= 2026]
            if valid_dates:
                data["issue_date"] = valid_dates[0]
            # 2026年以前の日付は採用しない（OCR誤認識と判断）

        # 取引先名（パターン強化 - 店舗名・会社名対応）
        # 特定のベンダーを先に探す（特殊パターン）
        special_vendor_patterns = [
            (r'三井のリパーク|リパーク', '三井不動産リアルティ株式会社'),
            (r'刈谷市会計管理者', '刈谷市会計管理者'),
            (r'名鉄協商|名鉄t.*パーキング', '名鉄協商株式会社'),
            (r'タイムズ|Times', 'タイムズ'),
        ]
        for pattern, vendor_name in special_vendor_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                data["vendor_name"] = vendor_name
                return data  # 特定できたら早期リターン

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

    def _calculate_confidence(self, result: PDFExtractResult) -> float:
        """
        抽出結果に基づく信頼度計算

        各項目の抽出成功に応じてスコアを加算

        Returns:
            信頼度スコア（0.0〜1.0）
        """
        score = 0.0

        # 金額が取得できた
        if result.amount > 0:
            score += 0.30
            # 金額が妥当範囲（50〜1000万円）
            if 50 <= result.amount <= 10000000:
                score += 0.15

        # 日付が妥当な形式（YYYYMMDD, 8桁）
        if result.issue_date and len(result.issue_date) == 8:
            try:
                year = int(result.issue_date[:4])
                month = int(result.issue_date[4:6])
                day = int(result.issue_date[6:8])
                if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    score += 0.20
            except ValueError:
                pass

        # 取引先名が取得できた
        if result.vendor_name and len(result.vendor_name) >= 2:
            score += 0.20

        # 事業者登録番号（T+13桁）
        if result.invoice_number:
            import re
            if re.match(r'^T\d{13}$', result.invoice_number):
                score += 0.15

        return min(score, 1.0)

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

            # 成功判定と信頼度計算
            if result.vendor_name or result.amount > 0 or result.issue_date:
                result.success = True
                # 抽出成功率に基づく信頼度計算
                result.confidence = self._calculate_confidence(result)

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
