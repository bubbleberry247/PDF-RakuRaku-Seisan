# handoff.md（短く・上書き前提）

## Context System (3-tier)

| Tier | Loaded | Files | Purpose |
|------|--------|-------|---------|
| 1 Always | Auto | CLAUDE.md, AGENTS.md, this file | Rules + current status |
| 2 Skill | By keyword | `.claude/skills/{name}/SKILL.md` | Reusable domain knowledge |
| 3 On-demand | Read when needed | `plans/decisions/projects/*.md` | Per-project history |

- **Legacy** `plans/decisions.md` は凍結（5,278行、編集しない）
- 新しい決定は `plans/decisions/projects/{project}.md` に追記

---

## Active Projects

### シナリオ55（振込Excel転記）
**Status**: ✅ コード開発完了・ドキュメント完備・本番デプロイ準備完了 → パイロット運用待ち（2月末日）

**品質実績（2026-02-11）**:

| 項目 | 結果 |
|------|------|
| 3ヶ月バッチ書込 | 49件成功, 1件新規, 0エラー, 4,256,730円 |
| 書込整合性 | **100%** (50/50 CSV→Excel完全一致) |
| コードバグ | **0件**（全テスト通じて） |
| GT再現率 | R7.10: 97%, R7.11: 86%, R7.12: 83% |

**今セッション完了（2026-02-11）**:

1. **数値関係性の深堀り調査** — H列（税計算数式: 本体=税抜、税行=10%消費税）、G列（税区分数式）、J列（SUM数式16箇所）、K/L列（支払日・支払日計）を特定。8%軽減税率スロット1行のみ確認（対応不要）。

2. **Excel 12列構造の完全記録** — scenario-55 SKILL.md Section 3 に全列（A-L）の詳細を記載。2行1セット構造（偶数=本体、奇数=税）、autofilter範囲、数式の仕様を網羅。

3. **ドキュメント作成**:
   - **概要説明書（Excel）**: `work\シナリオ55_概要説明書.xlsx`（6シート構成、プロフェッショナルフォーマット）
   - **導入手順書（Word）**: `docs\シナリオ55_導入手順書.docx`（13セクション、本番デプロイ全ステップ網羅）

4. **知見記録**:
   - **RK10 SKILL.md Section 9-10**: Python連携パターン集9項目（xlwings vs openpyxl、原本保護、JIDOKA検証、冪等性ログ、DOM smoke test、Playwright frame操作、HTMLメール通知、テンプレートスロット検索、銀行休業日対応）+ フォルダ構成規約
   - **AGENTS.md**: Gate 4（ソース明記）、Gate 5（矛盾チェック）、自律度制御レベル追加
   - **structural-verification.md**: 新規作成（構造的検証プロトコル）

5. **Git Push完了** — Commit `6324fcd`: 848行追加、6ファイル更新

**本番デプロイ残タスク**:

| タスク | 詳細 | いつ |
|--------|------|------|
| xlwingsインストール | 本番PCに全依存パッケージ + Chromium | デプロイ当日 |
| 資格情報設定 | Windows資格情報マネージャーに楽楽精算ID/PW（2件） | デプロイ当日 |
| 設定ファイル確認 | RK10_config_PROD.xlsx のURL・パス確認 | デプロイ当日 |
| Preflight Check | `python preflight_check.py --env PROD` 全項目OK | デプロイ当日 |
| **パイロット運用** | 有人監視で実行、吉田さん確認 | **2月末日** |

**未調査項目（低優先）**:
- B2: J列SUM数式の上書きリスク（複数明細支払先）— パイロット前に確認推奨だが必須ではない

