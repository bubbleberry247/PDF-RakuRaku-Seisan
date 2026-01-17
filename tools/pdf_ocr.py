# -*- coding: utf-8 -*-
"""
PDF OCR処理モジュール

OCR-JA（Adobe PDF Services）でSearchable PDFに変換後、
テキストを抽出して取引先名・日付・金額を取得する

Usage:
    from pdf_ocr import PDFOCRProcessor

    processor = PDFOCRProcessor()
    result = processor.process_pdf("20251117183719075.pdf")
    print(result)
    # {'vendor_name': 'ソニービズネットワークス株式会社',
    #  'issue_date': '20251107',
    #  'amount': 22803,
    #  'invoice_number': 'T1010701026820'}
"""
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List

# PyMuPDFでテキスト抽出
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# 共通モジュール
sys.path.insert(0, str(Path(__file__).parent))
from common.logger import get_logger
from pdf_rotation_detect import PDFRotationDetector
from ocr_dictionary import correct_ocr_text


@dataclass
class PDFExtractResult:
    """PDF抽出結果"""
    vendor_name: str = ""
    issue_date: str = ""  # YYYYMMDD
    amount: int = 0
    invoice_number: str = ""  # 事業者登録番号
    document_type: str = "領収書"  # "領収書" or "請求書"
    description: str = ""  # 但し書き
    raw_text: str = ""  # 抽出した生テキスト
    success: bool = False
    error: str = ""


