# Scenario 56: 資金繰り表エクセル入力

## 2026-05-27

### [PROCESS][VERIFICATION] Sheet1確認用コピー運用を採用
- 決定:
  - `全社入金予定表` と `資金繰り表` は、吉田様個人フォルダ内のRPA用コピー置き場を使用する。
  - ロボットは原本を直接更新せず、RPA用コピーから別名保存の成果物を作成する。
  - `資金繰り表` が `Sheet1` のみの場合は、確認用コピーとして扱い、`A列=日付`、`C列=工事金`、`D列=転記先` の形式で処理する。
  - `Sheet1` に存在しない日付は、確認用コピーの対象外としてスキップする。
  - 月別シート形式（例: `7.11` / `8.4`、`F列=工事金`、`G列=転記先`）は後方互換として維持する。
- 対象パス:
  - 入力: `\\192.168.7.251\TIC-mainSV\【個人使用フォルダ】\管理部\・𠮷田\RPA\RPA\②資金繰り表入力\全社入金予定表　20260526保存.xlsx`
  - テンプレート: `\\192.168.7.251\TIC-mainSV\【個人使用フォルダ】\管理部\・𠮷田\RPA\RPA\②資金繰り表入力\資金繰り表 20260526保存.xlsx`
- 実装:
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\main.py`
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\preflight_check.py`
- 検証:
  - `python -m py_compile "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\main.py" "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\preflight_check.py"` 成功。
  - `python "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\preflight_check.py" --env PROD` は `9/9` 成功。
  - `python "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\main.py" --env PROD --dry-run --no-mail` 成功。
  - `python "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\main.py" --env PROD --no-mail` 成功。
- 実行結果:
  - 成果物: `\\192.168.7.251\TIC-mainSV\【個人使用フォルダ】\管理部\・𠮷田\RPA\RPA\②資金繰り表入力\資金繰り表 20260526保存_20260527_075949_309512_p28220_b7d2ccca.xlsx`
  - 転記対象は `2026-05-25` → `Sheet1!D59`、`2026-05-29` → `Sheet1!D95` の2件。
  - `2026-06-01` 以降の28件は、今回の `Sheet1` 確認用コピーに存在しないため対象外としてスキップ。
- 7月フォーマット変更時:
  - 実ファイル到着後に `preflight` と `dry-run` でシート名・日付列・工事金列・転記列を再確認する。
  - 列構成が変わった場合は、原本を触らず確認用コピーに対する最小改修で対応する。

### [CONFIG][POKAYOKE][VERIFICATION] PROD/LOCALメール宛先の再固定
- 判明:
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\config\RK10_config_LOCAL.xlsx` には `MAIL_TO` が存在したが、値が本番宛先だった。
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\config\RK10_config_PROD.xlsx` には `MAIL_TO` が欠落していた。
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\main.py` の `ADMIN_EMAIL` が外部Gmailで、PRODの外部宛先禁止ポリシーと矛盾していた。
- 修正:
  - LOCAL `MAIL_TO`: `kalimistk@gmail.com`
  - PROD `MAIL_TO`: `kanri.tic@tokai-ic.co.jp`
  - `ADMIN_EMAIL`: `kanri.tic@tokai-ic.co.jp`
  - `preflight_check.py` で `MAIL_TO` 必須化とPROD社内ドメイン検証を追加。
  - `create_config.py` の再生成テンプレートにもLOCAL/PROD別の `MAIL_TO` を追加。
- バックアップ:
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\config\RK10_config_LOCAL_before_mailfix_20260527_091930.xlsx`
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\config\RK10_config_PROD_before_mailfix_20260527_091930.xlsx`
- 検証:
  - `python -m py_compile "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\main.py" "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\preflight_check.py" "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\create_config.py"` 成功。
  - `python "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\preflight_check.py" --env PROD` は `MAIL_TO: kanri.tic@tokai-ic.co.jp` を確認し `9/9` 成功。
  - `python "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\main.py" --env PROD --dry-run --no-mail` 成功。メールは送信していない。

### [RKS][VERIFICATION] 既存RKSはdry-run固定、本番実行用RKSを別名作成
- 判明:
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\senario\56資金繰り表.rks` は `--env {Env} --dry-run --no-mail` 固定だった。
  - 2026-05-27 09:33実行ログ `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\log\run_20260527_093334.log` は `DRY-RUN` で、実書込・メール送信はしていない。
