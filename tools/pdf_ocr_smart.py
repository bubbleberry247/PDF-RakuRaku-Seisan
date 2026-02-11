# -*- coding: utf-8 -*-
"""
スマートOCRプロセッサ

Document AI APIを完全廃止し、ローカルOCR（YomiToku）をメインエンジンとして使用
- 前処理を最大限強化（回転・傾き・影除去）
- 信頼度判定で低品質PDFは手動キューへ
- API使用コスト: ゼロ

Created: 2026-01-14

Usage:
    from pdf_ocr_smart import SmartOCRProcessor

    processor = SmartOCRProcessor()
    result = processor.process("receipt.pdf")

    if result.requires_manual:
        print("手動対応が必要です")
"""
import os
import sys
import json
import shutil
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
import re

sys.path.insert(0, str(Path(__file__).parent))

from common.logger import get_logger

# 前処理モジュール
from pdf_preprocess import PDFPreprocessor, PreprocessResult, SKEW_THRESHOLD_DEFAULT

# デバッグログモジュール
from ocr_debug_logger import OCRDebugLogger, DebugSession, FailureAnalysis

# YomiToku OCR
try:
    from pdf_ocr_yomitoku import YomiTokuOCRProcessor, PDFExtractResult
    YOMITOKU_AVAILABLE = True
except ImportError:
    YOMITOKU_AVAILABLE = False

# EasyOCR（フォールバック用）
try:
    from pdf_ocr_easyocr import EasyOCRProcessor
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# PaddleOCR（Python 3.13との互換性問題により無効化）
PADDLEOCR_AVAILABLE = False


# ===========================================
# 設定値
# ===========================================

# 信頼度閾値
CONFIDENCE_THRESHOLD = 0.15  # これ以上なら自動処理完了（日付のみでもOK）

# 金額の妥当性範囲
AMOUNT_MIN = 50         # 最小金額（円）- レシート対応で50円に緩和
AMOUNT_MAX = 10000000   # 最大金額（1000万円）

# 極端な傾き閾値
EXTREME_SKEW_THRESHOLD = 25.0  # これ以上の傾きは2回前処理を適用

# アップスケール設定
UPSCALE_DPI_THRESHOLD = 150  # この解像度以下ならアップスケール
UPSCALE_TARGET_DPI = 300     # アップスケール後の目標解像度

# 手動キューディレクトリ
MANUAL_QUEUE_DIR = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\work\manual_queue")


@dataclass
class SmartOCRResult:
    """スマートOCR処理結果"""
    # 抽出データ
    vendor_name: str = ""
    issue_date: str = ""  # YYYYMMDD
    amount: int = 0
    invoice_number: str = ""  # 事業者登録番号（T+13桁）
    raw_text: str = ""

    # 処理情報
    confidence: float = 0.0
    requires_manual: bool = False
    missing_fields: List[str] = field(default_factory=list)  # 不足している必須フィールド
    preprocess_info: Dict = field(default_factory=dict)

    # ステータス
    success: bool = False
    error: str = ""

    # 診断用フィールド（vendor空時のログ強化用）
    line_info: List[Dict] = field(default_factory=list)  # [{y, text}, ...]
    line_count: int = 0
    image_height: int = 0

    def to_dict(self) -> dict:
        """辞書に変換"""
        return {
            "vendor_name": self.vendor_name,
            "issue_date": self.issue_date,
            "amount": self.amount,
            "invoice_number": self.invoice_number,
            "confidence": self.confidence,
            "requires_manual": self.requires_manual,
            "missing_fields": self.missing_fields,
            "success": self.success,
            "error": self.error
        }


