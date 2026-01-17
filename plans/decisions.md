# decisions.md

- 目的: セッション間で引き継ぐ「決定」「制約」「非自明な知見」を記録する。
- 原則: **append-only**（追記が基本、過去は書き換えない）。変更は「新しい決定」として追記し、置換を明記する。
- 禁止: 秘密情報（鍵/トークン/個人情報/社外秘の生データ）は書かない。

---

## 2026-01-17

### Claude Code設定
- `plansDirectory: "./plans"` を設定済み
- `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE: "70"` を設定済み
- SessionStart hookでdecisions.md自動読み込みを設定
- 設定ファイル: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\.claude\settings.local.json`

### 47出退勤確認
- CC宛先に管理部メール（kanri.tic@tokai-ic.co.jp）を追加
- employee_master.csvにcc_email列を追加済み
- 要件定義書をv1.1に更新済み

### MDファイル整理
- 4つのdocsファイルを`docs/44_OCR_technical.md`に統合
- 削除したファイル（Git履歴に残る）:
  - `docs/scenario_info.md`
  - `docs/引継ぎ書_20260112.md`
  - `docs/引継ぎ書_20260114_OCR精度改善.md`
  - `docs/OCR前処理フロー詳細.md`
- CLAUDE.mdを421行→192行に圧縮
- セッション引継ぎルールを明確化（append-only、トリガー→アクション表）

### Notta単語登録リスト作成
- 従業員名、会社名、システム名、部署名、勤務区分、シナリオ名、技術用語を収集
- 保存先: scratchpad内の`notta_vocabulary.txt`

---
