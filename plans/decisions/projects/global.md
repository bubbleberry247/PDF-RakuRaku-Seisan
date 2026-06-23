# Global Project Decisions

このファイルは横断的な決定ログである。新規決定は append-only で追記する。
legacy `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\decisions.md` は凍結済みのため、新規追記しない。

---

## 2026-06-16 AIレディ会社化の初期導入方針

### 決定

客先のAI導入は、`Claude Team 5席 + Claude Platform API小額枠 + OpenAI比較枠` から開始する。Claude Managed Agents は基幹本番ではなく、AI担当者が作る次世代業務自動化基盤のPoCとして扱う。

### 背景

- 目的は全社員へのAIチャット配布ではなく、部署ごとのAI担当者が社内ツールを作れる状態を作ること。
- RK10置換は一括移行せず、低リスク業務からPython、軽量Webアプリ、ワークフロー、AIエージェントへ段階移行する。
- 既存RPA運用では100%品質、停止条件、通知、再実行安全が重要であり、AI導入でも同じ品質基準を維持する。

### 適用範囲

- 5名PoC、10名展開、最大50名展開、RK10段階置換。
- 部署AI担当者、業務承認者、AI統括管理者、保守担当者。
- AIで作成する社内ツール、プロンプト、ルーブリック、MCP、軽量アプリ、ワークフロー。

### 初期ルール

- AIが支払、承認、マスタ更新、基幹DB更新を単独実行する処理は禁止から開始する。
- 個人情報、会計、顧客情報、基幹DB接続は段階許可制にする。
- 初期PoCは匿名化データ、サンプルデータ、読み取り専用データで実施する。
- 業務ロジックはClaude/ChatGPT画面内だけに閉じ込めず、Markdown、Git、Python、API仕様、MCP仕様として保存する。
- 個別ツールは、目的、入力、出力、停止条件、承認者、ログ場所、再実行安全、復旧手順を持つ。

### 運用成果物

親ドキュメントは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\docs\ai-ready-company\README.md` とする。個別ツールの要件定義・処理フロー・例外設計・運用手順は `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\cases\_template\` を使う。

### 10名展開前の判定条件

- 5名PoCで最低3つの業務ツール試作が完成している。
- 各ツールに入力例、出力例、失敗時停止条件、人間レビュー手順がある。
- 月次コストが担当者別、用途別に説明できる。
- 機密データ投入ルールと禁止事項が文書化されている。
- Claude継続、OpenAI併用、Microsoft 365 / Google Workspace 採用有無を判断できる比較表が完成している。

### 参照

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\docs\ai-ready-company\README.md`
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\docs\operating_model.md`
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\docs\logging_policy.md`
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\docs\regression_criteria.md`
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\cases\_template\README.md`

---

## 2026-06-17 Digital Billder導入前提とAI連携方針

### 決定

客先は2027年4月までにDigital Billderを導入する前提で、AI導入ロードマップを組み直す。AIはDigital Billderと競合する別基幹ではなく、Digital Billder導入前後の業務整理、照合、例外検知、問い合わせ対応、RPA・自社UI連携を支える補助基盤として位置づける。

### 背景

- Digital Billderの提供URLでは、建設業に特化した請求書受領サービスとして、請求書の受領、承認、保管、インボイス制度、電子帳簿保存法への対応が示されている。
- 2027年4月の導入前に、現行業務、承認ルール、マスタ、帳票、CSV、例外処理、RPA対象を棚卸しする必要がある。
- AI導入の初期目的は、Digital BillderをAIで置き換えることではなく、導入・定着・運用改善を速く安全に進めること。

### 連携ステップ

- 2026年6月から2026年9月: 現行業務、請求書・帳票・CSV、RPA、自社UI、承認フロー、例外パターンを棚卸しする。
- 2026年10月から2027年3月: Digital Billder導入準備に合わせて、AIによる手順書作成、FAQ作成、入力前チェック、差戻し理由整理、テストデータ照合を行う。
- 2027年4月: Digital Billder稼働時は、AIを本番更新者にせず、問い合わせ対応、操作支援、ログ整理、承認前チェック、RPA失敗分析に限定する。
- 2027年5月以降: 効果が確認できた業務だけ、自社UIによるAI/RPA管理、Python RPA、Digital Billder出力、基幹補助連携へ段階的に広げる。

### 禁止・注意

- AI単独で支払、承認、マスタ更新、Digital Billderや基幹システムへの確定更新を行わない。
- 自社UIは請求書や支払の業務承認フローを担当しない。自社UIの役割は、AI/RPAの依頼、実行状況、ログ、費用、権限、失敗時確認を管理すること。
- APIがない場合は、いきなり画面操作自動化へ進めず、CSV出力、帳票、ログ、承認済みデータを優先して連携する。
- Digital Billder導入効果とAI導入効果を混同せず、請求書処理短縮、差戻し削減、RPA保守時間削減、問い合わせ削減を分けて測定する。

### 参照

- ユーザー提供URL: `https://www.lp.digitalbillder.com/invoice`
- 確認コマンド: `Invoke-WebRequest -Uri 'https://www.lp.digitalbillder.com/invoice' -UseBasicParsing`

