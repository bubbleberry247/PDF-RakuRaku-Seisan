# Scenario 43 ETC / Rakuraku Decisions

## 2026-05-21: RK10 RKS改修安全ゲート

- `.rks` はZIP/C#として正常でも、RK10独自の `ReactiveSyntaxTree` 変換で開けない場合がある。
- RKS本体の直接編集は原則避ける。変更は可能な限り外部BAT/Python/CSVへ寄せ、RKSは外部呼び出しの薄い入口にする。
- RKS変更が必要な場合は、RK10で開ける既存RKSを母体にし、1変更ごとに別名保存する。
- RKS変更時の静的ゲートは、`Program.cs`以外の差分なし、`try/catch/finally`増加なし、相対パスなし、未定義関数なし、旧BAT名残りなし。
- RKS変更時の最終ゲートは、必ずRK10で開けること。`zip OK`、C#構文OK、Python/BATテストOKだけではRKS作業完了にしない。
- 本番相当テスト前に、メールなし・一時保存クリックなし・自分IDのみの検証経路を先に用意する。

## 2026-05-21: v85失敗からの教訓

- v85/v85-1ではZIP内 `Program.cs` を直接合成し、RK10で開く確認を最終ゲート化しなかったことが問題だった。
- `..\config\env.txt` のような相対パスはRK10デバッガのTemp実行で破綻するため、RKS側では避ける。
- 今後のシナリオ43改修では、RKSを直接生成するより、RK10エディタで開ける母体を使い、外部スクリプトの契約を堅くする。

## 2026-05-21: v83_5 Playwright一時保存経路を実地確認

- RKSは触らず、外部入口 `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\run_apply_ready_stop_worker_v83_5_playwright.bat` を追加した。
- 実地テストでは `テスト masam` のWindows資格情報を使い、PDFアップロード、2価格明細入力、支払情報入力、一時保存まで確認した。
- 最終申請クリックとメール送信は行っていない。ログ `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\rakuraku_apply_ready_stop_20260521_142230.log` に `draft exists, no application click, no mail` を確認済み。
- 証跡フォルダは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\evidence\masam_temporary_save_20260521_142230`。
- 本番運用でメールを出す場合のみ `--send-mail` を明示する。デフォルトはメール送信なし。

## 2026-05-21: Edgeタブ自動終了ルール

- シナリオ43のPlaywright/Edge操作後は、自動操作用CDPポート `9222` のタブを閉じる。
- ユーザー通常利用のEdgeを巻き込まないため、閉じる対象は自動操作用CDPタブに限定する。
- 手動クリーンアップ入口は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\run_close_edge_automation_tabs.bat`。
- v83_5入口 `run_apply_ready_stop_worker_v83_5_playwright.bat` と `run_temporary_save_v83_5_masam_nomail.bat` は終了時に `tools\close_edge_cdp_tabs.py --port 9222` を呼ぶ。

## 2026-05-21: 一時保存完了メールの成果物添付

- v83_5の一時保存完了メールは、`--send-mail` 明示時だけ送信する。
- 成功メールには申請用PDFと申請用Excelの2ファイルを添付する。
- メール本文には成果物保存先ディレクトリ、添付PDF名、添付Excel名、証跡フォルダを記載する。
- 添付PDF/Excelのどちらかが存在しない場合は `S43_APPLICATION_ATTACHMENT_MISSING` で停止し、不完全な完了メールを送らない。

## 2026-05-21: v86 RKS最小改修

- v81を母体に `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\シナリオ４３客先作業分\本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v86_v81_enter_excel_playwright_mail.rks` を別名作成した。
- RKS内の変更はZIP内 `Program.cs` のみ。`id` / `version` / `meta` / `rootMeta` / 外部リソースはv81と同一バイトであることを確認した。
- `..\config` 相対パスを絶対パスへ変更し、PDF後処理を `run_pdf_annotate_safe_v85_pair_excel.bat` へ差し替えた。
- 楽楽精算のRK10 XPath/Windows「開く」ダイアログ操作は削除せず、2価格検証後に `run_apply_ready_stop_worker_v83_5_playwright.bat --send-mail` を呼んで `return` することでバイパスした。
- 静的ゲートでは `try/catch/finally` 数がv81から増えていないこと、ZIP整合性、UTF-8 BOM維持、外部BAT self-test、関連Python `py_compile` を確認済み。
- 最終ゲートはRK10でこのv86 RKSを手動で開けること。ZIP/C#静的検証だけでは完了扱いにしない。

## 2026-05-21: v86 PROD no-mail版

- v86本体を戻し先として温存し、`C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\シナリオ４３客先作業分\本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v86_prod_nomail.rks` を別名作成した。
- `env.txt=PROD` のまま実行できるが、worker呼び出しから `--send-mail --mail-to` を外したため、成功メールは送信しない。
- RKS外側catchの `エラーメール送信(シナリオエラー)` もno-mail版ではログ出力に置換し、失敗時メールも送信しない。
- 静的ゲートでは `Program.cs` 以外の差分なし、`try/catch/finally` 数の増加なし、`--send-mail` / `--mail-to` 残存なし、ZIP整合性、UTF-8 BOM維持を確認済み。
- メール送信ありへ戻す場合は `v86_v81_enter_excel_playwright_mail.rks` を実行する。

## 2026-05-21: 202604請求の年1回未使用回線料

- v86 no-mail実行時の `run_pdf_annotate_safe_v85_pair_excel.bat ExitCode=12` は、BATが日本語ファイル名フィルタ `ＥＴＣカード利用料_*.xlsx` で元Excelを見つけられず `LATEST_XLS=` になったことが直接原因だった。
- `run_pdf_annotate_safe_v85_pair_excel.bat` は、日本語フィルタをやめ、`*.xlsx` から申請用ファイル名パターン `_YYYYMMDD_AMOUNT` を除外して最新の元Excelを選ぶ方式へ変更した。
- 修正後の次の停止理由は `Department total mismatch: expected=350914 actual=348714`。これは請求PDFの `ご請求額 350,914円` と、通行明細Excelの `通行料合計 348,714円` の差額である。
- 差額 `2,200円` はPDF/CSV上の `年間未使用ETCカード負担金 2,200円 4枚`。ユーザー確認により「1年に1度の使用していない回線の使用料」として扱う。
- 年1回の未使用回線料は、ユーザー確認により管理費として管理部経費に合算する。202604では管理部 `12,850円` に `2,200円` を加え、管理部 `15,050円`、総合計 `350,914円` とする。
- `rk10_reconcile_dept_totals.py` は請求PDFから `年間未使用ETCカード負担金` を検出し、通行料合計との差額と一致する場合のみ管理部へ合算する。申請用Excelには `年間未使用ETCカード負担金` 行を追加し、税込 `2,200円`、税抜 `2,000円`、消費税 `200円` として出力する。
- 後続テスト用として `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\シナリオ４３客先作業分\本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v86_test_nomail_management_fee.rks` を作成した。中身は `v86_prod_nomail.rks` と同一で、メール送信なし、管理費加算済み共通BAT/Pythonを使う。

## 2026-05-21: PROD共有サーバー原本・成果物保存

- PROD時は、共有サーバー `\\192.168.7.251\TIC-mainSV\管理部\40.一般経費用データ\日本情報サービス協同組合\1.データ` を正規保存先にする。
- 既存の月別フォルダ命名は `11278_11278_東海インプル建設㈱_YYYYMM`。Downloads側の `(1)` / `(2)` 付きZIP名は、保存フォルダ名からは除去する。
- `archive_application_outputs_v86.py` を追加し、最新申請用PDF/Excelペアのmanifestから利用月を読み、同じ月の最新ZIPを検証して、解凍済み原本を月別フォルダへ保存する。
- Python標準 `zipfile` は今回のETC ZIP内の日本語ファイル名をCP437として誤読するため、UTF-8フラグなしのZIPメンバー名は `cp437 -> cp932` で復元してから保存する。これをしないとサーバー上に文字化けファイルを作る。
- 最終成果物は月別フォルダ直下ではなく、`申請用成果物` サブフォルダへ `【申請用】...pdf`、`【申請用】...xlsx`、`【申請用】...manifest.json` の3点を保存する。
- `run_pdf_annotate_safe_v85_pair_excel.bat` はPDF/Excel生成後に `archive_application_outputs_v86.py` を呼ぶ。envがPROD以外の場合は保存をSKIPする。
- 一時保存完了メールはmanifest内 `server_archive.outputs_dir` がある場合、共有サーバー保存先も本文へ記載する。
- 202604実地保存結果: `\\192.168.7.251\TIC-mainSV\管理部\40.一般経費用データ\日本情報サービス協同組合\1.データ\11278_11278_東海インプル建設㈱_202604\申請用成果物` にPDF/Excel/manifestを保存済み。ZIP原本6件は既存フォルダ内ファイルと一致し、追加抽出0件、既存一致6件だった。

## 2026-05-21: RKSラッパー化を進める外部統合入口

- 今後のシナリオ43は、RKSを「薄いラッパー」として扱い、重要処理は外部PY/BATへ寄せる。
- 外部統合入口として `run_scenario43_external_pipeline_v87.bat` と `tools\scenario43_external_pipeline_v87.py` を追加した。
- 統合入口は、`run_pdf_annotate_from_latest_zip_v85.bat` による最新ETC ZIPステージング・PDF/Excel生成・共有サーバー保存と、`run_apply_ready_stop_worker_v83_5_playwright.bat` による楽楽精算一時保存を順番に呼ぶ。
- メール送信は `--send-mail` を明示した場合だけ行う。デフォルトはメールなし。
- テスト用入口として `run_scenario43_external_pipeline_v87_masam_nomail.bat` を追加した。`テスト masam` のWindows資格情報を使い、`--temporary-save-only` 付きで動く。
- BATはcmd互換性のためCRLFで保存する。LFのみだと日本語変数を含むBATが `is not recognized as an internal or external command` を出すことがある。
- 検証済み: `python -m py_compile tools\scenario43_external_pipeline_v87.py`、`run_scenario43_external_pipeline_v87.bat --self-test`、`run_scenario43_external_pipeline_v87_masam_nomail.bat --self-test`、`run_scenario43_external_pipeline_v87.bat --skip-pdf --skip-rakuraku`。
- `scenario43_external_pipeline_v87.py` は子BAT出力をbytesで受け、UTF-8/CP932順に復号する。これにより、失敗時JSON出力がcp932の `UnicodeEncodeError` で二次停止する問題を避ける。
- dry-run/smokeでは `--allow-existing-draft` をworkerへ渡す。既に一時保存ドラフトが存在する場合でも、対象PDF・2価格・科目の検証に成功すればOK扱いにする。通常実行では従来どおり既存ドラフトを検出したら停止する。
- 2026-05-21 17:51実行: `run_scenario43_external_pipeline_v87_masam_nomail.bat --skip-pdf --rakuraku-dry-run` は成功。ログ `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\rakuraku_apply_ready_stop_20260521_175103.log` で、既存ドラフト1件検出、詳細ページ検証成功、`temporary-save-only accepted existing draft for dry-run/smoke` を確認。

## 2026-05-21: v87 RKS no-mailラッパー版

- `v86_prod_nomail.rks` を母体に、`C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\シナリオ４３客先作業分\本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v87_external_pipeline_wrapper_nomail.rks` を別名保存で作成した。
- v87 RKSは、既存v80/v86由来のETCログイン・Enter送信・ZIPダウンロード待ちまでは維持し、ダウンロード完了直後に `run_scenario43_external_pipeline_v87.bat` を呼んで `return` する。
- RKSから外部統合入口へ渡す値は、担当者GUIの `operator-name`、`login-credential`、`password-credential` の3つ。`--send-mail` と `--mail-to` は渡さないためメールなし版である。
- 旧RKS内のZip展開、Excel加工、PDF後処理、部署別金額検証、楽楽精算RK10ブラウザ操作、完了メールブロックは削除せず、`return` 後の未到達コードとして残した。RK10 ReactiveSyntaxTree破損リスクを避けるため、構造削除はしない。
- 静的ゲート結果: ZIP `testzip=None`、`Program.cs` 以外の `id` / `meta` / `version` / `rootMeta` / `externalActivitiesMeta` は母体と同一、`try/catch/finally` 数は `4/4/0` のまま、`--send-mail` / `--mail-to` なし。
- 外部契約検証: `run_scenario43_external_pipeline_v87.bat --self-test` と関連Python `py_compile` はPASS。
- 最終ゲートはRK10でこのv87 RKSを手動で開けること。ZIP/C#静的検証だけではRKS作業完了にしない。

## 2026-05-21: v87 ZIPステージング標準出力文字コード修正

- v87 RKS実行時の `run_scenario43_external_pipeline_v87.bat ExitCode=1` は、`stage_latest_etc_zip_v85.py` がZIPステージング成功後に `print(json.dumps(..., ensure_ascii=False))` した際、Windows `cp932` で表現できないZIPメンバー名由来文字に当たったことが原因だった。
- `stage_latest_etc_zip_v85.py` に標準出力/標準エラーの `utf-8` + `backslashreplace` 設定を追加した。
- `run_stage_latest_etc_zip_to_pdf_in_v85.bat` に `PYTHONIOENCODING=utf-8:backslashreplace` を追加し、cmd配下のPython出力を固定した。
- ZIP内メンバー名はUTF-8フラグなしの場合だけ `cp437 -> cp932` で復元してmanifestへ記録する。202604の `invoice_entry` は `PDF/202604-500法人請求書11278東海インプル建設㈱.pdf` として正常表示される。
- 検証済み: `python -m py_compile stage_latest_etc_zip_v85.py`、`run_stage_latest_etc_zip_to_pdf_in_v85.bat --self-test`、`run_scenario43_external_pipeline_v87.bat --self-test`、`run_scenario43_external_pipeline_v87.bat --skip-rakuraku`。
- 2026-05-21 18:55実行の `--skip-rakuraku` は成功し、PDF/Excel/manifestを再生成して共有サーバー `...\11278_11278_東海インプル建設㈱_202604\申請用成果物` へ保存済み。

