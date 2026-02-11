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