---

## 2026-06-22 客先安全入口BATのASCIIランナー化

### 決定

客先が直接押す安全入口BATは、日本語パスを `cmd.exe` に直接読ませない。BAT本文はASCIIだけにし、`run_customer_safe_entry.ps1` からBase64化したUTF-8パスを復元してPythonツールを起動する。GUI確認画面を担当者が見る必要がある入口は、非表示ではなく通常表示で起動する。

### 背景

- `C:\ProgramData\RK10\Robots\migration\customer_safe_entries_20260622` の一括スモークで、UTF-8 no-BOM BAT内の日本語パスが `cmd.exe` で文字化けし、37/38/42/43/51/52が起動前に失敗した。
- 57はexit0だったが、配下BATの日本語echo/commentがコマンドとして解釈され、stderrに不要エラーが出た。
- 58は既存入口の日本語パス直書きにより、SAFE v2確認画面起動前に `The system cannot find the path specified.` で失敗した。

### 修正

- 追加: `C:\ProgramData\RK10\Robots\migration\customer_safe_entries_20260622\run_customer_safe_entry.ps1`
- 修正: 37/38/42/43/51/52/57/58の安全入口BATをASCIIランナー呼び出しへ変更。
- バックアップ: 各BATに `.before_20260622_1706_ascii_runner_fix` を付与。
- 修正版コピー: 各BATとPS1に `.fixed_ascii_runner_20260622_1709` を付与。

### 検証

- 修正後再実行: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\customer_safe_entries_smoke_20260622\rerun_ascii_fix_20260622_170923\results.json`
- 結果: 37/38/42/43/51/52/57の対象10入口はexit0 10件、nonzero 0件、timeout 0件。58は別途、BAT exit0、stderr空、SAFE v2 GUIプロセス1件起動を確認。
- 検証一覧: `C:\ProgramData\RK10\Robots\migration\customer_safe_entries_20260622\validation_20260622.json` は22件、missing wrapper 0、missing target 0、BOM 0、unsafe target 0。

### 2026-06-22 追補

- 56のLOCAL/PROD入口も `run_customer_safe_entry.ps1` 経由に変更した。
- 12/13、44、47、55、63、70、71の安全入口BATにも日本語パス直書きが残っていたため、同じASCIIランナー方式へ統一した。
- `run_customer_safe_entry.ps1` は、Python/PowerShell出力と終了コードが混ざっても最後の数値終了コードを返す `Normalize-ExitCode` を持つ。
- `55_SAFE_V2_COPY_WRITE_NO_MAIL_ここから起動.bat` は `25日` 引数もBase64復元にし、Windows PowerShell 5.1での文字化けを回避した。
- `C:\ProgramData\RK10\Robots\migration\customer_safe_entries_20260622\validation_20260622.json` は22件、BOM 0、BAT本文non-ASCII 0、PS1本文non-ASCII 0。
- 56 PRODはMainSV未到達をexit1として親BATへ正しく伝播することを確認した。
- 55はASCIIランナー経由で再実行し、93件/12,938,354円照合OK、メールskip、exit0を確認した。

### 2026-06-22 RK10ライセンスダイアログ追補

- RK10起動時にライセンス種別ダイアログが出て、`RPA開発版AI付き` が既定選択されている場合、ラジオボタンは変更せずOKのみ押す。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\run_rks_editor_open_build_probe_20260620.py` は、`DevelopmentLicenseCheckBox` をクリックしない実装へ更新した。
- 検証: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tests\test_rk10_license_default_ok_policy_20260622.py` を固定ランナーへ組み込み、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` で最新 `overall_passed=True` を確認した。
- RK10 ButtonRun、業務実行、本番書込、実メール、実印刷、最終申請、支払実行はこの方針変更では許可しない。

---

## 2026-06-23 SoftBank 51/52 手動申請方針の再固定

### 決定

SoftBank 51/52 は、楽楽精算へ自動ログイン・一時保存・申請しない。シナリオで作成した資料と、郵送で来た請求を合算し、客先担当者が手動で楽楽精算へ申請する。

### 背景

- ユーザー確認により、SoftBankの楽楽精算申請は本シナリオの自動実行対象ではなく、担当者の手動申請であることを再確認した。
- 旧メモにはLOCAL一時保存テスト経路が残っているが、現行方針では合格条件にも検証対象にも採用しない。

### 修正

- `C:\ProgramData\RK10\Robots\51&52ソフトバンク部門集計楽楽精算申請\tools\main_52.py` は、手動申請待ちの結果JSONを出して正常終了する。`--allow-rakuraku-application` / `--save-draft` / `--submit-final` が指定された場合は安全停止する。
- `C:\ProgramData\RK10\Robots\51&52ソフトバンク部門集計楽楽精算申請\tools\run_pipeline.py` は、Stage 3を「SoftBank手動申請待ち記録」に変更し、楽楽精算の自動操作分岐を削除した。
- 変更前バックアップは `.before_20260623_softbank_manual_apply_1128` として別名保存した。

### 検証