- 作成:
  - 本番実行用RKS: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\senario\56資金繰り表_PROD実行_20260527_095013.rks`
  - 展開元確認用C#: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\senario\Program_PROD実行_20260527_095013.cs`
- 本番実行用RKSの差分:
  - `--dry-run --no-mail` を削除し、`--env {Env}` のみでPythonを起動する。
  - `env.txt` と `RK10_config_*.xlsx` の参照を絶対パス化する。
  - Pythonプロセスのタイムアウトと終了コードを検査し、異常時はRKS側も失敗扱いにする。
- 静的検査:
  - ZIP内ファイルは `Program.cs`。
  - `--dry-run` なし、`--no-mail` なし、`..\` 相対パスなし、`.bat/.cmd` 参照なし。
  - `try/catch/finally` は各0件。
  - `process.ExitCode != 0` と `TimeoutException` を確認。
- 未完了:
  - RK10で本番実行用RKSを開き、実書込・メールありで1回実行する確認が残っている。

### [RKS][PROD][DONE] 本番実行用RKSの実書込・メール送信確認
- 実行:
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\senario\56資金繰り表_PROD実行_20260527_095013.rks`
- ログ:
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\log\run_20260527_095351.log`
- 結果:
  - `Environment: PROD`
  - `Sheet1` 確認用コピー形式として検出。
  - 転記対象 `2` 件、対象外スキップ `28` 件。
  - `2026-05-25` → `Sheet1!D59` に `31,900,000` を転記。
  - `2026-05-29` → `Sheet1!D95` に `97,966,000` を転記。
  - 保存後の再オープン検証で全 `2` 件一致。
- 成果物:
  - `\\192.168.7.251\TIC-mainSV\【個人使用フォルダ】\管理部\・𠮷田\RPA\RPA\②資金繰り表入力\資金繰り表 20260526保存_20260527_095407_628624_p48264_d8023b53.xlsx`
- メール:
  - Outlook送信済みで `2026-05-27 09:54:34`、宛先 `kanri.tic@tokai-ic.co.jp`、件名 `【Robot56完了】資金繰表転記 PROD` を確認。
- 判定:
  - シナリオ56は、確認用コピー運用におけるRK10本番実行まで完了。

### [DOCS][DONE] 現行運用手順書・フロー図を更新
- 更新:
  - 正本: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs\56_現行運用手順書_20260527.xlsx`
  - 正本: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs\56_現行フロー図_20260527.docx`
  - 作業用Markdown: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs\56_現行運用手順書_20260527.md`
  - 作業用Markdown: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs\56_現行フロー図_20260527.md`
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs\FILE_USAGE_GUIDE.md`
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs\56_仕様書_v1.2.md`
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs\SCENARIO_INFO.md`
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\create_config.py`
- 内容:
  - Sheet1確認用コピー運用、RPAコピー置き場、PROD本番実行RKS、LOCAL/PRODメール宛先、別名保存成果物、JIDOKA検証、異常時停止を現行化。
- 検証:
  - `python -m py_compile "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\create_config.py"` 成功。
  - `rg -n "現行運用|現行フロー|Sheet1確認用コピー|56資金繰り表_PROD実行_20260527_095013|kanri\.tic|192\.168\.7\.251" ...` で現行資料・設定生成テンプレートに主要情報が反映済みであることを確認。
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs\SCENARIO_INFO.md` と `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\create_config.py` に旧 `\\172.20.0.70` パスが残っていないことを確認。
  - `56_現行運用手順書_20260527.xlsx` は `openpyxl` で5シートと主要セルを確認。
  - `56_現行フロー図_20260527.docx` は `python-docx` でタイトル・段落・3テーブルを確認。LibreOffice未導入のためPNGレンダリングQAは未実施。