## 2026-05-21: v87外部パイプライン完了マーカー

- RK10側のシナリオ画面が開いたままでも、外部パイプラインの完了状態を機械的に確認できるように、`scenario43_external_pipeline_v87.py` に完了マーカー出力を追加した。
- 成功時は `Temp\scenario43_external_pipeline_v87_last_completion.json`、時刻付き `Temp\scenario43_external_pipeline_v87_completion_YYYYMMDD_HHMMSS.json`、人間確認用 `Temp\scenario43_external_pipeline_v87_DONE.txt` を出力する。
- 完了ステータスは `COMPLETED_TEMPORARY_SAVE`、`COMPLETED_OUTPUTS_ONLY`、`COMPLETED_DRY_RUN`、`COMPLETED_NOOP` に分ける。通常の一時保存完了は `COMPLETED_TEMPORARY_SAVE` になる。
- 完了マーカーには `final_application_clicked=false`、`mail_requested`、実行担当者、申請用PDF/Excel、総額、利用月、manifest、共有サーバー保存先、ログ、証跡フォルダを記録する。
- 安全境界は引き続き「一時保存まで」。最終申請クリックは自動実行しない。
- 検証済み: `python -m py_compile scenario43_external_pipeline_v87.py`、`run_scenario43_external_pipeline_v87.bat --self-test`、`run_scenario43_external_pipeline_v87.bat --skip-pdf --skip-rakuraku`。

## 2026-05-21: v87実行完了確認

- 2026-05-21 19:56:27 に `Temp\scenario43_external_pipeline_v87_last_completion.json` が `COMPLETED_TEMPORARY_SAVE` を記録した。
- 実行環境は `PROD`、実行担当者は `テスト masam`、`mail_requested=false`、`final_application_clicked=false`。成功メール送信と最終申請クリックは行っていない。
- `pdf_excel_archive_pipeline` と `rakuraku_temporary_save` はどちらも `return_code=0`。
- 処理対象ZIPは `C:\Users\masam\Downloads\11278_11278_東海インプル建設㈱_202604 (5).zip`、請求PDFエントリは `PDF/202604-500法人請求書11278東海インプル建設㈱.pdf`。
- 申請用成果物は `【申請用】日本情報サービス協同組合_20260519_350914.pdf` と `【申請用】日本情報サービス協同組合_20260519_350914.xlsx`。総額は `350,914円`、利用月は `2026-04`。
- 共有サーバー保存先は `\\192.168.7.251\TIC-mainSV\管理部\40.一般経費用データ\日本情報サービス協同組合\1.データ\11278_11278_東海インプル建設㈱_202604\申請用成果物`。PDF/XLSX/manifestの3点が存在することを確認済み。
- Playwrightワーカーは一時保存完了後に自動操作タブ3件を閉じた。Pythonプロセスは残っていないことを確認済み。

## 2026-05-21: 目視確認メールの送信経路注意

- `send_completion_mail_v85.py` はOutlook COM送信に失敗してもシナリオ継続のため `exit 0` を返す設計。メール送信確認ではRCだけを信用せず、標準出力/ログの `[OK] Mail sent` を確認する。
- 2026-05-21 20:12の手動送信テストでは、Outlook COMが `サーバーの実行に失敗しました` を返し、自動送信できなかった。ログは `Temp\manual_send_final_notice_to_masam_20260521_201252.log`。
- 代替としてGmail下書きに目視確認用メールを作成した。正しい下書きは件名 `[TEST] シナリオ43 一時保存完了通知（目視確認・PDF+Excel添付）` で、申請用PDFと申請用Excelの2ファイルを添付済み。
- その前にZIP添付の下書きも1件作成されたため、目視確認ではPDF+Excel 2添付の下書きを正として扱い、ZIP添付の下書きは破棄してよい。

## 2026-05-21: v89一時保存後メール失敗修正と支払依頼形式知

- v89の `run_scenario43_external_pipeline_v87.bat ExitCode=1` は、支払依頼の一時保存失敗ではなく、一時保存完了後の成功メール作成で `TargetData.manifest_path` が無いことにより落ちたもの。一次ソースは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\rakuraku_apply_ready_stop_20260521_214325.log` の `temporary save completed` と `AttributeError: 'TargetData' object has no attribute 'manifest_path'`。
- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\rakuraku_apply_ready_stop_v60-1_operator_2price.py` の `TargetData` に `manifest_path` を追加し、申請用Excel manifestを保持するようにした。`_send_mail` は `encoding="utf-8", errors="replace"` で子プロセス出力を読む。
- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\rakuraku_temporary_save_v83_5_operator_2price.py` は `_target_manifest_path()` を追加し、古いTargetData形状でも `申請用Excel名.manifest.json` へフォールバックする。
- 完了メールのバトンタッチ情報は、部署 `TIC001 管理部`、支払先 `日本情報サービス協同組合`、支払予定日、支払方法 `口座振替`、備考 `ETC利用料金R8.4月分(一般経費のみ)`、2明細、科目 `30008 旅費交通費`、PDF/Excel添付名を明記する。
- 支払依頼画面の形式知調査用に `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\rakuraku_research_payment_history_v90.py` と `run_research_payment_history_v90.bat` を追加した。読み取り専用で、申請一覧検索・現在の一時保存・入力履歴をJSONへ保存し、CDPタブを閉じる。
- 2026-05-21 22:04調査結果は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\history_research\20260521_220452\rakuraku_payment_history_research.json`。現在の一時保存は `projectCd=TIC001`、`shihaName=日本情報サービス協同組合`、`shihaYoteiDate=2026/06/01`、`paymentMethod=口座振替`、`remark=ETC利用料金R8.4月分(一般経費のみ)`、`flowCd=TIC15`。
- 同調査で、振込先銀行・支店・口座番号・口座名義は現在の一時保存上では空欄だった。`口座振替` 案件ではPDFの銀行情報を推測入力しない。支払先コードや銀行情報を自動入力したい場合は、先に支払先マスタ検索で `日本情報サービス協同組合` を読取専用検証し、マスタ選択で自動補完されるか確認する。
- 入力履歴の形式知は、現行は2価格方式: `旅費交通費 / 日本情報サービス協同組合 / ETCカード利用料 YYYY.M月分 工事原価分 / 金額` と `旅費交通費 / 日本情報サービス協同組合 / ETCカード利用料 YYYY.M月分 販管費分 / 金額`。古い5部署方式（営繕・技術・業務・営業・管理）は履歴に残るが現行正は2価格方式。
- 検証済み: `python -m py_compile`（関連4ファイル）、`run_research_payment_history_v90.bat --self-test`、`run_apply_ready_stop_worker_v83_5_playwright.bat --self-test`、`run_scenario43_external_pipeline_v87.bat --self-test`、`send_completion_mail_v88.py --self-test`。

## 2026-05-21: v88 ETCサイト自動クローズ

- v87を母体に、別名RKS `本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v88_external_pipeline_wrapper_nomail_close_etc_site.rks` を作成した。
- v88 RKSはETC ZIPダウンロード完了待ち後、外部統合パイプライン実行前に `run_close_etc_download_site_tabs_v88.bat` を非同期起動する。RKS本体ではブラウザ終了APIを直接待たないため、EndBrowserタイムアウトで本処理を止めない。
- クローズ対象は `rbbrier.eco-serv.jp`、`eco-serv.jp/etc`、`WEB請求サービス` に一致するEdgeタブ/ウィンドウだけ。まずCDPの対象タブを閉じ、CDPが使えない場合はEdgeのトップレベルウィンドウタイトル一致で `WM_CLOSE` を送る。
- 既存のv87 RKSは上書きしていない。v88 RKSのZIP検査は `testzip=None`、`Program.cs` 以外の `ExternalActivities.cs` / `id` / `version` / `meta` / `rootMeta` / `externalActivitiesMeta` はv87と同一、`try/catch/finally` 数は `4/4/0` のまま。
- `close_etc_download_site_tabs_v88.py` は標準出力を `utf-8` + `backslashreplace` に固定し、Edgeタイトル中の特殊文字で `UnicodeEncodeError` が起きないようにした。
- 検証済み: `python -m py_compile close_etc_download_site_tabs_v88.py`、`run_close_etc_download_site_tabs_v88.bat --dry-run`、v88 RKS静的検証。
- 2026-05-21 20:37、残っていた `WEB請求サービス および他 2 ページ - 個人 - Microsoft​ Edge` ウィンドウ1件を手動でクローズし、その後のdry-runで一致0件を確認した。

## 2026-05-21: v88実行完了確認

- 2026-05-21 20:57:18 に `Temp\scenario43_external_pipeline_v87_last_completion.json` が `COMPLETED_TEMPORARY_SAVE` を記録した。
- `Temp\close_etc_download_site_tabs_v88_20260521_205327.log` で、`WEB請求サービス および他 1 ページ - 個人 - Microsoft​ Edge` ウィンドウ1件を検出し `closed=1` を確認した。
- 処理対象ZIPは `C:\Users\masam\Downloads\11278_11278_東海インプル建設㈱_202604 (6).zip`。請求PDFエントリは `PDF/202604-500法人請求書11278東海インプル建設㈱.pdf`。
- `pdf_excel_archive_pipeline` と `rakuraku_temporary_save` はどちらも `return_code=0`。楽楽精算は一時保存完了、最終申請クリックなし、メール送信なし。
- Playwright worker終了後の楽楽精算自動操作タブは3件クローズ済み。確認時点でPythonプロセスなし、`WEB請求サービス` / 楽楽精算系タイトルのEdgeウィンドウなし。

## 2026-05-21: RKS配置をscenario直下へ統一

- ユーザー作業により、v61以降のRKSは `scenario\シナリオ４３客先作業分` から1階層上の `scenario` 直下へ移動された。
- 2026-05-21 21:05確認時点で、v61〜v88の主要RKSは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario` 直下に存在する。
- 最新実行候補のv88は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v88_external_pipeline_wrapper_nomail_close_etc_site.rks`。
- 今後の案内では、旧パス `scenario\シナリオ４３客先作業分\...v88...rks` ではなく、`scenario` 直下のv88を正として扱う。

## 2026-05-21: v89メール送信復旧・本番切替掃除

- Outlook COM送信失敗をRC=0で見逃さないため、`C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\pdf_annotate\send_completion_mail_v88.py` を追加した。`--strict` 時は送信失敗で非0終了し、`--save-eml-on-failure` 時は `Temp\mail_fallback` に `.eml` を保存する。
- `send_completion_mail_v88.py` はまず既存Outlook COMへ接続し、失敗時のみ `--allow-outlook-restart --restart-only-if-no-visible-window` 条件で、表示中Outlookウィンドウがない場合だけOutlook再起動を試す。送信成否は `--result-json` に記録する。
- 楽楽精算一時保存ワーカーのメール経路は `send_completion_mail_v88.py` を優先し、成功メール送信が失敗した場合は `S43_MAIL_SEND_FAILED` で停止する。これにより「一時保存はできたがメールは飛んでいない」を成功扱いしない。
- v88 no-mail版を母体に、メールあり版RKS `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v89_external_pipeline_wrapper_mail_close_etc_site.rks` を別名保存した。変更はZIP内 `Program.cs` の外部統合入口引数に `--send-mail` を追加しただけで、`--mail-to` は渡さないため送信先は `env.txt` 依存の既定値になる。
- v89 RKS静的ゲートは `testzip=None`、変更エントリ `Program.cs` のみ、`try/catch/finally` 数はv88と同じ `4/4/0`、`--send-mail` あり、`--mail-to` なしを確認済み。最終ゲートはRK10でv89を開けること。
- 本番前にテスト担当者を戻せるよう、`C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\run_remove_masam_test_operator_v89.bat` と `tools\remove_masam_test_operator_v89.py` を追加した。通常実行はdry-run、`--apply` 時のみCSVバックアップ後に `テスト masam` 行とWindows資格情報 `ログインID　楽楽精算_masam_TEST` / `パスワード　楽楽精算_masam_TEST` を削除する。
- 検証済み: `python -m py_compile`（v88メール送信、v89掃除、関連ワーカー3本）、`send_completion_mail_v88.py --self-test`、`run_remove_masam_test_operator_v89.bat --self-test`、`run_remove_masam_test_operator_v89.bat` dry-run、`run_apply_ready_stop_worker_v83_5_playwright.bat --self-test`。

## 2026-05-21: v89メールあり実行完了確認

- 2026-05-21 22:31:06 に `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\scenario43_external_pipeline_v87_last_completion.json` が `COMPLETED_TEMPORARY_SAVE` を記録した。
- 実行環境は `PROD`、実行担当者は `テスト masam`、`mail_requested=true`、`final_application_clicked=false`。安全境界は引き続き一時保存までで、最終申請クリックは行っていない。
- `pdf_excel_archive_pipeline` と `rakuraku_temporary_save` はどちらも `return_code=0`。一次ログは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\scenario43_external_pipeline_v87_20260521_222915.log`。
- 成果物は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\work\pdf_out\【申請用】日本情報サービス協同組合_20260519_350914.pdf` と `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\work\pdf_out\【申請用】日本情報サービス協同組合_20260519_350914.xlsx`。総額は `350,914円`、利用月は `2026-04`。
- 共有サーバー保存先は `\\192.168.7.251\TIC-mainSV\管理部\40.一般経費用データ\日本情報サービス協同組合\1.データ\11278_11278_東海インプル建設㈱_202604\申請用成果物`。PDF/XLSX/manifestの3点が存在することを確認した。
- 完了メールは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\send_completion_mail_v88_20260521_223106.json` で `status=SENT`、宛先 `kanri.tic@tokai-ic.co.jp`、添付2件、Outlook `GetActiveObject` 成功を確認した。
- ETCサイトのEdgeウィンドウは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\close_etc_download_site_tabs_v88_20260521_222908.log` で `closed=1`。楽楽精算側の自動操作タブはworkerログ内で3件クローズ済み。

