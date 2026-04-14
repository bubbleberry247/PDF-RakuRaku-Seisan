# CLAUDE.md

For every project, write a detailed FOR[yourname].md file that explains the whole project in plain language.

---

## 憲法（Constitution）— 全ての判断に優先する原則

- **業界標準リサーチ**: 設計判断・技術選定の前に業界標準を調査し、自分たちの文脈に合わせて適用する
- **シンプルさ優先**: 素のClaude Code ＞ 複雑なagentワークフロー。複雑さを追加するたびに「本当に必要か？」を問う
- **コンテキスト予算管理**: CLAUDE.mdは入口（150行以下）。詳細はAGENTS.md・Skills・Rulesに分離
- **段階的情報開示**: Command（入口）→ Skill（知識）→ Subagent（実行）。必要な知識だけを必要なタイミングで
- **自己検証**: 「動いた」ではなく「検証できた」をもって完了とする。テストなきコード変更は禁止
- **オーケストレーション専念**: チーム編成時、リーダーは実装に手を出さない

---

## Canonical rules (Source of Truth)

@AGENTS.md

---

## Claude Code runtime notes

- plansDirectory は `./plans`（設定済み）
- SessionStart hook で `plans/handoff.md` を自動注入
- context_window が 70% 以上になったら: ① `plans/handoff.md` を更新 ② 必要なら `/compact`
- hook timeout は最大 120 秒

## 「MDに書いて」の追記先

- 恒常ルール → `AGENTS.md` 末尾 `## Project Memory` → Archive に記録し Active Rules Summary に昇格
- Claude Code固有の設定 → 本ファイルの runtime セクションへ

---

## Skills（キーワード → SKILL.md を読んでから作業開始）

詳細インデックス: `.claude/skills/INDEX.md`

| スキル | トリガーキーワード |
|--------|-------------------|
| RPA共通パターン | シナリオ作成、ロボット作成、パターン、前例、テンプレ |
| RK10シナリオ | RK10、Keyence、.rks、Program.cs、pywinauto |
| シナリオ55振込転記 | シナリオ55、振込、楽楽精算、総合振込、勘定奉行 |
| シナリオ44 OCR | PDF、OCR、テキスト抽出、請求書、回転補正 |
| Video2PDD | Video2PDD、PAD、Power Automate、Robin、PDD |
| レコル | レコル、RecoRu、勤怠、勤務区分、有休、打刻 |
| GAS Webapp | GAS、Google Apps Script、clasp、doGet |

**注意**: Skill を使うときは `external-repos/my-claude-skills/{name}/templates/` の実装コードも確認する。

---

## Debug

- `/memory` でメモリロード状況（imports含む）を確認する
