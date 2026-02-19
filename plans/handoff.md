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
**Status**: ⚠️ OCR改善適用済み・未検証 — pdf-ocr Skill統合完了（2026-02-18）

**今セッション完了（2026-02-18）**:

1. **G8/C2/G2/G9/G5/G3 完了**（前セッションから継続）
2. **pdf-ocr Skill統合（external-repos/my-claude-skills/pdf-ocr/templates/ 使用）**:
   - Phase1: DPI最適化（Tesseract 200/250/300、YomiToku 200/300、EasyOCR 200/300）
   - Phase2: EasyOCRをカスケードstep 3.5に追加（既存関数を接続）
   - Phase3: VENDOR_OCR_CORRECTIONS辞書追加（"緑エキスパート"→"縁エキスパート"）
   - **Phase4**: `_preprocess_png_for_ocr()` 追加 — pdf_preprocess.pyのdeskew（Hough変換）+影除去をTesseract/EasyOCRに適用
3. **SKILL.mdゲート追加**: pdf-ocr SKILL.md先頭に実装ファイル確認を必須化
4. **MEMORY.md記録**: "Skill application = use the implementation code, not just the docs"

**ゲート状態**:
| # | ゲート | 状態 |
|---|--------|------|
| G1 | routing実装（LCS+3gram） | ❌ 未実装 |
| G2 | filename-first抽出実装 | ✅ 完了 |
| G3 | --execute パイロット | ✅ 完了（OCR改善前） |
| G4 | Flag運用の藤田さん合意 | ❌ 未合意 |
| G5 | report.jsonのURLマスキング | ✅ 完了 |
| G6 | Runbook V1-V8検証 | ❌ 未検証 |
| G7 | 冪等性テスト | ❌ 未実施 |
| G8 | 全163件ファイル名規約適合率 | ✅ 完了（66.4%） |
| G9 | FlagStatus安全フォールバック | ✅ 完了 |
| G10 | 本番config preflight | ❌ 未実施 |

**Next（次セッション最優先）**:
- OCR改善後テスト未実施 → `--execute` on 202512フォルダで精度確認
- G1 routing実装（LCS+3gram）
- 藤田さんFlagStatus運用合意（G4）

**今セッション完了（2026-02-14 15:45-17:30）**:

1. **バッチファイル作成完了**（シナリオ44と同じパターン）:
   - `scenario/1_テスト実行.bat` — tool_config_test.json使用、既定ドライラン
   - `scenario/2_本番実行.bat` — tool_config_prod.json使用、本番実行
   - `scenario/_test_batch.bat` — 環境セットアップ検証用
   - `scenario/README.md` — 使い方ガイド、設定説明、トラブルシューティング

2. **Outlook COM接続確認済み**:
   - `--list-outlook-stores` 成功（`seikyu.tic@tokai-ic.co.jp`アクセス可能）
   - スクリプト構文チェック合格
   - BOM付きJSON読み込み対応確認（`utf-8-sig`使用）

3. **重要な発見: 設計の相違**

| 項目 | 現在の実装 | ヒアリング内容（2/13 藤田さん） |
|------|----------|-------------------------------|
| フォルダ作成 | **自動作成**（PDF内vendor名で） | **既存フォルダに振り分け**（工事名で） |
| マッチング | vendor名完全抽出 | **3文字一致ルール** |
| 不明時 | エラー停止 | 「その他」フォルダに保存 |

**現在の実装**:
- PDFから vendor（業者名）を自動抽出
- フォルダ構造: `save_dir/{vendor_short}/{vendor_short}__{issue_date}__{amount}.pdf`
- 例: `経理\請求書【現場】\モビテック\モビテック__20250213__123456円.pdf`

**ヒアリング内容**:
- 既存フォルダ名（工事名など）と3文字一致でマッチング
- PDF内容と既存フォルダ名を比較して振り分け
- 判断できないものは「その他」フォルダに保存

