# {CUSTOMER} / {PROJECT}

## 概要

| 項目 | 内容 |
|------|------|
| 顧客 | {CUSTOMER} |
| プロジェクト | {PROJECT} |
| シナリオ番号 | {SCENARIO_ID} |
| ステータス | 設計中 / 開発中 / テスト中 / 本番稼働 |
| 担当 | {OWNER} |
| 作成日 | YYYY-MM-DD |
| 最終更新 | YYYY-MM-DD |

## 目的

{このRPAが解決する業務課題を1-2文で記載}

## スコープ

### 対象業務
- {業務1}
- {業務2}

### 対象外
- {対象外の業務}

## 関連ドキュメント

| ドキュメント | パス |
|-------------|------|
| 要件定義 | [01_requirements.md](design/01_requirements.md) |
| 処理フロー | [02_flow.md](design/02_flow.md) |
| 例外設計 | [03_exceptions.md](design/03_exceptions.md) |
| RK10ステップ | [rk10_steps.md](implementation/rk10_steps.md) |
| 運用手順書 | [runbook.md](ops/runbook.md) |

## 環境情報

| 環境 | パス |
|------|------|
| LOCAL | `C:\ProgramData\RK10\Robots\{SCENARIO_ID}{PROJECT}\` |
| PROD | `C:\ProgramData\RK10\Robots\{SCENARIO_ID}{PROJECT}\` |
