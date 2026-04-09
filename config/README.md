# config/ — 設定ファイル

RPA シナリオ・OCR ツール共通の設定ファイル群。

## ファイル一覧

<!-- AUTO-GENERATED:START -->
| ファイル | 用途 |
|---|---|
| `env.txt` | 環境切替（PROD / LOCAL） |
| `RK10_config_LOCAL.xlsx` | LOCAL 環境の接続先・パス設定 |
| `RK10_config_PROD.xlsx` | PROD 環境の接続先・パス設定 |
| `tool_config_prod.json` | ツール実行時の本番設定 |
| `tool_config_test.json` | ツール実行時のテスト設定 |
| `golden_dataset_v4.json` | OCR ゴールデンデータセット（正解データ） |
| `golden_dataset_v4_eval.json` | OCR 評価用データセット |
| `project_master_export_mapping.example.json` | 工事マスタ出力マッピング（サンプル） |
| `project_master_export_mapping_juchu.example.json` | 受注マスタ出力マッピング（サンプル） |
| `project_master_v20260319.xlsx` | 工事マスタ正本 |
| `vendor_delivery_master_v4.xlsx` | 業者別配信マスタ |
| `vendor_hints.json` | OCR 業者名推定ヒント |
<!-- AUTO-GENERATED:END -->

## 注意

- `env.txt` の値を直接コミットしない（PROD/LOCAL の切替のみ）
- `.example.json` はサンプル。実運用時はサフィックスを外してコピー
- マスタ更新時は [AGENTS.md](../AGENTS.md) の横展開チェックリストを確認

[← ルートに戻る](../README.md)