**Next Steps（優先度順）**:

1. **藤田さんからの動画待ち** — Power Automate Desktop録画で実際の操作フローを確認
2. **実装方針決定**:
   - **案A（拡張）**: 既存vendor抽出 + 3文字一致ロジック追加
   - **案B（新規）**: 動画ベースで工事名マッチング新規実装
3. **設定ファイル拡張**（案A選択時）:
   - `existing_folders_root`: 既存フォルダのルートパス
   - `match_threshold`: 一致文字数閾値（デフォルト3）
   - `unknown_folder`: 不明時の退避先（デフォルト「その他」）

**Blocker / Risk**:
- **設計相違**: 現在の実装は「業者名ベース」、要件は「工事名ベース」
- **3文字一致の曖昧性**: 複数フォルダが一致する可能性 → 一致文字数が多い方を優先、同数なら「その他」
- URLのみ（Web請求サービス）メールは未自動化のため、検知したら停止して通知する（`fail_on_url_only_mail=true`）

**Key Files**:
- ドキュメント: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\docs\s12_13_outlook_pdf_save_and_batch_print.md`
- README: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\scenario\README.md`
- バッチ（テスト）: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\scenario\1_テスト実行.bat`
- バッチ（本番）: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\scenario\2_本番実行.bat`
- 検証バッチ: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\scenario\_test_batch.bat`
- メインツール: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py`
- Config（テスト）: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_test.json`
- Config（本番）: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_prod.json`
- Artifacts: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\artifacts\run_YYYYMMDD_HHMMSS\`

---

## 今セッション (2026-02-17)

### 1. rpa-workflows リポジトリ作成完了
**Status**: ✅ 完了 — GitHub push済み

**プロジェクト概要**:
- **リポジトリ**: `https://github.com/bubbleberry247/rpa-workflows` (private)
- **目的**: RPA自動化プロジェクトの標準構成テンプレート
- **構成**: RK10シナリオ + Playwright（4サービス） + Python ツール + CI/CD

**完了内容**:
1. **ディレクトリ構造作成**:
   - `rk10/scenarios/` — RK10シナリオ格納
   - `playwright/rakuraku-seisan/`, `recoru/`, `drive-report/`, `softbank-portal/` — サービス別Playwrightテスト
   - `python/` — Python自動化スクリプト
   - `tests/` — テストスイート
   - `.github/workflows/` — CI/CD定義

2. **設定ファイル作成**:
   - `.gitignore` — Python/Node/RK10/credentials除外
   - `README.md` — 技術スタック、セットアップ手順、開発ガイドライン
   - `requirements.txt` — Python依存関係（playwright, openpyxl, xlwings, pywinauto, easyocr, PyMuPDF）
   - `.env.example` — 環境変数テンプレート（4サービス認証情報、PROD/LOCAL切替）
   - `playwright/package.json` — サービス別npm scripts
   - `playwright/playwright.config.ts` — RPA最適化設定（headless:false、1920x1080、30s timeout、sequential実行）

3. **Git操作完了**:
   - 初回コミット（18ファイル、521行）
   - GitHub作成（`bubbleberry247/rpa-workflows`）
   - push完了