- 新ランナー: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\run_s51_52_manual_submission_safe_capture_20260623.py`
- 証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\s51_52_manual_submission_safe_recheck_20260623\run_20260623_112924\s51_52_manual_submission_safe_summary.json.numbered`
- 結果: `py_compile=0`、`pipeline_excel_only_dryrun_no_mail=0`、`main52_manual_submission_record_no_mail=0`、危険フラグ `--allow-rakuraku-application --save-draft` は期待通り `exit_code=2`、unexpected_failure_count=0。

### 2026-06-23 追記: 51/52 費用証跡マップの手動申請方針対応

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_business_cost_evidence_map_20260620.py` は、現行 `main_52.py` が出す `application_amounts_candidate` / `total_amount` / `manual_submission_required` / `manual_submission_basis=scenario51_created_documents_plus_postal_invoice` を、楽楽精算自動操作なしの費用証跡として扱う。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_goal_evidence_ledger_20260620.py` は `SOFTBANK_MANUAL_SUBMISSION_AMOUNT_REPORTED_RAKURAKU_SKIPPED` を `cost=SAMPLE_OK` として分類する。
- 最新監査では `REQ-04` が `PROVED` へ戻り、`business_cost_ready_count=14/14`。ただし 51/52 の楽楽精算申請は引き続き客先担当者の手動作業であり、自動ログイン・一時保存・申請はしない。

### 2026-06-23 追記: シナリオ43スコープ除外の入力パケット反映

- ユーザー指示により、シナリオ43は別システム修正中のため、この目標の残確認パケットから除外する。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_remaining_operator_evidence_digest_20260623.py` と `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_remaining_operator_input_packet_20260623.py` は、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\objective_scope_exclusions_20260623\objective_scope_exclusions.json` の active exclusion を読み、生成元で除外する。
- 最新結果は raw 11件からシナリオ43を1件除外し、残operator入力は10件。除外は承認扱いではなく、目標スコープ外扱い。
- 検証: `uv run python -X utf8 -m pytest tests\test_generate_remaining_operator_evidence_digest_20260623.py tests\test_generate_remaining_operator_input_packet_20260623.py tests\test_validate_remaining_operator_input_ready_20260623.py -q` は `14 passed in 2.01s`。全体safe runnerは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` で `overall_passed=True`。
- 同期証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\remaining_operator_scope_exclusion_filter_20260623\sync_manifest_remaining_operator_scope_filter_20260623.json.numbered`、コピー先は `C:\ProgramData\RK10\Robots\migration\reports\remaining_operator_scope_filter_20260623_1407` と `E:\東海インプル建設\RK10_本番移行キット_20260616\docs\latest_readiness_20260622\remaining_operator_scope_filter_20260623_1407`。

### 2026-06-23 追記: 最終レビューパック active scope 正本化

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_remaining_operator_final_review_pack_20260623.py` は、最終レビュー pack に `scope_exclusion_count` と `packet_scope_excluded_scenarios` を明示する。シナリオ43はスコープ除外であり、承認済み扱いではない。
- AI既定版固定ランナー `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\run_safe_goal_checks_20260620_ai_default_probe_20260622.py` 実行後の正本は、active review row 10件、scope exclusion 1件（43）、not ready 10件。
- 上流CSV自体がスコープ除外後の10件になったため、今後の現場レビューでは `packet_raw_row_count=11` ではなく、active row 10件 + scope exclusion count 1件として説明する。
- 検証: AI既定版固定ランナーは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` で `overall_passed=True`。pytestは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\02_pytest.stdout.txt` で `390 passed`。
- 同期証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_review_active_scope_counts_20260623\sync_manifest_final_review_active_scope_counts_20260623.json.numbered`、`source_count=22`、`copy_result_count=44`、`all_hashes_match=True`。

### 2026-06-23 追記: final_review_active_scope_counts 同期件数補正

- `plans\decisions\projects\global.md` と `plans\handoff.md` も同期対象へ追加したため、最終同期manifestは `source_count=24`、`copy_result_count=48`、`all_hashes_match=True` が正しい。
- 正本: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_review_active_scope_counts_20260623\sync_manifest_final_review_active_scope_counts_20260623.json.numbered`。

### 2026-06-23 追記: 最小operator入力UIの固定安全ランナー組み込み

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_minimum_operator_review_input_20260623.py` を追加し、`remaining_operator_input.csv` と active scope 最終レビューパックから `minimum_operator_review_input.csv` / HTML / summary / START_HERE を再生成できるようにした。
- 既存の人手入力欄 `operator_result/reviewer/reviewed_at` は保持するが、承認値は自動作成しない。RK10 ButtonRun、本番書込、実メール、実印刷、最終申請、支払実行、有償Azure OCRは行わない。
- AI既定版固定ランナー `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\run_safe_goal_checks_20260620_ai_default_probe_20260622.py` に `minimum_operator_review_input` と `minimum_operator_review_input_after_sync` を追加し、今後の安全確認で最小入力UIも最新化する。
- 最新結果は `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\minimum_operator_review_input_summary.md.numbered` で、active row 10件、blank operator row 10件、latest evidence 実在10件、scope exclusion 1件（43）。
- 検証: `uv run python -X utf8 -m pytest tests\test_generate_minimum_operator_review_input_20260623.py tests\test_run_safe_goal_checks_remaining_operator_digest_order_20260623.py -q` は `3 passed in 0.53s`。固定ランナーは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.json` で `overall_passed=True`、pytestは `392 passed in 20.67s`。
- 同期証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_active_scope_20260623\sync_manifest_minimum_operator_review_active_scope_20260623.json.numbered`、`source_count=27`、`copy_result_count=58`（manifest自身除外）、`all_copy_hashes_match=True`。コピー先は `C:\ProgramData\RK10\Robots\migration\reports\minimum_operator_review_active_scope_20260623_1442` と `E:\東海インプル建設\RK10_本番移行キット_20260616\docs\latest_readiness_20260622\minimum_operator_review_active_scope_20260623_1442`。

