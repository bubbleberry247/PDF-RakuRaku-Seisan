# シナリオ12・13: 受信メールのPDFを保存・一括印刷（自動化仕様 / 書き起こし）

## 対象ソース（観察元）

- 動画（前半）: `C:\Users\masam\Desktop\KeyenceRK\ロボット作成資料\【12・13受信メールのPDFを保存・一括印刷1】.mp4`
- 動画（後半）: `C:\Users\masam\Desktop\KeyenceRK\ロボット作成資料\【12・13受信メールのPDFを保存・一括印刷2】.mp4`
- 自動抽出（参考。OCR精度は低い）:
  - `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\_wip\video12_13_perfect_20260207_212520\part1\flow.md`
  - `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\_wip\video12_13_perfect_20260207_212520\part2\flow.md`

## 業務の目的（Why）

経理の請求書処理のため、受信メールから請求書PDFを漏れなく収集し、所定フォルダに保存したうえで、まとめて印刷（必要に応じてPDF結合）する。

## 入力 / 出力（What）

### 入力

- Outlook 受信メール（請求書通知メール）
  - PDF添付があるメール
  - Web請求サービス等のリンクのみのメール（例: キョーワWeb請求サービス）
  - 暗号化メールの「パスワード通知」メール（例: `[HENNGE One][パスワードをお知らせします]`）

### 出力

- 保存された請求書PDF（保存先は月次フォルダ配下など）
- 一括印刷（プリンタ設定に依存）
- 処理レポート（JSON/CSV/ログ）
- 完了通知メール（テスト時のみ。`kalimistk@gmail.com` へ）
- エラー通知メール（`kalimistk@gmail.com` へ。必要なら CC も設定）

### 用語の混同防止（必ず区別する）

- **入力元（Outlook受信フォルダ）**: Outlook内の「共有メールボックス/受信フォルダ」
- **出力先（保存先共有フォルダ）**: ネットワーク共有（例: `\\192.168.1.251\TIC-mainSV\経理\請求書【現場】\新しいフォルダー\`）

## 画面上の手作業フロー（As-Is / 自然言語）

※ここでは「人がやっていること」を過不足なく文章化する。自動化は次章で仕様化する。

1. VPN接続が必要な場合は接続する（例: FortiClient VPN）。
2. 請求書の保存先フォルダ（社内共有）を開く。
   - 社外: VPN接続後、デスクトップのショートカットから開く。
     - ショートカット: `C:\Users\masam\Desktop\TIC-mainSV (192.168.1.251).lnk`
     - 実体パス: `\\192.168.1.251\TIC-mainSV`
  - 例: `\\192.168.1.251\TIC-mainSV\経理\請求書【現場】\新しいフォルダー\`（必要に応じて対象月フォルダ配下に保存）。
3. Outlook を開き、対象のメールボックス/フォルダを開く。
   - 開発（このPC）: `\\masamaru1975@hotmail.com\\受信トレイ\\仮想フォルダ`
   - 本番: 対象メールボックス配下のフォルダ（設定で差し替え）
4. 請求書通知メールを上から確認し、以下を実施する。
   - PDF添付がある場合:
     1. 添付PDFを保存先フォルダへ保存する（ファイル名が衝突しないように注意）。
     2. PDFが暗号化されて開けない場合、パスワード通知メールを探し、パスワードで開いて保存/印刷できる状態にする。
   - リンクのみ（Web請求サービス）の場合:
     1. メール本文のURLを開く。
     2. Web請求サービスにログインする。
     3. 対象の請求書PDFをダウンロードして保存先フォルダへ保存する。
5. 収集したPDFを必要に応じて結合する（動画では iLovePDF を使用してPDF結合している場面がある）。
6. PDFを一括印刷する。
7. 完了後、処理した内容が分かる形で管理部へ通知する（例: 保存先、件数、対象メール/請求書、印刷の有無）。
8. 例外があれば処理を止め、管理部へ即時通知する（何が未完了か、次に何をすべきかを明記）。

## 暗黙知 -> 形式知（選別ルール/判断ルール）

自動化で事故を起こしやすいのは「どれを処理対象にするか」「どこまでを完了とみなすか」。
本シナリオでは、以下をルール化する。

### メールの選別（対象/対象外）

- 対象:
  - PDF添付が1つ以上あるメール（添付拡張子 `.pdf`）
  - もしくは本文に `http(s)://` の請求書ダウンロードURLが含まれるメール（Web請求サービス）
  - もしくは暗号化PDFのパスワード通知メール（例: 件名に `パスワード` / `HENNGE One` を含む）
