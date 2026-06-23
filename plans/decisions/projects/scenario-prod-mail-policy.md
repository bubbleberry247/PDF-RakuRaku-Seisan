# PRODメール通知ポリシー

## 2026-05-28 要修正候補の修正

### 決定
- PRODの正常完了通知は原則として担当者または管理部共有メールへ送る。
- PRODのエラー通知は担当者または管理部共有メールに加え、開発確認用に `kalimistk@gmail.com` または既存運用で使っている `masamaru1975@hotmail.com` を含める。
- LOCAL/TESTの送信先はテスト用外部アドレスを維持する。
- シナリオ56は既存の外部ドメイン抑止ポリシーを優先し、PROD外部Gmail追加は行わない。

### 変更したファイル
- `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_prod.json`
  - `mail.error_to` を `kanri.tic@tokai-ic.co.jp` に変更。
  - エラー時の開発宛は既存コードの `REQUIRED_ERROR_RECIPIENTS` で追加されるため、設定では重複させない。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\config\tool_config_prod.json`
  - リポジトリ側のPROD設定はコード側で必須追加されないため、`mail.error_to` に `kanri.tic@tokai-ic.co.jp` と `kalimistk@gmail.com` を明示。
- `C:\ProgramData\RK10\Robots\37レコル公休・有休登録\tools\mail_sender.py`
  - 既定の本番宛先を `kanri.tic@tokai-ic.co.jp` に変更。
- `C:\ProgramData\RK10\Robots\37レコル公休・有休登録\config\RK10_config_PROD.xlsx`
  - `MAIL_TO` を `kanri.tic@tokai-ic.co.jp` に変更。
- `C:\ProgramData\RK10\Robots\38受注登録\tools\mail_sender.py`
  - PROD正常は `kanri.tic@tokai-ic.co.jp`、PRODエラーはCC `kalimistk@gmail.com` に分離。
- `C:\ProgramData\RK10\Robots\42ドライブレポート抽出作業\tools\mail_sender.py`
  - PROD正常は `kanri.tic@tokai-ic.co.jp`、PRODエラーはCC `kalimistk@gmail.com` に分離。
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\mail_sender.py`
  - PRODエラーのみ `kalimistk@gmail.com` をCC追加し、正常通知には追加しない。
- `C:\ProgramData\RK10\Robots\51&52ソフトバンク部門集計楽楽精算申請\tools\mail_sender.py`
  - PROD正常は `kanri.tic@tokai-ic.co.jp`、PRODエラーはCC `kalimistk@gmail.com` に分離。
- `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py`
  - 設定読込失敗時の既定通知先も `kanri.tic@tokai-ic.co.jp` に変更。

### 検証
- Python構文確認: `python -m py_compile` 相当で、37/38/42/44/51&52/57の変更済みPythonを確認。
- JSON確認: 12・13のライブPROD設定とリポジトリ側PROD設定を `json.loads` で確認。
- Excel確認: 37の `RK10_config_PROD.xlsx` の `MAIL_TO` が `kanri.tic@tokai-ic.co.jp` であることを確認。
- Dry-run確認:
  - 38 PRODエラー: To `kanri.tic@tokai-ic.co.jp`, CC `kalimistk@gmail.com`
  - 42 PRODエラー: To `kanri.tic@tokai-ic.co.jp`, CC `kalimistk@gmail.com`
  - 44 PRODエラー: To `kanri.tic@tokai-ic.co.jp`, CC `kalimistk@gmail.com`
  - 51&52 PRODエラー: To `kanri.tic@tokai-ic.co.jp`, CC `kalimistk@gmail.com`
  - 57 PROD設定: 正常 To `kanri.tic@tokai-ic.co.jp`, エラー To `kanri.tic@tokai-ic.co.jp`, CC `kalimistk@gmail.com`

### バックアップ
- ライブファイルは修正前に `.before_prod_mailfix_20260528_*` を同一フォルダへ保存した。

## 2026-05-28 追加修正: PROD正常/エラー通知の未カバー対応

### 決定
- 12・13のPROD正常完了通知は、請求メールボックス `seikyu.tic@tokai-ic.co.jp` へ送る。
- 12・13のPRODエラー通知は、請求メールボックス `seikyu.tic@tokai-ic.co.jp` と開発確認用 `kalimistk@gmail.com` へ送る。
- 37/47/56/63/71のPRODエラー通知は、管理部共有 `kanri.tic@tokai-ic.co.jp` と開発確認用 `kalimistk@gmail.com` の両方へ届くようにする。
- 71のPROD正常終了通知は、管理部共有 `kanri.tic@tokai-ic.co.jp` へ送る。
- 47はRKS内メール処理のため、既存v5を直接上書きせず `４７レコル出退勤_完成版_v6_prod_error_mail.rks` として別名保存する。