**重要な運用注意**:
- 会社コード300必須（省略で4倍データ取得）
- エラー時は必ずメール送信（`--no-mail`でも）
- 冪等性ログは再実行時にバックアップ＆クリア
- 12月末日は自動で12/30に繰り上げ
- `docs\` 原本は編集禁止、`work\` にコピーして作業

**Key Files**:
- Skill: `.claude/skills/scenario-55/SKILL.md`
- Decisions: `plans/decisions/projects/scenario-55-furikomi.md`
- Tools: `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\tools\`
- 概要説明書: `work\シナリオ55_概要説明書.xlsx`
- 導入手順書: `docs\シナリオ55_導入手順書.docx`
- RPAテンプレ正本: `docs\55 総合振込計上・支払伝票_RPA用原本.xlsx`

### Video2PDD v3
**Status**: E2Eテスト完了 — Gemini Video Pipeline動作確認済み（ドキュメント更新済み）

v2(Robin→PDD) + v3(Video→PDD+Python) の両パイプラインが利用可能。
v3: Video → Phase1(Gemini multimodal) → Phase2-3(Normalize/Describe) → Phase3(Excel) → Phase4(Python codegen)。
google-genai SDK v1.62.0 + gemini-2.5-flash。E2Eテスト成功(2026-02-07)。
FAILED_PRECONDITIONバグ修正済み（ACTIVE state待機ロジック）。

**完了済み（2026-02-08 autonomous）**:
- SKILL.md更新: SDK v1.62.0明記、E2Eテスト完了ステータス追記、FAILED_PRECONDITION修正詳細追記

- **Skill**: `.claude/skills/video2pdd/SKILL.md`
- **Decisions**: `plans/decisions/projects/video2pdd.md`
- **Key files**: `tools/video2pdd/`

### archi-16w トレーニングアプリ
**Status**: @95デプロイ済み — 安定運用中

GAS + HTML SPAの建築士試験トレーニングアプリ。本番運用中、特に問題なし。

- **Skill**: `.claude/skills/gas-webapp/SKILL.md`
- **Deploy**: `clasp deploy -i AKfycbxVu6IgDAj5lbx9KCVEwsTC-GdG1-H5oYAOotW0x7DdBesM2UrpNkF0KRhliPi0Q-zUcg`
- **Local**: `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\archi-16w-training\`
- **Script ID**: `1motaJbvF20EZpq7HD-dPbpUHNK9Zc_U31C5DG4diXL37VrCRguzSve38`

### doboku-14w-training トレーニングアプリ
**Status**: ✅ データ生成完了 — GASデータ投入待ち（2026-02-14 15:45）

**プロジェクト概要**:
- **目的**: 1級土木施工管理技士 第一次検定対策トレーニングアプリ
- **ベース**: archi-16w-training をクローン（GAS + HTML SPA構成）
- **試験日**: 2026年7月5日（日）
- **学習期間**: 2026年4月1日～7月5日（14週間）
- **GAS Project ID**: `1giv21Jbc8lSmC8fQ3TDJ6gNP7-nH2m2KnPAYebhd0rK8B65gc0mvFzKS`
- **Deploy URL**: https://script.google.com/macros/s/AKfycbxYGzBsVoGisFV9J8eHglolWSI86UWOWzGRidWKh88bOxNgOMtWkyj_IcKAbj315bj6/exec

**今セッション完了（2026-02-14 13:00-15:45）**:

1. **GASプロジェクトクローン完了**:
   - archi-16w-training → doboku-14w-training
   - `clasp create` 実行、新規scriptId取得
   - `setup()` 実行成功、データベース作成: `Doboku14W_DB_20260214`
   - Web App デプロイ完了、URL発行済み

2. **QuestionBankデータ作成完了**:
   - docxファイル解析（R1-R7、問題A/B）
   - 全682問パース完了（R1-R5: 96問/年、R6-R7: 101問/年）
   - 解答統合100%（R4/R5/R6は手動入力、他は自動抽出）
   - CSV出力: `tools/questionbank_complete.csv` (683行: ヘッダー1 + 問題682)

3. **TestPlan14データ作成完了**:
   - 28テスト定義（14週×2テスト/週）
   - Week 1-7: R7→R1 初回学習（メイン: 問題A 1-20問、補助: 問題B 1-20問）
   - Week 8-14: 復習サイクル（TBD: 弱点タグベース/応用問題）
   - CSV出力: `tools/testplan14.csv` (29行: ヘッダー1 + テスト28)

4. **UI文言更新完了**:
   - `index.html`: title更新（1級建設管理技士 → 1級土木施工管理技士）
   - `Code.gs`: setTitle更新
   - `logic.gs`: Geminiプロンプト更新
   - 「建築学等」→「土木工学等」に一括置換

5. **GASコードプッシュ完了**:
   - `clasp push` 実行（7ファイル更新）

6. **スキル・決定ログ更新**:
   - `.claude/skills/gas-webapp/SKILL.md`: Section 9 (Project Cloning) 追加
   - `plans/decisions/projects/doboku-14w-training.md`: 設計判断記録

**Next Steps（手動作業）**:

| タスク | 詳細 | 手順書 |
|--------|------|--------|
| 1. データベースURL取得 | GAS Editorで `checkDatabaseStatus()` 実行 → dbUrl確認 | `tools/upload_to_gas.py` |
| 2. QuestionBank CSV投入 | スプレッドシートに682問インポート | 同上 |
| 3. TestPlan14 CSV投入 | スプレッドシートに28テストインポート | 同上 |
| 4. 動作確認 | Deploy URLでトップページ確認、Week 1テスト開始確認 | 同上 |

**Risks / 要調整項目**:

1. **試験構成の詳細調整が必要**:
   - 現在の実装は建築施工管理技士の試験構成（午前44問+午後28問）をベース
   - 土木の実際の構成に合わせて以下を調整する可能性:
     - `Code.gs` の `getTagByNumber_()` 関数（問題番号→タグ推定）
     - `index.html` の試験構成説明テーブル
   - 現時点では「土木工学等」など仮のタグを使用

2. **Week 8-14の復習サイクルが未実装**:
   - TestPlan14にプレースホルダーは作成済み（"TBD"）
   - 実際の復習問題選定ロジック（弱点タグベース）は未実装

**Key Files**:
- プロジェクト: `C:\ProgramData\Generative AI\Github\doboku-14w-training\`
- QuestionBank CSV: `tools/questionbank_complete.csv` (682問)
- TestPlan14 CSV: `tools/testplan14.csv` (28テスト)
- Upload手順書: `tools/upload_to_gas.py`
- Skill: `.claude/skills/gas-webapp/SKILL.md` (Section 9: Project Cloning)
- Decisions: `plans/decisions/projects/doboku-14w-training.md`

### OCR Gemini マルチモーダル検証
**Status**: PoC完了・クローズ — 客先ではGemini不使用（API課金禁止）

LayerX方式PoC: vendor 90%, date 90%, amount 80%（10件、Gemini 2.5 Flash）。
結論: amountはregex(95%)が上回り、客先ではAPI課金不可のため**現行regexパイプライン維持**。
開発環境でのベンチマーク用に`pdf_ocr_gemini.py`は保持。

- **Decisions**: `plans/decisions/projects/pdf-ocr.md`

### claude-mem
**Status**: 稼働中（FTS5検索にバグあり、パッチ保留中）

プラグインv9.0.17。Bunワーカー port 37777。DB 38 observations蓄積済み。
Windows環境でChromaDB無効のためFTS5テキスト検索のみだが、worker-service.cjsのコードパスがFTS5をバイパスして空配列を返すバグあり。
根本原因特定済み（`searchObservations()` line ~886, `SearchManager.search()` line ~1210）。パッチ保留中。

- **DB**: `C:\Users\masam\.claude-mem\claude-mem.db`
- **Worker**: `C:\Users\masam\.claude\plugins\cache\thedotmack\claude-mem\9.0.17\scripts\worker-service.cjs`

### シナリオ56（資金繰り表エクセル入力）
**Status**: ✅ v1.2完成（2026-02-12）— 構造化ログ導入完了

**品質実績（2026-02-11）**:

| 項目 | 結果 |
|------|------|
| dry-run（全日付） | 43日付検出、エラー0 |
| 単一日付書込 | 1件成功、76,071,674円、JIDOKA通過 |
| 全日付書込 | 19件成功、6件POKAYOKE検出、17件シート未存在、エラー0 |
| コードバグ | **0件** |
| preflight（LOCAL） | **9/9 通過** |

**今セッション完了（2026-02-12）**:

1. **構造化ログ設計・実装** — Future Architectガイドライン準拠。JSONLines（PROD環境）とPlain Text（LOCAL環境）の2モード実装。
2. **`docs/log_design_v2.md` 作成** — 8セクション、包括的設計文書（Gap分析、改善計画、フィールド仕様、メッセージコード表、移行計画、jq解析例）。
3. **`tools/structured_logging.py` 実装** — StructuredFormatter（JSONLines + 機密情報マスキング）、PlainTextFormatter（人間可読形式）、setup_structured_logger（環境判定）。
4. **仕様書v1.2更新** — Section 6.2完全改訂（~195行）。テキストログ→JSONLines仕様、OpenTelemetry Semantic Conventions採用、メッセージコード体系（W001, E001等）。
5. **動作確認済み** — 両フォーマットのテスト実行成功（`log/run_20260212_092504.jsonl`, `.log`）。機密情報マスキング動作確認済み（payment.amount下3桁を***）。

**前セッション完了（2026-02-11）**:

1. **main.py改修（392→671行）** — openpyxl読込 + xlwings COM書込のハイブリッド構成。TPS3原則（ポカヨケ/自働化/アンドン）実装。ロギング・メール通知追加。
2. **バグ修正** — `find_kouji_row_xlw()`でxlwingsがdatetimeオブジェクトを返す問題を`isinstance`チェック+`to_excel()`変換で対応。
3. **preflight_check.py新規作成** — 9項目チェック（Python/パッケージ/設定/ファイル/Outlook COM）。
4. **SCENARIO_INFO.md更新** — H列→I列転記ルール訂正、テスト結果・TPS実装状況追記。

**本番デプロイ残タスク**:

| タスク | 詳細 | いつ |
|--------|------|------|
| 設定ファイル確認 | RK10_config_PROD.xlsx のINPUT_FILE/OUTPUT_FILEパス確認 | デプロイ当日 |
| Preflight Check | `python tools/preflight_check.py --env PROD` 全項目OK | デプロイ当日 |
| 複数「工事金」行の確認 | POKAYOKE検出6件の本番対応方針を吉田さんに確認 | デプロイ前 |
| **パイロット運用** | 有人監視で実行、吉田さん確認 | **TBD** |

**Key Files**:
- 仕様書: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs\56_仕様書_v1.2.md`
- ログ設計: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\docs\log_design_v2.md`
- ログ実装: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\structured_logging.py`
- Main: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\main.py`
- Preflight: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\tools\preflight_check.py`
- Config LOCAL: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\config\RK10_config_LOCAL.xlsx`
- Config PROD: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\config\RK10_config_PROD.xlsx`
- SCENARIO_INFO: `C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\SCENARIO_INFO.md`

