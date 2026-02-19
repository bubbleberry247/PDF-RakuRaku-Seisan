# Scenario 57: 基幹システムより仕訳はきだし

## 2026-02-11

### [PROCESS][CODE][KAIZEN] 初期立ち上げと実行ブロッカー整理
- 目的:
  - 57シナリオを `pre/run/post` 分離で運用可能にし、test/prod設定分離と通知統一を実施。
- 実施:
  - `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py`
  - `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py`
  - `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py`
  - `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\docs\57_automation_assumptions.md`
- 実行結果:
  - dry-run は `run-all(test/prod)` で通過。
  - non-dry-run は `Notepad window was not found.` で停止。
- 判明事実:
  - ログ上、`172.16.0.53 - 個人 - Microsoft Edge` がログイン窓として誤選択されるケースがある。
  - ログイン入力用Editとして期待するコントロールを取得できず、URLバー相当2件のみのケースがある。
- 既存資産チェック:
  - 候補1: `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\output\automation\automation_20260211_161834_4a27ca.py`
    - 動画解析由来の工程順（VPN→ログイン→月次→入金仕訳→保存）が含まれる。
    - ただしセレクタは TODO で未確定のため、そのままは利用不可。
  - 候補2: `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py`
    - 既存のリトライ/ログ/保存フォールバックを再利用しつつ、窓判定ロジックを改善する方針。
- 次アクション:
  - ログイン窓誤認防止のスコア判定を導入。
  - Notepad非経由（SaveAs直出し）にも対応する。

### [CODE][VERIFICATION] ログイン窓判定の改修と検証結果
- 変更:
  - `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py`
    - ログイン窓選択を `title一致` から `スコア判定` へ変更（Edit/Combo/Button構成で判定）。
    - URLバー疑い（Edit<=2 + host文字列のみ）を明示除外。
    - シナリオエディタ窓（`.rks` / scenario / editor）をログイン候補から除外。
    - 保存処理を `Notepad` と `Save As直出し` の両経路に対応。
- 検証:
  - `python -m py_compile ...\s57_ui_run.py` 成功
  - `python ...\s57_main.py --phase run-all --env test --dry-run --allow-missing-output` 成功
  - `python ...\s57_main.py --phase run-all --env prod --dry-run --allow-missing-output` 成功
  - `python ...\s57_ui_run.py --env test --plan-file ...\run_plan_20260211_233608_test.json` 失敗（期待通り早期停止）
- 現在の事実:
  - 実行時刻 `2026-02-11 23:44` の non-dry-run は
    `RuntimeError("Login window was not found after launch_url retry.")` で停止。
  - `LOGIN_WINDOW_SCORING` ログでは host付きEdge窓の `score=0`（URLバーEditのみ）で閾値未満。
  - つまり「ログインフォーム自体が pywinauto から観測できない」段階であり、
    以前の誤選択よりも手前で安全停止できる状態になった。

### [CODE][PROCESS] エラー通知ハング対策
- 変更:
  - `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py`
    - `_send_outlook_with_timeout(..., timeout_sec=30.0)` を追加。
    - `NOTIFY_POST_SUCCESS` / `NOTIFY_ERROR` の送信処理をタイムアウト付き呼び出しへ変更。
- 背景:
  - non-dry-run 失敗時に Outlook COM 送信で待ち続け、`run-all` コマンドがタイムアウトするケースがあった。
- 検証:
  - `python -m py_compile ...\s57_main.py` 成功
  - `python ...\s57_main.py --phase run-all --env test` は 158秒/188秒で `exit code 1` 返却（ハングせず復帰）。
  - ログ上は `ERROR_NOTIFY_FAILED ... Outlook send timed out after 30.0s` を記録し、通知失敗時もプロセスは終了する。

## 2026-02-12

### [CODE][POKAYOKE][VERIFICATION] Host到達性チェックとログインフォールバック整理
- 変更ファイル:
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py
- 変更内容:
  - UI実行前に `application.launch_url` の host に対して TCP:80 到達性チェックを追加（`HOST_CONNECTIVITY_OK/FAIL` をログ出力）。
  - ログイン窓スコアが閾値未満でも、`host + Edge` 一致の窓は `fallback_host_edge` として採用。
  - URLバー相当（Edit<=2, Combo=0, host文字列のみ）を検出したら、コントロール直接入力をやめてキーボード順次入力へ切替（会社CD→担当者ID→パスワード→Enter）。
  - キーボードログイン後に main menu が見つからない場合は即停止（誤継続を防止）。
