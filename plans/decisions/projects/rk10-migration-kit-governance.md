# RK10本番移行キット 回収・台帳・監査（governance）

## 概要
- RK10で全シナリオを客先本番納品し、その後段階的に自社UIへ移行する「過渡期」の管理基盤。
- 今回作るのは自社UIの**実行**機能ではなく、「どれが本番か／いつ誰が何を適用・確認したか／未確定は何か／自社UI移行で何を引き継ぐか」を迷子にしないための**ファイルファースト台帳・監査・フィードバック回収**。
- 役割分担: RK10=実行 / 台帳・HTML=本番ファイル・結果・未確定の閲覧 / governance_events=操作履歴 / migration_plan=将来移行準備。
- まだやらないこと: 自社UIからの本番実行 / RK10停止 / 楽楽精算申請・支払確定の自社UI実行 / 認証情報・業務本文の収集。
- **実装は別AIに委託**。本ファイルはレビュー確定事項＝実装AIへの引き渡し正本。

## Source Of Truth（優先順）
1. この文書（governanceイニシアチブのレビュー確定事項）
2. 本番確定の正本: `C:\ProgramData\Generative AI\Github\rpa-automation\rk10\本番確定_整理プロトコル.md`（8段status階梯の正本）
3. シナリオ移行分類: `C:\ProgramData\Generative AI\Github\rpa-mgmt-console\docs\scenario_migration_matrix_v0.md`
4. scenario_id等の宣言値: `rpa-mgmt-console\mgmt_console\manifests\*.yaml`（schema_version:2）
5. 各シナリオの decision（scenario-43 / scenario-70 等）

## 計画（第4版・manifest正本化）— レビュー対象
- 最新正本キット: `E:\RK10_本番移行キット_20260616`
- 回収対象を「ファイル再スイープ」ではなく `manifest_files_20260616.sha256.txt`（40行・SHA256付き）正本にする。
- `99_作業後に実行_結果ログを残す.bat:6` を 20260616 参照へ。`save_feedback_log_20260615.ps1` の `$kit` を `$PSCommandPath` から自己解決、`$delta` を `$kit\delta\RK10_差分移行キット_12_13` に統一。
- 新規成果物: `production_files.json`（manifest 40件・初期 status=unconfirmed）/ `governance_events.jsonl`（BOMなしUTF-8・自動feedback_collected,unconfirmed_warning＋人間production_confirmed,hidden_logic_checked）/ `hidden_logic_fixtures_template.md`（43の安全境界）。

## レビュー総合判定
方向性は妥当。ただし**土台に致命的な穴1件**と、**既存正本があるのに作り直そうとしている戦略ミス**がある。実装前に下記 CRITICAL と「正本へのバインド」を確定すること。
- レビュー方式: 7観点×並列レビュー→敵対的検証ワークフロー。56指摘→confirmed 39（critical 1 / major 18 / minor 16 / nit 4）/ 却下17。
- 検証はBOM破壊・クロスリポジトリ依存を実ファイルで再現済み。事実系の信頼度は高い。

## 🔴 CRITICAL — MIG-2: 依存クロージャの欠落（土台を変える）
- **実証**: `run_70.bat` は `REPO_ROOT=C:\…\PDF-RakuRaku-Seisan` を設定し `tools\scenario70_preflight.py` と `rakuraku_payment_confirm.py`(74KB) を実行。両方**キット・manifestに無い**（別gitリポジトリに実在）。s70は最重要の不可逆操作（支払確定）。`run_v2026.06.08.1.bat`(s43) は `scenario43_external_pipeline_v92.py` を呼ぶが manifestにあるのは下位モジュール `2price.py` のみで**入口チェーンが切れている**。
- **意味**: manifest由来の production_files.json は「キット同梱物の一覧」であって「本番で実際に動くファイルの台帳」ではない。最重要シナリオの実行コードが台帳に載らない。
- **対処**: 回収を「ファイル列挙」→「**依存クロージャ抽出**」へ。各 `run*.bat` を静的解析し (a) 呼ぶ .py 全パス（別リポジトリ含む）(b) `--config-dir/--root` の config/env (c) import先 (d) batが手動実行を指示する **.rks**（s38は `【38】1受注工事入力.rks` が業務本体）を `dependency_closure[]`（file_path+sha256+source_repo）に登録。キット外参照は `status=external_unresolved` で警告。
- **付随 MIG-3 (major)**: run batが在るのは6本(37/38/42/43/55/70)のみ。残り9本は共有ハッシュの `RK10終了_ライセンス解放.bat` しか拾えない → `entry_point` を設け9本は `null`、ライセンス解放batは `role=license_release`（入口ではない）とタグ付け。