- 対象外（原則）:
  - 添付もURLも無いメール（通知のみ等）
  - 画像のみのメール（運用で必要なら後で追加）

### PDFの扱い（暗号化）

- PDFが暗号化されている場合:
  - 対応するパスワード通知メールが **一意に特定できる** なら復号して保存/結合/印刷対象にする
  - 一意に特定できない（候補が複数/無し）なら **処理停止（自働化）** し、エラー通知（アンドン）

### Web請求サービス（URL）

- URLのみのメール（添付なし）を検知したら:
  - 自動ダウンロードが未実装/未設定なら **処理停止（自働化）** し、エラー通知（アンドン）
  - 実装済みの場合のみ、決められた手順でダウンロードして保存する

### 保存先とファイル名

- 保存先は「対象月フォルダ + 作業用サブフォルダ」を前提に、設定で指定する（固定値にしない）。
- **リネームはPDFの値を正（SSOT）** とする:
  - PDF本文から `vendor`（発行元）, `issue_date`（請求日/発行日）, `amount`（**支払決定金額を優先**。無ければ請求金額/合計など）を抽出し、テンプレートで命名する。
  - 抽出できない場合は **処理停止（ポカヨケ）** とし、エラー通知する（誤リネーム防止）。
  - 既定テンプレート例: `{vendor_short}__{issue_date}__{amount_comma}円.pdf`
  - `vendor_short` は `株式会社` 等の法人格を除去した短縮名（例: `株式会社モビテック` -> `モビテック`）

### メール通知（テスト/本番の送信先ルール）

運用事故（テストで管理部に送ってしまう等）を防ぐため、送信先は **環境で固定** する。

- テスト環境:
  - 成功: `kalimistk@gmail.com`
  - エラー: `kalimistk@gmail.com`
- 本番環境:
  - 成功: 送らない（`mail.send_success=false`）
  - エラー: `kalimistk@gmail.com`

※送信は SMTP ではなく **Outlook COM** で行う（送信元アカウントは、このPCのOutlookにログインしているアカウント）。
※切り替えは `config\tool_config_test.json` / `config\tool_config_prod.json` を使う（`mail.*` を明示設定する）。

## 自動化仕様（To-Be）

### CLIツール

- 正本（リポジトリ）: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\outlook_save_pdf_and_batch_print.py`
- 配布（ロボット配下）: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py`
- 設定例（推奨）:
  - テスト: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_test.json`
  - 本番: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_prod.json`
- 実行例（ドライラン）:
  - `python C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py --config C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_test.json --dry-run --dry-run-mail`

### 設定（config）必須項目

- Outlookフォルダパス（入力元・開発このPC）: `\\masamaru1975@hotmail.com\\受信トレイ\\仮想フォルダ`
- Outlookフォルダパス（入力元・本番）: 対象メールボックスのフォルダパスに差し替え
- 保存先ディレクトリ（出力先・UNCパス可）
- 成功/エラー通知メール宛先（`mail.send_success`, `mail.success_to`, `mail.error_to`, `mail.error_cc`）
- 一括印刷の有無、プリンタ名（未指定なら既定プリンタ）
- 再実行で二重保存しないための運用（推奨）: `outlook.mark_as_read_on_success=true`（成功時に既読化）
- リネーム（PDF SSOT）設定（必須）:
  - `rename.enabled=true`
  - `rename.company_deny_regex`（自社名除外。例: `東海インフラ建設株式会社`）
  - `rename.file_name_template`（命名テンプレート）

### 生成物（Artifacts）