### 2026-06-23 追記: 最小operator入力UIの証跡シグナル追加

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_minimum_operator_review_input_20260623.py` は、各行の latest evidence 本文から成功シグナル・注意シグナル・安全停止/副作用なしシグナルを抽出し、CSV/HTML/Markdownへ表示する。
- この変更は人手レビューの判断材料を増やすだけで、`operator_result/reviewer/reviewed_at` は引き続き自動入力しない。
- 最新再生成結果は active row 10件、blank operator row 10件、latest evidence 実在10件、scope exclusion 1件（43）。証跡シグナルは success 7行、attention 6行、safety 8行。
- 検証: `uv run python -X utf8 -m pytest tests\test_generate_minimum_operator_review_input_20260623.py -q` は `2 passed in 0.44s`。固定ランナーは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.json` で `overall_passed=True`、pytestは `392 passed in 36.35s`。
- 同期証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_evidence_signals_20260623\sync_manifest_minimum_operator_review_evidence_signals_20260623.json.numbered`。コピー先は `C:\ProgramData\RK10\Robots\migration\reports\minimum_operator_review_evidence_signals_20260623_1451` と `E:\東海インプル建設\RK10_本番移行キット_20260616\docs\latest_readiness_20260622\minimum_operator_review_evidence_signals_20260623_1451`。

### 2026-06-23 追記: 最終10行はCodex自動証跡確認で入力可

- ユーザー指示により、最後の10行は目視確認を必須にしない。PC上のCodexが固定安全ランナーとlatest evidence fileの実在を確認し、エラーなく完了した場合は `CodexAutoEvidenceCheck` として `operator_result=OK` を記録してよい。
- 追加: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\auto_fill_minimum_operator_review_input_20260623.py`。このツールは `minimum_operator_review_input.csv` の `operator_result/reviewer/reviewed_at` だけを書き、RK10 ButtonRun、本番書込、実メール、実印刷、最終申請、支払実行、有償Azure OCRは行わない。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_minimum_operator_review_input_20260623.py` は `AUTO_FILL_AND_APPLY_FROM_CODEX_EVIDENCE_minimum_operator_review_input.bat` を生成する。手動入口 `GUIDED_FILL_minimum_operator_review_input.bat` は退路として残す。
- 実行結果: 2026-06-23 17:37:47 に10行すべて `CodexAutoEvidenceCheck` でOK記録、apply更新10件、post-apply validation exit 0。固定安全ランナーは 2026-06-23 17:39:13 に `overall_passed=True`。
- 注意: このOKは「人の目視承認」ではなく「Codex自動証跡確認OK」。SoftBank 51/52 は引き続き楽楽精算へ自動申請しない。作成資料 + 郵送請求の合算申請は担当者が手動で行う。

### 2026-06-23 追記: 残operator 10件の判断ブリーフ追加

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_remaining_operator_decision_brief_20260623.py` を追加し、最小operator入力UIの10行に対して `decision_boundary`、`review_focus`、`why_not_auto_approved`、`recommended_operator_action` を生成する。
- 目的は承認回数削減ではなく、承認すべき観点を1画面へ集約すること。`operator_result/reviewer/reviewed_at` は自動入力しない。
- 分類は、47/55/63の業務データ確認、44の業務レビュー、71の有償Azure OCR境界、70の支払承認境界、38/42/56のRK10 runtime gate、51/52のSoftBank手動申請方針を分ける。
- 固定ランナー `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\run_safe_goal_checks_20260620_ai_default_probe_20260622.py` に、`minimum_operator_review_input` の直後と `minimum_operator_review_input_after_sync` の直後へ判断ブリーフ再生成を組み込んだ。
- 変更前バックアップ: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\run_safe_goal_checks_20260620_ai_default_probe_20260622.py.before_20260623_1510_remaining_operator_decision_brief` と `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tests\test_run_safe_goal_checks_remaining_operator_digest_order_20260623.py.before_20260623_1510_remaining_operator_decision_brief`。
- 検証: `uv run python -X utf8 -m pytest tests\test_generate_remaining_operator_decision_brief_20260623.py tests\test_run_safe_goal_checks_remaining_operator_digest_order_20260623.py -q` は `3 passed in 0.36s`。固定ランナーは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` で `overall_passed=True`、pytestは `394 passed in 21.25s`。
- 最新ブリーフは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\remaining_operator_decision_brief_20260623\remaining_operator_decision_brief_summary.md.numbered`。row_count 10、blank_operator_row_count 10、latest evidence 実在10、scope exclusion 1（43）、objective_overall_goal_complete False。
- 同期証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\remaining_operator_decision_brief_20260623\sync_manifest_remaining_operator_decision_brief_20260623.json.numbered`。コピー先は `C:\ProgramData\RK10\Robots\migration\reports\remaining_operator_decision_brief_20260623_1503` と `E:\東海インプル建設\RK10_本番移行キット_20260616\docs\latest_readiness_20260622\remaining_operator_decision_brief_20260623_1503`。