## 🧭 戦略修正（最重要）— 作り直すな、既存正本にバインド
却下17件の多くは検証エージェントが「ファイルがまだ無い＝前提虚偽」と過剰却下したが、その過程で既存正本を発見。これが核心。
1. **status は8段protocolが正本**。`本番確定_整理プロトコル.md` が `copied_only→static_checked→rk10_open_confirmed→rk10_build_confirmed→safe_stop_confirmed→business_write_confirmed→production_confirmed` の8段と各段の証拠、「一時保存/確認出力どまりは最高でも safe_stop/business_write」を定義済み。→ 計画の「最小4状態」は**衝突**（PS-9 confirmed）。4状態にするなら「8段への意図的サブセット」と明記しマッピングを書く。黙って分岐させない。
2. **scenario_id は宣言済みmanifestが正本**。`manifests\sNN.yaml` に `s57 / s51_52 / s12_13` 宣言済み。→ **フォルダ名から正規表現導出するな**（PS-2/PS-4/TP-1 のバグclassが消える）。manifests/*.yaml を lookup/join。正規表現はfallbackのみ。
3. production_files.json は既存の構造化manifest（side_effects/idempotency/execution/errors）と一部重複。「キット同梱物台帳」と「本番実行台帳」を用語・目的で分ける（MIG-7）。

## 🟠 MAJOR（実装前に仕様確定）
### PowerShell実装の罠
- **PS-1（最重要級）**: `.bat` は `powershell.exe`(Windows PowerShell **5.1**) で `-File` 起動。5.1はBOMなし.ps1を**CP932で読み日本語リテラルが全滅**（検証で ParserError/ExitCode=1 を再現）。→ 編集後 `save_feedback_log_20260615.ps1` は**必ず UTF-8 with BOM (EF BB BF)** 保存。**Writeツール/pwsh7 Set-Content はBOMを落とすので禁止**。検証に「先頭3バイト=EF BB BF」「powershell -File で日本語が化けない」を必須化。
- **出力側は逆にBOMなし必須（TP-4）**: jsonl/json は `[IO.File]::WriteAllLines(path,lines,(New-Object System.Text.UTF8Encoding($false)))`。`-Encoding UTF8` は5.1でBOM付きになり禁止。※**スクリプト本体=BOM付き／出力=BOMなし**の非対称を明記。
- **PS-6（冪等）**: production_files.json は**upsert必須**（人間が上げた status/confirmed_by を保持マージ、manifest差分のみ更新。全消去再生成は data-safety DS-002 違反）。governance_events.jsonl は append、`(event,file_path,stamp)` で二重追記抑止。
- **PS-7（fail-closed）**: manifest不在/0行/hex不正は **STOP**、`manifest_invalid` を記録、既存台帳を上書きしない（TPS ポカヨケ/自働化）。「空台帳を黙って出す」禁止。

### 監査スキーマ（event名以外が未定義）
- **GOV-1 / PS-6(handoff)**: 各行最低 `{ts(ISO8601), event, source:auto|human, actor_id, machine_id(COMPUTERNAME), run_id(=stamp), scenario_id, file_path, sha256, note}`。人間判断は `confirmed_by` 必須。
- **GOV-7**: `confirmed_by` は自由記述禁止、シナリオ別の事前承認者リスト（s70=北村さん, s55=吉田さん：matrix由来）から選択。`production_confirmed` は現地実物確認＋`evidence_ref` 必須。

### セキュリティ/PII
- **PS-3**: actor/confirmed_by/machine_id に実名・ホスト名が入る前提でマスキング無し。→ 役割ID（`APPROVER_KEIRI`）＋machine_idハッシュ化、氏名(+さん)/社員コード/メール形式を書込前ブロック。※**既存 matrix/manifests に「吉田さん/北村さん」が平文混入**しているので併せて是正。

### 出力先（第4版で消失）
- **PS-1(handoff)**: production_files.json / governance_events.jsonl は `$kit\governance_current\` に永続化、feedback_<stamp> には控えコピー、fixtures templateは1回だけ生成し既存は上書きしない（人間記入保護）。

### テスト不足
- 件数 `==40`（manifest非空行数と動的突合、ハードコード禁止）/ scenario_id期待値表（common×12・s51_52・s12_13・s58、None/数字単体ゼロ）/ **BOMバイトチェック**（出力先頭3byte≠EF BB BF＋各jsonl行 json.loads）/ 既存挙動回帰（memo/inventory/safe_copies/-NoOpen）/ 全件 status=unconfirmed / **dedupはhashでなくfile_path**（同一ハッシュのライセンス解放bat14件が潰れない）/ note validate に擬似秘密値→STOP。

## 🟡 MINOR / nit
- 重複ハッシュ14件（`C7D86865…`）を hash dedup すると14→1に潰れる → file_pathキーで保持。
- file_path に取引先名（日本情報サービス協同組合）が必ず入る。READMEのPIIスキャンは**本文対象でパス文字列は保証外** → パスを許容メタとするか判断。
- `.bat:6` は20260611参照のまま（計画は修正を謳うが旧キット内 .ps1 も温存→誤起動経路）。
- note validate はブロックリスト方式で原理的に漏れる → 空必須/allowlist寄りに。
- governance_events と operation_ledger の橋渡し（将来execute時に両方書く）を定義。

## ✅ 計画が既に正しい点（再指摘不要）
- `$PSCommandPath` 自己解決は `-File` 経由で正しく動作。
- manifest分割 `-split '\s+',2`・起点 `$kit\files` は妥当。
- 「管理から始める／observe-only／実行ボタン無し」の基本設計は妥当（matrix で全件 rk10_owns=true・platform execute禁止と整合）。

## 検証プロセスの注意（開示）
却下17件のうち `本番確定protocol`・`manifests/*.yaml`・`.rks未捕捉` 系は「ファイルがまだ無い」を理由にした弱い却下。実体ある論点として CRITICAL/戦略修正に再昇格済み。PowerShell/事実系の検証（BOM破壊・クロスリポジトリ依存）は実ファイル再現済みで信頼できる。

## 実装AIへの引き渡し優先順
1. **MIG-2 依存クロージャ抽出**（s70/s43の別リポジトリ実行コード＋.rksを台帳化、external_unresolved警告）
2. **status を8段protocolに合わせる／scenario_idはmanifests正本をlookup**
3. **BOM**（スクリプト本体=付き・出力=なし）
4. **監査スキーマ＋承認者リスト＋evidence_ref**
5. **出力先 governance_current 固定＋upsert/fail-closed**
6. **テスト7種**（件数40・scenario_id期待値・BOMバイト・回帰・全件unconfirmed・file_path dedup・note validate STOP）

## Non-Goals
- 自社UIからの本番実行 / RK10停止
- 認証情報・業務データ本文の収集
- hash-chain監査（今回見送り。改ざん検知はgit commit＋持ち帰り運用に委ねる）

## 履歴
- 2026-06-16: 計画第1版（重DB/Web）→第4版（manifest正本化）まで反復。Claude多角レビュー（7観点・敵対的検証）でconfirmed 39件確定。実装は別AIへ委託。本ファイルを引き渡し正本として作成。