- 既定: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\artifacts\run_YYYYMMDD_HHMMSS\`
  - `run.log`
  - `report.json`
  - `report.csv`
  - `merged.pdf`（結合を有効にした場合）

## 検証（Verification）

### Outlookフォルダパスの調べ方（必須）

- 補足: 既定プロファイルで目的のストアが出ない場合は `--outlook-profile "<プロファイル名>"` を付けて実行する。
- 補足: config の `outlook.folder_path` を一時的に上書きしたい場合は `--outlook-folder-path "\\<Store>\\受信トレイ"` を使う。
- ストア一覧（トップレベル）:
  - `python C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py --list-outlook-stores`
- フォルダ一覧（子フォルダを列挙）:
  - まずストア直下を列挙（`受信トレイ` 等を探す）:
    - `python C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py --list-outlook-folders "\\masamaru1975@hotmail.com"`
  - 受信トレイ配下を列挙（サブフォルダがある場合）:
    - `python C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py --list-outlook-folders "\\masamaru1975@hotmail.com\\受信トレイ"`
- スキャンのみ（保存せず、候補をレポート化）:
  - `python C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py --config C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_test.json --scan-only`
  - ※ `--scan-only` は **メール通知を一切行わない**（ログ/レポートのみ）。

1. 構文チェック:
   - `python -m py_compile C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py`
2. ドライラン（保存/印刷なし、メール送信もドライラン推奨）:
   - `python C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py --config <config> --dry-run --dry-run-mail`
3. 本番前の小さな代表入力で実行（数件のみ）:
   - `--max-messages 3` などで制限して保存だけ実行し、保存先/ファイル名/レポートが期待通りか確認
4. 印刷ありの実行は最後に（紙コストが出るため）:
   - `--print --execute`

### 未検証マトリクス（精度向上の前提）

状態は `未検証 / 一部検証 / 検証済` のいずれかで更新する。

| ID | 項目 | 目的/リスク | 検証方法（最小） | 現状 | 記録先 |
| --- | --- | --- | --- | --- | --- |
| V1 | 本番Outlookストア/フォルダパス確定 | 誤フォルダ処理による漏れ/誤処理 | `--list-outlook-stores` / `--list-outlook-folders` で特定し config 反映 | 一部検証（テスト環境: `run_20260210_003921` でフォルダ解決） | `artifacts/run_YYYYMMDD_HHMMSS/run.log` |
| V2 | URLのみメール検知時の停止/通知 | Web請求未対応での取りこぼし/誤完了 | `--scan-only` でURL-only件数と対象メール件数を確認 | 一部検証（URL-only 0件: `run_20260210_003921`） | `artifacts/run_YYYYMMDD_HHMMSS/report.json` |
| V3 | 暗号化PDFのパスワード照合 | 復号失敗による保存/印刷漏れ | パスワード通知メールと暗号化PDFを1件ずつ通す | 未検証 | `artifacts/run_YYYYMMDD_HHMMSS/run.log` |
| V4 | ZIP添付のパスワード解凍 | ZIP内PDFの取りこぼし | パスワード通知 + ZIP添付の組で1件検証 | 未検証 | `artifacts/run_YYYYMMDD_HHMMSS/run.log` |
| V5 | リネーム抽出精度（vendor/date/amount） | 誤命名による運用混乱 | 代表5件で `report.csv` と実物照合 | 未検証 | `artifacts/run_YYYYMMDD_HHMMSS/report.csv` |
| V6 | 保存先UNC到達性/権限 | 保存失敗・サイレント失敗 | `--execute --max-messages 1` で保存先まで到達確認 | 未検証 | `artifacts/run_YYYYMMDD_HHMMSS/run.log` |
| V7 | 印刷/結合の実機挙動 | 誤印刷・印刷漏れ | `--print --execute --max-messages 1` で検証 | 未検証 | `artifacts/run_YYYYMMDD_HHMMSS/run.log` |
| V8 | 成功時の既読化 | 二重処理/処理漏れ | `mark_as_read_on_success=true` で1件検証 | 未検証 | Outlook画面 + `run.log` |

## 安全設計（TPS: ポカヨケ/アンドン/自働化）

- ポカヨケ:
  - 保存先が存在しない場合は即停止
  - 添付名衝突時はリネームして衝突回避（上書き禁止）
  - 暗号化PDFの復号パスワードが一意でない場合は停止
- アンドン:
  - 失敗時は必ずメール通知（`kalimistk@gmail.com`）、traceback と run.log のパスを含める
- 自働化:
  - 未対応のWeb請求URLを検知したら停止（設定/実装が無い状態で続行しない）