class PDFOCRProcessor:
    """PDF OCR処理クラス"""

    # OCR-JAのパス（RK10配下に配置）
    OCR_JA_DIR = Path(r"C:\ProgramData\RK10\Tools\OCR-JA")

    def __init__(self):
        self.logger = get_logger()

        # OCR-JAフォルダの確認
        if not self.OCR_JA_DIR.exists():
            raise FileNotFoundError(f"OCR-JAが見つかりません: {self.OCR_JA_DIR}")

        self.input_dir = self.OCR_JA_DIR / "input"
        self.output_dir = self.OCR_JA_DIR / "output"
        self.archive_dir = self.OCR_JA_DIR / "archive"
        self.error_dir = self.OCR_JA_DIR / "error"

    def fix_rotation(self, pdf_path: Path) -> Path:
        """PDFの向きを検出して補正（テキスト方向解析を使用）

        横長の画像PDFを正しい向きに回転（90度 or 270度を自動判定）

        Args:
            pdf_path: 入力PDFパス

        Returns:
            補正済みPDFパス（補正不要の場合は元のパス）
        """
        if not PYMUPDF_AVAILABLE:
            return pdf_path

        try:
            doc = fitz.open(str(pdf_path))
            page = doc[0]  # 最初のページ

            needs_rotation = False
            rotation_angle = 0

            # 回転検出器を使用
            detector = PDFRotationDetector(dpi=150)

            # ページサイズで判定（横長なら回転が必要）
            if page.rect.width > page.rect.height:
                needs_rotation = True
                # テキスト方向を解析して90度か270度かを判定
                rotation_angle = detector.detect_orientation_for_landscape(pdf_path)
                self.logger.info(f"横長PDF検出 ({page.rect.width:.0f}x{page.rect.height:.0f}) → {rotation_angle}度回転")

            # 画像のアスペクト比も確認
            images = page.get_images()
            if images and not needs_rotation:
                xref = images[0][0]
                base_image = doc.extract_image(xref)
                img_w, img_h = base_image['width'], base_image['height']
                # 画像が横長でページが縦長の場合も回転が必要
                if img_w > img_h and page.rect.width < page.rect.height:
                    needs_rotation = True
                    rotation_angle = detector.detect_orientation_for_landscape(pdf_path)
                    self.logger.info(f"横長画像検出 ({img_w}x{img_h}) → {rotation_angle}度回転")

            doc.close()

            if needs_rotation:
                # 指定角度で回転
                doc = fitz.open(str(pdf_path))
                for p in doc:
                    p.set_rotation(rotation_angle)

                # 新しいファイルに保存
                rotated_path = pdf_path.parent / f"_rotated_{pdf_path.name}"
                doc.save(str(rotated_path))
                doc.close()
                return rotated_path

            return pdf_path

        except Exception as e:
            self.logger.warning(f"回転補正エラー（スキップ）: {e}")
            return pdf_path

    def run_ocr(self, pdf_path: Path) -> Optional[Path]:
        """OCR-JAを実行してSearchable PDFを生成

        Args:
            pdf_path: 入力PDFパス

        Returns:
            出力PDFパス（失敗時はNone）
        """
        self.logger.info(f"OCR処理開始: {pdf_path.name}")

        # 回転補正
        corrected_path = self.fix_rotation(pdf_path)
        use_corrected = corrected_path != pdf_path

        # inputフォルダにコピー
        input_file = self.input_dir / pdf_path.name
        shutil.copy2(corrected_path, input_file)

        # 一時ファイルを削除
        if use_corrected and corrected_path.exists():
            try:
                corrected_path.unlink()
            except Exception:
                pass

        # OCR実行
        try:
            result = subprocess.run(
                ["node", "ocr_folder.js"],
                cwd=str(self.OCR_JA_DIR),
                capture_output=True,
                text=True,
                timeout=300  # 5分タイムアウト
            )

            if result.returncode != 0:
                self.logger.error(f"OCR失敗: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            self.logger.error("OCRタイムアウト")
            return None
        except Exception as e:
            self.logger.error(f"OCR実行エラー: {e}")
            return None

        # 出力ファイルを確認
        output_name = pdf_path.stem + "_ocr.pdf"
        output_file = self.output_dir / output_name

        if output_file.exists():
            self.logger.info(f"OCR完了: {output_file.name}")
            return output_file

        # エラーフォルダを確認
        error_file = self.error_dir / pdf_path.name
        if error_file.exists():
            self.logger.error(f"OCR失敗（errorフォルダに移動）: {pdf_path.name}")
            return None

        self.logger.error(f"OCR出力ファイルが見つかりません: {output_name}")
        return None

    def extract_text(self, pdf_path: Path) -> str:
        """PDFからテキストを抽出

        Args:
            pdf_path: PDFファイルパス

        Returns:
            抽出したテキスト
        """
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
            '\u2F46': '日',  # ⽇ → 日
            '\u2F51': '日',  # ⽇ → 日 (別のコードポイント)
            '\u2F49': '月',  # ⽉ → 月
            '\u2F4B': '年',  # ⽛ → 年
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
        """テキストから請求書データを抽出

        Args:
            text: PDFから抽出したテキスト

        Returns:
            抽出結果
        """
        result = PDFExtractResult(raw_text=text)

        if not text.strip():
            result.error = "テキストが空です"
            return result

        # OCR誤認識補正（辞書ベース）
        text = correct_ocr_text(text)

        # CJK互換漢字を正規化（レガシー処理、辞書補正でカバーされない分）
        text = self.normalize_cjk(text)

        # --- 事業者登録番号を抽出 ---
        # T + 13桁の数字（ハイフン・スペースあり対応）
        invoice_patterns = [
            # 基本パターン（既存）
            r'[TＴ][\s\-]*(\d[\d\s\-]{11,17}\d)',  # T1-0107-0102-6820 形式
            r'登録番号[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'インボイス[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            # 追加パターン: ラベル付き
            r'事業者[登録]*番号[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'適格請求書[発行]*事業者[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'適格[:\s：]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'Invoice\s*(?:No|Number)?[:\s\.]*[TＴ]?[\s\-]*(\d[\d\s\-]{11,17}\d)',
            # OCR誤認識対応（Tが7や1に誤認識される場合）- ラベル直後のみ
            r'登録番号[:\s：]*[7１1][\s\-]*(\d[\d\s\-]{11,17}\d)',
            r'事業者番号[:\s：]*[7１1][\s\-]*(\d[\d\s\-]{11,17}\d)',
        ]
        for pattern in invoice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # ハイフン・スペースを除去して13桁に正規化
                raw_num = re.sub(r'[\s\-]', '', match.group(1))
                if len(raw_num) == 13 and raw_num.isdigit():
                    result.invoice_number = f"T{raw_num}"
                    break

        # --- 金額を抽出 ---
        # OCR誤認識のクリーニング（スペースで区切られた数字を連結）
        # 例: "¥1 1 a" → "¥110", "1 100円" → "1100円", "¥2, 140-" → "¥2140-"
        cleaned_text = text
        # ¥記号の後のスペース区切り数字を連結
        cleaned_text = re.sub(r'[¥￥\\]\s*(\d)\s+(\d)\s+([0a-zA-Z])',
                              lambda m: '¥' + m.group(1) + m.group(2) + ('0' if m.group(3).lower() in ['o', 'a'] else m.group(3)),
                              cleaned_text)
        # カンマの後のスペースを除去 (¥2, 140 → ¥2,140)
        cleaned_text = re.sub(r'([¥￥\\][\d,]+),\s+(\d)', r'\1,\2', cleaned_text)
        # 数字間のスペースを除去（金額内のみ）
        cleaned_text = re.sub(r'(\d)\s+(\d{3})\s*[-\-ー円]', r'\1\2', cleaned_text)

        # 様々な金額パターンに対応（優先度付き）
        # (パターン, 優先度) - 優先度が高いパターンで見つかった金額を優先
        amount_patterns_priority = [
            # 最優先: 明示的な合計・請求金額（優先度10）
            (r'(?:合計金額|ご請求金額|請求金額)[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?', 10),
            (r'(?:税込合計|税込金額)[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?', 10),
            # 高優先: 一般的な合計表現（優先度8）
            (r'合計[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?', 8),
            (r'現計[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 8),
            (r'ご請求額[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?', 8),
            (r'お買[い]?上[げ]?[金額計]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 8),
            # 中優先: 業種別表現（優先度7）
            (r'通行料金[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 7),
            (r'駐車料金[:\s：（(]*[一般]*[）):\s：]*\s*([\d,，\.]+)', 7),
            (r'クレジット支払[:\s：]*\s*([\d,，\.]+)', 7),
            (r'料金計[:\s：]*\s*([\d,，\.]+)', 7),
            (r'領収[金額]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 7),
            # 中低優先: 汎用パターン（優先度6）
            (r'税込[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 6),
            (r'支払[い]?[金額計]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 6),
            # 低優先: 小計・¥記号（優先度5）
            (r'小計[:\s：]*[¥\\￥]?\s*([\d,，\.]+)', 5),
            (r'[¥\\￥]\s*([\d,，\.]+)\s*[-\-ー]*', 5),
            # 最低優先: 単独の円表記（優先度4）
            (r'([\d,，\.]+)\s*円', 4),
            # 除外: 「お預り」は採用しない（受取金額であり請求額ではない）
        ]

        best_amount = 0
        best_priority = 0

        for pattern, priority in amount_patterns_priority:
            # クリーニング済みテキストで検索
            matches = re.findall(pattern, cleaned_text, re.MULTILINE)
            for m in matches:
                try:
                    # ピリオドも除去（1.100円 → 1100円）
                    amount = int(re.sub(r'[,，\.]', '', m))
                    if amount >= 100 and amount <= 10000000:  # 100円以上、1000万円以下
                        # 優先度が高い、または同じ優先度で金額が大きい場合に更新
                        if priority > best_priority or (priority == best_priority and amount > best_amount):
                            best_amount = amount
                            best_priority = priority
                except ValueError:
                    pass

        if best_amount > 0:
            result.amount = best_amount

        # --- 日付を抽出 (E案: CJK正規化 + 令和変換 + 複数行対応 + TEL除外) ---
        # 電話番号行を除外
        lines = text.split('\n')
        filtered_lines = [l for l in lines if not re.search(r'TEL|FAX|電話', l, re.IGNORECASE)]
        filtered_text = '\n'.join(filtered_lines)

        # 日付ラベルのリスト（優先順）
        date_labels = ['請求日', '発行日', '利用日', '購入日', '取引日', '日付', '発行']

        # 「請求日」等のラベルの近くにある日付を探す（複数行対応）
        date_found = False
        for i, line in enumerate(filtered_lines):
            if any(label in line for label in date_labels):
                # 同じ行に日付があるか - 令和形式
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

                # 次の行に日付があるか確認（ラベルと日付が別行の場合）
                for j in range(i+1, min(i+3, len(filtered_lines))):
                    next_line = filtered_lines[j].strip()
                    # 令和形式
                    match = re.search(r'令和\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', next_line)
                    if match:
                        year = self.reiwa_to_seireki(int(match.group(1)))
                        month, day = int(match.group(2)), int(match.group(3))
                        result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                        date_found = True
                        break

                    # 西暦形式
                    match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', next_line)
                    if match:
                        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                        date_found = True
                        break
                if date_found:
                    break

        # ラベルなしでも西暦年月日形式を探す
        if not date_found:
            for match in re.finditer(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', filtered_text):
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 2026 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                    date_found = True
                    break

        # YYYY/MM/DD形式（レシート等）・YYYY.MM.DD形式（ドット区切り）
        if not date_found:
            for match in re.finditer(r'(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})', filtered_text):
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 2026 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                    date_found = True
                    break

        # 和暦短縮形式 / 西暦下2桁形式（26年1月9日, I25年12月24日, 改行区切りも含む）
        # OCR誤認識で先頭に「I」「l」「1」等が付くことがある
        # また、改行で「26年\n1月\n9日」のように分割されることもある
        # 注意: 高速道路レシート等では西暦下2桁（26年=2026年）を使う
        if not date_found:
            # 改行・空白を正規化してから検索（改行区切りパターンに対応）
            normalized_text = re.sub(r'[\r\n\s]+', ' ', text)
            for match in re.finditer(r'[Il1|]?(\d{1,2})\s*年\s+(\d{1,2})\s*月\s+(\d{1,2})\s*日', normalized_text):
                year_num, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    # 年の判定: 1-20は令和、21-99は西暦下2桁
                    if 1 <= year_num <= 20:
                        year = self.reiwa_to_seireki(year_num)
                    else:
                        year = 2000 + year_num  # 西暦下2桁（26→2026）
                    result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                    date_found = True
                    break

        # R7/1/9 や R7.1.9 形式（令和短縮形式）
        if not date_found:
            for match in re.finditer(r'[RrＲ]\s*(\d{1,2})[/\.\-](\d{1,2})[/\.\-](\d{1,2})', filtered_text):
                year_num, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 1 <= year_num <= 20 and 1 <= month <= 12 and 1 <= day <= 31:
                    year = self.reiwa_to_seireki(year_num)
                    result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                    break

        # 入庫/出庫日時形式（2026年01月09日15時29分）
        if not date_found:
            for match in re.finditer(r'(\d{4})年(\d{2})月(\d{2})日\d{2}時\d{2}分', text):
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 2026 <= year <= 2100:
                    result.issue_date = f"{year:04d}{month:02d}{day:02d}"
                    break

        # --- 取引先名を抽出 ---
        # 除外パターン（これを含む行は取引先としない）
        vendor_exclude_patterns = [
            r'御中', r'様$', r'殿$',
            r'トナリティ', r'しごとラボ',  # 自社名
            r'^\d+$',  # 数字のみ
            r'^[ァ-ヶー]{1,2}$',  # カタカナ1-2文字のみ
            r'合計', r'小計', r'税込', r'税抜',  # 金額ラベル
            r'^〒', r'^\d{3}-\d{4}',  # 郵便番号
        ]

        def is_excluded_vendor(line: str) -> bool:
            """取引先として除外すべき行か判定"""
            for pattern in vendor_exclude_patterns:
                if re.search(pattern, line):
                    return True
            return False

        # 「御請求書」「請求書」ラベルの直前にある会社名を優先（発行元）
        lines = text.split('\n')
        company_patterns = [
            r'^((?:株式会社|有限会社|合同会社|一般社団法人|税理士法人).+)$',
            r'^(.+(?:株式会社|有限会社|合同会社|㈱|㈲))$',
            r'^(税理士法人.+)$',
            r'^(楽天市場.+)$',
            r'^(.+税務署)$',
            r'^([ァ-ヶー・a-zA-Z]+株式会社.*)$',  # カタカナ・英字で始まる会社名
            r'^(.+・.+株式会社)$',  # 中黒を含む会社名
            r'^(ニトリ|セリア|Seria|ダイソー|DAISO|キャンドゥ|CanDo).*$',  # 小売店
            r'^(.{3,}(?:本店|支店|営業所))$',  # 支店名（3文字以上＋本店/支店/営業所）
            r'^(.+コンセッション.*)$',  # 道路コンセッション会社
            r'^(名鉄協商.*)$',  # 名鉄協商（駐車場）
            r'^(.+パーキング.*)$',  # パーキング
            r'^(郵便局.*)$',  # 郵便局
            r'^(.{3,}店)$',  # 〇〇店形式（3文字以上＋店）- 誤マッチ防止
        ]

        # 戦略1: 「御請求書」「請求書」の直前数行にある会社名を探す
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if '請求書' in line_stripped or '御請求書' in line_stripped:
                # 直前5行を逆順に探索
                for j in range(max(0, i-5), i):
                    prev_line = lines[j].strip()
                    # 除外パターンチェック
                    if is_excluded_vendor(prev_line):
                        continue
                    for pattern in company_patterns:
                        match = re.match(pattern, prev_line)
                        if match:
                            vendor = match.group(1).strip()
                            if len(vendor) >= 2 and not is_excluded_vendor(vendor):
                                result.vendor_name = vendor
                                break
                    if result.vendor_name:
                        break
                break

        # 戦略2: 戦略1で見つからなかった場合、最初に見つかる会社名を使う
        if not result.vendor_name:
            for line in lines:
                line = line.strip()
                # 除外パターンチェック
                if is_excluded_vendor(line):
                    continue
                for pattern in company_patterns:
                    match = re.match(pattern, line)
                    if match:
                        vendor = match.group(1).strip()
                        if len(vendor) >= 2 and not is_excluded_vendor(vendor):
                            result.vendor_name = vendor
                            break
                if result.vendor_name:
                    break

        # 戦略3: 特定のキーワード（高速道路会社、駐車場、店舗など）を直接探す
        if not result.vendor_name:
            special_vendors = [
                (r'愛知道路コンセッション', '愛知道路コンセッション株式会社'),
                (r'名鉄協商', '名鉄協商株式会社'),
                (r'名鉄t.*パーキング', '名鉄協商株式会社'),
                (r'刈谷市会計管理者', '刈谷市会計管理者'),
                (r'刈谷市登録番号', '刈谷市'),
                (r'多治見市', 'バロー'),  # 岐阜県多治見市のスーパー
                (r'沖縄料理', '沖縄料理店'),
                (r'安城市', '安城市内店舗'),
                # 小売店・チェーン店
                (r'オートバックス|AUTOBACS', 'オートバックス'),
                (r'セリア|Seria', 'セリア'),
                (r'ニトリ|NITORI', 'ニトリ'),
                (r'東京インテリア', '東京インテリア家具'),
                (r'ダイソー|DAISO', 'ダイソー'),
                (r'キャンドゥ|Can.*Do', 'キャンドゥ'),
                (r'烏けん|からけん', '烏けん'),  # 飲食店
                (r'平林シート', '平林シート'),  # 業務用資材
                (r'ドン[・]?キホーテ|ドンキ|DON.*QUIJOTE', 'ドン・キホーテ'),
                (r'スギ薬局|スギドラッグ', 'スギ薬局'),
                (r'マツモトキヨシ|マツキヨ', 'マツモトキヨシ'),
                (r'ウエルシア|welcia', 'ウエルシア'),
                (r'イオン|AEON', 'イオン'),
                (r'アピタ|ユニー', 'アピタ'),
                (r'ピアゴ', 'ピアゴ'),
                (r'バロー|VALOR', 'バロー'),
                (r'カネスエ', 'カネスエ'),
                (r'コメダ珈琲', 'コメダ珈琲'),
                (r'スターバックス|STARBUCKS', 'スターバックス'),
                (r'マクドナルド|McDonald', 'マクドナルド'),
                (r'吉野家', '吉野家'),
                (r'すき家', 'すき家'),
                (r'松屋', '松屋'),
                (r'CoCo壱番屋|ココイチ', 'CoCo壱番屋'),
                # ガソリンスタンド
                (r'ENEOS|エネオス', 'ENEOS'),
                (r'出光|idemitsu', '出光'),
                (r'コスモ石油|COSMO', 'コスモ石油'),
                (r'シェル|Shell', 'シェル'),
                # コンビニ
                (r'セブン[−-]?イレブン|7-ELEVEN', 'セブン-イレブン'),
                (r'ファミリーマート|FamilyMart', 'ファミリーマート'),
                (r'ローソン|LAWSON', 'ローソン'),
                (r'ミニストップ|MINISTOP', 'ミニストップ'),
                # ホームセンター
                (r'カインズ|CAINZ', 'カインズ'),
                (r'コメリ|KOMERI', 'コメリ'),
                (r'DCM', 'DCMホールディングス'),
                (r'ケーヨー|K-YO', 'ケーヨー'),
                # 駐車場
                (r'タイムズ|Times', 'タイムズ'),
                (r'三井のリパーク|リパーク', '三井不動産リアルティ株式会社'),
                (r'NPC24H', 'NPC24H'),
            ]
            for pattern, vendor_name in special_vendors:
                if re.search(pattern, text, re.IGNORECASE):
                    result.vendor_name = vendor_name
                    break

        # --- 領収書区分を判定 ---
        # 「請求書」キーワードがあれば請求書、なければ領収書（デフォルト）
        invoice_keywords = [
            r'請\s*求\s*書',
            r'御\s*請\s*求',
            r'ご\s*請\s*求',
            r'INVOICE',
        ]
        for pattern in invoice_keywords:
            if re.search(pattern, text, re.IGNORECASE):
                result.document_type = "請求書"
                break
        # 「領収書」「領収証」があれば明示的に領収書
        receipt_keywords = [r'領\s*収\s*書', r'領\s*収\s*証', r'レシート', r'RECEIPT']
        for pattern in receipt_keywords:
            if re.search(pattern, text, re.IGNORECASE):
                result.document_type = "領収書"
                break

        # --- 但し書きを抽出 ---
        description_patterns = [
            r'但[し]?[:\s：、]*(.+?)(?:\s*として|として|$)',
            r'但[し]?書[き]?[:\s：]*(.+?)(?:\s|$)',
            r'品\s*名[:\s：]*(.+?)(?:\s|$)',
            r'摘\s*要[:\s：]*(.+?)(?:\s|$)',
            r'内\s*容[:\s：]*(.+?)(?:\s|$)',
            r'(?:上記|上記の?金額)[^。]*(?:として|を)[:\s：]*(.+?)(?:代|費|料|として)',
        ]
        for pattern in description_patterns:
            match = re.search(pattern, text)
            if match:
                desc = match.group(1).strip()
                # ノイズ除去
                desc = re.sub(r'[\r\n\t]', '', desc)
                desc = desc[:100]  # 100文字まで
                if len(desc) >= 2:
                    result.description = desc
                    break

        # 抽出成功判定
        if result.vendor_name or result.amount > 0:
            result.success = True
        else:
            result.error = "データを抽出できませんでした"

        return result

    def extract_from_filename(self, filename: str) -> dict:
        """ファイル名から情報を抽出（フォールバック用）

        ファイル名の形式例:
        - "2025,12,27名鉄協商400.pdf" → 日付:20251227, 取引先:名鉄協商, 金額:400
        - "ごとう歯科打合せ駐車場代.pdf" → 取引先:ごとう歯科
        - "領収証2025.12.26.pdf" → 日付:20251226
        - "0109セリア(百均)買物.pdf" → 日付:20260109（令和8年=2026年と推定）
        """
        info = {'vendor': '', 'date': '', 'amount': 0}
        name = Path(filename).stem

        # 日付パターン: YYYY,MM,DD or YYYY.MM.DD
        date_match = re.search(r'(\d{4})[,\.](\d{1,2})[,\.](\d{1,2})', name)
        if date_match:
            year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            if 2026 <= year <= 2100:
                info['date'] = f"{year:04d}{month:02d}{day:02d}"

        # MMDDで始まるパターン（0109セリア → 2026年1月9日と推定）
        if not info['date']:
            date_match = re.match(r'^(\d{2})(\d{2})', name)
            if date_match:
                month, day = int(date_match.group(1)), int(date_match.group(2))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    # 現在年を使用（令和8年=2026年）
                    import datetime
                    current_year = datetime.datetime.now().year
                    info['date'] = f"{current_year:04d}{month:02d}{day:02d}"

        # YYYYMMDD形式のファイル名（BP-60C31_20260108_100404.pdf）
        if not info['date']:
            date_match = re.search(r'_(\d{4})(\d{2})(\d{2})_', name)
            if date_match:
                year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                if 2026 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    info['date'] = f"{year:04d}{month:02d}{day:02d}"

        # ファイル名末尾のYYYYMMDD（20260109181028.pdf → 20260109）
        if not info['date']:
            date_match = re.search(r'(\d{4})(\d{2})(\d{2})\d*\.pdf$', filename, re.IGNORECASE)
            if date_match:
                year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                if 2026 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    info['date'] = f"{year:04d}{month:02d}{day:02d}"

        # ファイル名内のYYYYMMDD形式（doc06591420260109181028.pdf → 20260109）
        if not info['date']:
            date_match = re.search(r'(20(?:2[6-9]|[3-9][0-9]))(\d{2})(\d{2})', name)
            if date_match:
                year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    info['date'] = f"{year:04d}{month:02d}{day:02d}"

        # 金額パターン: 末尾の数字
        amount_match = re.search(r'(\d+)$', name)
        if amount_match:
            amount = int(amount_match.group(1))
            if 100 <= amount <= 1000000:
                info['amount'] = amount

        # 取引先パターン
        vendor_patterns = [
            (r'ニトリ', 'ニトリ'),
            (r'名鉄協商', '名鉄協商株式会社'),
            (r'ごとう歯科', 'ごとう歯科'),
            (r'鶴舞クリニック', '鶴舞クリニック'),
            (r'東京インテリア', '東京インテリア家具'),
            (r'セリア', 'セリア'),
            (r'もち吉', 'もち吉'),
            (r'日本郵便', '日本郵便株式会社'),
            (r'沖縄料理', '沖縄料理店'),
            (r'消防打合せ', '駐車場'),  # 駐車場代の領収書
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
            skip_ocr: Trueの場合はOCRをスキップ（既にSearchable PDFの場合）

        Returns:
            抽出結果
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            return PDFExtractResult(error=f"ファイルが存在しません: {pdf_path}")

        # まず直接テキスト抽出を試みる
        text = self.extract_text(pdf_path)

        # テキストが取れない場合はOCR実行
        if not text.strip() and not skip_ocr:
            self.logger.info("テキストなし → OCR実行")
            ocr_pdf = self.run_ocr(pdf_path)
            if ocr_pdf:
                text = self.extract_text(ocr_pdf)

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

        self.logger.info(f"抽出結果: vendor={result.vendor_name}, date={result.issue_date}, amount={result.amount}, invoice={result.invoice_number}")

        return result


def main():
    """テスト実行"""
    import argparse

    parser = argparse.ArgumentParser(description="PDF OCR処理")
    parser.add_argument("pdf", help="PDFファイルパス")
    parser.add_argument("--skip-ocr", action="store_true", help="OCRをスキップ")

    args = parser.parse_args()

    # ロガー設定
    from common.logger import setup_logger
    setup_logger("pdf_ocr")

    processor = PDFOCRProcessor()
    result = processor.process_pdf(Path(args.pdf), skip_ocr=args.skip_ocr)

    print("\n=== 抽出結果 ===")
    print(f"取引先名: {result.vendor_name}")
    print(f"発行日: {result.issue_date}")
    print(f"金額: {result.amount:,}円" if result.amount else "金額: -")
    print(f"事業者登録番号: {result.invoice_number}")
    print(f"成功: {result.success}")
    if result.error:
        print(f"エラー: {result.error}")


if __name__ == "__main__":
    main()