- 検証:
  - `python -m py_compile C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py` 成功。
  - `python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env test --dry-run --allow-missing-output` 成功。
  - `python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env test` は 41.8秒で終了し、`Launch host is unreachable on TCP port 80: 172.16.0.53.` を返すことを確認（従来の曖昧なログイン窓未検出より原因特定が容易）。

### [CODE][POKAYOKE][VERIFICATION] launch_url の scheme/port 解釈統一
- 変更ファイル:
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py
- 変更内容:
  - `launch_url` の解析を `scheme/host/port` 対応へ拡張（https=443, http=80, 明示ポート優先）。
  - `run_prep` に `launch_connectivity` を追加し、run_planで到達性を先に可視化。
  - `ui_run` は同じURL解析結果を使って到達性エラーを出すよう統一。
- 検証:
  - `python -m py_compile ...\s57_ui_run.py ...\s57_run_prep.py ...\s57_main.py` 成功。
  - `python ...\s57_run_prep.py --env test --dry-run` で `launch_connectivity` 出力確認。
  - `python ...\s57_main.py --phase run-all --env test --dry-run --allow-missing-output` 成功。
  - `python ...\s57_main.py --phase run-all --env test` は `Launch host is unreachable on TCP port 80: 172.16.0.53.` で停止。
  - `python ...\s57_run_prep.py --env prod --dry-run` で `target_parent_status.error=WinError 53` を確認。

### [CODE][VERIFICATION] Subprocess decode hardening and pre-UI connectivity gate
- Changed files:
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py
- What changed:
  - Switched child process capture from text-mode decoding to byte capture + utf-8/cp932 fallback decode.
  - Added subprocess error summarization in main orchestrator for clearer root-cause messages.
  - Added pre-UI launch connectivity gate for non-dry-run. If run_plan shows host unreachable, stop before UI automation.
  - Prevented duplicate network hint text in top-level error handling.
- Verification:
  - python -m py_compile C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py
  - python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env test --dry-run --allow-missing-output
  - python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env prod --dry-run --allow-missing-output
  - python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env test
- Result:
  - No UnicodeDecodeError recurrence during latest runs.
  - Non-dry-run now stops with explicit message: launch host unreachable + route conflict hint.

### [CODE][POKAYOKE][VERIFICATION] Pre-UI readiness gate expanded (password/path/connectivity)
- Changed file:
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py
- What changed:
  - Added `_load_plan_json()` to centralize run_plan loading (utf-8-sig).
  - Added `_assert_plan_ready_for_ui()` and wired it into non-dry-run `run` / `run-all`.
  - Readiness checks now fail fast before UI start when any of these are false:
    - `launch_connectivity.reachable`
    - `password.is_set`
    - `target_parent_status.created_or_exists`
  - Error now reports combined causes in one line to reduce trial-and-error.
- Verification:
  - python -m py_compile C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py
  - python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env test --dry-run --allow-missing-output
  - python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env test
  - python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env prod
- Result:
  - test non-dry-run now stops before UI with explicit causes:
    - launch host unreachable
    - password env var missing (`RK10_S57_PASSWORD`)
  - prod non-dry-run now stops before UI with explicit causes:
    - launch host unreachable
    - password env var missing (`RK10_S57_PASSWORD`)
    - target save parent unreachable (`WinError 53` on `\\192.168.1.251\TIC-mainSV\...`)

### [CODE][KAIZEN][VERIFICATION] UNC parent check timeout to avoid long stalls in prod preflight
- Changed file:
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py
- Existing asset reused:
  - `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\outlook_save_pdf_and_batch_print.py` (`_test_path_with_timeout`, PowerShell `Test-Path` with timeout)
- What changed:
  - Added `TARGET_PARENT_TIMEOUT_SEC=12.0`.
  - For UNC paths in `_ensure_target_parent`, switched from direct `Path.mkdir(...)` to PowerShell check/create with explicit timeout.
  - Kept local path behavior unchanged (`mkdir(parents=True, exist_ok=True)`).
- Verification:
  - python -m py_compile C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py
  - python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py --env prod --dry-run
  - python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env prod
