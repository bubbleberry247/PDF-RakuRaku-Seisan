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
**Status**: v5完了（部署ドリルダウン実装+テスト成功） — 本番デプロイ可

**完了済み（2026-02-08 夕方 v5）**:
17. **部署情報ドリルダウン実装**: 詳細画面から部署名取得（`_enrich_department_info()`）
18. **テスト成功**: 会社300の3件全件で`管理部(TIC001)`取得成功
19. **CLI統合**: `--include-department` フラグ追加（main.py）
20. **SKILL.md v4更新**: R7.12結果、iframe知見、source-excel追記

**部署ドリルダウン仕組み**:
- 一覧テーブルにはcells[7]=空（部署カラムなし）
- 詳細画面（`sapShihairaiDenpyoView/detailView`）の`部署名`th-tdに値あり
- `window.open()` + `expect_page()` で新タブ → 抽出 → クローズ（~3秒/件）
- `--include-department` で有効化（デフォルトoff、パフォーマンス考慮）

**残タスク**:
1. 本番PCでのデプロイ（PROD環境）
2. 部署情報のExcel書き込み列確定（E列?）

- **Skill**: `.claude/skills/scenario-55/SKILL.md`
- **Decisions**: `plans/decisions/projects/scenario-55-furikomi.md`
- **Key files**: `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\tools\`

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
