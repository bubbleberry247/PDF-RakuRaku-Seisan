# OCR前処理 A/Bテスト知見

## 概要

2026年1月のA/Bテストにより、YomiToku OCRエンジンに対する最適な前処理設定を確定。

---

## テスト結果サマリー

| テスト | 設定 | OK率 | 結果 |
|--------|------|------|------|
| ベースライン (dpi=200) | 全新オプションOFF | **60.6%** (20/33) | 基準 |
| テスト1 (dpi=300) | 全新オプションOFF | **60.6%** (20/33) | dpiは影響なし |
| テスト2 (dpi=300) | do_border=Trueのみ | 57.6% (19/33) | -3% 逆効果 |
| 全ON | 全新オプションON | 54.5% (18/33) | -6% 逆効果 |

---

## 確定設定

```python
# pdf_ocr_smart.py 532-538行目
do_deskew=True,
do_enhance=False,       # YomiTokuに任せる
do_shadow_removal=True,
do_border=False,        # OFF（YomiTokuには逆効果）
do_sharpen=False,       # OFF
do_stretch=False,       # OFF（RGB→Gray変換で劣化）
do_thickness_adjust=False,  # OFF（RGB→Gray変換で劣化）
```

---

## 学んだこと

### 1. YomiTokuには追加前処理が不要
- YomiToku自体が高品質な内部前処理を持つ
- 外部で追加の画像処理を行うと逆効果になる

### 2. RGB→Gray→RGB変換は避けるべき
- `stretch_contrast()` と `adjust_character_thickness()` の両方で発生
- 色空間変換の繰り返しが情報損失を引き起こす
- 解決策: 変換が必要な処理は使用しない

### 3. Tesseract向けTipsはYomiTokuに適用不可
- **白ボーダー追加**: Tesseract推奨だがYomiTokuでは-3%の逆効果
- **コントラストストレッチ**: Tesseract向けだがYomiTokuでは不要
- **文字太さ調整**: 同上
- **教訓**: OCRエンジンごとに最適な前処理は異なる

### 4. dpi設定は影響なし
- dpi=200 と dpi=300 で結果は同一（60.6%）
- 処理速度を考慮すると200dpiでも十分だが、300dpiを維持しても問題なし

---

## 実装済み前処理メソッド（参考）

| メソッド | 説明 | YomiToku効果 |
|----------|------|--------------|
| `add_border()` | 10px白ボーダー | 逆効果（-3%）|
| `stretch_contrast()` | コントラスト正規化 | 逆効果（RGB→Gray→RGB変換で劣化）|
| `adjust_character_thickness()` | 膨張/収縮 | 逆効果（RGB→Gray→RGB変換で劣化）|
| `sharpen_unsharp_mask()` | エッジ強調 | 未検証（OFFで運用）|

---

## 有効な前処理（継続使用）

| 処理 | 説明 | 効果 |
|------|------|------|
| 傾き補正 (deskew) | Hough変換による傾き検出・補正 | 必須 |
| 4方向回転検出 | 0/90/180/270度の自動判定 | 必須 |
| 影除去 | 影検出時のみ実行 | 条件付き有効 |

---

## 検証コマンド

```bash
cd C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools
python test_sample_ocr.py
```

期待結果: OK 20/33 (60.6%)

---

---

## Phase 2: 精度改善手法 (69.2% → 84.6%)

### 改善アプローチ（優先順）

1. **診断ログ強化で原因特定**
   - vendor空時に `line_info`, `line_count`, `image_height` をログ出力
   - 「OCR認識不足」vs「抽出ロジック不足」を切り分け

2. **NG分析 → パターン/ロジック追加**
   - raw_textに文字がある → 抽出パターン追加
   - raw_textが空 → 画像品質問題（ROI or DPI強化）

3. **ファイル名からの抽出強化**
   - `vendor_keywords` リストにキーワード追加
   - 例: `名鉄協商`, `ゆうちょ銀行`, `三井不動産` 等

4. **2段階カスケードOCR**
   - `lite_mode=True` → 欠損時のみ `lite_mode=False` で再処理
   - `--cascade` オプションで有効化

### 診断ログの見方

```json
{
  "raw_text_length": 1234,    // 総文字数
  "line_count": 45,           // 総行数
  "line_info": [              // 上位行（y座標付き）
    {"y": 50, "text": "株式会社..."},
    {"y": 80, "text": "領収書"}
  ],
  "image_height": 3508        // 画像高さ（px）
}
```

| 状況 | 原因 | 対策 |
|------|------|------|
| raw_text_length < 100 | OCR全滅 | DPI 300 or ROI |
| 上部1/3に行がない | OCR上部認識不足 | ROI or 回転確認 |
| 文字はあるがvendor空 | 抽出パターン不足 | パターン追加 |

### 追加したvendor_keywords (pdf_ocr_smart.py)

```python
# 銀行
"ゆうちょ銀行", "三菱UFJ銀行", "三井住友銀行", "みずほ銀行",
# 駐車場
"名鉄協商", "タイムズ", "三井のリパーク", "NPC24H",
# 家具・インテリア
"ニトリ", "IKEA", "東京インテリア",
# 100円ショップ
"セリア", "ダイソー", "キャンドゥ",
```

---

## 更新履歴

- 2026-01-19: Phase 2完了 - 精度改善手法追加 (69.2% → 84.6%)
- 2026-01-19: A/Bテスト完了、設定確定