## 2026-05-21: 支払先マスタ読取専用調査

- 支払先マスタ調査用に `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\rakuraku_research_supplier_master_v90.py` と `run_research_supplier_master_v90.bat` を追加した。保存・一時保存・申請は押さず、支払先検索と未保存フォーム上の選択結果だけをJSON保存する。
- `テスト masam` 権限で `日本情報サービス協同組合`、`日本情報`、`情報サービス`、`協同組合`、`日本情報サービス`、`JIS`、`T2290005015070` を検索したが、よく使う項目・すべて・画面ダイアログ検索のいずれも0件だった。代表証跡は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\supplier_master_research\20260521_231537\rakuraku_supplier_master_research.json`。
- 検索ロジックの陽性確認として `ガステクノ` 検索は2件を返した。証跡は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\supplier_master_research\20260521_231748\rakuraku_supplier_master_research.json`。
- 実在する一意候補 `ナルハマ` を未保存フォーム上で選択したところ、支払先コード `TF009`、支払先名 `株式会社ナルハマ`、支払予定日 `2026/06/01`、銀行コード `0543`、支店コード `161`、口座種別 `1`、口座番号 `3001540`、口座名義 `ｶ)ﾅﾙﾊﾏ` が自動補完された。証跡は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\supplier_master_research\20260521_231905\rakuraku_supplier_master_research.json`。
- 長坂とも子権限でも `日本情報サービス協同組合` は0件だった。証跡は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\supplier_master_research\20260521_232042\rakuraku_supplier_master_research.json`。
- 瀬戸阿紀子権限は自動ログインが完了せず、マスタ検索まで到達しなかった。エラーは `Rakuraku Seisan login did not complete`。否定的結論には使わない。
- 結論: 楽楽精算は支払先マスタ選択で振込先・口座番号を自動補完できる。ただし、日本情報サービス協同組合は現時点で検索可能な支払先マスタに見つからないため、シナリオ43ではPDF銀行情報を推測入力せず、従来どおり支払先名テキスト入力 + 支払方法 `口座振替` で止める。口座情報まで自動入力するには、まず楽楽精算側の支払先マスタ登録または表示権限確認が必要。

## 2026-05-21: 2025年11月動画からの楽楽精算実業務フロー確認

- 一次ソース動画は `C:\Users\masam\Desktop\KeyenceRK\ロボット作成資料\43 【⑥楽楽精算申請】2025-11-24 16-30-01.mp4`。`ffprobe` で長さ `266.5秒`、3分10秒以降を抽出し、証跡は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\video_flow_20260521_43` に保存した。
- 3:10時点では楽楽精算トップから `支払依頼` の `一覧` 系入口を開く。3:15〜3:20で `支払依頼` の申請一覧を検索し、検索キーワードは `日本情報サービス協同組合`、対象年は `2023年〜2025年`。過去の申請済み支払依頼を選ぶ。
- 3:25では過去申請の詳細画面を開き、下部の `コピー` を押して新規支払依頼へ複製している。これは支払先マスタ検索ではない。
- 3:30〜3:40のコピー後入力画面では、会社名 `東海インプル建設株式会社(300)`、部署名 `TIC001 管理部`、申請者 `30085 瀬戸 阿紀子`、支払先名 `日本情報サービス協同組合`、支払方法 `口座振替`、承認者 `吉田恵理 300999` / `北村健 30002` が入っている。支払先コードは未入力、振込先・振込先支店・口座番号・口座名義は空欄、口座種別は普通、振込手数料は当方負担。
- 同画面で支払予定日を `2025/11/04` から `2025/12/01` へ変更し、備考を `ETC利用料R7.10月分(一般経費のみ)` に更新している。
- 3:55では `領収書/請求書一覧` から当月アップロード済みの請求PDFを選び、4:05では支払依頼明細にPDFが紐づいた状態で金額・科目・摘要を確認している。
- 4:10では最終的な支払依頼PDFが出力され、支払先 `日本情報サービス協同組合`、支払予定日 `2025/12/01`、支払方法 `口座振替`、振込先欄は空欄、総額 `94,495円`、明細は部署別の旧形式で出力されている。
- 現行v89との差分: 動画の人手フローは「過去申請コピー」を使うが、現行v89はブラウザ差異回避と2価格要件のため、最新PDF/Excelから明細を再構成し、支払先名・支払予定日・支払方法・備考・2明細・PDF添付を直接入力する。銀行/口座欄を空欄にする点は動画の実業務フローと一致する。
- 重要判断: `日本情報サービス協同組合` の支払先コード・銀行情報を推測入力しない方針は動画でも補強された。動画でも支払先コード・振込先・口座番号は空欄で、支払方法 `口座振替` のまま申請している。

## 2026-05-21: 過去申請コピーは自動化では不要

- ユーザー確認により、動画内の過去支払依頼コピーは人手作業の手順省略のための操作であり、自動化では必須ではない。
- 自動化では過去申請コピーを使わず、最新ZIP/PDF/Excelを正として支払先名・支払予定日・支払方法・備考・2価格明細・PDF添付を直接入力する現行v89方針を維持する。
- 過去申請コピーは古い部署別明細、過去添付、過去備考を引きずるリスクがあるため、2価格要件では採用しない。
- この判断による追加実装は不要。既存の直接入力ルートを正とする。

## 2026-05-21: 過去コピー不要方針の実装照合

- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\rakuraku_apply_ready_stop_v60-1_operator_2price.py` は、支払先 `日本情報サービス協同組合` と支払方法 `口座振替` を定数で持ち、2価格明細、支払予定日、備考を直接入力している。
- 同ファイルの `_fill_payment_header_and_save` は `shihaName`、`shihaYoteiDate`、`freeText2`、`biko` を入力後に画面値を読み戻して検証し、一時保存までで止める。
- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\rakuraku_temporary_save_v83_5_operator_2price.py` は既存アップロードPDFまたは現在作成中の支払依頼に対して同じ直接入力関数を呼び、最終申請ボタンは押さない。
- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\*.py` を `コピー|copy\(|click\(.*コピー|支払依頼.*コピー` で検索し、支払依頼コピーをクリックする自動化経路は検出されなかった。
- 検証済み: `python -m py_compile`（外部パイプライン、Playwright wrapper、楽楽本体）、`run_apply_ready_stop_worker_v83_5_playwright.bat --self-test`、`run_scenario43_external_pipeline_v87.bat --self-test` はすべて成功した。

## 2026-05-22: 客先移行用資料・持参パッケージ v89

- 客先移行時の正本RKSは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v89_external_pipeline_wrapper_mail_close_etc_site.rks` とする。
- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_業務フロー図.drawio` をv89フローへ更新した。内容は最新ZIP取得、外部Pythonパイプライン、申請用PDF+Excel生成、Playwrightによる楽楽精算PDFアップロード、2価格支払依頼入力、一時保存、PDF+Excel添付メール、担当者手動申請。
- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_業務フロー説明資料.md` と `43_運用ガイド.md` をv89仕様へ更新した。旧5部署申請確定ではなく、2価格・一時保存・PDF+Excel添付・共有保存先記載を正とする。
- 客先移行用の持参ファイル正本として `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_客先移行_持参ファイル一覧_v89.md` を追加した。資格情報本体、Temp、Edgeプロファイル、テスト用 `テスト masam` は持参しない。
- パッケージ作成スクリプト `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\build_customer_migration_package_v89.ps1` を追加した。`config\rakuraku_operators.csv` は `masam_TEST` を除外してパッケージ化する。
- 生成済みパッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v89_20260522_005020.zip`。展開フォルダは同名拡張子なし、manifest上のファイル数は43。
- `deploy\00_preflight.bat` の必須ファイルチェックをv89実行経路へ更新し、旧v81/v82/v83 guarded RKSや旧v60-1/v83 BAT要求を削除した。
- 検証済み: draw.io XML構文、関連Python `py_compile`、`run_scenario43_external_pipeline_v87.bat --self-test`、`run_pdf_annotate_from_latest_zip_v85.bat --self-test`、`run_apply_ready_stop_worker_v83_5_playwright.bat --self-test`、パッケージ作成、パッケージ内 `rakuraku_operators.csv` の `masam_TEST` 除外。

## 2026-05-22: 非エンジニア向け業務説明資料・条件分岐フロー図

- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_業務フロー説明資料.md` を非エンジニア向けに書き換えた。`Playwright`、`manifest`、`Python`、`パイプライン`、`トークン` 等の保守者向け語は本文から外し、担当者が見る「何を確認するか」「どこで止まるか」「一時保存後に何をするか」を中心にした。
- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_業務フロー図.drawio` を客先説明用の全体フローに更新した。ロボット処理、担当者操作、楽楽精算入力、一時保存、完了メール、担当者の手動申請を図示する。
- 新規に `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_条件分岐フロー図.drawio` を追加した。最新請求データ取得、PDF/Excel月額一致、成果物作成、楽楽精算PDF添付、支払依頼入力の各判断で、NG時は停止・連絡する流れを図示する。
- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_運用ガイド.md` の冒頭と実行手順の文言を非エンジニア向けに寄せ、条件分岐フロー図への参照を追加した。
- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_客先移行_持参ファイル一覧_v89.md` に `43_条件分岐フロー図.drawio` を必須持参資料として追加した。
- 検証済み: `43_業務フロー図.drawio` と `43_条件分岐フロー図.drawio` のXML構文、客先向け資料内の技術語除去確認、パッケージ作成。新しい移行パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v89_20260522_010234.zip`、manifest上のファイル数は44。

## 2026-05-22: S43_UNKNOWN manifest_path 成功メール後処理エラーの整理

- 2026-05-21 21:45の通知メール `[RK10 Robot] ERROR S43_UNKNOWN - Scenario 43 ETC (PROD)` は、楽楽精算の一時保存が完了した後、成功メール本文に共有サーバー保存先を追加する処理で `AttributeError: 'TargetData' object has no attribute 'manifest_path'` が発生したもの。
- 一次ログは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\rakuraku_apply_ready_stop_20260521_214325.log`。同ログでは `temporary save completed` の後に `_build_success_mail_addendum` で失敗しているため、誤申請ではなく「一時保存後の成功メール本文作成エラー」だった。
- 現行コード `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\rakuraku_temporary_save_v83_5_operator_2price.py` は、`target.manifest_path` が無い旧TargetDataでも `application_workbook_path` から `*.xlsx.manifest.json` を推定する `_target_manifest_path()` を使う構造に修正済み。
- 再発防止として同ファイルの `self_test()` に `manifest_path` 属性が無いTargetData風オブジェクトで成功メール本文を作れることを確認する `manifest_path_fallback` テストを追加した。
- 最新成功状態は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\scenario43_external_pipeline_v87_last_completion.json` が `COMPLETED_TEMPORARY_SAVE`、`mail_requested=true`、`final_application_clicked=false`。最新送信結果 `Temp\send_completion_mail_v88_20260521_235907.json` は `status=SENT`、添付PDF/XLSXの2件を確認済み。
- 検証済み: `python -m py_compile`（楽楽一時保存ワーカー、v60-1基底、外部パイプライン）、`run_apply_ready_stop_worker_v83_5_playwright.bat --self-test`（`manifest_path_fallback=True`）、`run_scenario43_external_pipeline_v87.bat --self-test`、移行パッケージ再作成。新しいパッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v89_20260522_013602.zip`。

## 2026-05-22: 客先向けWord/PDF資料化とsetup継続実行化

- 非エンジニアが `.md` を読めない問題に対応し、客先向け正本資料として `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_客先向け_業務説明資料_v89.docx` / `.pdf` と `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_客先移行_セットアップ手順書_v89.docx` / `.pdf` を作成した。
- 生成スクリプトは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\tools\build_scenario43_v89_customer_docs.py`。Word COMでPDF化し、PyMuPDFでPDFページ画像を `docs\customer_v89_render` に出力して目視確認した。
- 前回移行トライ時に `deploy\01_setup.bat` が1箇所の失敗で後続インストールに進めなかった問題に対応し、`deploy\01_setup.bat` を薄い入口、`deploy\01_setup_resilient_v89.ps1` を実処理に分離した。新setupは個別失敗後も後続チェックを継続し、最後にOK/NG一覧を出す。
- BAT/PS1はcmd.exeの文字化け・誤解釈を避けるため、実行系ファイル内の表示文言をASCII中心にした。日本語説明はWord/PDF資料側に置く。
- `deploy\build_customer_migration_package_v89.ps1` に `deploy\01_setup_resilient_v89.ps1` と `*v89.docx` / `*v89.pdf` の同梱を追加した。古い `43_運用ガイド.docx` や旧 `43_業務フロー図.drawio.pdf` は同梱対象外。
- 検証済み: `deploy\01_setup.bat --no-pause` はこのPCで全項目OK、`build_scenario43_v89_customer_docs.py` の `py_compile`、Word/PDF生成、PDFレンダー画像の目視確認、移行パッケージ作成。最新パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v89_20260522_015719.zip`、manifest上のファイル数は49。