### [DOCS][RULE] 資料はdocsフォルダに集約
- 決定:
  - シナリオフォルダ直下に手順書・フロー図・仕様メモなどの資料ファイルを置かない。
  - 資料は `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs` 配下に置く。
- 移動:
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\SCENARIO_INFO.md` を `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs\SCENARIO_INFO.md` に移動。
- 検証:
  - シナリオフォルダ直下に `.md` / `.xlsx` / `.docx` の資料ファイルが残っていないことを確認する。

### [SAFE-GATE][FIX] 客先安全入口をsafe gate化し子プロセスUTF-8を固定
- 日付: 2026-06-22
- 背景:
  - 客先安全入口 `C:\ProgramData\RK10\Robots\migration\customer_safe_entries_20260622\56_SAFE_PROD_DRYRUN_NO_MAIL_ここから起動.bat` を `scenario56_safe_gate_nomail_dryrun_20260618.py` 経由に変更した。
  - 親プロセスは `python -X utf8` だったが、safe gate配下のpreflight/main子プロセスは `sys.executable` のみで起動していたため、MainSVパス内の `𠮷` 出力時に `UnicodeEncodeError` が発生した。
- 修正:
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\scenario56_safe_gate_nomail_dryrun_20260618.py` に子プロセス起動ヘルパーを追加し、preflight/mainも `python -X utf8` で起動するよう統一。
  - LOCAL確認入口 `C:\ProgramData\RK10\Robots\migration\customer_safe_entries_20260622\56_SAFE_LOCAL_DRYRUN_NO_MAIL_ここから起動.bat` を追加。
- バックアップ:
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\scenario56_safe_gate_nomail_dryrun_20260618.py.before_utf8_child_process_fix_20260622_1640`
  - `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\scenario56_safe_gate_nomail_dryrun_20260618.py.fixed_utf8_child_process_20260622_1640`
- 検証:
  - `python -m py_compile "C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\scenario56_safe_gate_nomail_dryrun_20260618.py"` 成功。
  - LOCAL safe gate dry-run/no-mailはpreflight 9/9、転記対象2件、対象外0件、書込skipでexit0。
  - PROD safe gate dry-run/no-mailは現PCからMainSV/UNCが見えないため、RPA用コピー置き場未検出でexit1安全停止。UnicodeEncodeErrorは再発していない。
- レポート:
  - `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\s55_s56_customer_safe_entries_runtime_20260622\s55_s56_customer_safe_entries_runtime_20260622.md`

## 2026-06-22 客先安全入口ASCII化と終了コード伝播修正

- `C:\ProgramData\RK10\Robots\migration\customer_safe_entries_20260622\56_SAFE_LOCAL_DRYRUN_NO_MAIL_ここから起動.bat` をASCII本文に変更し、`run_customer_safe_entry.ps1 -Entry s56_local` 経由にした。
- `C:\ProgramData\RK10\Robots\migration\customer_safe_entries_20260622\56_SAFE_PROD_DRYRUN_NO_MAIL_ここから起動.bat` をASCII本文に変更し、`run_customer_safe_entry.ps1 -Entry s56_prod` 経由にした。
- `run_customer_safe_entry.ps1` の終了コード正規化により、PROD側でMainSV未到達が発生した場合に親BATがexit1を返すことを確認した。
- LOCAL再実行: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\s56_ascii_runner_recheck_20260622\run_after_exitcode_fix_20260622_175658\results.json` でexit0。
- PROD再実行: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\s56_ascii_runner_recheck_20260622\run_after_exitcode_fix_20260622_175658\results.json` でexit1。MainSV未到達の安全停止として扱う。
