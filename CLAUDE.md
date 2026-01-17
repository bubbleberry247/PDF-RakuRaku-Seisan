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

## Debug

- `/memory` でメモリロード状況（imports含む）を確認する
