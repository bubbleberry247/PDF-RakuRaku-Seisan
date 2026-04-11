# scenario70 支払い確定

## 概要
- 対象業務は楽楽精算の `経理処理 -> 支払確定（支払先）` 画面での支払い確定です。
- このシナリオは承認済みの確定待ち伝票を扱うため、現在画面で `支払方法` を選択する業務ではありません。
- したがって scenario70 の自動化対象は、対象日の伝票選択、振込元設定、支払日設定、確認ダイアログ確認、`OK` 押下までとします。
- 銀行側アップロードは別工程です。本 decision は楽楽精算上の支払い確定までを扱います。

## 正式方針
- `--execute` 時は、楽楽精算の確認ダイアログ `OK` 押下まで自動実行してよいものとします。
- ただし、以下の fail-closed 条件が 1 つでも発生した場合は即停止し、`OK` は押しません。
- fail-closed 条件:
  - preflight 失敗
  - 検索結果 0 件
  - 複数ページ検知
  - 表示件数と抽出件数の不一致
  - `先方負担` または手数料値不明
  - 自動選択件数と UI 表示の選択件数不一致
  - 確認ダイアログの振込元不一致
  - 確認ダイアログの支払日不一致
  - 確認ダイアログの合計金額と RPA 側集計の不一致

## 業務理解
- 本画面で対象となるのは、実際に支払日を迎えた確定待ち伝票です。
- 都度振込や口座振替の upstream ルールは存在しますが、scenario70 の現在画面では `支払方法` 選択 UI を前提にしません。
- そのため、scenario70 の一次判定は `対象支払日` と `振込手数料` を中心に行います。
- 手数料は現行ルール上 `当方負担` が正です。`先方負担` は anomaly とします。
- 銀行側アップロード前の最終確認値として、件数と合計金額を重視します。

## Source Of Truth
優先順位は次のとおりです。

1. この文書
2. scenario55 の正式決定
3. ヒアリング記録
4. 動画書き起こし / 画面観察
5. 現行コード

## 本番 URL
- base URL: `https://rsatonality.rakurakuseisan.jp/rHqny3DOsIa/`
- 対象画面: `sapShihaShiharaiKakuteiKensaku/search`

## 確認済み UI 事実
- 対象画面は standalone page であり、`main` frame 前提ではありません。
- 1 伝票は 3 行 1 ブロックで表示されます。
- 各伝票 checkbox は `input[name^="kakutei("]` です。
- 振込手数料は `select[name^="tesuryoKbn("]` です。
- 伝票選択後、一覧上部に `659件中 2件が選択されています。` のような件数表示が出ます。
- 右下の `確定` を押すと確認ダイアログが開き、`振込元`、`支払日`、`支払額の合計` が表示されます。

## 自動選択ルール
- `(申請)支払日 = 実行対象日` の伝票だけを候補とします。
- 候補のうち `振込手数料 = 当方負担` のみを自動選択対象とします。
- `振込手数料 = 先方負担`、空欄、未知値は anomaly とします。
- 上記以外の伝票は `skipped` とします。

## 実行停止位置
- `--execute` なし: 候補抽出、チェック、振込元設定、支払日設定、確認ダイアログ読取まで。`OK` は押しません。
- `--execute` あり: 確認ダイアログの値照合がすべて通った場合のみ `OK` を押します。

## Read-only / Execute 共通の出力契約
最低限、以下を 1 run ごとに残します。

- `summary.json`
- `report.json`
- `full_inventory.csv`
- `selected_candidates.csv`
- `anomaly.csv`
- `screenshots/`

`full_inventory.csv` の最低列は次です。

- `page_no`
- `row_group_index`
- `slip_no`
- `request_date`
- `approval_date`
- `requested_payment_date`
- `vendor`
- `amount_yen`
- `fee_burden`
- `decision`
- `decision_reason`
- `checkbox_name`
- `raw_text`

## State / Ledger
- canonical ledger は `artifact_root/state/scenario70/<env>/ledger.jsonl`
- run ごとの抜粋は `artifacts/run_*/logs/ledger_excerpt.jsonl`
- ledger は append-only の補助 state であり、業務正本ではありません。
- 画面状態と ledger が食い違う場合は画面を優先し、fail-safe 側に倒します。

## preflight
preflight は fail-closed とします。最低限確認する項目は以下です。

- config 読込可否
- URL が正式 URL と一致するか
- credential target が解決できるか
- artifact_root が書込可能か
- Python 依存が揃っているか
- Playwright 実行可能か
- 対象画面の最小 DOM が存在するか
- 実行環境が LOCAL / PROD のどちらかを明示できるか

## execute 解禁条件
次を満たした時点で通常運用の `--execute` を解禁します。

- 連続 3 回以上、選択件数と確認ダイアログ合計金額が人手確認と一致する
- `count mismatch` が 0 回
- `先方負担` の anomaly 処理が期待通り動作する
- preflight / runbook / artifact 保全が整備済み
- 初回監視運用で partial failure が発生していない

## Non-Goals
- 銀行側アップロードの自動化
- 都度振込 / 口座振替の自動判定
- human memory でしか見抜けない upstream 例外の再現
