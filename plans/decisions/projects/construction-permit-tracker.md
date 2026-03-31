# Construction Permit Tracker — Decision Log

## 2026-03-29 [PROCESS] 納品・移行方針

### Phase 1: 現状納品（即時）
- 現在の構成（OCR + MLIT閲覧 + GASメール通知）のまま納品
- 運用開始して実際の使われ方・課題を把握する

### Phase 2: シンプル版移行（運用後）
- **MLIT閲覧システム（etsuran2）をデータ正本に切り替え**
- 管理項目: **許可業種（29業種 × 般/特）+ 有効期限のみ**
- 技術者・役員等の人情報は管理対象外（APIで取得不可＋実務上不要）
- OCRパイプライン・目視修正UI・Gmail PDF取り込みを廃止
- 120日前に更新要請メール送信 → 紙許可証受領 → APIで更新確認

### Phase 2 設計メモ
- etsuran2のレート制限: 1秒/リクエスト（既存実装済み）
- メール通知: GAS 150通/日制限（既存実装済み）
- API反映遅延: 90-120日の時差あり → 紙受領時に手動で期限更新 → API反映後に自動照合
- REST APIは存在しない。HTMLフォームPOST + BeautifulSoupスクレイピング

### Why
- 現状: 紙PDF → OCR → 目視修正 = 高工数
- 移行後: API自動取得 + メール通知のみ = 大幅工数削減
- ただし運用実績なしでいきなり移行はリスク → Phase 1で安定運用してから移行

## 2026-03-29 [DATA] MLIT全社スクレイピング実行

- 59社スクレイピング完了（56成功/3 NOT_FOUND）、所要5.5分
- 出力: `C:/tmp/mlit_permit_registry.xlsx`（4シート）、CSV 4本、サマリー
- DB更新10件（業種追加）、56社を CONFIRMED に更新
- 期限切迫: 三富(8日)、谷野宮組(15日)、前畑工務店(75日)

## 2026-03-29 [DATA] DB整合性問題の発見と修正

### 発見した問題
1. **131/216ファイル(60%)が company_id=NULL** — 会社未紐付けのまま放置
2. **4ファイルが別会社に誤分類** — 松島商店→サムテック、共立防災→三和シャッター等
3. **三富の8ファイルがインフラテックに誤分類** — 送信者コンテキスト喪失
4. **名西建材の3ファイルが三信建材工業に誤分類** — 類似会社名の混同
5. **名西建材の2通目メールがDB未登録** — inbound_messages に登録漏れ

### 修正実施
- 誤分類修正: 12件（4+8）
- company_id=NULL修正: 68件（業務対象ファイル）
- 名西建材メッセージ登録: 2件追加
- 修正後: ファイル紐付け率 39% → 71%、ファイルありの会社 ~50社 → 62社

### 根本原因
- fetch_gmail → inbound_log → files DB のパイプラインで会社マッチング失敗時にサイレント（エラーなし、NULL挿入）
- ZIP展開時に送信者コンテキスト（message_id）が失われる
- 類似会社名（三信建材/名西建材）のファジーマッチ誤判定

### 再発防止（Codex GPT-5.3 提言、未実装）
1. **ステージングテーブル**: 全添付を inbound_attachments に記録 → 会社解決ゲート → 曖昧なら review_queue → 確定後のみ files テーブルへ
2. **DBハード制約**: `files.company_id NOT NULL` + 外部キー制約（ポカヨケ）
3. **混同ペアリスト**: 三信建材↔名西建材 等を登録、自動マッチ禁止 → 手動確認キュー
4. **整合性チェック（アンドン）**: 毎夜実行、company_id=NULL等があればパイプライン停止+通知
5. **確定論的マッチング優先**: メール完全一致 → ドメイン → エイリアス → ファジー（スコア≥95+差≥8のみ）

### 残り56社（ファイル0件）
all_documents にもファイルが存在しない = **書類未提出の会社**（DB問題ではない）

## 2026-03-30 [DEPLOY] GAS+Sheets 新規デプロイ完了

### リソース
- **Spreadsheet**: `1FEj9OOz_NsFCDPd5eiYLrawB9x_Y5BI6cKOI3rtZlwA`（建設業許可管理_TIC）
- **GAS Script**: `1o3hSn6ae07OcIeNByJeYXEiGCJbkC5q1V5bIjmvvDDnD4Kk7gNb90Y0I`
- **GCP Project**: `permit-tracker-tic`（プロジェクト番号: 451823853903）
- **SA**: `permit-sync@permit-tracker-tic.iam.gserviceaccount.com`
- **SA JSON**: `C:\ProgramData\RK10\credentials\google_service_account.json`
- **アカウント**: kalimistk@gmail.com（将来客先に移設予定）

### 完了した設定
- GASファイル8本 clasp push済み
- シート初期化（Config/Companies/Permits/Submissions/Notifications/DocumentChecklist）
- MLITPermits + SyncRuns シート自動作成（sync_to_sheets.py）
- Config: NOTIFY_STAGES_DAYS=150, ENABLE_SEND=FALSE, ADMIN_EMAILS=kanri+fujita+kalimistk
- 日次トリガー設定（毎朝8時）
- CompanyView生成確認

### 月次運用手順
```bash
# 1. MLITスクレイピング
python src/mlit_batch_fetch.py
# 2. Sheets同期
python src/sync_to_sheets.py
# 3. 結果確認: スプレッドシートのMLITPermitsシート
```

### 通知開始手順（テスト完了後）
1. Config シート ENABLE_SEND を TRUE に変更
2. 「許可証管理」→「期限チェックを今すぐ実行」で対象確認
3. 150日以内の3社のみが通知対象であることを確認

## 2026-03-30 [DEPLOY] GAS Webapp デプロイ完了

### WebアプリURL
`https://script.google.com/macros/s/AKfycbwyFrMZSzQ6uTRHcTmvHPimE2cXMUIX1zcRmqIDN5Obl5b0DpQ78J_TDn13qy8jcdgo/exec`

### デプロイメントID（clasp deploy -i で使用）
`AKfycbwyFrMZSzQ6uTRHcTmvHPimE2cXMUIX1zcRmqIDN5Obl5b0DpQ78J_TDn13qy8jcdgo`

### 実装した画面
1. **ダッシュボード**: ステータスカード(4枚) + アンドンバー + 検索/フィルター + ソート付きテーブル
2. **会社詳細**: 基本情報 + 許可情報(業種展開) + 通知履歴 + 操作ログ + 無効化/再有効化/通知送信
3. **会社追加**: フォーム（会社名/メール/担当者）
4. **運用管理**: 同期状態 + 通知履歴 + 監査ログ

### 新規GASファイル
- `Code2.gs`: doGet + Auth allowlist
- `api.gs`: フロントエンド向けAPI（10関数）
- `logic.gs`: ビジネスロジック（CRUD + 通知）
- `db.gs`: シートCRUD + 監査ログ + 楽観ロック + toSerializable_
- `index.html`: SPA 4画面（inline CSS/JS、レスポンシブ）

### Mailer.gs修正
- 7段階通知 → 4段階（D-150/90/30/EXPIRED）
- 週次サマリーの閾値: 120→180日

### Auth
- ALLOWED_EMAILS: kanri.tic + m-fujita + kalimistk
- 未登録メールは403画面