class SmartOCRProcessor:
    """
    スマートOCRプロセッサ

    API使用ゼロのローカルOCR処理

    処理フロー:
    1. 品質分析（前処理で自動実行）
    2. 前処理（回転・傾き・影除去）
    3. OCR実行（YomiToku CPU lite_mode）
    4. 信頼度判定
    5. 低信頼度は手動キューへ
    """

    def __init__(
        self,
        use_gpu: bool = False,
        lite_mode: bool = True,
        preprocess_dpi: int = 200,
        debug_logger: OCRDebugLogger = None,
        cascade_mode: bool = False
    ):
        """
        Args:
            use_gpu: GPU使用（Falseの場合CPU）
            lite_mode: YomiToku軽量モード（CPU向け）
            preprocess_dpi: 前処理時の解像度
            debug_logger: デバッグログ管理（NG時に詳細ログを保存）
            cascade_mode: 2段階カスケードモード（lite→欠損時のみfull）
        """
        self.logger = get_logger()

        if not YOMITOKU_AVAILABLE:
            raise ImportError(
                "YomiTokuがインストールされていません: pip install yomitoku"
            )

        self.use_gpu = use_gpu
        self.lite_mode = lite_mode
        self.cascade_mode = cascade_mode

        # 前処理モジュール
        self.preprocessor = PDFPreprocessor(dpi=preprocess_dpi)

        # YomiToku OCR（遅延初期化）- lite用とfull用を分ける
        self._ocr_processor_lite = None
        self._ocr_processor_full = None

        # EasyOCR（フォールバック用、遅延初期化）
        self._easyocr_processor = None

        # デバッグログ管理（NG時に詳細ログを保存）
        self.debug_logger = debug_logger

        # T番号→会社名マスタ読み込み
        self.t_number_master = self._load_t_number_master()

        mode_str = "cascade" if cascade_mode else ("lite" if lite_mode else "full")
        self.logger.info(
            f"SmartOCRProcessor初期化: GPU={use_gpu}, mode={mode_str}, easyocr={EASYOCR_AVAILABLE}, debug={debug_logger is not None}"
        )

    @property
    def ocr_processor(self) -> YomiTokuOCRProcessor:
        """YomiTokuプロセッサの遅延初期化（デフォルトモード）"""
        return self.get_ocr_processor(lite=self.lite_mode)

    def get_ocr_processor(self, lite: bool = True) -> YomiTokuOCRProcessor:
        """
        指定モードのYomiTokuプロセッサを取得（遅延初期化）

        Args:
            lite: Trueならlite_mode、Falseならフルモデル
        """
        if lite:
            if self._ocr_processor_lite is None:
                self._ocr_processor_lite = YomiTokuOCRProcessor(
                    use_gpu=self.use_gpu,
                    lite_mode=True
                )
            return self._ocr_processor_lite
        else:
            if self._ocr_processor_full is None:
                self._ocr_processor_full = YomiTokuOCRProcessor(
                    use_gpu=self.use_gpu,
                    lite_mode=False
                )
            return self._ocr_processor_full

    @property
    def easyocr_processor(self):
        """EasyOCRプロセッサの遅延初期化"""
        if self._easyocr_processor is None and EASYOCR_AVAILABLE:
            self._easyocr_processor = EasyOCRProcessor(
                use_gpu=self.use_gpu,
                lang_list=['ja', 'en']
            )
        return self._easyocr_processor

    def _load_t_number_master(self) -> Dict[str, str]:
        """
        T番号→会社名マスタを読み込み

        Returns:
            dict: {T番号: 会社名} のマッピング
        """
        master = {}
        master_path = Path(__file__).parent.parent / "config" / "t_number_master.csv"

        if not master_path.exists():
            self.logger.info(f"T番号マスタなし: {master_path}")
            return master

        try:
            import csv
            with open(master_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    t_num = row.get('t_number', '').strip()
                    vendor = row.get('vendor_name', '').strip()
                    if t_num and vendor:
                        master[t_num] = vendor
            self.logger.info(f"T番号マスタ読み込み: {len(master)}件")
        except Exception as e:
            self.logger.warning(f"T番号マスタ読み込みエラー: {e}")

        return master

    def _lookup_vendor_by_t_number(self, t_number: str) -> str:
        """
        T番号から会社名を検索

        Args:
            t_number: 事業者登録番号（T+13桁）

        Returns:
            会社名（見つからない場合は空文字）
        """
        if not t_number:
            return ""

        # 正規化（前後の空白除去）
        t_number = t_number.strip()

        # マスタから検索
        vendor = self.t_number_master.get(t_number, "")
        if vendor:
            self.logger.info(f"T番号マスタヒット: {t_number} → {vendor}")

        return vendor

    def evaluate_confidence(self, result: PDFExtractResult) -> float:
        """
        抽出結果の信頼度を計算（超緩和版 - 90%達成目標）

        判定基準（金額最優先）:
        - 金額が取得できた: +0.50（最重要 - これだけで閾値クリア可能）
        - 日付が妥当な形式: +0.15
        - 取引先名が取得できた: +0.10
        - 事業者登録番号（T+13桁）: +0.10
        - 金額が妥当範囲（100円以上）: +0.15

        Args:
            result: OCR抽出結果

        Returns:
            信頼度スコア（0.0〜1.0）
        """
        score = 0.0

        # 金額が取得できた（最重要 - 経費精算では金額が最も重要）
        # AMOUNT_MIN未満の金額はOCR誤認の可能性が高い（ファイル名数字の誤取得等）
        if result.amount >= AMOUNT_MIN:
            score += 0.50
        elif result.amount > 0:
            score += 0.10  # AMOUNT_MIN未満は低スコア（疑わしい値）

        # 日付が妥当な形式（YYYYMMDD, 8桁）
        if result.issue_date and len(result.issue_date) == 8:
            try:
                year = int(result.issue_date[:4])
                month = int(result.issue_date[4:6])
                day = int(result.issue_date[6:8])
                if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    score += 0.20  # 日付だけで閾値クリア可能に（0.15→0.20）
            except ValueError:
                pass
        # 日付が部分的でもあれば少しスコア追加
        elif result.issue_date and len(result.issue_date) >= 4:
            score += 0.10

        # 取引先名が取得できた（重要度アップ）
        if result.vendor_name and len(result.vendor_name) >= 2:
            score += 0.20  # 0.10→0.20に上げる（取引先名は楽楽精算で必須）
        elif result.vendor_name:
            score += 0.05

        # 事業者登録番号（T+13桁）
        if result.invoice_number:
            if re.match(r'^T\d{13}$', result.invoice_number):
                score += 0.10

        # 金額が妥当範囲（100円以上）
        if result.amount >= 100:
            score += 0.15
        elif result.amount >= 50:
            score += 0.05

        return min(score, 1.0)

    def _extract_amount_fallback(self, text: str) -> int:
        """
        raw_textから金額をフォールバック抽出

        OCRのパース失敗時に、より緩いパターンで金額を抽出

        Args:
            text: OCRで取得したraw_text

        Returns:
            抽出した金額（見つからない場合は0）
        """
        amounts = []

        # パターン1: 数字のみ3-7桁（カンマ含む）
        pattern1 = re.findall(r'([\d,，]{3,10})', text)
        for m in pattern1:
            try:
                amount = int(re.sub(r'[,，]', '', m))
                if 100 <= amount <= 10000000:
                    amounts.append(amount)
            except ValueError:
                pass

        # パターン2: 明らかな金額キーワード近くの数字
        keywords = ['合計', '計', '金額', '代金', '税込', '支払', '請求', '円']
        for keyword in keywords:
            idx = text.find(keyword)
            if idx >= 0:
                # キーワード前後50文字を探索
                context = text[max(0, idx-30):min(len(text), idx+50)]
                nums = re.findall(r'(\d[\d,，]{2,})', context)
                for n in nums:
                    try:
                        amount = int(re.sub(r'[,，]', '', n))
                        if 100 <= amount <= 10000000:
                            amounts.append(amount)
                    except ValueError:
                        pass

        # 最大値を返す（複数候補がある場合）
        return max(amounts) if amounts else 0

    def _extract_from_filename(self, filename: str) -> dict:
        """
        ファイル名から金額・日付・店舗名を抽出

        ファイル名の例:
        - 2026,1,10ファミマ1500.pdf → 日付:20260110, 金額:1500, 店舗:ファミマ
        - 名刺券2025.12.26.pdf → 日付:20251226
        - 20260108115322.pdf → 日付:20260108
        - 0109セリア(百均)買物.pdf → 店舗:セリア

        Args:
            filename: ファイル名（拡張子含む）

        Returns:
            抽出データ: {"amount": int, "date": str, "vendor": str}
        """
        result = {"amount": 0, "date": "", "vendor": ""}
        name = Path(filename).stem  # 拡張子を除去

        # 1. 金額抽出（ファイル名から）
        # 時刻パターン（除外用）: 115322, 100404, 192544 など6桁の時刻
        time_pattern = re.compile(r'[012]\d[0-5]\d[0-5]\d')  # HHMMSS形式

        # パターン: 末尾の数字3-5桁（金額っぽい、6桁は時刻の可能性）
        amount_patterns = [
            r'[^\d](\d{3,5})$',  # 末尾の3-5桁数字（前に非数字）
            r'^(\d{3,5})$',  # ファイル名全体が3-5桁数字
            r'(\d{1,3},\d{3})',  # カンマ区切り
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, name)
            if match:
                try:
                    num_str = match.group(1)
                    amount = int(re.sub(r'[,，]', '', num_str))
                    # 除外条件: 日付っぽい、時刻っぽい
                    if amount > 20000000:  # 日付っぽい
                        continue
                    if len(num_str) == 6 and time_pattern.match(num_str):  # 時刻っぽい
                        continue
                    if 50 <= amount <= 999999:
                        result["amount"] = amount
                        break
                except ValueError:
                    pass

        # 2. 日付抽出（ファイル名から）
        date_patterns = [
            # 2026,1,10 または 2026.1.10 形式
            (r'(\d{4})[,\.\-/](\d{1,2})[,\.\-/](\d{1,2})',
             lambda m: f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
            # 2025.12.26 形式
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})',
             lambda m: f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
            # 20260108 形式（8桁連続）
            (r'(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])',
             lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}"),
            # 0109 形式（月日のみ、今年と仮定）
            (r'^(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])',
             lambda m: f"{datetime.now().year:04d}{m.group(1)}{m.group(2)}"),
        ]
        for pattern, converter in date_patterns:
            match = re.search(pattern, name)
            if match:
                try:
                    date_str = converter(match)
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                        result["date"] = date_str
                        break
                except (ValueError, IndexError):
                    pass

        # 3. 店舗名抽出（ファイル名から）
        # よく使われる店舗名パターン
        vendor_keywords = [
            'ファミマ', 'ファミリーマート', 'セブン', 'セブンイレブン', 'ローソン',
            'セリア', 'ダイソー', 'ニトリ', '東京インテリア', 'イオン',
            'ヤマダ', 'ビックカメラ', 'ヨドバシ', 'コジマ', 'ケーズ', 'エディオン',
            'ドンキ', 'ユニクロ', 'GU', '無印', 'しまむら', '西松屋',
            'スシロー', 'くら寿司', 'ガスト', 'サイゼ', 'マック', 'マクド',
            'スタバ', 'ドトール', 'タリーズ', 'コメダ',
            '埼玉', 'クリニック', '病院', '薬局', '医院',
            # 銀行・郵便局
            'ゆうちょ銀行', '三菱UFJ', '三井住友', 'みずほ',
            # 駐車場
            '名鉄協商', 'タイムズ', 'リパーク', 'NPC24H',
            # 公共料金
            '名古屋市上下水道局', '上下水道',
            # 追加ベンダー
            'ALPHA HOME', 'αホーム', 'アルファホーム',
            'エフアンドエム',
            '中部大学幸友会', '幸友会',
            '中部電力ミライズ', '中部ミライズ',
            'PCワールド', 'ＰＣワールド', 'PC ワールド', 'Ｐ Ｃワールド',
            '建築ソフト', '建設ソフト',
            'フロンティア',
            'NTPシステム',
        ]
        for keyword in vendor_keywords:
            if keyword in name:
                result["vendor"] = keyword
                break

        return result

    def _extract_vendor_fallback(self, text: str) -> str:
        """
        raw_textから取引先名をフォールバック抽出

        OCRのパース失敗時に、より緩いパターンで取引先名を抽出

        Args:
            text: OCRで取得したraw_text

        Returns:
            抽出した取引先名（見つからない場合は空文字）
        """
        # NFKC正規化
        text = unicodedata.normalize('NFKC', text)

        # よく出てくる店舗・企業名のキーワード（拡充）
        known_vendors = [
            # 小売店
            'セリア', 'ニトリ', '東京インテリア', 'ダイソー', 'キャンドゥ', 'ワッツ',
            'セブンイレブン', 'セブン-イレブン', 'ローソン', 'ファミリーマート', 'ファミマ',
            'イオン', 'マックスバリュ', 'イトーヨーカドー', 'アピタ', 'ピアゴ',
            'ヤマダ電機', 'ビックカメラ', 'ヨドバシカメラ', 'コジマ', 'ケーズデンキ',
            'エディオン', 'ノジマ', 'ドン・キホーテ', 'ドンキホーテ',
            'ユニクロ', 'GU', '無印良品', 'しまむら', '西松屋',
            # 飲食
            'スシロー', 'くら寿司', 'はま寿司', 'ガスト', 'バーミヤン', 'サイゼリヤ',
            'マクドナルド', 'ミスタードーナツ', 'モスバーガー',
            'スターバックス', 'ドトール', 'タリーズ', 'コメダ珈琲',
            # ドラッグストア・薬局
            'スギ薬局', 'ウエルシア', 'マツモトキヨシ', 'ツルハ', 'サンドラッグ',
            'クスリのアオキ', 'コスモス薬品', 'クリエイト',
            # ホームセンター
            'カインズ', 'コメリ', 'コーナン', 'ホーマック', 'ナフコ', 'DCM',
            # 物流・運輸
            '愛知運輸', '佐川急便', 'ヤマト運輸', '日本郵便', '日本郵政',
            # 通販・事務用品
            'アスクル', 'モノタロウ', 'ミスミ', 'たのめーる',
            # 公共
            '名古屋市', '愛知県', '都市整備公社', '公社',
            '名古屋市上下水道局', '上下水道局',
            # 医療
            'クリニック', '病院', '医院', '薬局', '診療所',
            # 追加ベンダー
            'ALPHA HOME', 'αホーム', 'アルファホーム',
            'エフアンドエム',
            '中部大学幸友会', '幸友会',
            '中部電力ミライズ', '中部ミライズ',
            'PCワールド', 'ＰＣワールド', 'PC ワールド', 'Ｐ Ｃワールド',
            '建築ソフト', '建設ソフト',
            'フロンティア',
            'NTPシステム',
        ]

        for vendor in known_vendors:
            if vendor in text:
                return vendor

        # 会社形式パターン（テキスト全体から）
        company_patterns = [
            r'(株式会社[\u4e00-\u9fff\u30a0-\u30ffA-Za-z]+)',
            r'([\u4e00-\u9fff\u30a0-\u30ffA-Za-z]+株式会社)',
            r'(有限会社[\u4e00-\u9fff\u30a0-\u30ffA-Za-z]+)',
            r'([\u4e00-\u9fff\u30a0-\u30ffA-Za-z]+有限会社)',
            r'(合同会社[\u4e00-\u9fff\u30a0-\u30ffA-Za-z]+)',
            r'(医療法人[\u4e00-\u9fff\u30a0-\u30ffA-Za-z]+)',
        ]

        for pattern in company_patterns:
            match = re.search(pattern, text)
            if match:
                vendor = match.group(1).strip()
                # 除外条件（自社名・敬称等）
                exclude_words = ['御中', '様', '行', '宛', '殿', '宛先', '請求先', '発行', '東海インプル建設']
                if len(vendor) >= 4 and not any(w in vendor for w in exclude_words):
                    return vendor[:30]  # 最大30文字

        return ""

    def add_to_manual_queue(
        self,
        pdf_path: Path,
        result: SmartOCRResult,
        reason: str = "low_confidence"
    ) -> None:
        """
        低信頼度PDFを手動キューに登録

        Args:
            pdf_path: 元PDFのパス
            result: OCR結果
            reason: 登録理由
        """
        queue_dir = MANUAL_QUEUE_DIR
        queue_dir.mkdir(parents=True, exist_ok=True)

        # PDFをコピー
        dest_path = queue_dir / pdf_path.name
        if not dest_path.exists():
            shutil.copy(pdf_path, dest_path)

        # キューJSONに登録
        queue_file = queue_dir / "queue.json"
        if queue_file.exists():
            queue = json.loads(queue_file.read_text(encoding="utf-8"))
        else:
            queue = []

        # 既存エントリを確認
        existing = [q for q in queue if q.get("file") == pdf_path.name]
        if existing:
            self.logger.info(f"既にキューに登録済み: {pdf_path.name}")
            return

        queue.append({
            "file": pdf_path.name,
            "timestamp": datetime.now().isoformat(),
            "partial_result": {
                "vendor_name": result.vendor_name,
                "issue_date": result.issue_date,
                "amount": result.amount,
                "invoice_number": result.invoice_number
            },
            "confidence": result.confidence,
            "reason": reason
        })

        queue_file.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        self.logger.info(f"手動キューに登録: {pdf_path.name} (理由: {reason})")

    def process(
        self,
        pdf_path: Path,
        output_dir: Path = None,
        skip_preprocess: bool = False,
        auto_queue: bool = True,
        debug_all: bool = False
    ) -> SmartOCRResult:
        """
        PDFをスマートOCR処理

        Args:
            pdf_path: 入力PDFパス
            output_dir: 前処理済みPDFの出力先
            skip_preprocess: 前処理をスキップするか
            auto_queue: 低信頼度時に自動的にキューに追加するか
            debug_all: 全ファイルでデバッグログを出力（通常はNG時のみ）

        Returns:
            処理結果
        """
        pdf_path = Path(pdf_path)
        result = SmartOCRResult()

        if not pdf_path.exists():
            result.error = f"ファイルが存在しません: {pdf_path}"
            return result

        # デバッグセッション（debug_loggerが設定されている場合）
        debug_session: DebugSession = None

        try:
            self.logger.info(f"スマートOCR処理開始: {pdf_path.name}")

            # 1. 前処理（回転・傾き・影除去・コントラスト調整等）
            if not skip_preprocess:
                preprocess_result = self.preprocessor.preprocess(
                    pdf_path,
                    output_dir=output_dir,
                    do_deskew=True,
                    do_enhance=False,  # YomiTokuに任せる
                    do_shadow_removal=True,
                    do_border=False,     # A/Bテスト確定: OFF（YomiTokuには逆効果）
                    do_sharpen=False,    # A/Bテスト: OFF
                    do_stretch=False,    # A/Bテスト: OFF（RGB→Gray変換による劣化防止）
                    do_thickness_adjust=False,  # A/Bテスト: OFF（RGB→Gray変換による劣化防止）
                    skew_threshold=SKEW_THRESHOLD_DEFAULT,
                    force_4way_rotation=True
                )

                if not preprocess_result.success:
                    result.error = f"前処理エラー: {preprocess_result.error}"
                    return result

                # 極端な傾き（25度以上）の場合は2回目の前処理を実行
                if abs(preprocess_result.skew_angle) >= EXTREME_SKEW_THRESHOLD:
                    self.logger.info(
                        f"極端な傾き検出: {preprocess_result.skew_angle:.1f}度 → 2回目前処理実行"
                    )
                    preprocess_result2 = self.preprocessor.preprocess(
                        preprocess_result.output_path,
                        output_dir=output_dir,
                        do_deskew=True,
                        do_enhance=True,  # 2回目は画像強調も適用
                        do_shadow_removal=True,
                        skew_threshold=0.3,  # より厳しい閾値
                        force_4way_rotation=True
                    )
                    if preprocess_result2.success:
                        preprocess_result = preprocess_result2
                        self.logger.info(
                            f"2回目前処理完了: 傾き={preprocess_result.skew_angle:.1f}度"
                        )

                # 前処理情報を保存
                result.preprocess_info = {
                    "rotated": preprocess_result.rotated,
                    "rotation_angle": preprocess_result.rotation_angle,
                    "deskewed": preprocess_result.deskewed,
                    "skew_angle": preprocess_result.skew_angle,
                    "shadow_removed": preprocess_result.shadow_removed
                }

                # 前処理済みPDFを使用
                ocr_target = preprocess_result.output_path
            else:
                ocr_target = pdf_path

            # 2. OCR実行（YomiToku）
            # カスケードモードの場合: まずliteで実行、欠損時のみfullで再実行
            if self.cascade_mode:
                # 1st pass: lite=True
                ocr_result = self.get_ocr_processor(lite=True).process_pdf(ocr_target)
                result.preprocess_info["cascade_1st_pass"] = "lite"

                # 欠損チェック（vendor空 or date空 or amount=0）
                has_missing = (
                    not ocr_result.vendor_name or
                    not ocr_result.issue_date or
                    ocr_result.amount == 0
                )

                if has_missing:
                    missing_info = []
                    if not ocr_result.vendor_name:
                        missing_info.append("vendor")
                    if not ocr_result.issue_date:
                        missing_info.append("date")
                    if ocr_result.amount == 0:
                        missing_info.append("amount")

                    self.logger.info(
                        f"lite失敗（欠損: {', '.join(missing_info)}）→ フルモデルで再処理"
                    )

                    # 2nd pass: lite=False（フルモデル）
                    ocr_result = self.get_ocr_processor(lite=False).process_pdf(ocr_target)
                    result.preprocess_info["cascade_2nd_pass"] = "full"
                    result.preprocess_info["cascade_reason"] = missing_info
            else:
                # 通常モード（lite_modeの設定に従う）
                ocr_result = self.ocr_processor.process_pdf(ocr_target)

            # 結果をコピー
            result.vendor_name = ocr_result.vendor_name
            result.issue_date = ocr_result.issue_date
            result.amount = ocr_result.amount
            result.invoice_number = ocr_result.invoice_number
            result.raw_text = ocr_result.raw_text

            # 診断用フィールドをコピー
            result.line_info = getattr(ocr_result, "line_info", [])
            result.line_count = getattr(ocr_result, "line_count", 0)
            result.image_height = getattr(ocr_result, "image_height", 0)

            # 2.3 YomiToku結果が不十分な場合、EasyOCRでフォールバック
            yomitoku_score = self.evaluate_confidence(ocr_result)
            if yomitoku_score < 0.5 and EASYOCR_AVAILABLE and self.easyocr_processor:
                self.logger.info(f"YomiToku信頼度低 ({yomitoku_score:.2f}) → EasyOCRフォールバック")
                try:
                    easyocr_result = self.easyocr_processor.process_pdf(ocr_target)
                    easyocr_score = self.evaluate_confidence(easyocr_result)

                    self.logger.info(f"EasyOCR信頼度: {easyocr_score:.2f}")

                    # EasyOCRの方が良い場合は結果を採用
                    if easyocr_score > yomitoku_score:
                        self.logger.info("EasyOCR結果を採用")
                        ocr_result = easyocr_result
                        result.vendor_name = ocr_result.vendor_name
                        result.issue_date = ocr_result.issue_date
                        result.amount = ocr_result.amount
                        result.invoice_number = ocr_result.invoice_number
                        result.raw_text = ocr_result.raw_text
                        result.preprocess_info["ocr_engine"] = "easyocr"
                    else:
                        # YomiTokuの結果をベースに、EasyOCRで不足項目を補完
                        if not result.vendor_name and easyocr_result.vendor_name:
                            result.vendor_name = easyocr_result.vendor_name
                            self.logger.info(f"EasyOCRから取引先補完: {easyocr_result.vendor_name}")
                        if not result.issue_date and easyocr_result.issue_date:
                            result.issue_date = easyocr_result.issue_date
                            self.logger.info(f"EasyOCRから日付補完: {easyocr_result.issue_date}")
                        if result.amount == 0 and easyocr_result.amount > 0:
                            result.amount = easyocr_result.amount
                            ocr_result.amount = easyocr_result.amount
                            self.logger.info(f"EasyOCRから金額補完: {easyocr_result.amount}")
                        result.preprocess_info["ocr_engine"] = "yomitoku+easyocr"
                except Exception as e:
                    self.logger.warning(f"EasyOCRフォールバック失敗: {e}")
                    result.preprocess_info["ocr_engine"] = "yomitoku"
            else:
                result.preprocess_info["ocr_engine"] = "yomitoku"

            # 2.5 金額が取れなかった場合、raw_textから再抽出を試みる
            if result.amount == 0 and result.raw_text:
                fallback_amount = self._extract_amount_fallback(result.raw_text)
                if fallback_amount > 0:
                    result.amount = fallback_amount
                    ocr_result.amount = fallback_amount  # 信頼度計算用にも反映
                    self.logger.info(f"フォールバック金額抽出成功: {fallback_amount}")

            # 2.6 ファイル名からの情報抽出（OCRで取れなかった項目を補完）
            filename_data = self._extract_from_filename(pdf_path.name)
            filename_used = False

            if result.amount == 0 and filename_data["amount"] > 0:
                result.amount = filename_data["amount"]
                ocr_result.amount = filename_data["amount"]
                filename_used = True
                self.logger.info(f"ファイル名から金額抽出: {filename_data['amount']}")

            if not result.issue_date and filename_data["date"]:
                result.issue_date = filename_data["date"]
                ocr_result.issue_date = filename_data["date"]
                filename_used = True
                self.logger.info(f"ファイル名から日付抽出: {filename_data['date']}")

            if not result.vendor_name and filename_data["vendor"]:
                result.vendor_name = filename_data["vendor"]
                ocr_result.vendor_name = filename_data["vendor"]
                filename_used = True
                self.logger.info(f"ファイル名から店舗抽出: {filename_data['vendor']}")

            # 2.7 取引先名がまだ取れていない場合、raw_textから再抽出
            if not result.vendor_name and result.raw_text:
                fallback_vendor = self._extract_vendor_fallback(result.raw_text)
                if fallback_vendor:
                    result.vendor_name = fallback_vendor
                    ocr_result.vendor_name = fallback_vendor
                    self.logger.info(f"フォールバック取引先抽出: {fallback_vendor}")

            # 2.8 T番号（事業者登録番号）から会社名を検索
            if not result.vendor_name and result.invoice_number:
                t_number_vendor = self._lookup_vendor_by_t_number(result.invoice_number)
                if t_number_vendor:
                    result.vendor_name = t_number_vendor
                    ocr_result.vendor_name = t_number_vendor
                    self.logger.info(f"T番号から会社名取得: {result.invoice_number} → {t_number_vendor}")

            # 2.9 自社名除外チェック（全抽出パス共通）
            # 請求書の「宛先」として自社名が抽出されるケースを除外
            self_company_keywords = ['東海インプル建設', '東海インプル']
            if result.vendor_name:
                for kw in self_company_keywords:
                    if kw in result.vendor_name:
                        self.logger.warning(f"自社名検出 → 除外: {result.vendor_name}")
                        result.vendor_name = ""
                        ocr_result.vendor_name = ""
                        break

            # 2.10 既知ベンダー優先マッチング（raw_textから既知ベンダーを検索）
            # OCRが誤ったベンダー名を抽出した場合でも、raw_text内に既知ベンダーがあれば優先
            known_vendor_priority = [
                # 正式名称とキーワードのペア: (正式名称, [キーワードリスト])
                # 公共料金（自社名より優先して検出）
                ('名古屋市上下水道局', ['名古屋市上下水道局', '上下水道局', '上下水道']),
                ('中部電力ミライズ', ['中部電力ミライズ', '中部ミライズ']),
                # 企業
                ('中部大学幸友会', ['中部大学幸友会', '幸友会']),
                ('建築ソフト', ['建築ソフト', '建設ソフト']),
                ('ALPHA HOME', ['ALPHA HOME', 'αホーム', 'アルファホーム']),
                ('エフアンドエム', ['エフアンドエム']),
                ('PCワールド', ['PCワールド', 'ＰＣワールド', 'PC ワールド', 'Ｐ Ｃワールド', '戸・ワールド', 'ワールド刈谷']),
                ('フロンティア', ['フロンティア', 'ﾌﾛﾝﾃｨｱ']),
                ('NTPシステム', ['NTPシステム']),
                ('名鉄協商', ['名鉄協商']),
                ('ゆうちょ銀行', ['ゆうちょ銀行']),
                ('クオカード', ['クオカード', 'QUOカード']),
            ]
            if result.raw_text:
                raw_text_normalized = unicodedata.normalize('NFKC', result.raw_text)
                for official_name, keywords in known_vendor_priority:
                    for kw in keywords:
                        if kw in raw_text_normalized:
                            # 既にその正式名称が設定されている場合はスキップ
                            if result.vendor_name == official_name:
                                break
                            self.logger.info(f"既知ベンダー優先: '{kw}' 検出 → {official_name} (旧: {result.vendor_name or '(なし)'})")
                            result.vendor_name = official_name
                            ocr_result.vendor_name = official_name
                            break
                    else:
                        continue
                    break  # 見つかったらループを抜ける

            if filename_used:
                result.preprocess_info["filename_extraction"] = True

            # 2.11 ファイル名の数字と金額の一致チェック（誤認識防止）
            pdf_stem = Path(pdf_path).stem if isinstance(pdf_path, (str, Path)) else ""
            try:
                stem_num = int(pdf_stem)
            except (ValueError, TypeError):
                stem_num = None

            if stem_num is not None and result.amount == stem_num and result.amount < 1000:
                self.logger.warning(
                    f"ファイル名数字と金額が一致（疑わしい）: amount={result.amount}, stem={pdf_stem}"
                )
                result.amount = 0
                ocr_result.amount = 0

            # 3. 信頼度判定（フォールバック後のocr_resultを使用）
            result.confidence = self.evaluate_confidence(ocr_result)

            # 4. 必須フィールド判定（楽楽精算アップロード要件）
            # 必須: 取引日、取引先名、金額（AMOUNT_MIN以上）
            missing_fields = []
            if not result.issue_date:
                missing_fields.append("取引日")
            if not result.vendor_name:
                missing_fields.append("取引先名")
            if result.amount < AMOUNT_MIN:
                missing_fields.append("金額")
                if result.amount > 0:
                    self.logger.warning(
                        f"金額が最小閾値未満: {result.amount}円 < {AMOUNT_MIN}円 → 手動確認必要"
                    )

            result.missing_fields = missing_fields

            # 成功判定: 全必須フィールドが揃っている場合のみ成功
            if missing_fields:
                result.requires_manual = True
                result.success = False
                self.logger.warning(
                    f"必須フィールド不足: {', '.join(missing_fields)} "
                    f"→ 担当者へメール通知が必要"
                )

                # 自動キュー登録
                if auto_queue:
                    self.add_to_manual_queue(pdf_path, result, reason="missing_fields")
            else:
                result.success = True
                result.requires_manual = False
                self.logger.info(
                    f"OCR完了（アップロード可能）: 信頼度={result.confidence:.2f}, "
                    f"vendor={result.vendor_name}, "
                    f"date={result.issue_date}, "
                    f"amount={result.amount}"
                )

            # デバッグログ保存（NG時または debug_all 時）
            if self.debug_logger and (not result.success or debug_all):
                debug_session = self.debug_logger.create_session(pdf_path.name)

                # 前処理情報を保存
                debug_session.save_preprocess_info(result.preprocess_info)

                # OCR結果を保存
                debug_session.save_ocr_result(result)

                # 抽出フィールドを保存
                debug_session.save_extracted_fields(
                    fields={
                        "vendor_name": result.vendor_name,
                        "issue_date": result.issue_date,
                        "amount": result.amount,
                        "invoice_number": result.invoice_number
                    },
                    confidence=result.confidence,
                    missing_fields=result.missing_fields
                )

                # 失敗分析を実行・保存
                analysis = debug_session.finalize(result)

                # サマリー用に結果を追加
                self.debug_logger.add_result(pdf_path.name, result, analysis)

                self.logger.info(f"デバッグログ保存: {debug_session.session_dir}")

        except Exception as e:
            result.error = str(e)
            self.logger.error(f"スマートOCRエラー: {e}")
            import traceback
            traceback.print_exc()

        return result

    def process_batch(
        self,
        pdf_dir: Path,
        output_dir: Path = None,
        dry_run: bool = False
    ) -> List[SmartOCRResult]:
        """
        ディレクトリ内の全PDFをバッチ処理

        Args:
            pdf_dir: PDFディレクトリ
            output_dir: 出力ディレクトリ
            dry_run: ドライラン（実際の処理をしない）

        Returns:
            処理結果のリスト
        """
        pdf_dir = Path(pdf_dir)
        results = []

        pdf_files = list(pdf_dir.glob("*.pdf"))
        self.logger.info(f"バッチ処理開始: {len(pdf_files)}ファイル")

        for pdf_path in pdf_files:
            if dry_run:
                self.logger.info(f"[DRY-RUN] {pdf_path.name}")
                continue

            result = self.process(pdf_path, output_dir)
            results.append(result)

        # サマリー
        success_count = sum(1 for r in results if r.success)
        manual_count = sum(1 for r in results if r.requires_manual)
        error_count = sum(1 for r in results if r.error)

        self.logger.info(
            f"バッチ処理完了: 成功={success_count}, "
            f"手動対応={manual_count}, エラー={error_count}"
        )

        return results


