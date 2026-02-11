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
**Status**: 3ヶ月バッチ書込完了・検証済み → 本番デプロイ待ち

**最新結果（2026-02-11 batch_3months.py）**:

| 月 | Success | New | Overflow | Error | 金額 |
|---|---|---|---|---|---|
| R7.10 (Nov) | 34 | 1 | 0 | 0 | 3,515,577円 |
| R7.11 (Dec) | 12 | 0 | 0 | 0 | 599,215円 |
| R7.12 (Jan) | 3 | 0 | 0 | 0 | 141,938円 |
| **合計** | **49** | **1** | **0** | **0** | **4,256,730円** |

- **書込整合性**: CSV→Excel **50/50 (100%)** 金額一致
- **コードバグ**: 0件
- **過去GT再現率**: R7.10: 97%, R7.11: 86%（同一コード、2026-02-10検証済み）

**解決済みバグ（今セッション）**:
- **転記0件問題**: 冪等性ログ(`log/v2_processed_LOCAL_*.csv`)が前回実行分のまま残存 → 全件が重複スキップされていた。ログをバックアップ(`backup_20260211_batch3m/`)してクリアし解決
- `find_supplier_row()` 自体は正常動作（209社354行キャッシュ構築OK）

**RPAテンプレ正本（2026-02-11確定）**:
- **正本**: `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\docs\55 総合振込計上・支払伝票_RPA用原本.xlsx`
- LOCAL: このファイルのRPAテンプレシートをそのまま使用
- PROD: RPAテンプレシートを本番原本に追加してから実行

**教師データ比較の注意**:
- `docs\`のExcelファイル（78シート版）はR7.10-R7.12の手入力実績データなし（合計行のみ）
- 吉田さん手入力の教師データは本番サーバー（`\\192.168.1.251\TIC-mainSV\...`）にのみ存在
- 過去セッションのGT比較スクリプト(`reproduce_gt_test.py`)は削除済み

**冪等性ログ運用ルール（重要）**:
- 再実行時は `log/v2_processed_LOCAL_*.csv` を事前にバックアップ＆クリアすること
- または `batch_3months.py` にログクリアオプションを追加する

**本番デプロイ残タスク**:
1. 本番PCデプロイ＋xlwings v0.33.20インストール
2. パイロット運用開始（2月末日、有人監視、吉田さんフィードバック）

- **Skill**: `.claude/skills/scenario-55/SKILL.md`
- **Decisions**: `plans/decisions/projects/scenario-55-furikomi.md`
- **Key files**: `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\tools\`
- **出力ファイル**: `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\work\55_RPA1_3M_retest_20260211.xlsx`
- **scratchpad**: `C:\Users\masam\AppData\Local\Temp\claude\c--ProgramData-Generative-AI-Github-PDF-RakuRaku-Seisan\78db80ac-e7d8-4318-a9be-086fe5eb3f82\scratchpad\`
- **CSV**: `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\data\payment_requests\payment_2025{10,11,12}_*_cc300.csv`

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

### シナリオ12・13（受信メールのPDFを保存・一括印刷）
**Status**: ツール実装/書き起こし/設定たたき台 完了。残は本番Outlook環境での「ストア名/フォルダパス確定」とE2E検証。

**Done**:
- Outlook COM でメール走査 → PDF添付保存 →（必要なら）復号/結合/印刷 → レポート出力 → 完了/エラー通知 まで実装。
- 保存先（UNC）の実在に合わせて config を更新。
- 書き起こし(runbook)を作成。

**Blocker / Risk**:
- この実行環境のOutlook COMではストア一覧が `masamaru1975@hotmail.com` のみで、設定の `\\\\RK用の経理\\\\受信トレイ` が解決できない。
  - 原因はネットワークというより「そのPCのOutlookプロファイルに共有メールボックス（RK用の経理）が設定されていない/見えていない」可能性が高い。
- URLのみ（Web請求サービス）メールは未自動化のため、検知したら停止して通知する（`fail_on_url_only_mail=true`）。

**Next**（本番PCで実施）:
1. `python C:\\ProgramData\\Generative AI\\Github\\PDF-RakuRaku-Seisan\\tools\\outlook_save_pdf_and_batch_print.py --list-outlook-stores`
2. `python C:\\ProgramData\\Generative AI\\Github\\PDF-RakuRaku-Seisan\\tools\\outlook_save_pdf_and_batch_print.py --list-outlook-folders \"\\\\<Store>\"`
3. `C:\\ProgramData\\RK10\\Robots\\12・13受信メールのPDFを保存・一括印刷\\config\\tool_config_prod.json` の `outlook.folder_path`（と必要なら `profile_name`）を確定値へ更新。
4. `--scan-only` → `--execute --max-messages 3` →（最後に）印刷あり、の順で段階検証。

**Key files**:
- Tool: `C:\\ProgramData\\Generative AI\\Github\\PDF-RakuRaku-Seisan\\tools\\outlook_save_pdf_and_batch_print.py`
- Mail helper: `C:\\ProgramData\\Generative AI\\Github\\PDF-RakuRaku-Seisan\\tools\\common\\email_notifier.py`
- Runbook: `C:\\ProgramData\\Generative AI\\Github\\PDF-RakuRaku-Seisan\\docs\\runbooks\\s12_13_outlook_pdf_save_and_batch_print.md`
- Prod config: `C:\\ProgramData\\RK10\\Robots\\12・13受信メールのPDFを保存・一括印刷\\config\\tool_config_prod.json`
- Test config: `C:\\ProgramData\\RK10\\Robots\\12・13受信メールのPDFを保存・一括印刷\\config\\tool_config_test.json`
- Artifacts: `C:\\ProgramData\\RK10\\Robots\\12・13受信メールのPDFを保存・一括印刷\\artifacts\\run_YYYYMMDD_HHMMSS\\`