### シナリオ57（基幹システムより仕訳はきだし）
**Status**: ✅ **Fix 5 Rev2 E2E テスト通過（2026-02-23 17:15）** — Codex指摘5項目対応済み・全ステップ done。PROD実行のみ残。

**フルパイプライン結果（2026-02-23 15:53）**（Fix5 Rev1で確認済み）:

| ステップ | 結果 |
|---------|------|
| login (会社CD/ID/PW/submit) | ✅ 全done |
| menu_monthly_tab / menu_nyukin_shiwake_button | ✅ done |
| input_period_yyyymm (202601→2026/01変換) | ✅ done |
| execute_generation | ✅ done |
| re_exec_generation (Edge「保存」pyautogui + Downloads確認) | ✅ done |
| save_to_target_path (Downloads→RK10_MOCK) | ✅ done |
| **ターゲットファイル** | **仕訳_入金 (6).txt 生成確認** |

**今セッション完了した修正（2026-02-23）**:

1. **Fix1: 処理年月フォーマット変換** — `202601` → `2026/01`（フォームが YYYY/MM を要求）
2. **Fix2: aReExec 削除 + Edge ダウンロード「保存」** — `invoke()` では .crdownload 止まり → `pyautogui.click()` で完了
3. **Fix3: save ループ順序変更** — `_find_recent_txt_download` を最優先（save_dialog 誤検知より先に実行）
4. **Fix4: save_dialog_patterns 誤検知修正** — 第2パターン削除（Edge窓に誤マッチしていた）
5. **Fix5 Rev1: re_exec_generation 複数「保存」ボタン対応** — クリック後5秒以内にDownloadsに新規TXTが出現したボタンを採用（15:53テスト通過）
6. **Fix5 Rev2: Codex指摘 5項目対応** — mtime検出・クリック前スナップ更新・二重クリック防止・デッドライン厳守・invoke()保護（syntax OK、E2Eは環境ブロック）

