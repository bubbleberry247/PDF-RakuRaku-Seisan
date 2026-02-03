# OCR精度向上 比較評価計画

## 目的
現行OCR方式（EasyOCRProcessor）を維持したまま、6つの改善手法を**独立した比較実験**として実装・評価する。有効性が証明されたもののみ本番パイプラインに統合検討する。

## 現状（ベースライン: セッション11, 73ファイル）
| 項目 | スコア |
|------|--------|
| amount | 94.5% (69/73) |
| date | 95.9% (70/73) |
| vendor | 97.3% (71/73) |
| ALL-3 | 93.2% (68/73) |

残NG 5件は全てLOW（OCRエンジン限界/スキャン品質）。

## 現行アーキテクチャ
- **本番**: `pdf_ocr_smart.py` → YomiToku(primary) → Adobe PDF Services(fallback)
- **リグレッション**: `scratchpad/run_regression.py` → `pdf_ocr_easyocr.py`（73ファイル）
- **前処理**: `pdf_preprocess.py`（回転・傾き・影除去）

## 比較実験の共通設計

### 評価フレームワーク
- `scratchpad/run_comparison.py` を新規作成
- 73ファイル同一テストセットで各手法を実行
- 出力: amount/date/vendor/ALL-3 の正解率 + 処理時間
- 既存 `ocr_cache.json` のベースライン結果と比較

### 共通インターフェース
```python
@dataclass
class ComparisonResult:
    amount: int
    issue_date: str      # YYYYMMDD
    vendor_name: str
    raw_text: str
    confidence: float
    method: str          # 手法名
    elapsed_ms: int      # 処理時間
```

---

## 手法1: PDF埋め込みテキスト抽出（優先度: 最高）

### 狙い
テキスト埋め込みPDFはOCR不要。pymupdf/pdfminer.sixで直接テキスト取得 → OCRより高精度・高速。

### 実装
- **ファイル**: `scratchpad/method1_pdf_text.py`
- **処理フロー**:
  1. `fitz.open(pdf)` でテキスト抽出（`page.get_text()`）
  2. テキスト量が閾値以上（例: 50文字+）→ テキスト埋め込みPDFと判定
  3. 抽出テキストから `parse_expense_data()` 相当のロジックで amount/date/vendor 抽出
  4. テキスト不足の場合 → 「OCR必要」フラグを返す
- **依存**: `pymupdf`（既にインストール済み）
- **期待効果**: テキスト埋め込みPDF（73件中の推定30-40件）で精度100%・処理速度10倍

### 検証
- 73件中テキスト埋め込みPDFの件数を特定
- テキスト抽出のみで amount/date/vendor が取れる件数を計測
- EasyOCR結果との差分を確認

---

## 手法2: bbox座標ベースフィールド抽出（優先度: 高）

### 狙い
OCR出力の `(text, confidence, bbox)` を活用し、「合計」「請求金額」等のラベル位置から右隣・下の値を空間的に取得。

### 実装
- **ファイル**: `scratchpad/method2_bbox_extract.py`
- **処理フロー**:
  1. EasyOCR（またはYomiToku）で `[(text, conf, [x1,y1,x2,y2])]` を取得
  2. ラベル辞書（「合計」「請求金額」「発行日」等）でラベル要素を検索
  3. ラベルのbboxから右方向/下方向に最も近い数値/日付要素を抽出
  4. 複数候補がある場合はスコアリングで最適選択
- **依存**: EasyOCRの `readtext()` 出力（bbox付き）
- **期待効果**: Phase 3（行結合）の誤結合問題を回避、ラベル近接で精度向上

### 検証
- 残NG 5件のうち amount NG（管理地草刈り等）で改善するか確認
- ラベル検出率（「合計」等が見つかる割合）を計測

---

## 手法3: マルチレシピ前処理＋スコア選択（優先度: 中）

### 狙い
単一の前処理パイプラインではなく、複数の二値化/ノイズ除去レシピを並列実行し、OCR結果のスコアが最も高いものを採用。

### 実装
- **ファイル**: `scratchpad/method3_multi_recipe.py`
- **レシピ一覧**:
  1. Sauvola二値化（局所適応）
  2. Adaptive Otsu（大域+局所）
  3. デノイズ（fastNlMeansDenoising）
  4. 膨張（dilate）→ かすれ文字補強
  5. 収縮（erode）→ にじみ除去
  6. 原画像（前処理なし）
- **スコア関数**: OCR confidence平均 × テキスト文字数 × フィールド抽出数
- **依存**: OpenCV（既にインストール済み）
- **期待効果**: 手書き/ドットマトリクス/スキャン品質問題の改善

