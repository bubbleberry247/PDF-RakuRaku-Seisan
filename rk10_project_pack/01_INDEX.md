# RK10ナレッジベース INDEX

## 目次

### プロジェクト指示
- [00_PROJECT_INSTRUCTIONS.md](00_PROJECT_INSTRUCTIONS.md) - プロジェクト概要と基本原則

### 設計・パターン
- [02_DESIGN_PATTERNS.md](02_DESIGN_PATTERNS.md) - RK10設計パターン集

### トラブルシューティング
- [03_TROUBLESHOOTING.md](03_TROUBLESHOOTING.md) - エラー解決ガイド

### 手順書（Playbooks）
| ファイル | 用途 |
|----------|------|
| [04_PLAYBOOKS/rks_edit.md](04_PLAYBOOKS/rks_edit.md) | RKSファイル編集手順 |
| [04_PLAYBOOKS/rakuraku_scraping.md](04_PLAYBOOKS/rakuraku_scraping.md) | 楽楽精算スクレイピング |
| [04_PLAYBOOKS/excel_transfer.md](04_PLAYBOOKS/excel_transfer.md) | Excel転記パターン |
| [04_PLAYBOOKS/rk10_ui_automation.md](04_PLAYBOOKS/rk10_ui_automation.md) | RK10 UI自動化 |
| [04_PLAYBOOKS/recoru_api.md](04_PLAYBOOKS/recoru_api.md) | レコルAPI連携 |
| [04_PLAYBOOKS/cybozu_scraping.md](04_PLAYBOOKS/cybozu_scraping.md) | サイボウズスクレイピング |

### テンプレート
| ファイル | 用途 |
|----------|------|
| [05_TEMPLATES/requirements_sheet.md](05_TEMPLATES/requirements_sheet.md) | 要件定義書10シート構成 |
| [05_TEMPLATES/python_cli.md](05_TEMPLATES/python_cli.md) | Python CLIインターフェース |
| [05_TEMPLATES/config_xlsx.md](05_TEMPLATES/config_xlsx.md) | 設定ファイル構成 |
| [05_TEMPLATES/case_folder.md](05_TEMPLATES/case_folder.md) | ケースフォルダ構成 |

### コードスニペット
| ファイル | 用途 |
|----------|------|
| [06_SNIPPETS/keyence_csharp_api.md](06_SNIPPETS/keyence_csharp_api.md) | Keyence C# APIリファレンス |
| [06_SNIPPETS/python_patterns.md](06_SNIPPETS/python_patterns.md) | Pythonパターン集 |

### エビデンス・決定ログ
- [90_EVIDENCE/decisions_sample.md](90_EVIDENCE/decisions_sample.md) - 決定ログサンプル

---

## キーワード索引

### A-Z
| キーワード | 参照先 |
|-----------|--------|
| ancestor:: (XPath) | [03_TROUBLESHOOTING.md#xpath制限](03_TROUBLESHOOTING.md) |
| CSS Selector | [03_TROUBLESHOOTING.md#xpath制限](03_TROUBLESHOOTING.md) |
| env.txt | [02_DESIGN_PATTERNS.md#環境切替](02_DESIGN_PATTERNS.md) |
| Excel転記 | [04_PLAYBOOKS/excel_transfer.md](04_PLAYBOOKS/excel_transfer.md) |
| ExternalResourceReader | [03_TROUBLESHOOTING.md#datatable](03_TROUBLESHOOTING.md) |
| ForceExitException | [06_SNIPPETS/keyence_csharp_api.md](06_SNIPPETS/keyence_csharp_api.md) |
| GetMatchValueList | [06_SNIPPETS/keyence_csharp_api.md](06_SNIPPETS/keyence_csharp_api.md) |
| Playwright | [04_PLAYBOOKS/rakuraku_scraping.md](04_PLAYBOOKS/rakuraku_scraping.md) |
| pywinauto | [04_PLAYBOOKS/rk10_ui_automation.md](04_PLAYBOOKS/rk10_ui_automation.md) |
| ReadPasswordFromCredential | [06_SNIPPETS/keyence_csharp_api.md](06_SNIPPETS/keyence_csharp_api.md) |
| RepeatCount | [06_SNIPPETS/keyence_csharp_api.md](06_SNIPPETS/keyence_csharp_api.md) |
| RKS編集 | [04_PLAYBOOKS/rks_edit.md](04_PLAYBOOKS/rks_edit.md) |
| XPath | [03_TROUBLESHOOTING.md#xpath制限](03_TROUBLESHOOTING.md) |
| ZIP展開 | [03_TROUBLESHOOTING.md#zip](03_TROUBLESHOOTING.md) |

### あ-ん
| キーワード | 参照先 |
|-----------|--------|
| 楽楽精算 | [04_PLAYBOOKS/rakuraku_scraping.md](04_PLAYBOOKS/rakuraku_scraping.md) |
| 勘定科目推定 | [02_DESIGN_PATTERNS.md#科目推定](02_DESIGN_PATTERNS.md) |
| 資格情報 | [06_SNIPPETS/keyence_csharp_api.md](06_SNIPPETS/keyence_csharp_api.md) |
| シート名ハードコード | [03_TROUBLESHOOTING.md#ハードコード](03_TROUBLESHOOTING.md) |
| 承認ステータス | [04_PLAYBOOKS/rakuraku_scraping.md](04_PLAYBOOKS/rakuraku_scraping.md) |
| ダイアログ処理 | [04_PLAYBOOKS/rk10_ui_automation.md](04_PLAYBOOKS/rk10_ui_automation.md) |
| 日付フォーマット | [06_SNIPPETS/keyence_csharp_api.md](06_SNIPPETS/keyence_csharp_api.md) |
| リトライパターン | [02_DESIGN_PATTERNS.md#リトライ](02_DESIGN_PATTERNS.md) |
| レコル | [04_PLAYBOOKS/recoru_api.md](04_PLAYBOOKS/recoru_api.md) |

---

## シナリオ別リファレンス

| シナリオ番号 | 名称 | 関連ドキュメント |
|-------------|------|-----------------|
| 37 | レコル公休・有休登録 | recoru_api.md, cybozu_scraping.md |
| 42 | ドライブレポート抽出 | excel_transfer.md |
| 43 | ETC明細作成 | rks_edit.md, excel_transfer.md |
| 47 | 出退勤確認 | recoru_api.md |
| 55 | 振込Excel作成 | rakuraku_scraping.md, excel_transfer.md |
| 56 | 資金繰り表入力 | excel_transfer.md |