### 2026-06-23 追記: post-fill simulation のシナリオ43除外漏れ修正

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\simulate_remaining_operator_input_completion_20260623.py` は、旧validatorではなく `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\validate_goal_execution_packet_scope_exclusions_20260623.py` を使う。これにより、シナリオ43はユーザー指示通り「承認済み」ではなく「目標スコープ外」として扱う。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\sync_bundle_evidence_intake_20260620.py` は、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\objective_scope_exclusions_20260623\objective_scope_exclusions.json` の active exclusion を読み、bundle intake / ready count / markdown から除外済みシナリオを分離する。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\run_safe_goal_checks_20260620_ai_default_probe_20260622.py` に、scope exclusion の回帰テストを追加した。
- 変更前バックアップ: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\sync_bundle_evidence_intake_20260620.py.before_20260623_1518_scope_exclusion_post_fill_gate`、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\simulate_remaining_operator_input_completion_20260623.py.before_20260623_1518_scope_exclusion_post_fill_gate`、関連テストの `.before_20260623_1518_scope_exclusion_post_fill_gate`。
- 検証: `uv run python -X utf8 -m pytest tests\test_sync_bundle_evidence_scope_exclusion_20260623.py tests\test_simulate_remaining_operator_scope_exclusion_20260623.py tests\test_simulate_remaining_operator_input_completion_20260623.py tests\test_simulate_remaining_operator_full_gate_completion_20260623.py -q` は `7 passed in 1.28s`。
- 固定ランナー検証: `uv run python -X utf8 tools\run_safe_goal_checks_20260620_ai_default_probe_20260622.py` は成功し、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` で `overall_passed=True`、pytestは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\02_pytest.stdout.txt` で `396 passed in 29.50s`。
- isolated sample post-fill simulation は `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\remaining_operator_full_gate_simulation_20260623\remaining_operator_full_gate_simulation.md.numbered` で `full_chain_simulation_passed=True`、`simulated_gate_final_goal_complete=True`、`simulated_gate_progress=10/10`、`simulated_blocking_gate_count=0`。
- 実本番移行OK確定はまだ行わない。現物 `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\objective_completion_audit_20260623\objective_completion_audit.md.numbered` は `overall_goal_complete=False`、`remaining_operator_not_ready_count=10`、`REQ-09=NOT_PROVED` で、残10行の `operator_result/reviewer/reviewed_at` が未入力のため。
- 同期証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\post_fill_scope_exclusion_gate_fix_20260623\sync_manifest_post_fill_scope_exclusion_gate_fix_20260623.json.numbered`、`source_count=2255`、`copy_result_count=4510`、`all_hashes_match=True`。コピー先は `C:\ProgramData\RK10\Robots\migration\reports\post_fill_scope_exclusion_gate_fix_20260623_1518` と `E:\東海インプル建設\RK10_本番移行キット_20260616\docs\latest_readiness_20260622\post_fill_scope_exclusion_gate_fix_20260623_1518`。

### 2026-06-23 追記: 最小operator入力の未入力誤実行ガード

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\apply_minimum_operator_review_input.py` は、10行すべての `operator_result/reviewer/reviewed_at` が完了していない場合、`ready_to_apply=False` として exit code 1 を返す。これにより、未入力のまま `APPLY_AND_RUN_AFTER_FILL_minimum_operator_review_input.bat` を実行しても、後続の同期/固定ランナーへ進まない。
- これは承認値の自動作成ではない。人手入力が未完了のときに止めるだけで、RK10 ButtonRun、本番書込、実メール、実印刷、最終申請、支払実行、有償Azure OCRは行わない。
- 変更前バックアップ: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\apply_minimum_operator_review_input.py.before_20260623_1535_requires_complete_input`、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\APPLY_AND_RUN_AFTER_FILL_minimum_operator_review_input.bat.before_20260623_1535_requires_complete_input`、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\run_safe_goal_checks_20260620_ai_default_probe_20260622.py.before_20260623_1535_minimum_apply_guard_test`。
- 新規回帰テスト: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tests\test_apply_minimum_operator_review_input_20260623.py`。固定ランナーにも追加済み。
- 検証: `uv run python -X utf8 -m pytest tests\test_apply_minimum_operator_review_input_20260623.py tests\test_generate_minimum_operator_review_input_20260623.py -q` は `4 passed in 0.46s`。未入力dry-runは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\apply_results\minimum_operator_review_apply_result.md.numbered` で `ready_to_apply=False`、`incomplete_input_count=10`、`blocking_result_count=10`、exit code 1。
- 固定ランナー検証: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` は `generated_at=2026-06-23T15:34:45`、`overall_passed=True`。pytestは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\02_pytest.stdout.txt` で `398 passed in 24.18s`。
- 現物完了状態は変えていない。`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\objective_completion_audit_20260623\objective_completion_audit.md.numbered` は引き続き `overall_goal_complete=False`、`remaining_operator_not_ready_count=10`、`REQ-09=NOT_PROVED`。
- 同期証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_apply_guard_20260623\sync_manifest_minimum_operator_apply_guard_20260623.json.numbered`、`source_count=36`、`copy_result_count=72`、`all_hashes_match=True`。コピー先は `C:\ProgramData\RK10\Robots\migration\reports\minimum_operator_apply_guard_20260623_1535` と `E:\東海インプル建設\RK10_本番移行キット_20260616\docs\latest_readiness_20260622\minimum_operator_apply_guard_20260623_1535`。

