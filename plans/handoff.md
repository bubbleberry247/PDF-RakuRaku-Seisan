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
**Status**: 開発完了 — 本番PC作業のみ残

開発機での検証は全て完了。R7.10実書き込みでI列238/251(94.8%)、コードバグ起因の不一致0件を確認済み。
不一致13件は全て業務判断（都度振込除外5、手動追加1、担当者調整2、未登録空行5）。
本番PCでinstall.bat実行→dry-run→実書き込みの3ステップが残。

- **Skill**: `.claude/skills/scenario-55/SKILL.md`
- **Decisions**: `plans/decisions/projects/scenario-55-furikomi.md`
- **Key files**: `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\tools\`

### Video2PDD v2
**Status**: MVP完了 — 全4フェーズ実装済み

PAD Free版のRobinスクリプトからPDD(Excel)を自動生成するパイプライン。
Phase1(Robin parse + Gap検出) → Phase2(Normalize + Japanese description) → Phase3(Excel 4シート出力)。
テスト済み、resume機能も動作確認済み。次は実業務での録画テスト。

- **Skill**: `.claude/skills/video2pdd/SKILL.md`
- **Key files**: `tools/video2pdd/`

### archi-16w トレーニングアプリ
**Status**: @95デプロイ済み — 安定運用中

GAS + HTML SPAの建築士試験トレーニングアプリ。本番運用中、特に問題なし。

- **Skill**: `.claude/skills/gas-webapp/SKILL.md`
- **Deploy**: `clasp deploy -i AKfycbxVu6IgDAj5lbx9KCVEwsTC-GdG1-H5oYAOotW0x7DdBesM2UrpNkF0KRhliPi0Q-zUcg`

### claude-mem
**Status**: 稼働中（FTS5検索にバグあり、パッチ保留中）

プラグインv9.0.17。Bunワーカー port 37777。DB 38 observations蓄積済み。
Windows環境でChromaDB無効のためFTS5テキスト検索のみだが、worker-service.cjsのコードパスがFTS5をバイパスして空配列を返すバグあり。
根本原因特定済み（`searchObservations()` line ~886, `SearchManager.search()` line ~1210）。パッチ保留中。

- **DB**: `C:\Users\masam\.claude-mem\claude-mem.db`
- **Worker**: `C:\Users\masam\.claude\plugins\cache\thedotmack\claude-mem\9.0.17\scripts\worker-service.cjs`