def main():
    """テスト実行"""
    import argparse

    parser = argparse.ArgumentParser(description="スマートOCR処理")
    parser.add_argument("pdf", nargs="?", help="PDFファイルパス")
    parser.add_argument("--batch", action="store_true", help="バッチ処理モード")
    parser.add_argument("--dry-run", action="store_true", help="ドライラン")
    parser.add_argument("--gpu", action="store_true", help="GPU使用")
    parser.add_argument("--no-lite", action="store_true", help="フルモデル使用")

    args = parser.parse_args()

    # ロガー設定
    from common.logger import setup_logger
    setup_logger("pdf_ocr_smart")

    processor = SmartOCRProcessor(
        use_gpu=args.gpu,
        lite_mode=not args.no_lite
    )

    if args.batch:
        # バッチ処理
        sample_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\sample PDF")
        results = processor.process_batch(sample_dir, dry_run=args.dry_run)

        print("\n=== バッチ処理結果 ===")
        for r in results:
            status = "OK" if r.success else ("MANUAL" if r.requires_manual else "ERROR")
            missing = f" 不足: {', '.join(r.missing_fields)}" if r.missing_fields else ""
            print(f"[{status}] conf={r.confidence:.2f} amt={r.amount} date={r.issue_date} vendor={r.vendor_name}{missing}")

    elif args.pdf:
        # 単一ファイル処理
        result = processor.process(Path(args.pdf))

        print("\n=== スマートOCR結果 ===")
        print(f"取引先名: {result.vendor_name}")
        print(f"発行日: {result.issue_date}")
        print(f"金額: {result.amount:,}円" if result.amount else "金額: -")
        print(f"事業者登録番号: {result.invoice_number}")
        print(f"信頼度: {result.confidence:.2%}")
        print(f"成功（アップロード可能）: {result.success}")
        print(f"手動対応必要: {result.requires_manual}")
        if result.missing_fields:
            print(f"不足フィールド: {', '.join(result.missing_fields)}")
        if result.error:
            print(f"エラー: {result.error}")

        print("\n--- 前処理情報 ---")
        for k, v in result.preprocess_info.items():
            print(f"  {k}: {v}")

    else:
        # サンプルテスト
        sample_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\sample PDF")
        test_files = [
            "(株)ニトリ.pdf",
            "0109セリア(百均)買物.pdf",
        ]

        print("=== スマートOCRテスト ===")
        print(f"信頼度閾値: {CONFIDENCE_THRESHOLD}")
        print("=" * 60)

        for fname in test_files:
            pdf_path = sample_dir / fname
            if not pdf_path.exists():
                print(f"\n[SKIP] {fname}")
                continue

            print(f"\n--- {fname} ---")
            result = processor.process(pdf_path)

            status = "OK" if result.success else ("MANUAL" if result.requires_manual else "ERROR")
            print(f"  ステータス: {status}")
            print(f"  信頼度: {result.confidence:.2%}")
            print(f"  取引先: {result.vendor_name}")
            print(f"  日付: {result.issue_date}")
            print(f"  金額: {result.amount:,}円" if result.amount else "  金額: -")
            if result.error:
                print(f"  エラー: {result.error}")


if __name__ == "__main__":
    main()
