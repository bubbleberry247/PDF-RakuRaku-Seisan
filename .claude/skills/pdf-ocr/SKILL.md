# PDF OCR処理 Skill

## 概要
スキャンPDFからテキストを抽出し、請求書・領収書データ（取引先名、日付、金額等）を自動認識

## 前提条件
- Python 3.11+
- PyMuPDF, OpenCV, NumPy, Pillow インストール済み
- （オプション）OCRエンジン（Adobe OCR-JA, Tesseract等）

---

## 1. 機能概要

| 機能 | ファイル | 説明 |
|------|---------|------|
| PDF前処理 | `pdf_preprocess.py` | 回転補正、傾き補正、影除去、画像強調 |
| 回転検出 | `pdf_rotation_detect.py` | 4方向（0/90/180/270度）の自動判定 |
| OCR・データ抽出 | `pdf_ocr.py` | テキスト抽出＋請求書データパース |

---

## 2. PDF前処理（pdf_preprocess.py）

### 2.1 基本的な使い方

```python
from pdf_preprocess import PDFPreprocessor

preprocessor = PDFPreprocessor(dpi=200)
result = preprocessor.preprocess(
    pdf_path="input.pdf",
    output_dir="output/",
    do_deskew=True,           # 傾き補正
    do_enhance=False,         # 画像強調
    do_shadow_removal=True,   # 影除去
    force_4way_rotation=True  # 4方向回転検出
)

print(f"出力: {result.output_path}")
print(f"回転: {result.rotated} ({result.rotation_angle}度)")
print(f"傾き補正: {result.deskewed} ({result.skew_angle:.1f}度)")
```

### 2.2 処理フロー

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

### 2.3 傾き検出アルゴリズム

| 方法 | 特徴 | 用途 |
|------|------|------|
| Hough変換 | 水平線を検出、-20〜+20度の範囲 | メイン（精度高） |
| PCA | テキスト領域の主成分分析 | フォールバック |

---

## 3. OCR・データ抽出（pdf_ocr.py）

### 3.1 基本的な使い方

```python
from pdf_ocr import PDFOCRProcessor

processor = PDFOCRProcessor()
result = processor.process_pdf("invoice.pdf")

print(f"取引先名: {result.vendor_name}")
print(f"発行日: {result.issue_date}")  # YYYYMMDD形式
print(f"金額: {result.amount:,}円")
print(f"事業者登録番号: {result.invoice_number}")
```

### 3.2 抽出可能なデータ

| 項目 | 対応フォーマット |
|------|-----------------|
| 日付 | 西暦（2025年1月9日）、令和（令和7年1月9日）、R7/1/9、YYYY/MM/DD |
| 金額 | ¥1,234、1,234円、合計:1234、税込1234 等 |
| 事業者登録番号 | T1234567890123（インボイス制度対応） |
| 取引先名 | 株式会社○○、○○株式会社、㈱○○、店舗名 等 |

### 3.3 日付抽出の優先順位

1. 「請求日」「発行日」ラベルの近くにある日付
2. 西暦年月日形式（2025年1月9日）
3. YYYY/MM/DD形式（レシート等）
4. 和暦短縮形式（26年1月9日 → 2026年）
5. R7/1/9形式（令和短縮）

### 3.4 ファイル名からの補完

OCRで抽出できなかった情報をファイル名から補完:

```
2025,12,27名鉄協商400.pdf
    → 日付: 20251227
    → 取引先: 名鉄協商
    → 金額: 400円
```

---

## 4. カスタマイズポイント

### 4.1 取引先名の追加

`pdf_ocr.py` の `special_vendors` リストに追加:

```python
special_vendors = [
    (r'会社名パターン', '正式名称'),
    (r'ENEOS|エネオス', 'ENEOS'),
    # 追加
    (r'新しい取引先', '新しい取引先株式会社'),
]
```

### 4.2 金額パターンの追加

```python
amount_patterns = [
    r'合計[金額]?[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?',
    r'請求金額[:\s：]*[¥\\￥]?\s*([\d,，\.]+)\s*円?',
    # 追加
    r'新しいパターン[:\s]*[¥\\￥]?\s*([\d,]+)',
]
```

---

## 5. OCR精度改善手順

### 診断→対策フロー

1. **診断ログ強化で原因特定**
   - vendor空時に `line_info`, `line_count`, `image_height` を出力
   - 「OCR認識不足」vs「抽出ロジック不足」を切り分け

2. **NG分析→対策決定**
   - raw_textに文字あり → パターン追加
   - raw_text空 → 画像品質問題（DPI/ROI）

3. **ファイル名抽出強化**
   - `vendor_keywords` にキーワード追加

4. **カスケードOCR**
   - `lite_mode=True` → 欠損時のみ `lite_mode=False` で再処理

---

## 6. トラブルシューティング

### 問題1: 回転が逆になる
**解決:** `force_4way_rotation=False` で2方向のみ比較

### 問題2: 傾き補正が過剰
**解決:** `skew_threshold=1.0` で閾値を上げる

### 問題3: 金額が抽出できない
**解決:**
1. `raw_text` を確認
2. 新しいパターンを `amount_patterns` に追加

---

## 7. 参照

- **詳細スキル**: `repo:/external-repos/my-claude-skills/pdf-ocr/skill.md`
- **元実装**: `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\`
- **OCR技術ドキュメント**: `repo:/docs/KNOWLEDGE_OCR_PREPROCESSING.md`
