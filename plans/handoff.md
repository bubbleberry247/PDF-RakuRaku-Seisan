# handoff.md（短く・上書き前提）

## Current focus
- シナリオ44 OCR精度改善 - **目標達成済み (84.6%)**

## Done
- AGENTS.md 正本化、CLAUDE.md 入口化（Phase 1）
- SessionStart hook で decisions + handoff 自動注入設定
- 運用ドキュメント7本作成 → v0.2に更新
- **運用体制をOM3に確定**
- **シナリオ37 完了**（レコルAPI統合、PDF保存、メール送信、RKSファイル作成）
- **シナリオ44 OCR精度改善完了** (2026-01-19):
  - **改善前: 69.2% (9/13)** → **改善後: 84.6% (11/13)** 目標80%達成
  - 2段階カスケードOCR実装（lite_mode=True → 欠損時のみ再処理）
  - ファイル名からの取引先抽出強化（銀行・駐車場キーワード追加）
  - 診断用ログ強化（line_info, line_count, image_height追加）
  - NumpyEncoder追加（float32 JSONシリアライズ修正）

## 実装済み機能 (2026-01-19)
1. **2段階カスケードOCR** (pdf_ocr_smart.py)
   - `lite_mode=True` → 欠損時のみ `lite_mode=False` で再処理
   - `--cascade` オプションで有効化
2. **ファイル名からの取引先抽出強化** (pdf_ocr_smart.py)
   - `vendor_keywords` に銀行・駐車場を追加
   - 「名鉄協商」「ゆうちょ銀行」等
3. **診断用ログ強化** (pdf_ocr_yomitoku.py, ocr_debug_logger.py)
   - `line_info`, `line_count`, `image_height` フィールド追加
   - NG時に自動でデバッグログ保存
4. **NumpyEncoder** (ocr_debug_logger.py:24-33)
   - float32 JSON シリアライズエラー修正

## Key learnings (OCR)
1. **YomiTokuには追加前処理が不要** - 内部で高品質な前処理を持つ
2. **RGB→Gray→RGB変換は避けるべき** - 情報損失を引き起こす
3. **Tesseract向けTipsはYomiTokuに適用不可** - 白ボーダー等は逆効果
4. **dpi 200 vs 300 は影響なし** - 300dpi維持で問題なし
5. **カスケード処理が有効** - lite_mode失敗時のフォールバックで精度向上

## 残りのNG（2件）
1. **東京インテリア家具.pdf** - 取引日が欠損（vendorはファイル名から抽出OK）
2. **領収証2025.12.26.pdf** - OCR全滅（raw_text 0文字）、画像品質問題

## Next (top 3)
1. Phase 3: ROI切り出し実装（背景除去で更に精度向上の可能性）
2. マスキング関数実装/既存ログの機微情報チェック（LP-004/LP-005）
3. config/*.xlsxの構造確認 → スキーマ定義完成（CS-001/CS-002）

## Risks / blockers
- 残り2件のNGは画像品質の問題で、システム改善の限界
- 二重登録防止策の実装状況が未確認（RB-004）

## Verification commands
```bash
# シナリオ44 OCRテスト（カスケードモード）
cd C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools
python test_sample_ocr.py --cascade --sample-dir "C:\ProgramData\RK10\Tools\sample PDF\精度低い"
# 期待結果: OK 11/13 (84.6%)

# シナリオ44 OCRテスト（全体）
python test_sample_ocr.py --cascade
# 期待結果: 高精度

# シナリオ37 テストモード
cd C:\ProgramData\RK10\Robots\37レコル公休・有休登録
run_37_test.bat
```

## Relevant files (full paths)
### シナリオ44 (OCR)
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\pdf_ocr_smart.py` - メインOCR処理（カスケード実装）
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\pdf_ocr_yomitoku.py` - YomiToku呼び出し
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\ocr_debug_logger.py` - デバッグログ（NumpyEncoder追加）
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\pdf_preprocess.py` - 前処理
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\test_sample_ocr.py` - テストスクリプト
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\KNOWLEDGE_OCR_PREPROCESSING.md` - 知見記録

### シナリオ37 (レコル)
- `C:\ProgramData\RK10\Robots\37レコル公休・有休登録\tools\main_37.py`
- `C:\ProgramData\RK10\Robots\37レコル公休・有休登録\senario\37レコル公休有休登録_20260118.rks`

## OCR確定設定 (pdf_ocr_smart.py)
```python
# カスケードモード推奨
do_deskew=True,
do_enhance=False,       # YomiTokuに任せる
do_shadow_removal=True,
do_border=False,        # OFF（YomiTokuには逆効果）
do_sharpen=False,       # OFF
do_stretch=False,       # OFF（RGB→Gray変換で劣化）
do_thickness_adjust=False,  # OFF（RGB→Gray変換で劣化）
```

## Next change (if current approach fails)
- Phase 3: ROI切り出し実装（背景除去で更に精度向上の可能性）
- 残り2件のNG対応は画像品質の問題で、システム改善の限界