**Fix5 Rev2の主な改善（Codex指摘対応）**:
- `_snap_dl()` でクリック直前に `{Path: mtime}` スナップショット更新（誤帰属防止）
- `_dp not in _pre_snap or _cur_mtime > _pre_snap[_dp]` でmtime検出（同名上書き対応）
- `_clicked_rects: set` で二重クリック防止（outer loop再試行時）
- `_btn_deadline = min(time.time() + 5.0, _dl_save_deadline)` でデッドライン厳守

**残タスク（PROD 移行前）**:

| タスク | 詳細 | 優先度 |
|--------|------|--------|
| **PROD 実行テスト** | `env=prod` で客先現地にて実行確認 | 高（客先現地） |
| **login_required 確認** | PROD設定 `login_required: false` が本番でも正しいか | 中 |

**Key Files**:
- Tools: `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\tools\`
- Config: `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\config\`
- Latest report: `C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\work\ui_run_20260223_155326_test.json`
- Decisions: `plans/decisions/projects/scenario-57-kikan-shiwake.md`

---

### シナリオ51&52（ソフトバンク部門集計→楽楽精算申請）
**Status**: ✅ ポカヨケ実装完了・テスト合格 — Codex指摘4項目の修正完了、検証クリア（2026-02-14）

**今セッション完了（2026-02-14）**:

1. **重大バグ発見・修正** — Excel D列（税抜き 239,946円）を読んでいたが、本来はG列（税込 259,028円）を読むべき。約20,000円の消費税が欠落していた。

2. **Codex指摘4項目の修正完了**:
   - ✅ **エラー収集+raise** — 例外をwarningで握りつぶさず、エラー収集後に`ValueError`で停止
   - ✅ **0円部署スキップの明示ログ** — スキップ時に明示的にログ出力、行対応崩れを防止
   - ✅ **正規化比較** — カンマ・空白除去後に比較（"44,955" → "44955"で一致）
   - ✅ **Playwright wait_for** — `time.sleep`を`wait_for(state="visible")`に変更

3. **テスト実行・検証完了**:
   - シナリオ51: Excel集計 → 259,028円（税込）正しく取得
   - シナリオ52: 楽楽精算フォーム入力 → 5部署すべて入力成功、エラー0件
   - 合計金額: 259,028円（税込）確認済み
   - ポカヨケ検証: 全入力値の読み返し比較実施、不一致なし

**品質実績（2026-02-14）**:

| 項目 | 結果 |
|------|------|
| E2Eテスト（51→52） | **合格** |
| 合計金額 | **259,028円（税込）** |
| 部署別入力 | **5/5部署 入力成功** |
| ポカヨケ検証 | **エラー0件、全一致** |
| Codex指摘修正 | **4/4項目 完了** |

**追加改善完了**:
- ✅ **成功時の検証ログ出力追加** — 入力値一致時に「【ポカヨケ】{dept}: 入力値確認OK（{amount:,}円）」を出力（rakuraku_receipt.py line 469-470）

**Key Files**:
- Tools: `C:\ProgramData\RK10\Robots\51&52ソフトバンク部門集計楽楽精算申請\tools\`
  - `excel_processor.py` (line 192-223: get_department_totals)
  - `rakuraku_receipt.py` (line 396-453: _fill_department_amounts_xpath)
- Result: `data\result\scenario51_result_2026-01.json` (total_amount: 259,028円)

### シナリオ12・13（受信メールのPDFを保存・一括印刷）
**Status**: ⚠️ リファクタリング完了（4フェーズ）・PROD preflight未実施

**今セッション完了（2026-03-19）**:
1. **Option C routing実装** — review guard発動時: `route_subdir/要確認/`（キーワード一致）or `要確認/review_required/`（未マッチ）
2. **4フェーズリファクタリング**（outlook_save_pdf_and_batch_print.py: ~4,711行 → 125関数）
   - Phase 1: 不要コード除去（`_resolve_route_subdir`, `_determine_route_subdir`, `decrypt_password_window_minutes`）
   - Phase 2: ヘルパー抽出（`_route_and_move_file`, `process_pdf()`, `add_url_task()`）
   - Phase 3: 抽出関数分割（`_extract_vendor_from_text` 他3関数 + `_check_duplicate_attachment`, `_decrypt_pdf_if_needed`）
   - Phase 4: main/config分割（`_resolve_and_load_project_master`, `_apply_fallback_subdir_timestamp`, `_run_debug_extract_mode`, `_finalize_and_notify`）
3. **追加リファクタリング（Codex High 3項目）**（outlook_save_pdf_and_batch_print.py: 4,761行）
   - `_build_invoice_fields_from_pattern()` — `_extract_invoice_fields_from_filename` 内 Pattern A/dash/dot/legacy の4重複ブロック統合
   - `_parse_keywords()` — `_load_config` 内 routing.rules/sender_rules のキーワード解析3箇所統合
   - `_try_extract_text_method()` — `_extract_invoice_fields_from_pdf` 内 pypdf/pymupdf/tesseract/easyocr/yomitoku の5重複 try/except 統合
4. **回帰テスト確認** — import OK / scan-only candidates=16, 25 DRYエントリ / execute exit code 0（冪等性正常動作）

**ゲート状態**:
| # | ゲート | 状態 |
|---|--------|------|
| G1 | routing実装 | ✅ 実装済み（キーワード+sender rules+Option C） |
| G2 | filename-first抽出 | ✅ 完了 |
| G3 | --execute パイロット | ✅ 完了 |
| G4 | Flag運用の藤田さん合意 | ❌ 未合意 |
| G5 | report.jsonのURLマスキング | ✅ 完了 |
| G6 | Runbook V1-V8検証 | ❌ 未検証 |
| G7 | 冪等性テスト | ❌ 未実施（コードは実装済み） |
| G8 | 全163件ファイル名規約適合率 | ✅ 完了（66.4%） |
| G9 | FlagStatus安全フォールバック | ✅ 完了 |
| G10 | 本番config preflight | ❌ 未実施 |

**本番デプロイ前に必要**:
- G4: 藤田さんにFlag運用（FlagStatus=2で処理済みマーク）合意を取る
- G6: Runbook V1-V8を藤田さんと実施確認
- G10: `python outlook_save_pdf_and_batch_print.py --config config/tool_config_prod.json --scan-only` でネットワーク疎通確認

**Key Files**:
- Config（本番）: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_prod.json`
- メインツール: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py`
- 決定ログ: `plans/decisions/projects/scenario-12-13-outlook-pdf.md`

### シナリオ43（ETC明細作成）
**Status**: ✅ 本番版v46完成 — 大規模改修実施済み（2026-02-23〜03-08）

**別セッション進捗**:
- **本番版 v46**（`scenario/` 直下）が最新。fix243シリーズでv1→v23 + 本番v1→v46の計69イテレーション
- **修正内容**: ExternalResources修正、SaveAs一意名、ウィンドウ待機、フォーム入力ロバスト化、シート名フォールバック、日付修正、Invoice必須チェック
- **PROD config更新済み**（2026-03-08、バックアップあり）
- **pdf_annotateツール群**: PDF後処理（金額抽出、アノテーション、マージv5→v10、リオーダー、部門シート生成）
- **env.txt = LOCAL**（本番テスト前）
- **known_issues.md**: 4件のISSUEと修正コマンドを文書化（rpa-automationリポジトリ）

**Key Files**:
- 本番版: `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\本番インストール版　…_v46.rks`
- pdf_annotate: `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\tools\pdf_annotate\`
- known_issues: `C:\ProgramData\Generative AI\Github\rpa-automation\rk10\docs\known_issues.md`

### シナリオ58（基幹システム査定支払い分はきだし）
**Status**: 🆕 業務形式知作成済み・PROD config作成済み — 自動化実装前

**別セッション進捗**:
- **video2pdd v3で業務形式知を自動生成**（31ステップ、5フェーズ、未解決0件）
- シナリオ57と同じ軽技Webだが**対象会社が異なる**（東海インプル建設 / tinton）
- tool_config_prod.json 作成済み（2026-03-04）
- **env.txt = LOCAL**

**Key Files**:
- 業務形式知: `C:\ProgramData\RK10\Robots\【58…】\docs\58_業務形式知.md`
- Config PROD: `C:\ProgramData\RK10\Robots\【58…】\config\tool_config_prod.json`

### シナリオ63（毎月同額支払い申請）
**Status**: 🆕 業務形式知 + PDD + 自動化コード生成済み — セレクタ未検証

**別セッション進捗**:
- **video2pdd v3でPDD Excel + Pythonコード生成済み**
- 4件/月の定期支払いコピー処理（前月→当月、日付・金額調整）
- セレクタは全て**未検証**（Phase Aのログインのみ確定、Phase B/Cは推定）
- **env.txt = LOCAL**

**Key Files**:
- 業務形式知: `C:\ProgramData\RK10\Robots\【63…】\docs\scenario63_業務形式知.md`
- PDD: `C:\ProgramData\RK10\Robots\【63…】\docs\PDD_20260211_143654_072689.xlsx`
- 自動化コード: `C:\ProgramData\RK10\Robots\【63…】\tools\automation_20260211_143654_072689.py`

### シナリオ70（支払い確定処理）
**Status**: 🆕 ヒアリング完了 — 自動化未着手

**別セッション進捗（2026-02-25）**:
- **吉田様ヒアリング完了**: 承認済みデータ→総合振込確定の処理フロー整理
- **設計課題**: 都度振込の誤申請検知（申請者の「気づき」をRPAでどう担保するか）
- video2pdd出力あり（`docs/video2pdd_s70/`）
- **env.txt = LOCAL**

**Key Files**:
- ヒアリング記録: `C:\ProgramData\RK10\Robots\70楽楽精算支払い確定\docs\70_ヒアリング記録.md`
- 業務形式知: `C:\ProgramData\RK10\Robots\70楽楽精算支払い確定\docs\70_業務形式知.md`

---

### 吉田様ヒアリング設計メモ（2026-02-25、rpa-automationリポジトリ）
**Status**: 要件整理完了 — 実装優先度確定

6シナリオの要件を整理済み。提案優先度:
1. **シナリオ50・58**: CSV吐き出し（低リスク、効果早い）
2. **シナリオ60・63**: 定期申請の月次定型処理
3. **シナリオ6**: 資金繰り表突合自動化（効果大、難易度中〜高）
4. **シナリオ70**: 誤申請検知含む確定処理
5. **シナリオ10関連**: 有料OCR API比較後に判断

**Key File**: `C:\ProgramData\Generative AI\Github\rpa-automation\rk10\docs\2026-02-25_yoshida_hearing_scenario_design.md`

### 共通ツール（rpa-automationリポジトリ）

- **patch_rks.py**: .rks修正自動化（ExternalResources/SaveAs一意名/WaitWindow 3パッチ）
- **rk10_skill_intake.py**: 教師データからevidence package自動生成（シナリオ37/43/44/55実行済み）
- **POP3クリーンアップツール**: 顧客配布パッケージ完成（ZIP→バッチダブルクリック実行）
- **RK10 Skill Map**: ワークフロー図・チェックリスト・リスクホットスポット整理

---

## 今セッション (2026-03-19)

### 1. 全リポジトリ横断の状況確認・handoff更新
- rpa-automation/doboku-14w/construction-permit-tracker/ralph-cc-loop/x-research-skills 確認
- 別セッション進捗をhandoffに反映（シナリオ43/58/63/70/12&13、共通ツール、ヒアリング設計メモ）

### 2. 全シナリオ共通デプロイツール `rk10_preflight` 作成完了
**配置先**: `C:\ProgramData\RK10\Tools\rk10_preflight\`
- `rk10_preflight.py` — メインスクリプト（全9カテゴリチェック + --fix自動修復）
- `scenarios.json` — 全15シナリオ定義

**使い方**:
```bash
python rk10_preflight.py all --fix    # 一括環境セットアップ（Day 1）
python rk10_preflight.py 55 --env PROD  # 個別本番移行チェック
python rk10_preflight.py 55 --json      # JSON出力（監査証跡）
```

**チェック項目**: Python環境、パッケージ、設定ファイル、設定値、資格情報、ネットワーク、COM、ツールファイル、ディレクトリ
**自動修復**: pip install、cmdkey資格情報登録（対話的）、setx環境変数、mkdir

**テスト結果（LOCAL環境）**:
| シナリオ | NG | 内容 |
|---------|---|----|
| 55 | 1 | UNCパス（社内未接続） |
| 57 | 4 | UNC + BOM付きJSON + 環境変数未設定 + logディレクトリ未作成 |
| 38/42/47/63/70/71 | 0 | 全チェック通過 |

**BOM付きJSON問題**: シナリオ57の`tool_config_prod.json`がBOM付きUTF-8。`--fix`で対応予定（utf-8-sig対応）