## 2026-05-22: 客先PCのETC明細画面ローディング遅延対策

- 客先移行時にEdgeで `https://rbbrier.eco-serv.jp/etc/mypage/` へ入り「明細の確認」タブをクリックするとローディングが非常に長い事象を確認。v89 RKSのETC取得部はまだRK10 Web操作で、`bapPublishedBillAppSearch` へ遷移後60秒待機、一覧の先頭リンククリック後45秒待機して外部パイプラインへ進むため、客先回線が遅い場合はZIP保存完了前に後段が動くリスクがある。
- RKS本体は破損リスクを避けて変更せず、`C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\stage_latest_etc_zip_v85.py` に最大600秒のZIP待機、`.crdownload` 検知、5秒のファイル安定確認、30分以内の新規ZIP優先を追加した。手動再処理だけ `--allow-stale` で古いZIP利用を許可できる。
- v89 RKSが既に参照していたが未配置だった `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\rk10_43_download_button_watcher.ps1` を追加した。RKSのETCリンククリック直前からDownloadsを監視し、新規ZIP保存完了またはタイムアウトをTempログに残す。
- 客先移行時の手動スモーク確認として `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\04_etc_site_smoke.bat` を追加した。ETCサイトを開き、ログイン後に「明細の確認」一覧と最新請求データが表示されることを人が確認する。5分以上ローディングする場合はRKSを実行せず、ネットワーク・プロキシ・ETCサイト状態を先に確認する。
- `deploy\00_preflight.bat`、`docs\tools\build_scenario43_v89_customer_docs.py`、`docs\43_運用ガイド.md`、`docs\43_業務フロー説明資料.md`、`docs\43_客先移行_持参ファイル一覧_v89.md` を更新し、ETC明細画面の遅延確認と新規ファイルを移行手順に含めた。
- 検証済み: `python -m py_compile`（ZIPステージング、資料生成）、`run_stage_latest_etc_zip_to_pdf_in_v85.bat --self-test`、`run_pdf_annotate_from_latest_zip_v85.bat --self-test`、`run_scenario43_external_pipeline_v87.bat --self-test`、watcherの一時Downloads陽性テスト、Word/PDF資料再生成、移行パッケージ作成。最新パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v89_20260522_024316.zip`、manifest上のファイル数は51。

## 2026-05-22: 移行済みPC向けフォルダ差し替え確認ルート

- 前回の客先移行で `deploy\01_setup.bat` が途中エラーとなり、インストール作業を手動で補った。次回以降、既にPython、Playwright、Excel、Edge、Windows資格情報が移行済みのPCでは、原則として `deploy\01_setup.bat` を再実行せず、43フォルダ差し替え後の読取専用確認へ切り替える。
- 新規に `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\05_folder_only_update_check.bat` を追加した。このBATはインストールを行わず、Python/必須パッケージ、必須ファイル、`env.txt=PROD`、Windows資格情報ターゲット、外部パイプラインself-testだけを確認する。
- `deploy\00_preflight.bat` に `--no-pause` を追加し、BAT改行をCRLFへ正規化した。これにより検証時にpauseで止まらず、またLF混在によるcmd.exeの誤解釈を避ける。
- 客先向けセットアップ手順書生成元 `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\tools\build_scenario43_v89_customer_docs.py`、`docs\43_運用ガイド.md`、`docs\43_客先移行_持参ファイル一覧_v89.md` に「アプリ・認証情報が移行済みなら43フォルダ差し替え + 05チェック」を追記した。
- 検証済み: `deploy\00_preflight.bat --no-pause` はPASS、`deploy\05_folder_only_update_check.bat --no-pause` はPASS、`run_scenario43_external_pipeline_v87.bat --self-test` はPASS、Word/PDF資料再生成とページ画像目視確認、移行パッケージ作成。最新パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v89_20260522_091106.zip`、manifest上のファイル数は52。

## 2026-05-22: ZIP選定の30分ルール撤回・処理済みZIP除外へ変更

- 「30分以内に新しく落ちたZIPだけを正とする」ルールは撤回した。客先で明細画面やダウンロードが遅い場合の安全策として追加したが、シナリオ43の正しい要件は「今までに処理したことのある請求データを除外する」こと。
- 正しい判定元は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\work\pdf_out\*.manifest.json` 内の `server_archive.source_zip.sha256`。ここに記録済みのZIPは処理済みとして除外し、未処理ZIPであればファイルの更新時刻が30分より古くても対象にする。
- すべての候補ZIPが処理済みの場合は `S43_ETC_ZIP_ALREADY_PROCESSED` で停止する。手動で同じZIPを再処理したい場合だけ `--allow-processed`、旧互換名として `--allow-stale` を使える。
- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\stage_latest_etc_zip_v85.py` と `run_stage_latest_etc_zip_to_pdf_in_v85.bat` を修正し、`STAGE_REQUIRE_RECENT_SECONDS=1800` と `--require-recent-seconds` の実運用利用をやめた。
- 客先向け資料では「最新ZIP」中心の表現を減らし、「まだ処理していない請求データ/ZIP」を正として説明するよう更新した。
- 検証済み: `python -m py_compile`、`run_stage_latest_etc_zip_to_pdf_in_v85.bat --self-test`、`run_pdf_annotate_from_latest_zip_v85.bat --self-test`、`run_scenario43_external_pipeline_v87.bat --self-test` はPASS。最新パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v89_20260522_100534.zip`。

## 2026-05-22: シナリオ43の対象は最新ZIPのみ

- ユーザー確認により、シナリオ43の入力対象はETCサイトからダウンロードするZIPのみと確定した。他シナリオのメール添付PDF/Excel処理済み判定とは混同しない。
- 43の正ルールは「ETCサイトの一番新しいZIPをダウンロードし、その最新月ZIPだけを処理対象にする」。最新月ZIPが既に処理済みなら、古い月の未処理ZIPへフォールバックせず `S43_ETC_ZIP_ALREADY_PROCESSED` で停止する。
- `stage_latest_etc_zip_v85.py` は候補ZIPを請求月・更新日時で並べ、最新請求月の候補だけを処理対象にするよう修正した。古い請求月のZIPがDownloadsに残っていても自動処理しない。
- 現状確認では、Downloads内の最新月は `202604`、最新ファイルは `11278_11278_東海インプル建設㈱_202604 (9).zip`、SHA-256は `b043d1722bd918a9a8faf709e11cf884c017de1f9b89d8f0d85e97c740aaf440`。これは既に `work\pdf_out\【申請用】日本情報サービス協同組合_20260519_350914.xlsx.manifest.json` に記録済みのため、現在は処理する新規最新ZIPなし。
- 検証済み: `run_stage_latest_etc_zip_to_pdf_in_v85.bat --self-test` は `processed_latest_does_not_fallback_to_old_month=true`、`run_scenario43_external_pipeline_v87.bat --self-test` はPASS。最新パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v89_20260522_101721.zip`。

## 2026-05-22: RK10 Edge拡張機能タブ誤捕捉対策 v90

- 2026-05-22のRKS実行で、ETCログイン中の `ClickMouseLeft` が `BadRequest : dispatchMouseClick failed / Cannot access a chrome-extension:// URL of different extension` で停止した。一次ソースはRK10エラーの `Program.cs:line 103` で、v89展開後Program.csではETCパスワード欄 `//input[@id='password']` のクリック位置だった。
- 原因は、RK10 WebActionが制御対象タブをETCログインページではなく `chrome-extension://` 系ページとして扱ったこと。v89は `StartEdgeWithEngineSelection("https://rbbrier.eco-serv.jp/etc/mypage", ..., new List<string>{}, false, 3d)` で既存Edge状態の影響を受けやすく、ETCページ表示を明示再保証していなかった。
- 古い安定系の確認では、v56/v65/v66は `--new-window`、`--no-first-run`、`--disable-features=msEdgeStartupBoost` と明示 `GoToUrl` を使っていた。特にv66は `about:blank` 起動後にETCログインページへ遷移しており、拡張機能・残存タブ・Edge起動状態の影響を減らす設計だった。
- Claude CLIにも相談し、短期対策は「about:blank新規ウィンドウ起動 + 明示GoToUrl」、恒久対策は「ETCログイン/ダウンロードもPlaywright化してRK10 WebAction DOMクリックを廃止」とレビューされた。
- 短期対策として、v89を上書きせず `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v90_edge_extension_target_hotfix.rks` を作成した。変更はZIP内 `Program.cs` のみ。
- v90ではETC起動を `about:blank` の新規ウィンドウに変更し、Edge引数 `--new-window`、`--no-first-run`、`--disable-features=msEdgeStartupBoost` を付けたうえで、`GoToUrl(webController1, "https://rbbrier.eco-serv.jp/etc/mypage/", true, 240, false)` を実行してからログインIDクリックへ進む。
- 静的検証: v89/v90のZIPエントリは同一、差分は `Program.cs` のみ、`testzip=None`、`try/catch/finally` 数はv89と同じ `11/4/0`。`run_scenario43_external_pipeline_v87.bat --self-test`、`deploy\00_preflight.bat --no-pause`、`deploy\05_folder_only_update_check.bat --no-pause` はPASS。
- 客先移行パッケージの正本RKSをv90へ更新した。最新パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v90_20260522_103414.zip`、manifestの `latest_rks` は `scenario\*v90_edge_extension_target_hotfix.rks`。
## 2026-05-22: v91 ETC取得Playwright化・RK10 Webクリック撤去

- v90でもETCログイン中のRK10 `ClickMouseLeft` が `chrome-extension:// URL of different extension` を誤捕捉して停止したため、ETCサイト操作をRK10 WebActionで続ける方針を撤回した。
- 新規に `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\download_latest_etc_zip_v91.py` と `run_download_latest_etc_zip_v91.bat` を追加した。Windows資格情報 `ETC_ID` / `ETC_Pass` を読み、Playwright Edgeでログインし、パスワード欄でEnter送信して最新ZIPを取得する。取得後はブラウザを必ず閉じる。
- 最新ZIPだけを対象にし、最新ZIPのSHA-256が既に `work\pdf_out\*.manifest.json` の `server_archive.source_zip.sha256` に記録済みなら `S43_ETC_ZIP_ALREADY_PROCESSED` で停止する。古い月の未処理ZIPへフォールバックしない。
- 新規に `tools\scenario43_external_pipeline_v91.py` と `run_scenario43_external_pipeline_v91.bat` を追加した。処理順は `ETC最新ZIP取得 -> 既存PDF/Excel生成 -> 既存楽楽精算Playwright一時保存 -> 完了メール`。
- v90を上書きせず、別名RKS `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v91_external_pipeline_no_rk10_webclick.rks` を作成した。ZIP内差分は `Program.cs` のみで、実行経路のETC向け `Keyence.WebActions` / `ClickMouseLeft` / watcher起動を撤去し、担当者選択後にv91外部BATを呼ぶだけにした。
- 客先移行資料とチェックをv91へ更新し、`deploy\00_preflight.bat` / `deploy\05_folder_only_update_check.bat` はv91 RKS、v91 BAT/Python、`ETC_ID` / `ETC_Pass` を確認する。日本語RKS名はcmd.exeの文字化けを避け、PowerShellのワイルドカード確認へ変更した。
- 客先向け資料は `docs\43_客先向け_業務説明資料_v91.docx/.pdf` と `docs\43_客先移行_セットアップ手順書_v91.docx/.pdf` を生成した。持参一覧は `docs\43_客先移行_持参ファイル一覧_v91.md`。
- 最新移行パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v91_20260522_111138.zip`。manifestの `latest_rks` は `scenario\*v91_external_pipeline_no_rk10_webclick.rks`、ファイル数は53、`masam_TEST` は除外済み。
- 検証済み: `python -m py_compile`（v91 downloader / v91 pipeline / docs builder）、`run_download_latest_etc_zip_v91.bat --self-test`、`run_scenario43_external_pipeline_v91.bat --self-test`、`run_apply_ready_stop_worker_v83_5_playwright.bat --self-test`、v91 RKS ZIP静的検証、`run_scenario43_external_pipeline_v91.bat --skip-pdf --skip-rakuraku`、`deploy\00_preflight.bat --no-pause`、`deploy\05_folder_only_update_check.bat --no-pause`、移行パッケージmanifest検証。
- 実サイトスモーク（ETCログイン・最新ZIPリンク検出）は、実サイトへアクセスするためこの実装フェーズでは未実行。次回はv91 RKSをRK10で開けることを人間が確認した後、必要なら `run_download_latest_etc_zip_v91.bat --smoke` で実施する。

## 2026-05-22: v91 既処理ZIPのLOCAL再処理・PROD二重申請防止

- v91実行停止の一次原因は、最新ZIP `11278_11278_東海インプル建設㈱_202604.zip` のSHA-256が既に `work\pdf_out\*.manifest.json` に記録済みで、`tools\download_latest_etc_zip_v91.py` が `S43_ETC_ZIP_ALREADY_PROCESSED` を返したことだった。ログイン失敗やダウンロード失敗ではない。
- 方針を「PRODは再処理しない / LOCALだけテスト用再処理を許可」に確定した。PRODで最新ZIPが既処理ならPDF/Excel再生成、楽楽精算一時保存、完了メールへ進まず、`COMPLETED_ALREADY_PROCESSED_NO_NEW_ZIP` の完了マーカーを残して二重申請を防ぐ。
- `tools\scenario43_external_pipeline_v91.py` を修正し、`config\env.txt=LOCAL` の場合だけETCダウンロードとZIPステージングへ `--allow-processed` を渡す。LOCAL以外では古い月へフォールバックせず、既処理ZIPは「新しい請求データなし」として終了する。
- 新規に `run_pdf_annotate_from_latest_zip_v91.bat` を追加した。v85の安定PDF/Excel処理は維持しつつ、ステージングBATへ引数を転送できるようにし、LOCALの `--allow-processed` を後段にも伝える。
- `tools\rakuraku_temporary_save_v83_5_operator_2price.py` に `--allow-duplicate-draft-for-test` を追加した。このフラグはLOCAL専用で、PRODで指定された場合は `S43_LOCAL_ONLY_REPROCESS_FORBIDDEN` で停止する。LOCALでは既存一時保存があってもテスト用に別一時保存を作るため、既存ドラフトを証跡保存後に無視して新規アップロード経路へ進む。
- LOCAL再処理時に明示宛先が `kanri.tic@tokai-ic.co.jp` を含む場合は `S43_LOCAL_MAIL_TO_PROD_FORBIDDEN` で停止する。LOCAL再処理メールはLOCAL宛先のみとする。
- 移行チェックと持参パッケージをv91入口へ更新した。`deploy\00_preflight.bat`、`deploy\05_folder_only_update_check.bat`、`deploy\build_customer_migration_package_v89.ps1`、持参一覧は `run_pdf_annotate_from_latest_zip_v91.bat` を確認・同梱する。
- 検証済み: `python -m py_compile`（v91 pipeline / v91 downloader / 楽楽v83_5 worker）、`run_download_latest_etc_zip_v91.bat --self-test`、`run_pdf_annotate_from_latest_zip_v91.bat --self-test`、`run_apply_ready_stop_worker_v83_5_playwright.bat --self-test`、`run_scenario43_external_pipeline_v91.bat --self-test`、PROD既処理no-workのモンキーパッチ単体検証、LOCAL `--allow-processed` 伝播単体検証、LOCAL宛先ガード単体検証、`deploy\00_preflight.bat --no-pause`、`deploy\05_folder_only_update_check.bat --no-pause`、`run_scenario43_external_pipeline_v91.bat --skip-pdf --skip-rakuraku`。
- 最新移行パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v91_20260522_125020.zip`。manifestでは `run_pdf_annotate_from_latest_zip_v91.bat` と `tools\scenario43_external_pipeline_v91.py` が同梱済み、`masam_TEST` は除外済み。


