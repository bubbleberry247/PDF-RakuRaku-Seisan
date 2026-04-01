# Handoff — 2026-04-01

## 最新セッション (2026-04-01)

### Done
1. **AWSログイン復旧**: パスキーMFA使用不可 → 代替認証 → 1Password TOTP MFA再設定
2. **自社土地アプリ修正** (http://54.238.230.57:8000/):
   - 地図バグ修正（404件ジオコーディング）、テストデータ削除
   - 全件ピン表示、検索フィルタ連動、トップマップ（現在位置対応）
   - 用途地域プルダウン修正、詳細フィルタ常時展開
3. **自社土地アプリ用MCP作成** (`tools/mcp-land-registry/server.py`, 7ツール):
   - search_properties, get_property_packet, lookup_market_price（国交省API）
   - save_property_draft, submit_for_approval, list_pending_approvals, review_approval
4. **国交省API接続**: reinfolib API（APIキー取得済み）→ 実データ210件投入
5. **Ollama + GLM-OCR**: インストール済み（Intel Iris Xeでは実行不可→GPU PCで継続）

### 反省・学び
- ダッシュボード（analytics API + HTML）を依頼なく勝手に作成 → 全削除
- GPT-5.4が「不要」と判定した機能を無視して作った
- **教訓**: 作る前に「何を・誰が使う」を確認。GPT-5.4の判定を実行判断に反映する
- メモリ保存済み: `feedback_build_discipline.md`, `feedback_need_check.md`

### Next
- GLM-OCR vs YomiToku 比較テスト（GPU PCで）
- 商談管理・アクション追跡機能（GPT-5.4推奨の最優先機能）
- 建設業許可管理: 藤田さんへの返信、ENABLE_SEND=TRUE

## 参照
- OCR Plan: `C:\Users\owner\.claude\plans\linear-mapping-marble.md`
- OCR Skill: `.claude/skills/ocr-universal/SKILL.md`
- 建設業decisions: `plans/decisions/projects/construction-permit-tracker.md`
- Webapp: `https://script.google.com/macros/s/AKfycbwyFrMZSzQ6uTRHcTmvHPimE2cXMUIX1zcRmqIDN5Obl5b0DpQ78J_TDn13qy8jcdgo/exec`
