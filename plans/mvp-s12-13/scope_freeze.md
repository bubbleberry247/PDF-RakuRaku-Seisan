# Scope Freeze — Scenario 12/13 MVP
**凍結日時**: 2026-02-19
**承認**: T0 (Claude オーケストレーター)
**ステータス**: FROZEN（変更禁止 — 変更は T0 経由のみ）

---

## 1. MVP 成功条件（全条件を満たすまで本番投入しない）

| # | 条件 |
|---|------|
| 1 | 本番対象メール（NoFlag=0）の処理が実行できる |
| 2 | PDF保存・命名・振り分け・PDF出力（疑似印刷）が完了する |
| 3 | 命名失敗時は `要確認_` 付きで保存、後工程が止まらない |
| 4 | 重大不具合（誤保存・誤上書き・誤振り分け）がゼロ |
| 5 | Runbook で第三者が再現実行できる |

---

## 2. 固定スコープ（変更禁止）

| 項目 | 固定値 |
|------|--------|
| 正規保存先 | `\\192.168.1.251\TIC-mainSV\経理\請求書【現場】` |
| メール対象 | `\\seikyu.tic@tokai-ic.co.jp\受信トレイ` の FlagStatus=0 のみ |
| Flag 運用 | `0（未処理）→ 2（処理済/レビュー待ち）→ 1（月次完了）` |
| MVP 印刷 | `pdf_copy`（PDF出力、実機印刷なし） |
| 命名形式 | `{vendor}_{issue_date}_{amount_comma}_{project}.pdf` |
| 命名失敗 | `要確認_` を先頭付与、取得済み値は埋める |

---

## 3. MVP 対象外（今回は実装しない）

| 機能 | 対応方針 |
|------|---------|
| PDF 結合 | `merge.enabled=false` で無効化済み |
| URL-only メール Web 取得 | `fail_on_url_only_mail=false` でスキップ |
| HENNGE 復号 | `enable_pdf_decryption=false` で無効化済み |
| ZIP 処理 | `enable_zip_processing=false` で無効化済み |
| LCS/3gram ルーティング | keyword routing（モビテック/中村）で代替 |
| ✖/× 隔離フォルダ自動化 | スキップ＋ログのみ |

---

## 4. 現在確定している設定値

### tool_config_prod.json（本番）
```json
{
  "save_dir": "\\\\192.168.1.251\\TIC-mainSV\\経理\\請求書【現場】",
  "outlook": {
    "folder_path": "\\\\seikyu.tic@tokai-ic.co.jp\\受信トレイ",
    "use_flag_status": true,
    "mark_flag_on_success": true,
    "max_messages": 400,
    "received_within_days": null
  },
  "merge": { "enabled": false },
  "print": { "method": "pdf_copy" },
  "rename": {
    "file_name_template": "{vendor}_{issue_date}_{amount_comma}_{project}.pdf",
    "filename_first": true
  },
  "routing": {
    "enabled": true,
    "fallback_subdir": "その他",
    "rules": [
      { "subdir": "モビテック", "keywords": ["モビテック", "シン・テクニカルセンター", "3329"] },
      { "subdir": "中村", "keywords": ["中村", "中島三丁目", "3285"] }
    ]
  },
  "fail_on_url_only_mail": false,
  "enable_zip_processing": false,
  "enable_pdf_decryption": false
}
```

### tool_config_test.json（テスト）
- `save_dir`: ローカル `RK.Mock\saved`
- `folder_path`: `受信トレイ\RK用`（テスト専用サブフォルダ）
- `use_flag_status: false`, `mark_as_read_on_success: false`（Outlook 変更なし）

---

## 5. チーム構成（固定）

| Team | AI | 担当 | 主成果物 |
|------|----|------|---------|
| T0 | Claude | 計画・優先順位・依存管理・Go/No-Go | scope_freeze.md, go_no_go.md |
| T1 | Codex | 実装・設定変更・修正・構文検証 | Python差分, config差分 |
| T2 | Analyst | ルール抽出（動画/教師データ/現状） | rule_book.md |
| T3 | QA | テスト設計・実行・不具合票 | test_plan.md, test_result_round1.md |
| T4 | Docs | 運用手順整備 | runbook.md, daily_checklist.md |

---

## 6. 実行順（依存順）

```
1. ORCH-001（このファイル）← 完了
2. IMP-001（T1）║ DATA-001（T2）← 並列実行
3. QA-001（T3 テスト設計）
4. QA-002（T3 テスト実行）
5. IMP-002（T1 不具合修正）
6. QA-003（T3 再試験）
7. OPS-001（T4 運用文書確定）
8. ORCH-002（Go/No-Go判定）
```

---

## 7. 標準試験コマンド（固定）

```bash
# Stage 1: スキャンのみ
python outlook_save_pdf_and_batch_print.py --config ../config/tool_config_test.json --scan-only

# Stage 2: dry-run
python outlook_save_pdf_and_batch_print.py --config ../config/tool_config_test.json --dry-run

# Stage 3: 実行（テスト環境）
python outlook_save_pdf_and_batch_print.py --config ../config/tool_config_test.json --execute --print
```

---

## 8. 対象ファイル

| ファイル | パス |
|---------|------|
| メインスクリプト | `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py` |
| 本番 config | `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_prod.json` |
| テスト config | `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\config\tool_config_test.json` |
| 設計判断ログ | `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\decisions\projects\scenario-12-13-outlook-pdf.md` |
| MVP 成果物置き場 | `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\mvp-s12-13\` |

---

## 9. Blocked 判定基準（即時 T0 通知）

- Outlook COM 接続不可
- ネットワーク共有（NAS）到達不能
- 仕様の未合意（保存先・対象メール・Flag 運用）
- 重大不具合が1件でも発見された場合