## 2026-05-22: v92 ETC明細ローディング遅延・Edgeプロファイル分離対策

- 本番PCで `https://rbbrier.eco-serv.jp/etc/mypage/` ログイン後、「明細の確認」表示が遅く停止する問題に対し、原因をEdgeプロファイルだけに断定せず、v91の弱点だった「明細ページ到達後2秒待って1回だけZIPリンク取得」を本命リスクとして対策した。
- 新規に `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\download_latest_etc_zip_v92.py` と `run_download_latest_etc_zip_v92.bat` を追加した。Playwright `launch_persistent_context` で `Temp\edge_profiles\etc_v92_{timestamp}` の使い捨てEdgeプロファイルを使い、通常Edgeの既存タブ、拡張機能、キャッシュ、Codex起動中Edgeの影響を受けにくくした。
- v92 downloaderはETCログイン後に「明細の確認」タブをRK10クリックせず、`bapPublishedBillAppSearch` へ直接遷移する。ZIP候補は2秒固定待ちではなく、5秒間隔・最大600秒でポーリングし、表示されない場合は `S43_ETC_BILLING_PAGE_TIMEOUT` で停止する。
- 証跡には使い捨てEdgeプロファイルパス、ログイン/明細ページ到達時刻、ZIP候補初回検出時刻、候補一覧、スクリーンショット、HTML抜粋、download SHA-256を残す。成功/失敗後は通常プロファイルを削除し、診断時のみ `--keep-profile-on-failure` で残せる。
- 新規に `tools\scenario43_external_pipeline_v92.py` と `run_scenario43_external_pipeline_v92.bat` を追加した。後段はv91の安定仕様を維持し、PDF/Excel生成は `run_pdf_annotate_from_latest_zip_v91.bat`、楽楽精算一時保存は `run_apply_ready_stop_worker_v83_5_playwright.bat` を使う。
- v91を上書きせず、別名RKS `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v92_external_pipeline_isolated_edge_wait.rks` を作成した。ZIP内差分は `Program.cs` のみで、BAT名をv92へ差し替え、ログ表記もv92へ更新した。
- 客先移行チェックと資料をv92へ更新した。`deploy\00_preflight.bat`、`deploy\05_folder_only_update_check.bat`、`deploy\build_customer_migration_package_v89.ps1` はv92 RKS/BAT/Pythonを確認・同梱する。`deploy\02_test.bat` は既処理ZIP再処理テスト要件に合わせ、`env.txt` を `TEST` ではなく `LOCAL` に切り替えるよう修正した。
- 非エンジニア向け資料は `docs\43_客先向け_業務説明資料_v92.docx/.pdf` と `docs\43_客先移行_セットアップ手順書_v92.docx/.pdf` を生成した。持参一覧は `docs\43_客先移行_持参ファイル一覧_v92.md`。drawioタイトルもv92へ更新した。
- 検証済み: `python -m py_compile`（v92 downloader / v92 pipeline / 楽楽v83_5 worker）、v92 RKS ZIP静的検証（`Program.cs` 以外同一、`testzip=None`、v91 BAT参照0）、`run_download_latest_etc_zip_v92.bat --self-test`、`run_scenario43_external_pipeline_v92.bat --self-test`、`run_apply_ready_stop_worker_v83_5_playwright.bat --self-test`、`deploy\00_preflight.bat --no-pause`、`deploy\05_folder_only_update_check.bat --no-pause`、v92移行パッケージmanifest/zip検証。
- 最新移行パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v92_20260522_141836.zip`。manifestの `latest_rks` は `scenario\*v92_external_pipeline_isolated_edge_wait.rks`、ファイル数は54、`masam_TEST` は除外済み。
- 実サイトスモーク `run_download_latest_etc_zip_v92.bat --smoke --timeout-seconds 600` は、実サイトへアクセスするため今回の自動検証では未実行。客先/本番前に人間承認のうえ実施する。


## 2026-05-22: v92専用Edge分離の正式運用表現を確定

- 客先PCはRK10実行専用で、人間の普段使いEdgeプロファイルはない。このため、v92の説明は「人間プロファイル回避」ではなく「RK10 WebAction/Edge拡張の誤捕捉、残タブ、残セッション、ETC明細画面の遅延回避」を主目的として統一した。
- `docs\43_運用ガイド.md` と `docs\43_業務フロー説明資料.md` を修正し、RK10専用PCでもETC取得だけはロボット専用Edgeを使う理由を非エンジニア向けに明記した。
- 客先向けWord/PDF生成元 `docs\tools\build_scenario43_v89_customer_docs.py` も同じ表現へ更新し、`docs\43_客先向け_業務説明資料_v92.docx/.pdf` と `docs\43_客先移行_セットアップ手順書_v92.docx/.pdf` を再生成した。
- v92コード方針は維持する。`download_latest_etc_zip_v92.py` は `Temp\edge_profiles\etc_v92_{timestamp}` の使い捨てEdgeプロファイル、明細URL直接遷移、最大600秒ZIPリンク待機、`S43_ETC_BILLING_PAGE_TIMEOUT` 証跡保存を正とする。
- 検証済み: docs生成、`python -m py_compile`、v92 RKS静的検証、`run_download_latest_etc_zip_v92.bat --self-test`、`run_scenario43_external_pipeline_v92.bat --self-test`、`deploy\00_preflight.bat --no-pause`、`deploy\05_folder_only_update_check.bat --no-pause`、v92移行パッケージmanifest/zip検証。
- 最新移行パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\customer_migration_v92_20260522_154454.zip`。manifestの `latest_rks` は `scenario\*v92_external_pipeline_isolated_edge_wait.rks`、ファイル数は54、`masam_TEST` は除外済み。

## 2026-05-26: フル置換途中失敗PC向けの部分復旧パッケージ

- 客先PCで `E:\rk10-full-replacement_20260517` のバッチが途中エラーになった場合は、フル置換を再実行する前に、シナリオ43だけを差し替えて環境到達度を確認する部分復旧ルートを使う。
- 新規に `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\build_partial_recovery_package_v92.ps1` を追加した。生成物は `00_START_HERE_PARTIAL_RECOVERY.bat`、`01_REPAIR_ENVIRONMENT_AND_RECHECK.bat`、`02_COLLECT_DIAGNOSTIC_LOGS.bat`、`README_部分復旧手順.txt`、`scenario43` ペイロードを含む。
- `00_START_HERE_PARTIAL_RECOVERY.bat` は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成` へシナリオ43のみをコピーし、`Temp` と `work` はコピー対象から外し、`config\env.txt` を `PROD` に固定してから `deploy\05_folder_only_update_check.bat --no-pause` を実行する。保存・申請は行わない。
- 部分復旧パッケージでは `config\rakuraku_operators.csv` から `テスト masam` を除外し、Windows資格情報のパスワード本体は含めない。
- 生成済みパッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\scenario43_partial_recovery_v92_20260526_103052.zip`。展開フォルダは同名拡張子なし、manifestは `partial_recovery_manifest.json`、ZIP内ファイル数は63。
- 検証済み: 生成コマンド `PowerShell -NoProfile -ExecutionPolicy Bypass -File ...\build_partial_recovery_package_v92.ps1`、ペイロード `config\env.txt=PROD`、`rakuraku_operators.csv` の `masam_TEST` 除外、ZIP必須エントリ存在、`scenario43\run_scenario43_external_pipeline_v92.bat --self-test` PASS。ZIP SHA-256 は `7E3EDF959C41D0B060663BDE10B6429443F346CD015CBF53989E7084F8EA66EB`。

## 2026-05-27: v92 Edge新規プロファイル検証とログインフォーム待ち補強

- 本番PCでEdge読み込みが極端に遅くETC取得が止まる件について、「新規プロファイルだけで解消」とは断定しない方針にした。一次証跡では、使い捨てEdgeプロファイルでも修正前5回スモークが4成功/1失敗で、失敗は `S43_LOGIN_REQUIRED_OR_2FA` だった。
- 失敗証跡は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\evidence\edge_profile_smoke_benchmark_20260527_112758\run_05\download_latest_etc_zip_v92.json`。ログインページDOM読込後、入力欄表示を十分待たずに直接明細URLへ進み、`ログインしてください` 画面で停止していた。
- `tools\download_latest_etc_zip_v92.py` を修正し、ログイン入力欄を最大30秒・0.5秒間隔でポーリングするようにした。ログイン必須画面に戻った場合は、`S43_LOGIN_REQUIRED_OR_2FA` としてスクリーンショット/HTML抜粋を保存する。
- 修正後5回スモーク `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\evidence\edge_profile_smoke_benchmark_after_login_wait_20260527_113612\summary.json` は5成功/0失敗。最長runでは `login_fields_wait_seconds=2.1`、`login_fields_poll_attempts=5` で、旧1秒待ちでは不安定になり得ることを確認した。
- `tools\scenario43_external_pipeline_v92.py` に、`--smoke --skip-pdf` を `S43_SMOKE_REQUIRES_ETC_DOWNLOAD` で停止するガードを追加した。`--skip-pdf` はETC取得もスキップするため、従来は実サイト検証なしでOKになる偽陽性があり得た。
- 実サイトスモーク `run_scenario43_external_pipeline_v92.bat --smoke --skip-rakuraku --timeout-seconds 600` は成功し、証跡 `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\evidence\scenario43_external_pipeline_v92_20260527_130321\etc_download\download_latest_etc_zip_v92.json` では `edge_profile_mode=ephemeral_persistent_context`、`login_fields_wait_seconds=0.7`。
- 検証済み: `python -m py_compile`、`run_download_latest_etc_zip_v92.bat --self-test`、修正後5回スモーク、正しいv92パイプラインスモーク、偽陽性スモーク禁止ガード、`run_scenario43_external_pipeline_v92.bat --self-test`。
- 検証メモは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_Edge新規プロファイル検証メモ_20260527.md` に保存した。
- 部分復旧パッケージを再作成した。最新ZIPは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\scenario43_partial_recovery_v92_20260527_131325.zip`、SHA-256は `9BE76F65257BE513A3AA6CB61DBC8B4A1963931D30BE1ABB98E3F1AF373CDAE9`。ペイロード `config\env.txt=PROD`、`masam_TEST` 除外、更新済みv92 Python/検証メモ同梱、ペイロード内 `run_scenario43_external_pipeline_v92.bat --self-test` PASSを確認した。
- ユーザー観察「ローディング中のウィンドウをクリックしたら表示された気がする」を受け、`download_latest_etc_zip_v92.py` にページ左上 `x=2,y=2` のフォーカス用クリックを追加した。ログイン画面表示後、ログイン完了後、明細画面表示後に1回ずつ実行し、証跡JSONの `focus_nudges` に結果を記録する。
- クリック追加後の `run_download_latest_etc_zip_v92.bat --self-test` は `focus_nudge_records_evidence=true` を含めてPASS。実サイトスモーク `run_scenario43_external_pipeline_v92.bat --smoke --skip-rakuraku --timeout-seconds 600` もPASSし、証跡 `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\Temp\evidence\scenario43_external_pipeline_v92_20260527_141115\etc_download\download_latest_etc_zip_v92.json` では `focus_nudges` 3件がすべて `status=OK`、ZIP候補3件検出。
- フォーカスクリック入りの部分復旧パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\scenario43_partial_recovery_v92_20260527_142833.zip`、SHA-256は `6ADD9BE7B93803D3B94A7D2F789C083AA1C6AC7234B2D6AE52A10F5169C57EE7`。ペイロード `config\env.txt=PROD`、`masam_TEST` 除外、`FOCUS_NUDGE_X` 同梱、ペイロード内 `run_scenario43_external_pipeline_v92.bat --self-test` PASSを確認した。

