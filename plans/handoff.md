# handoff.md（短く・上書き前提）

## Current focus
- シナリオ44 OCR前処理A/Bテスト完了・設定確定

## Done
- AGENTS.md 正本化、CLAUDE.md 入口化（Phase 1）
- SessionStart hook で decisions + handoff 自動注入設定
- 運用ドキュメント7本作成 → v0.2に更新
- **運用体制をOM3に確定**
- **シナリオ37 完了**（レコルAPI統合、PDF保存、メール送信、RKSファイル作成）
- **シナリオ44 OCR前処理A/Bテスト完了** (2026-01-19):
  - **最終結果: 60.6% (20/33)** - ベースライン設定が最適
  - 新前処理オプション（do_border, do_stretch, do_thickness_adjust）は全て逆効果
  - **知見ドキュメント作成**: `docs/KNOWLEDGE_OCR_PREPROCESSING.md`
  - **Git push完了**: `e6a8e7d` - PDF-RakuRaku-Seisan

## Key learnings (OCR)
1. **YomiTokuには追加前処理が不要** - 内部で高品質な前処理を持つ
2. **RGB→Gray→RGB変換は避けるべき** - 情報損失を引き起こす
3. **Tesseract向けTipsはYomiTokuに適用不可** - 白ボーダー等は逆効果
4. **dpi 200 vs 300 は影響なし** - 300dpi維持で問題なし

## Next (top 3)
1. シナリオ44 残りのNG 13件の原因分析・改善策検討
2. マスキング関数実装/既存ログの機微情報チェック（LP-004/LP-005）
3. config/*.xlsxの構造確認 → スキーマ定義完成（CS-001/CS-002）

## Risks / blockers
- シナリオ44 NGファイル13件（主に取引先名未検出）
- 二重登録防止策の実装状況が未確認（RB-004）

## Verification commands
```bash
# シナリオ44 OCRテスト
cd C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools
python test_sample_ocr.py
# 期待結果: OK 20/33 (60.6%)

# シナリオ37 テストモード
cd C:\ProgramData\RK10\Robots\37レコル公休・有休登録
run_37_test.bat
```

## Relevant files (full paths)
### シナリオ44 (OCR)
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\pdf_ocr_smart.py` - メインOCR処理
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\pdf_preprocess.py` - 前処理
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\test_sample_ocr.py` - テストスクリプト
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\KNOWLEDGE_OCR_PREPROCESSING.md` - 知見記録

### シナリオ37 (レコル)
- `C:\ProgramData\RK10\Robots\37レコル公休・有休登録\tools\main_37.py`
- `C:\ProgramData\RK10\Robots\37レコル公休・有休登録\senario\37レコル公休有休登録_20260118.rks`

## OCR確定設定 (pdf_ocr_smart.py:532-538)
```python
do_deskew=True,
do_enhance=False,       # YomiTokuに任せる
do_shadow_removal=True,
do_border=False,        # OFF（YomiTokuには逆効果）
do_sharpen=False,       # OFF
do_stretch=False,       # OFF（RGB→Gray変換で劣化）
do_thickness_adjust=False,  # OFF（RGB→Gray変換で劣化）
```

## Next change (if current approach fails)
- OCR精度向上が必要な場合: 取引先名辞書マッチング強化、または別OCRエンジン（PaddleOCR）併用検討