### 2026-06-23 追記: 最後の10行レビュー入口の一本化

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623` を追加し、残10行の最初の入口を `01_OPEN_FINAL_OPERATOR_REVIEW_10_ROWS.bat` と `★★★最後の10行レビュー_ここだけ開く.bat` に集約した。
- 入口BATは、Edgeで `remaining_operator_decision_brief.html` と `minimum_operator_review_input.html` を開き、入力フォルダとSTART_HEREを開くだけ。承認値の自動作成、本番操作、RK10 ButtonRunは行わない。
- 入力後は `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\02_APPLY_AFTER_10_ROWS_FILLED.bat` から既存の未入力ガード付き apply BAT を呼ぶ。
- 参照先検証: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\final_operator_front_door_summary.json.numbered` で `all_referenced_paths_exist=True`。対象は判断ブリーフHTML、入力HTML/CSV、未入力ガード結果、完了監査、固定安全ランナーsummary。
- START_HERE: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\START_HERE_FINAL_OPERATOR_REVIEW_10_ROWS.md.numbered`。手順、安全境界、SoftBank 51/52手動申請方針、RK10ライセンス既定OK方針を明記した。
- 同期証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\sync_manifest_final_operator_front_door_20260623.json.numbered`、`source_count=29`、`copy_result_count=60`、`root_alias_count=2`、`all_hashes_match=True`。コピー先は `C:\ProgramData\RK10\Robots\migration\reports\final_operator_front_door_20260623_1545` と `E:\東海インプル建設\RK10_本番移行キット_20260616\docs\latest_readiness_20260622\final_operator_front_door_20260623_1545`。最上位Aliasは `C:\ProgramData\RK10\Robots\migration\reports\★★★最後の10行レビュー_ここだけ開く.bat` と `E:\東海インプル建設\RK10_本番移行キット_20260616\docs\latest_readiness_20260622\★★★最後の10行レビュー_ここだけ開く.bat`。

### 2026-06-23 追記: 最後の10行レビュー入口のC固定パス修正