## 2026-05-27: 客先向け資料にカードマスタ更新手順をスクリーンショット付きで追加

- ユーザー要望により、客先へ渡す資料に `config\card_master.xlsx` の更新方法を追加した。対象は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\43_客先向け_業務説明資料_v92.docx/.pdf` と `docs\43_客先移行_セットアップ手順書_v92.docx/.pdf`。
- 生成元 `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\tools\build_scenario43_v89_customer_docs.py` を更新し、Excelの `カードマスタ` シート範囲を画像化してWordに埋め込むようにした。正本ファイルの場所、入力列、触らない列、追加行の位置、追加/変更/削除時の注意点を説明する。
- 客先向け業務説明資料は4ページ、セットアップ手順書は5ページとして再生成。Word/PDFとも `card_master.xlsx` の説明と画像が入っていること、DOCX内画像数が業務説明資料4点・セットアップ手順書3点であることを確認した。
- Visual QAは、Documentsスキルの `render_docx.py` は `soffice` 未検出で失敗したため、既存生成処理のWord COM PDF出力とPyMuPDF PNG化で全ページを確認した。確認用PNGは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\customer_v92_render\43_客先向け_業務説明資料_v92\contact_sheet.png` と `docs\customer_v92_render\43_客先移行_セットアップ手順書_v92\contact_sheet.png`。
- 資料更新後の部分復旧パッケージは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\scenario43_partial_recovery_v92_20260527_170759.zip`、SHA-256は `791A2EE7C1E8F0FA42A6FE09DB00F8177433BE6D208E4CBDB8AA85966B2F9E6C`。ペイロード `config\env.txt=PROD`、`masam_TEST` 除外、更新済みDOCX/PDF同梱、ペイロード内 `run_scenario43_external_pipeline_v92.bat --self-test` PASSを確認した。

## 2026-05-27: シナリオ43フォルダ整理・退避

- ユーザー確定方針「かなり整理」＋「各フォルダ内に退避」に従い、削除なしで不要候補を `_退避_20260527_整理前` へ移動した。実行スクリプトは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\organize_scenario43_archive_20260527.ps1`。
- 整理前に `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\00_今使うファイル一覧_43.txt` と `退避候補_20260527.csv` を作成し、整理後に `退避_manifest_20260527.json` を作成した。
- 退避結果は `退避_manifest_20260527.json` 上で `moved_count=586`、`skipped_count=0`。自己テスト後に再生成された `deploy\logs`、`tools\__pycache__`、`tools\pdf_annotate\__pycache__` も追加退避した。
- `work\pdf_out\*.manifest.json` は処理済みZIP判定に使うため残した。成果物PDF/XLSX本体、`work\pdf_in` の過去入力PDF、`Temp` と `Temp\evidence` の過去実行証跡は各フォルダ内の退避フォルダへ移動した。
- 直下は現行v92系BAT、`requirements.txt`、一覧/退避CSV/manifest、必要フォルダだけに整理した。完全未使用候補 `artifacts`、`backup`、`log`、`logs`、`script` はシナリオ直下の退避フォルダへ移動した。
- 検証済み: `run_download_latest_etc_zip_v92.bat --self-test` PASS、`run_scenario43_external_pipeline_v92.bat --self-test` PASS、`deploy\05_folder_only_update_check.bat --no-pause` PASS。`05_folder_only_update_check` は `env.txt=LOCAL` 警告を出したが、Required files と Scenario self-test はOKだった。
- 追加確認として、`scenario` 直下の非退避RKSは `*v92_external_pipeline_isolated_edge_wait.rks` 1件、`docs` 直下にはv92のDOCX/PDF資料・運用ガイド・drawio・Edge検証メモが残っていることを確認した。実サイトアクセスや楽楽精算保存は実行していない。

## 2026-05-28: v93 実行者選択GUIの序盤化

- ユーザー要望「実行者選択画面をもっと序盤で出す」に対し、v92 RKSを上書きせず、別名RKS `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v93_operator_select_first.rks` を作成した。
- 変更範囲はZIP内 `Program.cs` のみ。実行者選択ブロックを `ExternalResources` 展開直後へ移動し、`env.txt` 読込・Config Excel読込・ETC取得より前に表示する。
- 選択GUIは `tools\select_rakuraku_operator.ps1` と `config\rakuraku_operators.csv` だけに依存し、環境判定やConfig Excelの読込結果には依存しないため、前倒ししても外部パイプラインへ渡す `--operator-name`、`--login-credential`、`--password-credential` の契約は維持する。
- `deploy\00_preflight.bat`、`deploy\05_folder_only_update_check.bat`、`deploy\build_partial_recovery_package_v92.ps1`、`00_今使うファイル一覧_43.txt`、運用ガイド、持参一覧をv93 RKS参照へ更新した。
- 最新配布ZIPは `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\deploy\scenario43_partial_recovery_v93_20260528_180145.zip`。manifestの `latest_rks` は `scenario\*v93_operator_select_first.rks`、ペイロード `config\env.txt=PROD`、`masam_TEST` 除外、ファイル数は56。
- 旧v92 RKS、旧v92配布ZIP、v93配布ZIP生成時の展開フォルダは削除せず退避し、追補退避記録 `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\退避_manifest_20260528_v93追補.json` に記録した。
- 静的ゲートでは、RKS ZIPエントリ構成同一、`try/catch/finally` 数 `4/4/0` 維持、実行者選択位置が環境判定・Config読込より前であること、`scenario` 直下の非退避RKSがv93のみであることを確認した。`deploy\05_folder_only_update_check.bat --no-pause` は `env.txt=LOCAL` 警告つきでPASS。最終ゲートは、RK10でv93 RKSを手動で開けること。

## 2026-05-29: v93連続デバッグ（担当者選択タイムアウト→名義二重防御まで）— RKSは未変更、外部PS1/Pythonのみ修正

すべて `env.txt=LOCAL` で実施。RKS本体は一切変更していない（修正は外部PS1/Pythonに限定）。各Python修正前に対象ファイルを `*.bak_20260529_*` でバックアップ済み。

### (1) 担当者選択GUIタイムアウト（Program.cs:750 `楽楽精算担当者選択がタイムアウト`）
- 原因: `tools\select_rakuraku_operator.ps1` のWinFormsダイアログに `TopMost`/前面化が無く、リダイレクト付き子プロセスから起動するとRK10の背後に隠れ、5分無操作でタイムアウト（v93で序盤化したため開始直後に裏で待機）。`Temp\rakuraku_operator_selection.env` 未生成＝OK選択未成立、エラーが「タイムアウト」＝`ShowDialog`が5分ブロックで確定。
- 修正: `select_rakuraku_operator.ps1` に `$form.TopMost=$true` ＋ `Add_Shown{ Activate/BringToFront }`、エラー/警告MessageBoxも `Show-TopMostMessage`（TopMostオーナー）で前面化。
- 検証: 構文OK、C#同等起動でフォアグラウンドウィンドウ=「シナリオ43 楽楽精算 担当者選択」を実測（前面化OK）。

### (2) 外部パイプラインExitCode=1（`finalize_application_outputs_v85 ... LATEST_XLS=` 空, RC=12）
- 原因: 2026-05-27のフォルダ整理で、`finalize` が読む**元Excel** `ＥＴＣカード利用料_2026.X月分.xlsx` を `work\pdf_out\_退避_20260527_整理前\` へ巻き込み退避。`run_pdf_annotate_safe_v85_pair_excel.bat` の `LATEST_XLS` は `work\pdf_out` 内「申請用命名でない最新xlsx」を探すため空に。
- 対処: 元Excel `ＥＴＣカード利用料_2026.5月分.xlsx`（106,641B・内容2026-04・総額350,914＝前回成功時source_workbook）を `work\pdf_out` へ復元（copy、退避側は残置）。これは生成物ではなく**人が用意する必須入力**（ETC ZIPはPDF3+CSV3のみでxlsxを含まない）。
- 検証: `run_pdf_annotate_from_latest_zip_v91.bat --allow-processed` BAT_EXITCODE=0、申請用PDF/Excel/manifest再生成。

### (3) ebookポップアップ誤捕捉（`S43_FINAL_CONFIRMATION_BLOCKED: Unexpected ebook list URL: chrome-extension://.../welcome`）
- 原因: `rakuraku_temporary_save_v83_5_operator_2price.py` の `_open_ebook_file_list_strict` が `context.expect_page()` で「最初の新規ページ」を取得 → ユーザーEdgeに同期された拡張機能のwelcomeタブを誤捕捉。
- 修正: 既存ページをスナップショット→トリガ後に新規ページをポーリングし `ebookFileFormView` を含むrsatonalityページだけ採用（about:blank/拡張タブ無視、最大~30秒）。

### (4) アップロード後ナビ競合（`Page.evaluate: Execution context was destroyed ... navigation` @ `_assert_no_visible_submit_errors`）
- 原因: ebookアップロード確定(`button.kakuteiEbook`)後にページが再遷移し、`_assert_no_visible_submit_errors` の `page.evaluate` が遷移中に走って落ちた。
- 修正: 同関数を `wait_for_load_state` ＋ 最大6回のナビゲーション例外リトライへ堅牢化。

### (5) 担当者名義の二重防御（Codex GPT-5.5 設計レビュー反映）
- 既存挙動の問題: 旧 `_login_if_needed` は「楽楽セッションが1つでもアクティブなら名義を確認せず再利用」。`_ensure_edge_cdp` はポート9222が開いていれば再利用。プロファイル `work\edge_apply_ready_profile` は全operator共有。→ 別名義セッションが残ると、選択担当者を無視してその名義で支払依頼を作る恐れ（実際に岡村優名義で作成されていた。ただしテスト masam=岡村優=30094で同一アカウントのため実害はなかった）。
- 実装（`rakuraku_apply_ready_stop_v60-1_operator_2price.py`）:
  - operator別Edgeプロファイル `work\edge_apply_ready_profile_<loginId>` ＋ 決定論ポート `9222 + sha256(loginId)%1000`（`_operator_cdp_port` / `_safe_profile_key`）。`_ensure_edge_cdp(root, port, base_url, login_id)` がactual_portを返す。呼び出し側（base main / worker）を更新。
  - 名義検証: ログイン中の `shainCd` を `page.request.get({base}/sapKojinSettei/initializeView)` のHTML `name="shainCd" value="(\d+)"` から取得し、選択operatorの loginId と照合。不一致なら `_logout_rakuraku`（`{base}/sapLogout/logout`）→ 再ログイン、読取不能なら停止（fail-closed）。ログイン後も再検証。saved-password autofillガード（`fill("")`→`fill(id)`→`input_value`一致確認）。
  - 確定セレクタ（実物探索で取得）: 名義=`sapKojinSettei` の hidden `shainCd`、ログアウト=`a.szb-menu-item[href*="sapLogout/logout"]`。
- 検証: 30094でフルログイン→名義検証→一時保存到達(WORKER_EXITCODE=0)。瀬戸(30085)でフルRKS一時保存到達、下書き名義=瀬戸阿紀子で確認。

### (6) Edge拡張クラッタ（「実行中に関係ないサイトが開く」）
- 原因: 自動化EdgeプロファイルがユーザーのMicrosoftアカウントにサインインし拡張機能34個が同期 → 起動時に各拡張がwelcomeタブを開く（(3)のchrome-extension welcomeもこれ）。`account_info present: True`、`Default\Extensions` 34フォルダで確認。
- 修正: `_ensure_edge_cdp` のEdge起動引数に `--disable-extensions --disable-sync` を追加。検証: 当該プロファイル＋新オプション起動で開いたタブ=楽楽精算1枚のみ、拡張welcomeタブ0（CDP `/json` 実測）。

### (7) 瀬戸阿紀子ログイン失敗（`S43_LOGIN_REQUIRED_OR_2FA`／HTML「ログインできませんでした。ID・パスワードをご確認ください。」）
- 原因: Windows資格情報の `ログインID　楽楽精算_瀬戸阿紀子` が `300085`（0が1個多いタイプミス）。正しい社員コードは本決定ログL208記録の `30085`（岡村30094と同じ5桁、loginId=社員コード）。
- 対処: win32credで当該credのCredentialBlobを `30085` へ書換（旧値300085記録・可逆、パスワードcredは不変）。検証: 瀬戸で実ログイン成功（IDもパスワードも通る＝原因はIDタイプミスのみ）。

### 一時保存下書きの削除手順（確定）
- 一覧: `{base}/sapShihairaiKensaku/tmpView` の `tr`（金額＋「一時保存」＋詳細href）。削除: 詳細ページ `button.accesskeyDelete` → 確認（ネイティブダイアログaccept or `button.confirmKakutei`）→ `sapShihairaiDenpyo/delete` 遷移。
- 安全則: 署名「日本情報サービス協同組合／350,914／一時保存」一致のみ削除、1件ごとに件数減を検証、想定外の下書きがあれば中断。未登録名義はログイン不可＝削除不可。登録済みは masam_TEST/岡村優=30094、長坂とも子=30057、瀬戸阿紀子=30085。
- 実施: 瀬戸名義のテスト一時保存下書きを削除（残0件を検証）。

### 残課題
- 私のE2Eテストで作成した 30094（岡村優）名義のテスト一時保存下書き2件は未削除（要クリーンアップ）。
- 名義不一致時のログアウト→再ログイン経路は確定セレクタ上に実装済みだが、2人目の実アカウントでのミスマッチ実発火までは未試験（ハッピーパスは検証済み）。
- 無冪等のため失敗runごとにアップロード/下書きが残る点は今回未対応（ユーザー判断で保留）。

