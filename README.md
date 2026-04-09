# PDF-RakuRaku-Seisan

楽楽精算連携・PDF 処理を中心とした RPA シナリオ開発リポジトリ。
OCR 精度向上、業務自動化ツール、ナレッジ蓄積を一元管理する。

---

## ディレクトリ構成

<!-- AUTO-GENERATED:START -->
| ディレクトリ | 用途 | README |
|---|---|---|
| [config/](config/) | RPA・OCR 設定ファイル（env, マスタ, ゴールデンデータ） | [→](config/README.md) |
| [data/](data/) | OCR テスト用 PDF サンプル | [→](data/README.md) |
| [docs/](docs/) | 技術ドキュメント・運用手順書・ドメイン知識 | [→](docs/README.md) |
| [external-repos/](external-repos/) | 外部リポジトリ参照コピー（agent-browser, スキル等） | [→](external-repos/README.md) |
| [plans/](plans/) | 意思決定ログ・計画・セッション引継ぎ | [→](plans/README.md) |
| [rk10_project_pack/](rk10_project_pack/) | RK10 ナレッジ移植パック（パターン・トラブル集・Playbook） | [→](rk10_project_pack/README.md) |
| [tools/](tools/) | Python ユーティリティスクリプト（OCR, RPA, マスタ管理） | [→](tools/README.md) |
| [tests/](tests/) | pytest テストスイート | [→](tests/README.md) |
<!-- AUTO-GENERATED:END -->

### その他（通常参照不要）

| ディレクトリ | 用途 |
|---|---|
| `.claude/` | Claude Code スキル・フック・ルール |
| `scratchpad/` | 一時的な実験スクリプト |
| `work/` | RPA 作業出力（コミット非推奨） |
| `logs/` | 実行ログ（生成物） |

---

## 主要エントリポイント

| 目的 | 見るべき場所 |
|---|---|
| プロジェクトルール・品質基準 | [AGENTS.md](AGENTS.md) |
| Claude Code 設定 | [CLAUDE.md](CLAUDE.md) |
| RK10 ナレッジ検索 | [rk10_project_pack/01_INDEX.md](rk10_project_pack/01_INDEX.md) |
| OCR 技術詳細 | [docs/44_OCR_technical.md](docs/44_OCR_technical.md) |
| セッション引継ぎ | [plans/handoff.md](plans/handoff.md) |
| ツール選定方針 | [docs/tool_selection_policy.md](docs/tool_selection_policy.md) |

---

## ルートの重要ファイル

| ファイル | 用途 |
|---|---|
| `AGENTS.md` | エージェント運用ルール（正本） |
| `CLAUDE.md` | Claude Code プロジェクト指示（入口） |
| `FORClaude.md` | プロジェクト全体説明（平易な言葉） |
| `.mcp.json` | MCP サーバー設定 |