### 検証
- 安城印刷（手書き）、管理地草刈り（文字混同）で改善するか
- 処理時間のオーバーヘッド計測（6レシピ×OCR）

---

## 手法4: タイル分割OCR（優先度: 中）

### 狙い
A4を3×3グリッドに分割し、各タイルでOCR実行。小さい文字や表の認識精度向上。

### 実装
- **ファイル**: `scratchpad/method4_tile_ocr.py`
- **処理フロー**:
  1. PDF→画像変換（DPI=300）
  2. 3×3（9タイル）に分割（隣接タイルと10%オーバーラップ）
  3. 各タイルでEasyOCR実行
  4. 重複テキスト除去（オーバーラップ領域）
  5. 全タイル結果を座標順に結合
- **依存**: EasyOCR + OpenCV
- **期待効果**: 小文字・表形式データの認識率向上

### 検証
- ETC利用明細（個別通行料テーブル）の認識精度
- 全体的なテキスト量の変化（タイルOCR vs フルページOCR）

---

## 手法5: PaddleOCR再導入（優先度: 低）

### 狙い
EasyOCRの3rdフォールバックとして、PaddleOCRを再導入。Python 3.13互換性改善。

### 実装
- **ファイル**: `scratchpad/method5_paddleocr.py`
- **処理フロー**:
  1. `paddleocr.PaddleOCR(lang='japan')` 初期化
  2. PDF→画像→PaddleOCR実行
  3. 結果を共通フォーマットに変換
- **依存**: `paddlepaddle`, `paddleocr`（要インストール確認）
- **期待効果**: EasyOCRが苦手なフォント/レイアウトの補完
- **リスク**: Python 3.13互換性、インストール重量

### 検証
- まずインストール可否を確認
- EasyOCR NG件でPaddleOCRが改善するか

---

## 手法6: VLM（Vision-Language Model）（優先度: 低）

### 狙い
最終フォールバックとして、VLM（Japanese-Receipt-VL-3B-JSON等）でPDF画像から直接JSON抽出。

### 実装
- **ファイル**: `scratchpad/method6_vlm.py`
- **処理フロー**:
  1. PDF→画像変換
  2. VLMにプロンプト付きで画像投入（「この請求書のvendor/date/amountをJSONで」）
  3. JSON応答をパース
- **候補モデル**:
  - `Japanese-Receipt-VL-3B-JSON`（ローカル実行、3B軽量）
  - Claude Vision API（高精度だがAPIコスト発生）
  - GPT-4o Vision（同上）
- **リスク**: ローカルVLMはGPU必要、API版はコスト発生
- **期待効果**: OCR困難なPDF（手書き、ドットマトリクス等）の最終手段

### 検証
- 残NG 5件（特に靴下15544、安城印刷）で改善するか
- 処理時間・コスト計測

---

## 実装順序と判定基準

### フェーズ1（即時実施）
1. **手法1（PDF text）** → テキスト埋め込みPDF判定 + 抽出テスト
2. **手法2（bbox）** → ラベル近接抽出テスト

### フェーズ2（フェーズ1結果後）
3. **手法3（multi-recipe）** → 前処理バリエーションテスト
4. **手法4（tile OCR）** → タイル分割テスト

### フェーズ3（必要に応じて）
5. **手法5（PaddleOCR）** → インストール確認 + テスト
6. **手法6（VLM）** → モデル選定 + テスト

### 統合判定基準
各手法の採用条件:
- ALL-3スコアがベースライン（93.2%）を**下回らない**こと
- 改善対象の項目で**1件以上の改善**があること
- 処理時間が許容範囲内（1ファイルあたり30秒以内）

---

## 変更対象ファイル

| ファイル | 変更内容 |
|---------|---------|
| `scratchpad/run_comparison.py` | 新規: 比較評価フレームワーク |
| `scratchpad/method1_pdf_text.py` | 新規: PDF埋め込みテキスト抽出 |
| `scratchpad/method2_bbox_extract.py` | 新規: bbox座標ベース抽出 |
| `scratchpad/method3_multi_recipe.py` | 新規: マルチレシピ前処理 |
| `scratchpad/method4_tile_ocr.py` | 新規: タイル分割OCR |
| `scratchpad/method5_paddleocr.py` | 新規: PaddleOCR |
| `scratchpad/method6_vlm.py` | 新規: VLM抽出 |

**既存ファイルの変更: なし**（比較実験のため全て新規ファイル）

## 検証方法
1. 各手法を `scratchpad/run_comparison.py --method N` で実行
2. 73ファイルの結果をベースライン（`ocr_cache.json`）と比較
3. 改善/悪化の差分レポート出力
4. フェーズ1完了後に結果レビュー → フェーズ2以降の優先度調整
