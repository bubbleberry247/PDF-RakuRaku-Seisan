# PDF OCR処理 Skill

## 説明
スキャンPDFからテキストを抽出し、請求書・領収書データ（取引先名、日付、金額等）を自動認識するテンプレートを提供

## 使用方法
```
/pdf-ocr --target ~/Projects/my-project
```

## 前提条件
- Python 3.11+
- PyMuPDF, OpenCV, NumPy, Pillow インストール済み
- （オプション）OCRエンジン（Adobe OCR-JA, Tesseract等）

---

## 1. 機能概要

このスキルは以下の機能をテンプレートとして提供:

| 機能 | ファイル | 説明 |
|------|---------|------|
| PDF前処理 | `pdf_preprocess.py` | 回転補正、傾き補正、影除去、画像強調 |
| 回転検出 | `pdf_rotation_detect.py` | 4方向（0/90/180/270度）の自動判定 |
| OCR・データ抽出 | `pdf_ocr.py` | テキスト抽出＋請求書データパース |

---

## 2. テンプレートのセットアップ

### 2.1 ファイルコピー

以下のファイルをプロジェクトにコピー:

```bash
# テンプレートディレクトリからコピー
cp -r templates/*.py ~/Projects/my-project/tools/
```

### 2.2 依存関係インストール

```bash
pip install PyMuPDF opencv-python numpy pillow
```

### 2.3 ロガー設定

`common/logger.py` を作成するか、既存のロギング設定に合わせて修正:

```python
# 最小限のロガー設定
import logging

def get_logger():
    return logging.getLogger(__name__)
```

---

## 3. PDF前処理（pdf_preprocess.py）

### 3.1 基本的な使い方

```python
from pdf_preprocess import PDFPreprocessor

preprocessor = PDFPreprocessor(dpi=200)
result = preprocessor.preprocess(
    pdf_path="input.pdf",
    output_dir="output/",
    do_deskew=True,           # 傾き補正
    do_enhance=False,         # 画像強調（OCRエンジン側に任せる場合はFalse）
    do_shadow_removal=True,   # 影除去（影検出時のみ実行）
    force_4way_rotation=True  # 4方向回転検出
)

print(f"出力: {result.output_path}")
print(f"回転: {result.rotated} ({result.rotation_angle}度)")
print(f"傾き補正: {result.deskewed} ({result.skew_angle:.1f}度)")
```

### 3.2 処理フロー

```
入力PDF
    ↓
1. 傾き検出・補正（Hough変換 + PCA）
    ↓
2. 回転方向検出（4方向: 0/90/180/270度）
    ↓
3. 低解像度の場合はアップスケール
    ↓
4. 影検出・除去（オプション）
    ↓
5. 画像強調（オプション）
    ↓
出力PDF
```

### 3.3 傾き検出アルゴリズム

| 方法 | 特徴 | 用途 |
|------|------|------|
| Hough変換 | 水平線を検出、-20〜+20度の範囲 | メイン（精度高） |
| PCA | テキスト領域の主成分分析 | フォールバック |

**ポイント:**
- CLAHE（適応的ヒストグラム均等化）で薄い印刷も検出可能
- 0.5度以上の傾きがある場合のみ補正

### 3.4 回転方向検出

横長PDF・画像の場合、90度か270度のどちらに回転すべきかを判定:

```python
from pdf_rotation_detect import PDFRotationDetector

detector = PDFRotationDetector(dpi=150)
best_angle = detector.detect_best_rotation(pdf_path)
print(f"推奨回転角度: {best_angle}度")
```

**スコアリング基準:**
- 水平エッジ比率（テキスト行は水平エッジが多い）
- 上部テキスト密度（レシートは上部に店名がある）
- 行連続性（水平プロジェクション）
- Hough変換による水平線検出

---

## 4. OCR・データ抽出（pdf_ocr.py）

### 4.1 基本的な使い方

```python
from pdf_ocr import PDFOCRProcessor

processor = PDFOCRProcessor()
result = processor.process_pdf("invoice.pdf")

print(f"取引先名: {result.vendor_name}")
print(f"発行日: {result.issue_date}")  # YYYYMMDD形式
print(f"金額: {result.amount:,}円")
print(f"事業者登録番号: {result.invoice_number}")
```

### 4.2 抽出可能なデータ

| 項目 | 対応フォーマット |
|------|-----------------|
| 日付 | 西暦（2025年1月9日）、令和（令和7年1月9日）、短縮形式（R7/1/9）、YYYY/MM/DD |
| 金額 | ¥1,234、1,234円、合計:1234、税込1234 等 |
| 事業者登録番号 | T1234567890123（インボイス制度対応） |
| 取引先名 | 株式会社○○、○○株式会社、㈱○○、店舗名 等 |

### 4.3 日付抽出の優先順位

1. 「請求日」「発行日」ラベルの近くにある日付
2. 西暦年月日形式（2025年1月9日）
3. YYYY/MM/DD形式（レシート等）
4. 和暦短縮形式（26年1月9日 → 2026年）
5. R7/1/9形式（令和短縮）

