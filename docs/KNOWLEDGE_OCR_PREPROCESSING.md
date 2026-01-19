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

## 更新履歴

- 2026-01-19: A/Bテスト完了、設定確定
