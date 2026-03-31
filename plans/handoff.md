# Handoff — 2026-03-31

## 最新セッション (2026-03-31)

### Done
1. **AWSログイン復旧**: パスキーMFA → 1Password TOTP MFA再設定
2. **自社土地アプリ修正**: 404件のlat/lng欠損修正、トップマップ追加
3. **Ollama + GLM-OCR**: ollama 0.18.3 + glm-ocr:latest インストール済み
4. **ocr-universal スキル構築**: GPT-4o Vision主体の汎用OCRパイプライン
   - 4段階: 分類→GPT-4o API→jp_norm正規化→品質ゲート
   - テスト: 領収書90%、許可証100%（旧70.7%→大幅改善）
   - ocr-bestに統合済み（cli.py差し替え、cli_legacy.pyバックアップ）
5. **建設業許可管理**: 145社マスタ同期、43社新規追加、7社データ移行

### Next
- OCR Phase 2-3: 評価ハーネス、50枚ベースライン
- GLM-OCR vs YomiToku 比較: `C:\tmp\ocr_compare.py`
- 建設業許可管理: 藤田さんへの返信、ENABLE_SEND=TRUE

## 参照
- OCR Plan: `C:\Users\owner\.claude\plans\linear-mapping-marble.md`
- OCR Skill: `.claude/skills/ocr-universal/SKILL.md`
- 建設業decisions: `plans/decisions/projects/construction-permit-tracker.md`
- Webapp: `https://script.google.com/macros/s/AKfycbwyFrMZSzQ6uTRHcTmvHPimE2cXMUIX1zcRmqIDN5Obl5b0DpQ78J_TDn13qy8jcdgo/exec`