### 4.4 金額抽出のパターン

```python
# 対応パターン例
amount_patterns = [
    r'合計[金額]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?',
    r'請求金額[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?',
    r'税込[金額合計]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?',
    r'[¥\\￥]\s*([\d,，\.]+)\s*[-\-ー]*',  # ¥200- 形式
    # ... 他多数
]
```

### 4.5 ファイル名からの補完

OCRで抽出できなかった情報をファイル名から補完:

```
2025,12,27名鉄協商400.pdf
    → 日付: 20251227
    → 取引先: 名鉄協商
    → 金額: 400円

0109セリア(百均)買物.pdf
    → 日付: 20260109（現在年を推定）
    → 取引先: セリア
```

---

## 5. カスタマイズポイント

### 5.1 取引先名の追加

`pdf_ocr.py` の `special_vendors` リストに追加:

```python
special_vendors = [
    (r'会社名パターン', '正式名称'),
    (r'ENEOS|エネオス', 'ENEOS'),
    # 追加
    (r'新しい取引先', '新しい取引先株式会社'),
]
```

### 5.2 金額パターンの追加

`pdf_ocr.py` の `amount_patterns` リストに追加:

```python
amount_patterns = [
    # 既存パターン...
    # 追加
    r'新しいパターン[:\s]*[¥\\￥]?\s*([\d,]+)',
]
```

### 5.3 OCRエンジンの変更

`pdf_ocr.py` の `run_ocr()` メソッドを修正:

```python
def run_ocr(self, pdf_path: Path) -> Optional[Path]:
    # Adobe OCR-JAの代わりにTesseractを使用
    import pytesseract
    from pdf2image import convert_from_path

    images = convert_from_path(pdf_path)
    text = pytesseract.image_to_string(images[0], lang='jpn')
    # ...
```

---

## 6. ログ設定

### 6.1 共通ロガー（common/logger.py）

```python
import logging
import sys
from pathlib import Path

_logger = None

def setup_logger(name: str, log_dir: Path = None):
    global _logger

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _logger = logger
    return logger

def get_logger():
    global _logger
    if _logger is None:
        _logger = setup_logger("pdf_ocr")
    return _logger
```

---

## 7. 使用例

### 7.1 バッチ処理

```python
from pathlib import Path
from pdf_preprocess import PDFPreprocessor
from pdf_ocr import PDFOCRProcessor

input_dir = Path("./invoices")
output_dir = Path("./processed")
output_dir.mkdir(exist_ok=True)

preprocessor = PDFPreprocessor(dpi=200)
ocr_processor = PDFOCRProcessor()

results = []
for pdf_path in input_dir.glob("*.pdf"):
    # 前処理
    preproc_result = preprocessor.preprocess(pdf_path, output_dir)

    # OCR
    ocr_result = ocr_processor.process_pdf(preproc_result.output_path)

    results.append({
        "file": pdf_path.name,
        "vendor": ocr_result.vendor_name,
        "date": ocr_result.issue_date,
        "amount": ocr_result.amount,
    })

# 結果をCSV出力
import csv
with open("results.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["file", "vendor", "date", "amount"])
    writer.writeheader()
    writer.writerows(results)
```

### 7.2 単一ファイル処理

```python
from pdf_preprocess import PDFPreprocessor
from pdf_ocr import PDFOCRProcessor

# 前処理
preprocessor = PDFPreprocessor()
result = preprocessor.preprocess("receipt.pdf")
print(f"前処理完了: {result.output_path}")

# OCR
processor = PDFOCRProcessor()
data = processor.process_pdf(result.output_path)

print(f"取引先: {data.vendor_name}")
print(f"日付: {data.issue_date}")
print(f"金額: {data.amount:,}円")
```

---

## 8. トラブルシューティング

### 問題1: 回転が逆になる

**原因:** テキスト密度が均一でスコアリングが効かない

**解決策:**
```python
# force_4way_rotation=False で2方向のみ比較
result = preprocessor.preprocess(pdf_path, force_4way_rotation=False)
```

### 問題2: 傾き補正が過剰

**原因:** ノイズや枠線を傾きと誤検出

**解決策:**
```python
# 傾き補正閾値を上げる（デフォルト0.5度）
result = preprocessor.preprocess(pdf_path, skew_threshold=1.0)
```

### 問題3: 金額が抽出できない

**原因:** OCR誤認識またはパターン不一致

**解決策:**
1. `raw_text` を確認して実際のテキストを確認
2. 新しいパターンを `amount_patterns` に追加

```python
result = processor.process_pdf("invoice.pdf")
print(result.raw_text)  # 生テキストを確認
```

### 問題4: PyMuPDFがインストールできない

```bash
# pip でインストール
pip install PyMuPDF

# conda の場合
conda install -c conda-forge pymupdf
```

---

## 9. 参考資料

- PyMuPDF Documentation: https://pymupdf.readthedocs.io/
- OpenCV Python: https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html
- 元実装: `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\`