### 変更したファイル
- `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_prod.json`
  - `mail.send_success=true`、`mail.success_to=["seikyu.tic@tokai-ic.co.jp"]` に変更。
  - `mail.error_to=["seikyu.tic@tokai-ic.co.jp"]` に変更。開発確認用 `kalimistk@gmail.com` はコード側の必須追加で送る。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\config\tool_config_prod.json`
  - リポジトリ側PROD設定も12・13の成功通知先・エラー通知先に合わせた。
- `C:\ProgramData\RK10\Robots\37レコル公休・有休登録\tools\mail_sender.py`
  - エラー通知メール関数を追加し、PROD時 To=`kanri.tic@tokai-ic.co.jp` / CC=`kalimistk@gmail.com` にした。
- `C:\ProgramData\RK10\Robots\37レコル公休・有休登録\tools\main_37.py`
  - Pythonコマンドの致命エラー時にPRODエラー通知を送るガードを追加。
- `C:\ProgramData\RK10\Robots\47出退勤確認\senario\４７レコル出退勤_完成版_v6_prod_error_mail.rks`
  - v5を別名保存し、PRODサマリーエラー通知先を `kanri.tic@tokai-ic.co.jp;kalimistk@gmail.com` に変更。
- `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\main.py`
  - PROD正常通知は社内ドメイン制限を維持し、PRODエラー時だけ `kalimistk@gmail.com` を許可・追加。
- `C:\ProgramData\RK10\Robots\【63楽楽精算申請（毎月同額支払い分】2026-02-02\tools\automation_20260211_143654_072689.py`
  - PROD正常通知の未設定fallbackを `kanri.tic@tokai-ic.co.jp` にし、PRODエラー通知を To=`kanri.tic@tokai-ic.co.jp` / CC=`kalimistk@gmail.com` にした。
- `C:\ProgramData\RK10\Robots\【63楽楽精算申請（毎月同額支払い分】2026-02-02\config\master_data.xlsx`
  - `設定!notify_to` を `kanri.tic@tokai-ic.co.jp` に設定。
- `C:\ProgramData\RK10\Robots\【71法定調書用　士業請求書集計】2026-01-28\tools\main_71_v2.py`
  - PROD正常終了通知とPRODエラー通知を追加。
- `C:\ProgramData\RK10\Robots\【71法定調書用　士業請求書集計】2026-01-28\config\scenario71_settings_v2.json`
  - 71の通知先設定を追加。

### 検証
- `python -m py_compile` で37/56/63/71の変更済みPythonを確認。
- JSON確認で12・13/71の通知設定を確認。
- Excel確認で63 `master_data.xlsx` の `notify_to` を確認。
- 37のエラー通知を `--test-mode --dry-run` で確認。
- 56のPRODエラー宛先は `kanri.tic@tokai-ic.co.jp` + `kalimistk@gmail.com` が許可され、PROD正常側の外部宛先は引き続きブロックされることを確認。
- 47 v6 RKSはZIP展開でき、`Program.cs` 内にエラー通知先と `OutlookAction.SendEmail` があること、try/catch/finally件数がv5と同じことを確認。

## 2026-05-28 追加修正: 47 PROD正常サマリー宛先

### 決定
- 47のPROD正常サマリー通知は `kanri.tic@tokai-ic.co.jp` へ送る。
- 47のPROD正常サマリー通知は `kalimistk@gmail.com` へ送らない。
- 47のPRODエラー通知は従来通り `kanri.tic@tokai-ic.co.jp;kalimistk@gmail.com` へ送る。

### 変更したファイル
- `C:\ProgramData\RK10\Robots\47出退勤確認\senario\４７レコル出退勤_完成版_v7_prod_success_kanri_error_kanri_kalimistk.rks`
  - v6を上書きせず、v7として別名保存した。
  - `COMPLETE_MAIL_TO_PROD` を `kanri.tic@tokai-ic.co.jp` に変更した。

### 検証
- v6/v7をZIP展開し、`Program.cs` の `COMPLETE_MAIL_TO_PROD`、`ERROR_MAIL_TO`、`OutlookAction.SendEmail` を確認した。
- try/catch/finally件数がv6とv7で同じことを確認した。

## 2026-05-28 追加修正: 58 岡村側通知先

### 決定
- 58の岡村側通知先は `masamaru1975@hotmail.com` ではなく `kalimistk@gmail.com` に統一する。
- PROD正常通知の客先宛 `e-yoshida@unionsystems.co.jp` は維持する。
- PRODエラー通知は `e-yoshida@unionsystems.co.jp` と `kalimistk@gmail.com` へ送る。
- LOCAL通知は `kalimistk@gmail.com` へ送る。

### 変更したファイル
- `C:\ProgramData\RK10\Robots\【58基幹システムより査定支払い分はきだし（25日・末日】2026-01-27\config\tool_config_local.json`
  - `notifications.to` を `kalimistk@gmail.com` に変更。
- `C:\ProgramData\RK10\Robots\【58基幹システムより査定支払い分はきだし（25日・末日】2026-01-27\config\tool_config_prod.json`
  - `notifications.error_cc` を `kalimistk@gmail.com` に変更。
- `C:\ProgramData\RK10\Robots\【58基幹システムより査定支払い分はきだし（25日・末日】2026-01-27\docs\58_業務形式知.md`
  - 現行運用表の通知先を更新。