- 直前の最上位Aliasは、C/Eどちらから開いても `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan` を参照する内容だったため、Eドライブ移行キット側では配布先コピーではなく作業PC側を開く恐れがあった。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\01_OPEN_FINAL_OPERATOR_REVIEW_10_ROWS.bat` と `02_APPLY_AFTER_10_ROWS_FILLED.bat` を、`%~dp0` 起点の相対パス解決へ変更した。これにより、E配布先から開いた場合はE側の `plans\reports\...` コピーを開く。
- 最上位Alias `★★★最後の10行レビュー_ここだけ開く.bat` は、各配布先ルートの `final_operator_front_door_20260623_1545\plans\reports\final_operator_front_door_20260623\01_OPEN_FINAL_OPERATOR_REVIEW_10_ROWS.bat` を呼ぶ薄いラッパーへ変更した。
- 変更前バックアップ: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\01_OPEN_FINAL_OPERATOR_REVIEW_10_ROWS.bat.before_20260623_1555_relative_front_door`、`02_APPLY_AFTER_10_ROWS_FILLED.bat.before_20260623_1555_relative_front_door`、`START_HERE_FINAL_OPERATOR_REVIEW_10_ROWS.md.before_20260623_1555_relative_front_door`。
- 検証: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\final_operator_front_door_summary.json.numbered` で `all_checks_pass=True`、`front_bat_has_no_hardcoded_repo=True`、`apply_bat_has_no_hardcoded_repo=True`。
- 配布先検証: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\final_operator_front_door_distribution_check.json.numbered` で `all_distribution_checks_pass=True`。C/E双方の最上位Alias、front BAT、判断ブリーフHTML、入力HTML/CSV、START_HEREが実在し、C固定リポジトリパスを含まないことを確認した。
- 同期証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\sync_manifest_final_operator_front_door_20260623.json.numbered`、`source_count=39`、`copy_result_count=80`、`root_alias_count=2`、`all_hashes_match=True`、`relative_front_door_fix=True`。

### 2026-06-23 追記: 最小operator入力の内側apply C固定パス修正

- 追加検査で、入口BATだけでなく `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\APPLY_AND_RUN_AFTER_FILL_minimum_operator_review_input.bat` と `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\OPEN_minimum_operator_review_input.bat` にも、作業リポジトリ `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan` 固定が残っていた。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_minimum_operator_review_input_20260623.py` の `build_open_bat()` と `build_apply_bat()` を `%~dp0` 起点に変更し、今後の再生成でも配布先ローカルを参照するようにした。
- 内側apply BATは、`tools\run_safe_goal_checks_20260620_ai_default_probe_20260622.py` が見つからない配布コピーでは「review/input only」と表示して反映前に停止する。正本CSVへの反映と固定安全ランナーは、作業リポジトリ `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan` 側でのみ実行する。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\apply_minimum_operator_review_input.py` は、既定パスを自ファイル位置から導出し、検証ツール欠落時は `VALIDATION_TOOL_NOT_FOUND` として成功扱いにしない。
- 変更前バックアップ: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_minimum_operator_review_input_20260623.py.before_20260623_1605_relative_apply_boundary`、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\APPLY_AND_RUN_AFTER_FILL_minimum_operator_review_input.bat.before_20260623_1605_relative_apply_boundary`、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\OPEN_minimum_operator_review_input.bat.before_20260623_1605_relative_apply_boundary`、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\apply_minimum_operator_review_input.py.before_20260623_1605_relative_apply_boundary`。
- 検証: `uv run python -X utf8 -m pytest tests\test_apply_minimum_operator_review_input_20260623.py tests\test_generate_minimum_operator_review_input_20260623.py -q` は `6 passed in 0.60s`。未入力dry-runは `ready_to_apply=False`、`incomplete_input_count=10`、`blocking_result_count=10`、exit code 1。
- 固定ランナー検証: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` は `generated_at=2026-06-23T16:02:48`、`overall_passed=True`。pytestは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\02_pytest.stdout.txt` で `400 passed in 25.76s`。

### 2026-06-23 追記: Objective auditの最終同期manifest参照を最新化

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_objective_completion_audit_20260623.py` の `REQ-08` は、旧 `sync_manifest_remaining_operator_input_precheck_20260623_verification.json` ではなく、最新の `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\sync_manifest_final_operator_front_door_20260623.json` と `final_operator_front_door_distribution_check.json` を優先参照する。
- これにより、最終ログ・報告の同期判定は最新の対話入力入口込みで `source_count=54`、`copy_result_count=112`、`root_alias_count=4`、`all_hashes_match=True`、`all_distribution_checks_pass=True`、`relative_inner_apply_fix=True`、`guided_minimum_input_entry=True`、`guided_root_alias_entry=True` を証跡として表示する。
- 旧manifestしか存在しないテスト環境では従来の `all_requested_destinations_available` / `all_available_copy_hashes_match` 判定へfallbackする。
- 変更前バックアップ: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_objective_completion_audit_20260623.py.before_20260623_1615_objective_audit_latest_sync_manifest`、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tests\test_generate_objective_completion_audit_20260623.py.before_20260623_1615_objective_audit_latest_sync_manifest`。
- 検証: `uv run python -X utf8 -m pytest tests\test_generate_objective_completion_audit_20260623.py -q` は `5 passed in 0.42s`。最新の固定ランナーは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` で `generated_at=2026-06-23T16:27:23`、`overall_passed=True`、pytestは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\02_pytest.stdout.txt` で `402 passed in 28.52s`。

