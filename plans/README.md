# plans/ — 意思決定・計画・引継ぎ

セッション間の判断一貫性を保つための決定ログと計画書。

## 主要ファイル

<!-- AUTO-GENERATED:START -->
| ファイル | 用途 |
|---|---|
| `handoff.md` | セッション引継ぎ（Done / Next / Risks） |
| `decisions.md` | 決定ログ **凍結済み**（5,278 行）。新規追記禁止 |
| `scenario55_rules.md` | シナリオ 55 業務ルール |
| `plan.md` | 直近の計画 |
<!-- AUTO-GENERATED:END -->

## サブディレクトリ

| ディレクトリ | 内容 |
|---|---|
| `decisions/` | **プロジェクト別決定ログ（新規追記先）** |
| `mvp-s12-13/` | シナリオ 12-13 MVP 計画・テスト・ランブック |

## 運用ルール

- 新しい決定は `decisions/projects/{project}.md` に追記（append-only）
- legacy `decisions.md` は参照のみ。新規追記禁止
- `handoff.md` はセッション終了時に短く更新

[← ルートに戻る](../README.md)