- Result:
  - `target_parent_status.error` is now deterministic timeout (`timeout after 12.0s`) instead of long blocking.
  - `run_prep --env prod --dry-run` elapsed about 20.9s in this environment.
  - `run-all --env prod` now fails pre-UI with full combined causes and does not enter UI automation.

### [CODE][POKAYOKE][VERIFICATION] Input-page confirmation gate to prevent false progress after URL-bar login fallback
- Changed file:
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py
- Existing assets checked (Gate 1 evidence):
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py (existing login/save detection flow)
  - C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\outlook_save_pdf_and_batch_print.py (timeout/pokeyoke pattern reused earlier for prep)
- What changed:
  - Added `_looks_like_shiwake_input_window()` with UI-marker heuristics (title/control text) to validate real transition to shiwake input page.
  - Added `INPUT_WINDOW_CHECK` at post-menu fallback and before period input.
  - If only URL-bar-like Edge state is detected, automation now stops with:
    - `RuntimeError: Shiwake input page was not confirmed after menu navigation (possible login failure).`
  - Added `_force_navigate_url_in_edge()` and one extra retry path to navigate URL from Edge omnibox when login window detection misses.
- Verification:
  - `python -m py_compile C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py`
  - `python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env test --dry-run --allow-missing-output`
  - `python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env prod --dry-run --allow-missing-output`
  - `$env:RK10_S57_PASSWORD='dummy-pass-for-test'; python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env test`
- Result:
  - Previous failure (`Output save window was not found`) no longer appears in this run.
  - New deterministic stop point is earlier and actionable:
    - `INPUT_WINDOW_CHECK ... result=False reason=likely_url_bar_window_with_host_only`
    - `RuntimeError: Shiwake input page was not confirmed after menu navigation (possible login failure).`
  - This indicates login success/state transition is still not confirmed with dummy credential; real credential + app-side screen markers are required for full E2E.

### [CODE][POKAYOKE][VERIFICATION] Preflight password availability aligned with UI credential fallback
- Changed file:
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py
- Existing assets checked (Gate 1 evidence):
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py (`_load_password`, `_read_env_from_registry`, `_read_generic_credential_password`)
- What changed:
  - Extended `_password_status()` from env-only check to multi-source check:
    - environment variable
    - Windows registry env values
    - Generic Credential by env var name
    - fallback targets: `Password`, `パスワード`, `webログイン`, `パスワード　楽楽精算`
  - Added `password.source` in run plan JSON for observability.
- Verification:
  - `python -m py_compile C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py`
  - `python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py --env test`
  - `python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env test`
- Result:
  - run plan now reports `password.is_set=true` with `password.source="credential:Password"`.
  - `run-all --env test` proceeds without manual env var injection and reaches UI phase.
  - Current deterministic stop remains:
    - `RuntimeError: Shiwake input page was not confirmed after menu navigation (possible login failure).`

### [CODE][KAIZEN] Input-page mismatch diagnostics enriched
- Changed file:
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py
- Change:
  - `_looks_like_shiwake_input_window()` now includes top visible control text samples in failure reason to speed up selector mismatch analysis.
- Verification:
  - `python -m py_compile C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py`

### [CONFIG][CODE][VERIFICATION] Env split for login requirement (LOCAL requires login, PROD skips login)
- User decision (2026-02-12):
  - LOCAL (`test`) is outside network and can log in via VPN.
  - PROD (`prod`) is inside internal network and must run without login.
- Changed files:
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\config\tool_config_test.json
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\config\tool_config_prod.json
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py
  - C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py
- Implementation:
  - Added `application.login_required` in both env configs (`true` for test, `false` for prod).
  - `s57_run_prep.py` now writes `application.login_required` into run_plan and changes known step 03 text by env.
  - `s57_ui_run.py` now skips login steps when `login_required=false` and marks those steps as `skipped` in run report.
  - `s57_main.py` preflight now enforces password readiness only when `login_required=true`.
- Verification:
  - `python -m py_compile C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_run_prep.py C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_ui_run.py C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py`
  - `python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env test --dry-run --allow-missing-output`
  - `python C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\s57_main.py --phase run-all --env prod --dry-run --allow-missing-output`
- Result evidence:
  - Test run plan contains `"login_required": true` and step03 `"会社CDを選択してログイン"`.
  - Prod run plan contains `"login_required": false` and step03 `"ログイン不要（社内ネットワーク内）"`.
  - Prod run report marks login steps with detail `"login not required for this environment"`.