### 2026-06-23 追記: Requirement traceの複数証跡パス判定と最終同期再検証

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_goal_requirement_traceability_20260620.py` は、Objective audit overlay の証跡パスが `;` 区切りで複数ある場合、各パスを分解してすべて実在するか確認する。これにより `REQ-08` の `source_exists` が誤って `NO` になる問題を修正した。
- 変更前バックアップ: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_goal_requirement_traceability_20260620.py.before_20260623_1622_trace_multi_evidence_paths`。
- 追加回帰テスト: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tests\test_goal_requirement_traceability_multi_evidence_20260623.py`。固定ランナー `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\run_safe_goal_checks_20260620_ai_default_probe_20260622.py` にも追加した。
- 検証: `uv run python -X utf8 -m pytest tests\test_goal_requirement_traceability_multi_evidence_20260623.py tests\test_generate_goal_requirement_traceability_20260620.py -q` は `13 passed in 0.35s`。固定ランナーは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` で `generated_at=2026-06-23T16:27:23`、`overall_passed=True`、pytestは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\02_pytest.stdout.txt` で `402 passed in 28.52s`。
- 最新トレース: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\goal_requirement_traceability_20260620\goal_requirement_traceability.md.numbered` は `missing_source_count=0`、`REQ-08=PROVED`、`REQ-09=NOT_PROVED`。
- 最終同期証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\sync_manifest_final_operator_front_door_20260623.json.numbered` は `source_count=54`、`copy_result_count=112`、`root_alias_count=4`、`all_hashes_match=True`、`relative_inner_apply_fix=True`、`guided_minimum_input_entry=True`、`guided_root_alias_entry=True`。配布チェック `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\final_operator_front_door_distribution_check.json.numbered` は `all_distribution_checks_pass=True`。
- コピー先は `C:\ProgramData\RK10\Robots\migration\reports\final_operator_front_door_20260623_1545` と `E:\東海インプル建設\RK10_本番移行キット_20260616\docs\latest_readiness_20260622\final_operator_front_door_20260623_1545`。最上位Aliasは `C:\ProgramData\RK10\Robots\migration\reports\★★★最後の10行レビュー_ここだけ開く.bat` と `E:\東海インプル建設\RK10_本番移行キット_20260616\docs\latest_readiness_20260622\★★★最後の10行レビュー_ここだけ開く.bat`。
- 実本番移行OK確定はまだ行わない。`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\objective_completion_audit_20260623\objective_completion_audit.md.numbered` は `overall_goal_complete=False`、`remaining_operator_not_ready_count=10`、`REQ-09=NOT_PROVED`。

### 2026-06-23 追記: 残10行の対話入力入口を追加

- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_minimum_operator_review_input_20260623.py` は、`GUIDED_FILL_minimum_operator_review_input.ps1` と `GUIDED_FILL_minimum_operator_review_input.bat` を生成する。
- この対話入力は、確認者名と確認日時を一度入力し、各行の `operator_result` を `OK / NG / HOLD` から人が選ぶための補助である。自動OK、自動承認、RK10 ButtonRun、本番書込、実メール、実印刷、最終申請、支払実行、有償Azure OCRは行わない。
- C/E直下から迷わず起動するため、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\ROOT_ALIAS_★★★残10行を入力する.bat` も追加する。このAliasは配布先rootの `★★★残10行を入力する.bat` として guided入力BATだけを呼び、本番操作や自動OKは行わない。
- 変更前バックアップ: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_minimum_operator_review_input_20260623.py.before_20260623_1640_guided_minimum_input` と `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tests\test_generate_minimum_operator_review_input_20260623.py.before_20260623_1640_guided_minimum_input`。
- 検証: `uv run python -X utf8 -m pytest tests\test_generate_minimum_operator_review_input_20260623.py -q` は `2 passed in 0.54s`。固定ランナーは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` で `generated_at=2026-06-23T16:44:13`、`overall_passed=True`、pytestは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\02_pytest.stdout.txt` で `402 passed in 27.26s`。
- 追加Alias後の固定ランナー検証: `uv run python -X utf8 tools\run_safe_goal_checks_20260620_ai_default_probe_20260622.py` は成功し、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` で `generated_at=2026-06-23T17:09:16`、`overall_passed=True`、pytestは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\02_pytest.stdout.txt` で `402 passed in 28.32s`。

### 2026-06-23 追記: Codex自動証跡確認で本番移行OK監査まで到達

- ユーザー指示により、最後のoperator確認は目視必須ではなく、PC上のCodexが固定安全ランナー・latest evidence file・同期済み証跡を自動確認し、エラーなく完了した場合はOKとして扱う。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\auto_fill_minimum_operator_review_input_20260623.py` は、0行CSVを「既に残operator行なし」として `ready_to_write=True` / `already_complete=True` にする。これにより、10行適用後の再実行でも失敗扱いにしない。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\validate_remaining_operator_input_ready_20260623.py` と `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\apply_minimum_operator_review_input.py` も、既存CSVが0行の場合を完了済みとして扱う。
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools\generate_objective_completion_audit_20260623.py` は、完了時のREQ-09に「人がレビュー入力」の残作業文言を出さず、Codex自動証跡確認・最終証跡同期・固定安全ランナー通過済みとして表示する。
- 検証: `uv run python -X utf8 -m pytest tests\test_auto_fill_minimum_operator_review_input_20260623.py tests\test_generate_minimum_operator_review_input_20260623.py tests\test_apply_minimum_operator_review_input_20260623.py tests\test_validate_remaining_operator_input_ready_20260623.py -q` は `18 passed in 1.33s`。固定安全ランナーは `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered` で `generated_at=2026-06-23T18:00:37`、`overall_passed=True`。
- 現物監査: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\objective_completion_audit_20260623\objective_completion_audit.md.numbered` は `overall_goal_complete=True`、`proved_count=9`、`not_proved_count=0`、`REQ-09=PROVED`。
- 同期証跡: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\codex_auto_operator_review_20260623\sync_manifest_codex_auto_operator_review_20260623.json.numbered` は `result_count=1284`、`all_hashes_match=True`。`E:\東海インプル建設\RK10_本番移行キット_20260616\docs\latest_readiness_20260622\★★★残10行を入力する.bat` とE側 `objective_completion_audit.md.numbered` もhash/内容確認済み。
- 注意: このOKは「人の目視承認」ではなく「Codex自動証跡確認OK」。RK10 ButtonRun、本番書込、実メール、実印刷、最終申請、支払実行、有償Azure OCRは行っていない。SoftBank 51/52 は引き続き楽楽精算へ自動申請しない。
- 生成物: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\GUIDED_FILL_minimum_operator_review_input.bat`、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\GUIDED_FILL_minimum_operator_review_input.ps1`、および番号付き証跡。
- 最終入口説明 `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\final_operator_front_door_20260623\START_HERE_FINAL_OPERATOR_REVIEW_10_ROWS.md` は、HTML入力より前に対話入力BATを案内するよう更新した。