## 2026-05-29: 担当者ログイン値の事前検証ツール追加・preflight/05組込み・パッケージ同梱・客先資料更新

ユーザー要望「A〜C実行」「1〜4実行」に対応。preflightは資格情報の**ターゲット存在**しか見ず**値の正誤（300085のようなタイプミス）**を検出できないギャップを埋める。

- **新規ツール**: `tools\verify_operator_logins.py` ＋ `run_verify_operator_logins.bat`。`config\rakuraku_operators.csv` の有効担当者ごとに、修正済みログイン経路（per-operatorプロファイル＋名義検証）で「ログイン→shainCd照合→ログアウト」を行いOK/NGを出す。**下書きは作らず、パスワードは表示しない**。全員OKでexit0、1人でもNGでexit1。
- **実機検証**: 瀬戸阿紀子(30085)/長坂とも子(30057)/テストmasam(30094) 全員OK（長坂は今回初の実ログイン確認、問題なし）。
- **preflight/05組込み**: `deploy\05_folder_only_update_check.bat`（Scenario self-testの前）と `deploy\00_preflight.bat`（資格情報チェック直後）に、`run_verify_operator_logins.bat` を呼ぶ `:OPLOGIN` チェックを追加。NGは `NG_COUNT` に算入。検証: 05は `RESULT: PASS`（env=LOCAL警告のみ）、00_preflightは `[OK] 全担当者ログイン検証`。
- **BAT改行の教訓（再）**: 新規 `run_verify_operator_logins.bat` をLF改行で作ったところ、cmd.exeが `'nableExtensions' is not recognized`（`setlocal EnableExtensions` 誤読）でexit255。`run_verify_operator_logins.bat` / `05` / `00_preflight.bat` を**CRLFへ正規化**（BOM無し）して解決。BATは必ずCRLF。
- **客先資料(A)**: `docs\43_運用ガイド.md` の初回セットアップに、担当者別ログインID（瀬戸=**30085**／長坂=**30057**）、`300085`等の桁数違い警告、資格情報はPC単位、登録後 `run_verify_operator_logins.bat` で全員OK確認、を追記。
- **移行ツールは認証情報を自動登録しない（確認）**: パッケージの `rakuraku_operators.csv` は**ターゲット名のみ**でID/パスワード実値を含まない。`00_preflight`/`05` は従来「ターゲット存在」確認のみ→今回「実ログイン検証」を追加。客先PCでは人が手動で資格情報登録が必要（値の正値は運用ガイド参照）。
- **パッケージ再生成(B/③)**: `deploy\build_partial_recovery_package_v92.ps1` の `$requiredFiles` に `run_verify_operator_logins.bat` と `tools\verify_operator_logins.py` を追加（追加前は同梱漏れ＝客先でOPLOGINがファイル無しNGになる問題があった）。最新パッケージ `deploy\scenario43_partial_recovery_v93_20260529_114006.zip` に新ツール2件・更新BAT(OPLOGIN)・更新ガイド(30085)が同梱されたことを確認。env=PROD強制・`masam_TEST`除外済み。
- **掃除(C)**: `tools\*.bak_20260529_*`（3件）と一時スクリプトを削除。
- **30094下書き**: ユーザーが手動削除済み。
- **既存の別問題（この後に修正済み）**: `00_preflight.bat` が `run_close_etc_download_site_tabs_v88.bat not found` で1件NGだった（v88時代の旧ファイル要求の残り。v92は使い捨てプロファイルで本来不要）。

### 仕上げ（同日・続き）
- **preflight旧要求の除去**: `00_preflight.bat` の `:TOOL12` ブロック（`run_close_etc_download_site_tabs_v88.bat` のif-exist→NGチェック）をREMコメントへ置換し除去。v92フロー（`scenario43_external_pipeline_v92` 系）が同BATを呼ばないこと、実体は退避済み旧パッケージ内のみに存在することを確認のうえ廃止。除去後 `deploy\00_preflight.bat --no-pause` は `RESULT: PASS（全項目 OK）` exit0、`05_folder_only_update_check.bat` も PASS。
- **最終配布パッケージ**: `deploy\scenario43_partial_recovery_v93_20260529_114707.zip`（2.82MB）。`run_verify_operator_logins.bat` ＋ `tools\verify_operator_logins.py` 同梱、`00_preflight`/`05` にOPLOGIN（ログイン検証）入り、close-tabs能動チェックなし（REMのみ）、env=PROD強制、`masam_TEST` 除外。本日途中の中間ビルド（110748/113856/114006）は不完全のため削除し、最新1本のみ残置。
- **BAT編集時の鉄則（再確認）**: Edit挿入はLFになり既存CRLF BATと混在→cmd誤読の恐れ。編集したBATは都度バイト単位でCRLF正規化（BOM無し）してから検証する。

## 2026-06-15: 納品物セット作成（要件定義書v2.0・テスト結果報告書・納品書/検収書）