**Key Files**:
- Repository: `https://github.com/bubbleberry247/rpa-workflows`
- Local: `C:\ProgramData\Generative AI\Github\rpa-automation\` (rpa-workflowsとしてpush)

### 2. doboku-14w-training データ収集進捗更新
**Status**: ⚠️ 残り5問 — Claude for Chrome実行待ち

**完了内容**:
1. **グループ6完了**（17問）:
   - Word文書のチェックリスト更新
   - グループ6ステータス: "一部不完全（17問）- 残り3個を収集" → "✅完了（17問）"

2. **全体進捗分析**:
   - 総問題数: **159問**
   - 完了: **154問**（97%）
   - 不完全: **5問**（3%）
   - 不完全問題の内訳:
     - **グループA（全フィールド収集）**: 3問
       - R1gakkaA-050（R1 選択肢50）
       - R1gakkaA-056（R1 選択肢56）
       - R6gakkaB-025（R6 必須25）
     - **グループB（一部補完）**: 2問
       - R6gakkaA-031（R6 問題A 31）— explainLongのみ必要
       - R6gakkaB-022（R6 問題B 22）— explainD完成 + explainShort/Long必要

3. **Claude for Chrome用プロンプト作成**:
   - ファイル: `C:\Users\masam\Downloads\claude_chrome_prompt_残り5問.txt`
   - 参照サイト: `https://kakomonn.com/doboku-1/`
   - データ形式: パイプ区切り（`|`）
   - 挿入位置指定: グループA（新規行追加）、グループB（既存行編集）

**Next Steps**:
1. **Claude for Chrome実行**:
   - プロンプトファイルを読み込み
   - kakomonn.com から5問の説明文を収集
   - Word文書に反映

2. **完了確認**:
   - 全159問が完全になったことを確認
   - パイプ区切り形式が正しいことを確認
   - Ctrl+S で保存

**Key Files**:
- Word文書: `C:\Users\masam\Downloads\無題のドキュメント (1).docx`
- プロンプト: `C:\Users\masam\Downloads\claude_chrome_prompt_残り5問.txt`
- QuestionBank CSV: `C:\ProgramData\Generative AI\Github\doboku-14w-training\tools\questionbank_complete.csv`

### 3. シナリオ12&13 教師データPSTインポート＆Dry-Run
**Status**: ✅ PSTインポート完了・Dry-Run成功（2026-02-17）

**完了内容（2026-02-17）**:

1. **PSTインポート完了**:
   - ファイル: `backup.pst`（1.7GB）、パスワード: `1`
   - インポート先: `seikyu.tic@tokai-ic.co.jp\受信トレイ`（サブフォルダではなく直接）
   - 107通インポート成功
   - **注意**: 受信トレイはサーバーサイドフォルダ（ドラッグ＆ドロップではpermissionエラーが出るが、インポートウィザード経由では書込可能）

2. **Config更新**:
   - `tool_config_test.json` の `folder_path` を `\\seikyu.tic@tokai-ic.co.jp\受信トレイ` に変更
   - `[テスト]教師データ` サブフォルダは削除済み（permission問題のため受信トレイ直下に統一）
   - `unread_only: false`, `use_flag_status: true` — FlagStatusで処理済み/未処理を管理

3. **Dry-Run テスト成功**:
   - 179通読み込み → 151通（FlagStatusフィルタ後）→ 125通候補（件名フィルタ後）→ 163件添付ファイル検出（PDF+ZIP）
   - エラー: 0件
   - 結果: success
   - ログ: `artifacts/run_20260217_233052/run.log`

**Next Steps（優先度順）**:

1. **`--execute` テスト実行** — 実際にPDF保存＋リネーム処理を確認（ユーザー承認後）
2. **設計相違の解決** — 現在のvendor名ベースのフォルダ作成 vs 藤田さん要件の3文字マッチング（工事名フォルダ振り分け）
3. **藤田さんからの動画待ち** — Power Automate Desktop録画で実際の操作フローを確認

**設計相違（未解決）**:

| 項目 | 現在の実装 | ヒアリング内容（2/13 藤田さん） |
|------|----------|-------------------------------|
| フォルダ作成 | **自動作成**（PDF内vendor名で） | **既存フォルダに振り分け**（工事名で） |
| マッチング | vendor名完全抽出 | **3文字一致ルール** |
| 不明時 | エラー停止 | 「その他」フォルダに保存 |

**Key Files**:
- メインツール: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py`
- Config（テスト）: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_test.json`
- Config（本番）: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config.json`
- バッチ（テスト）: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\scenario\1_テスト実行.bat`
- Artifacts: `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\artifacts\`
