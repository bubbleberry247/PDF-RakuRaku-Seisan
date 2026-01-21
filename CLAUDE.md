# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Canonical rules (Source of Truth)

@AGENTS.md

---

## Claude Code runtime notes（Claude Code固有）

- plansDirectory は `./plans`（設定済み）
- SessionStart hook で、セッション開始時に以下を自動注入：
  - `plans/decisions.md`（必読）
  - `plans/handoff.md`（あれば）
- context_window が 70% 以上になったら：
  1) `plans/handoff.md` を短く更新（Done/Next/Risks/検証）
  2) 新しい"決定"があれば `plans/decisions.md` に追記
  3) 必要なら `/compact`
- hook timeout は最大 120 秒（重い処理はhookに入れない）

---

## 「MDに書いて」の追記先（重要）

- 原則：恒常ルールは `AGENTS.md` 末尾 `## Project Memory` に追記する（CLAUDE.mdは入口のため肥大化させない）
- 例外：Claude Code固有の設定・運用（hooks/statusLine/plansDirectory など）を明示的に書きたい場合のみ、本ファイルの runtime セクションへ追記

---

## Skills（ドメイン知識スキル）

### RK10シナリオスキル（最重要）

**場所**: `.claude/skills/rk10-scenario/`
**自動参照**: @.claude/skills/rk10-scenario/SKILL.md

**キーワード**: RK10、Keyence、シナリオ、.rks、Program.cs、pywinauto

**知識範囲**:
- .rksファイル編集（ZIP形式、Program.csのみ編集）
- RK10 UI操作（pywinauto UIA）
- Keyence C# API（Excel、日付、ファイル操作）
- エラーパターンと解決策

---

### PDF OCRスキル

**場所**: `.claude/skills/pdf-ocr/`
**自動参照**: @.claude/skills/pdf-ocr/SKILL.md

**キーワード**: PDF、OCR、テキスト抽出、請求書、領収書、回転補正、傾き補正

---

### レコル（RecoRu）スキル

**場所**: `.claude/skills/recoru/`

**自動起動キーワード**: レコル、RecoRu、勤怠管理、勤務区分、有休、振休、代休、公休、打刻、締め、申請

**使用方法**:
- 上記キーワードを含む質問をするとスキルが自動起動
- スキルはドメイン知識ドキュメント（`docs/domain/recoru/`）を参照して回答

**参照ドキュメント**:
| ドキュメント | 用途 |
|-------------|------|
| `docs/domain/recoru/10_kbn_dictionary.md` | 勤務区分辞書（最重要） |
| `docs/domain/recoru/30_application_howto.md` | 申請手順 |
| `docs/domain/recoru/40_edge_cases.md` | 例外ケース |

**質問例**:
```
振休と代休の違いは？
有休申請の手順を教えて
締め後に修正したい
```

---

## Debug

- `/memory` でメモリロード状況（imports含む）を確認する