- Qiita「要件定義書の書き方」(https://qiita.com/syantien/items/9a8a7cbaeca2be3ef0d7) の7セクション構成を参考に、納品物3点をWord/PDFで生成した。生成元は `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\docs\tools\build_scenario43_delivery_docs.py`（python-docx＋Word COMでPDF化、フォント=メイリオ、再生成可能）。
- 要件定義書 `docs\43_要件定義書_v93.docx/.pdf`（REQ-43-002 v2.0）。旧Excel版(REQ-43-001 v1.0, 退避フォルダ内)の「F-xxx/NF-xxx ID＋優先度＋分類」表構造を踏襲し、内容をv93現行へ全面更新（2価格方式、一時保存まで、最終申請は人間、申請額は一般経費のみ83,049円＝販管費81,649＋工事原価(技術福岡)1,400、安全境界・対象外を追加）。旧Excelは印刷時に「分類」「詳細」列が本体表と別ページに飛ぶ不具合があったため、本体表に統合して解消。
- テスト結果報告書 `docs\43_テスト結果報告書_v93.docx/.pdf`（TEST-43-001 v1.0）。静的検証/構文/self-test/preflight/担当者ログイン検証/実機スモーク/本番相当通し実行の結果サマリと、2026-06-01 瀬戸阿紀子ID・83,049円一時保存の実行記録、残課題（名義不一致再ログインの2人目実発火未試験、冪等性なし）を記載。
- 納品書/検収書 `docs\43_納品書_検収書_v93.docx/.pdf`（DLV-43-001 / ACC-43-001）。宛先=東海インプル建設株式会社 管理部 御中、納品物一覧＋検収チェックリスト＋署名欄。納品元（自社名・担当）は要記入。
- 整合チェック: `43_運用ガイド.md`・`43_担当者向け変更点_20260601.md`・`43_客先移行_持参ファイル一覧_v92.md` はいずれもv93・83,049円・一時保存までで新文書と一致。矛盾なし。`43_客先移行_持参ファイル一覧_v92.md` の「納品書類」節に新規3文書(docx/pdf)を追記。
- セッション中に先行作成したMarkdown版要件定義書(`43_要件定義書_v93.md`)とWord narrative版は、ID構造版へ一本化するため破棄済み。
- データフロー図の正本は `docs\条件分岐データフロー図_43_20260610.drawio/.png`（Codex作成）。納品では「③設計・保守」束として渡す。

## 2026-06-15: docsフォルダ棚卸し・退避（旧版/重複の整理）

- 2026-05-27と同じ安全手順（削除なし・移動・manifest付き）で、`docs` 直下の旧版/バックアップ/重複を `docs\_退避_20260615_整理前` へ移動した。9点退避（manifest: `docs\_退避_20260615_整理前\退避_manifest_20260615.json`）。
- 退避内訳: `*.before_docs_update_*`(業務説明資料/セットアップ手順書 旧版4点)、`43_業務フロー図.drawio.bak_20260601_191315`、`43_業務フロー図.png.before_drawio_export_20260601_2`、`43_業務フロー図.drawio_export_test.png`、`43_業務フロー図_drawio.png`(いずれも `43_業務フロー図.png` とバイト同一の重複)、`_backup_output_paths_20260603_150507\`。
- 残置（最新の正本）: 要件定義書/テスト結果報告書/納品書(v93)、業務説明資料/セットアップ手順書(v92 docx 6/03・pdf 6/01)、運用ガイド/業務フロー説明資料/担当者向け変更点/金額仕様(6/01)、業務フロー図(drawio+png 6/01)、条件分岐フロー図、条件分岐データフロー図(6/10)、持参ファイル一覧、Edge検証メモ、tools/。
- 未判断: `manual_v2026.06.08.1.pdf` と `manual_admin_v2026.06.08.1.pdf` は、それぞれ `43_客先向け_業務説明資料_v92.pdf` / `43_客先移行_セットアップ手順書_v92.pdf` とバイト完全一致。どちらの命名を正にするか未確定のため両方残置。

## 2026-06-15: リリース版二重命名の確認・データフロー図を配布物へ追加

- `manual_*.pdf` と `43_*.pdf` の重複は事故ではなく、`release_manifest_v2026.06.08.1.json`（2026-06-08作成）による「作業用名＋リリース版名(_v2026.06.08.1)」の意図的な二重持ちと判明。manifestルール: オンサイトはフォルダ丸ごとコピー・改名/選別しない、実行は固定入口(`run_…v92.bat`)のみ、`_v2026…`版は直接実行しない。よってどちらのPDFも退避・削除しない（片方削除はランタイムorリリースを壊す）。
- ユーザー指示「新しい方(manual_*)を正・配布で重複を避けたい」に対し、削除ではなく「配布リストをmanual_*に統一」で対応。`43_客先向け_業務説明資料_v92.pdf`＝`manual_v2026.06.08.1.pdf`(role=manual_staff)、`43_客先移行_セットアップ手順書_v92.pdf`＝`manual_admin_v2026.06.08.1.pdf`(role=manual_admin)。
- データワークフロー図 `docs\条件分岐データフロー図_43_20260610.drawio/.png` は、リリースmanifest(6/08)・持参一覧(5/28)・初版納品書のいずれにも未掲載だった（図は6/10作成で間に合っていない）。ユーザー要望により配布物へ追加: 納品書(DLV-43-001)の「設計・保守」に明記し再生成、`43_客先移行_持参ファイル一覧_v92.md` に drawio/png を必須追加。
- 残: 正式リリースパッケージ(`package_v2026.06.08.1.zip`)にデータフロー図を含めるには新リリース版の切り直しが必要（固定入口/checksum影響、未実施）。

## 2026-06-16: 重複・不完全な一時保存の扱いを書類化（Codex GPT-5.5 設計反映）

- Codex GPT-5.5に冪等性設計を相談。要点: 冪等性キー=月+支払先(正規化)+金額+支払方法+備考(正規化)+PDF安定テキストハッシュ。既存検出時は停止+担当者通知(対象月/金額/支払先/状態/件数/該当下書き)。不完全下書きはロボットが自動削除/補完しない(fail-closed)。多層防御=実行ロック/保存直前の再スキャン/監査台帳/run_idマーカー/アップロード前PDF照合。
- 致命的失敗モード(Codex): 金額未入力等の不完全下書きを「一致」と誤判定して正常停止扱いにすると、空金額申請 or 正しい申請が作られないまま月が過ぎる。対策=一致度を3段階分類(EXACT青/AMBIGUOUS黄/UNVERIFIABLE赤)し通知の重要度を変える。
- 書類反映(実装はコード別タスク):
  - 要件定義書(REQ-43-002)に「8. 既存の一時保存（重複・不完全）の扱い」を追加。3段階分類表＋「ロボットは自動削除/補完しない」「申請前に同一下書きが1件だけと確認」を明記。6ページ。
  - 運用ガイド(43_運用ガイド.md)に「既存の一時保存（重複・作りかけ）があったときの対応」節を追加。色別(青/黄/赤)の担当者対応、最終申請前の重複確認、月次の同月再実行禁止・月初棚卸しを明記。
- 保守窓口は当面 kalimistk@gmail.com（個人Gmail）のまま。業務用メール取得後に差し替え予定（Codex指摘あり）。
- 残: コード実装(冪等性ガード=署名照合で重複作成しない/3段階分類通知/実行ロック/保存直前再スキャン/監査台帳)。本体ロボット(rakuraku worker)改修＋テストが必要なため別タスク。着手前にCodexで設計レビュー。

## 2026-06-16: 冪等性コード実装 仕様書 作成＋Codex GPT-5.5レビュー反映(v0.2)

- 仕様書 `docs\43_冪等性コード実装_仕様書_20260616.md` を作成（未実装ドラフト）。現状の検出は `_tmp_draft_exists`（tmpViewを金額＋「一時保存」文字のみで照合）と確認し、これを冪等性キー＋3段階分類＋多層防御へ拡張する設計。
- Codex GPT-5.5レビューで致命3件を受け、v0.2に反映:
  - F-1（最重要）: tmpViewのページネーション未完走/フィルター/担当者スコープ/詳細取得失敗を見落として「該当なし」→新規作成すると無音の二重支払い。→ §5に「スキャン完全性ゲート」追加。完全性を証明できなければ UNVERIFIABLE(赤)で停止。
  - F-2: 月+支払先+金額+備考だけでは「再実行」と「正当な2件目」を区別不能。→ §4に強化キー（請求書番号/仕入先コード/口座番号/manifest行ID/PDF安定テキストのうち1件以上）を必須化。
  - F-3: run_idを備考へ埋め込むのは承認者表示・文字数・内容汚染リスク。→ §8で run_idマーカーは仕様確認まで実装保留。
  - MUST-FIX: 詳細取得失敗は赤、実行ロックはアトミック＋オーナー識別＋プロセス死亡確認後のみ失効、月表記正規化はテーブル駆動テスト必須、監査台帳は排他ロック＋fsync＋SaaS優先、保存後にも自分の下書き1件のみを再検証、本体改修前にフィクスチャ/黄金テスト整備。
- 安全境界は不変（最終申請しない/自動削除・補完しない/名義shainCd照合）。実装は本体ワーカー(rakuraku_apply_ready_stop_v60-1 / temporary_save_v83_5)改修＝回帰リスク大のため、ユーザー承認後に段階実装＋self-test。未決事項（tmpViewページング/担当者スコープ、強化キー用業務識別子の有無、備考のrun_id表示可否、赤通知SLA等）を実装前に確定する。

## 2026-06-16: 移行後改修(6/08)の所在判明・「バグ」判定を訂正

- 6/08以降に変わっていた `tools/scenario43_external_pipeline_v92.py` の差分は、**意図的な要件対応**だったと判明。一次ソース: `E:\20260608本番PC改修ファイル\01_回収対象一覧_原因対処.md` No.23。
  - 原因: 「処理済みZIPでも再実行したい、既存一時保存で止めたくない要件」
  - 対処: 「PRODの処理済みZIPガードを外し、既存一時保存を許容。最終申請クリックは引き続き禁止。」
  - No.26: `run_enable_force_processed_reprocess_once_43.bat` は「本体ガード削除済みのため任意ヘルパー」＝フラグ/マーカーは事実上死にコード（コード読解と一致）。
- 訂正: 同変更を本セッション前半で「バグの可能性が高い」と評価したが誤り。6/08の意図的対応である（早合点。記録確認で是正）。
- 6/08回収パッケージ `E:\20260608本番PC改修ファイル\`（回収36件・manifest/hash・状況一覧・終了メモ）が移行後フィードバックの正本。43は「OK/最終申請未クリック・MainSV成果物は削除済み」。Gitは本番PCからpush未実施・43はorigin/master比behind・開発PCで回収取り込み→必要分commit/push予定（未完の可能性）。43の他回収: operator CSVのPROD2名/LOCAL3名分離、select_rakuraku_operator.ps1のenv切替、select_latest_source_xlsx.py 等。
- **未解決の論点（要ユーザー判断）**: 6/08のガード削除（処理済みZIP再処理可・既存一時保存許容）は恒久要件か一時対応か。今日整備した要件定義書8章/運用ガイド/冪等性仕様(v0.2)は「ガードON（停止＋通知）」で、6/08の実挙動と矛盾。恒久なら docsを実挙動へ書換、一時なら冪等性設計でガード復活。どちらにするか確定後に整合させる。

## 2026-06-16: 重複方針を確定（止めない＋2件目通知）

- ユーザー判断: 6/08のガード削除（処理済みZIP再実行・既存一時保存許容）は**恒久運用として継続**。重複を作っても最終申請が人なので担当者が気づいて防ぐ。**ロボットは止めない**。
- 追加要望: **2件目を作ったら「2件目です」と通知**したい（ノーティス）。重複の見落とし防止。
- ドキュメント整合（実態＋通知方針へ統一）:
  - 要件定義書8章を「止めない＋2件目通知」へ書換（3段階停止の表を削除）。
  - 運用ガイドの該当節を「ロボットは止めない・2件目は完了通知で警告・申請は1件だけ」へ書換。
  - 冪等性仕様を v0.3 に方針確定（ブロック設計＝0章/§4〜§9は不採用・参考。実装は「支払先で下書き件数カウント→2件目以降は完了通知に重複警告」のみ）。
- 実装規模: 小。既存 `_tmp_draft_exists()`（金額一致のみ）を支払先での件数カウントへ拡張＋完了メール本文に重複警告を追加。安全境界（最終申請しない/自動削除・補完しない）は維持。
- 次: この軽量実装の小さな差分をCodexレビュー→承認→実装。

## 2026-06-16: 6/08本番改修 回収36件の開発PC反映状況を照合

- `E:\20260608本番PC改修ファイル\回収ファイル\01_RK10_Robots_full\` の36件を開発PC `C:\ProgramData\RK10\Robots\` とSHA256照合。
- 結果: 反映済(一致)=32 / 相違=2 / dev無し=2。**43は全て反映済み**。
- **未反映はシナリオ42のみ**（本セッションの43対象外だが重要なので記録）:
  - 相違: `42\tools\csv_to_excel.py`（ゼロ埋め互換名の上書き修正・未反映）、`42\config\env.txt`（PROD/LOCAL差＝想定内）
  - dev無し: `42\senario\42ドライブレポート_PROD本番実行_20260608.rks`、`同_v2_20260608.rks`（ExitCode誤判定→JSON判定のv2含む・本番新RKSが開発PCに無い）
- 注意: 本照合は6/08回収パッケージ範囲のみ。6/08以降の本番修正は対象外。本番からのgit push未実施のため、42は「回収済みだが開発PC/git未取り込み」。
- 次アクション候補: 42の未反映4件（実体は2 RKS＋csv_to_excel.py差分、env除く）を開発PCへ取り込み・差分レビュー・commit。43は同期完了。

## 2026-06-16: A/B/C実行（42同期確認・6/08以降確認・2件目通知実装）

### A: シナリオ42は同期ギャップではなかった（訂正）
- E:再接続後にdiff。dev側42は6/10に単一固定名RKS `42ドライブレポート_本番.rks` へ刷新、`csv_to_excel.py` も6/10版（6/08と352行差・dev側が新しい）。6/08回収の旧RKS2本はdev側v1で superseded。→ **42は「dev側が6/08より先行」。取り込み不要**。前回の「未反映」評価を訂正。

### B: 6/08以降の本番改修（43）は無し
- E:直下に `移行後フィードバック`(6/15・空) と `★★★客先はここだけ開く★★★`(6/15・Codex司令塔 客先入口) を発見。フィードバックは「客先作業後に feedback_日時 が生成される」仕組みで現状未生成。
- 43について6/08以降の本番コード変更は無し（devは6/08で同期済み）。他は6/11本番移行キット(43以外)・6/14の12_13差分のみ。

### C: 2件目通知を実装（止めない・重複したら完了メールで警告）
- Codex GPT-5.5で最小差分設計をレビュー後に実装。変更は `tools/rakuraku_temporary_save_v83_5_operator_2price.py` のみ（約50行）:
  - `_count_tmp_drafts_for_supplier()` 追加（tmpViewを読取専用で「一時保存」かつ支払先名を含む行を件数カウント）。
  - `run()` に `draft_count_holder` 引数（デフォルトNone・既存呼び出し非破壊）。一時保存(after_save)直後・非dry/smoke時に件数取得。
  - `main()` で完了メール本文に分岐追加: count>=2→【重複警告】これは2件目以降…申請は1件だけ／count=None→【重複確認不可】手動確認を／else→警告なし。止めない・自動削除/補完しない・最終申請は人。
- 検証: `py_compile` OK、worker `--self-test` 全True、`run_apply_ready_stop_worker_v83_5_playwright.bat --self-test` OK、`run_scenario43_external_pipeline_v92.bat --self-test` OK（回帰なし）。
- 残テスト（実機・未実施）: LOCALで `--allow-duplicate-draft-for-test --send-mail` により2件目を作り、完了メールに【重複警告】が入ることの確認。実サイト操作のため担当者/ユーザー承認のうえ実施。

## 2026-06-16: 本番移行キットを6/16最新へ更新（最小差分・Codex GPT-5.5レビュー反映）

- 方針: 6/11キット以降にコード変更があったのは43のみ（70は実行証跡・docsは進捗CSVでコード非変更／12_13は6/14差分キットあり）。よって全15再ビルドはせず、6/11検証済みベースラインを土台に**43だけ差し替え＋12_13差分同梱**。
- 生成物: `E:\RK10_本番移行キット_20260616`（6/11は温存）。
  - 43差し替え: `files\Robots\43...\tools\rakuraku_temporary_save_v83_5_operator_2price.py`（2件目通知）＋`docs\43_運用ガイド.md`（重複通知の節）。技術版要件定義書/テスト結果はベンダー内部保管として**非同梱**（個人名・社員コード・停止コードを含むため）。
  - 12_13差分は `delta\RK10_差分移行キット_12_13\` に同梱（本体apply後に別途適用）。
- Codex GPT-5.5レビュー反映（致命1=本番稼働中の上書き半更新）:
  - `apply_files.ps1`: 退避名を `.bak_premigration_20260616` へ／**同一SHAはスキップ**（再適用安全・冪等）／既存bak保護維持／冒頭に**RK10停止確認ゲート**（`APPLY_NONINTERACTIVE` で自動化時のみバイパス）。
  - PIIスキャン: 実秘密値の混入なし（検出は認証変数名/環境変数名と6/11既存ledgerの内部path程度）。
  - 新規 `00_README_20260616_変更点と適用手順.md`、`manifest_files_20260616.sha256.txt`、司令塔/Claudeプロンプトのキット参照を6/16・delta\へ更新。
- 検証: apply_files.ps1 構文OK／43 worker self-test・関連BAT self-test 合格／43ペイロード（worker＋運用ガイド）と delta\12_13 同梱を確認／worker に2件目通知コード在り。
- 適用は客先PCで `apply_files.bat`（yes）→必要なら delta 別途。ロールバックは `*.bak_premigration_20260616`。

## 2026-06-16: 客先Codex用 単一マスター指示書を作成（一括指示）

- 要望「客先PCでCodexに一気に全作業を指示できるように」。6/16キットに `00_客先Codex_全作業指示_20260616.md` を新規作成。これ1枚でPhase0(前提)→1(apply_files)→2(watcher)→3(シナリオ別57/63/55/71/12・13/47/56/70/58＋12_13差分はdelta\＋43はworker更新のみ)→3.5(V1-V10)→4(ログ収集・報告書・移行後フィードバック) を最後まで実行できる。
- 既存 prompt_claude_code_本番移行.md(Phase0-4) を土台に、6/16差分（apply_filesのRK10停止ゲート/同一SHAスキップ、43の2件目通知、12_13は delta\）を織り込み、Codex運用前提（--ask-for-approval untrusted / --sandbox workspace-write）と不可逆操作のSTOP関門・秘密値非取得・作業ログ必須を明記。
- `00_最初に読む.txt` にCodex入口（この1ファイルを渡す）を追記。客先には「このファイルに従って最後まで進めて」とだけ指示し、STOPで担当者OK/NGを返す運用。
- 未実施: この指示書のGPT-5.5レビュー（外部運用前に推奨）、実機での通し。

## 2026-06-16: Codex指示書の客先設置＋開発PC側「移行後同期」手順・差分照合ツール

- ① 客先がすぐ見つかる位置へ設置: `E:\★★★客先はここだけ開く★★★\00_客先Codex_全作業指示_20260616.md` をコピー、同フォルダ `00_最初に読む.txt` に「Codexにこの1ファイルを渡す」案内を追記。
- ② 開発PC側の移行後ワークフローを整備（再利用）:
  - 手順書 `C:\ProgramData\Generative AI\Github\rpa-automation\rk10\開発PC_移行後同期_手順.md`（①フィードバック確認→②本番改修有無→③差分確認→④取り込み判断(方向注意・dev先行あり)→⑤シナリオ別gitで同期→⑥決定ログ記録。env/秘密値は同期しない）。
  - 差分照合ツール `…\rk10\tools\compare_recovery_vs_dev.ps1`（回収パッケージ vs 開発PC現物をSHA256照合、SAME/DIFF/DEV_MISSING出力、読取専用、env.txt既定除外、-CsvOut対応）。
  - 検証: 6/08回収で実行し SAME=26/DIFF=1/DEV_MISSING=2、42のcsv_to_excel.pyはdev(6/10)先行を再現＝手動結果と一致。
- 運用: 毎移行サイクルで、客先=単一指示書1枚／開発PC帰着後=手順書＋compareスクリプトで差分確認→同期、を回す。

## 2026-06-16: 移行ファイル一式 Codex GPT-5.5レビュー反映（apply硬化・手順補強）

- Codex gpt-5.5レビューの高優先指摘をapply_files.ps1へ反映:
  - 適用前ゲート1: **RK10関連プロセス検出（RK-10/Keyence/netcoredbg/RunScenario・KEYENCE\RK-10パス）→ 稼働中なら問答無用でAbort**（半更新防止・人力yesだけに依存しない）。
  - 適用前ゲート2: `APPLY_NONINTERACTIVE` を**固定トークン `I_ACCEPT_PROD_FILE_APPLY_20260616` 必須**へ硬化（環境変数の偶発継承で誤バイパスしない）。使用時はログ表示。トークン不一致時は対話確認へフォールバック。
  - **コピー後のSHA検証**（src/dst不一致なら throw で中止）。既存の同一SHAスキップ・bak一度だけ退避・既存bak保護は維持。
  - 構文OK確認済み。
- 開発PC側 `開発PC_移行後同期_手順.md` に「**取り込み前にGitバックアップ必須**（stash -u もしくは backup/ ブランチ）」を追記＝逆方向上書きでdev先行を潰す事故の歯止め。
- Codex評価: 冪等性設計・除外ポリシー(PII/secrets)・Phase順とSTOP配置は妥当。残注意: `--ask-for-approval untrusted` は意味的危険を防がない＝STOP規約は指示書ルール依存（人の確認が要）。Phase4ログ/報告書の必須実行、客先前のbakリストア試験・ビルド後PII再スキャンをチェックリスト化。
