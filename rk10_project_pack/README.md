# RK10 ナレッジ移植パック

## 概要
KEYENCE RK-10 RPAシナリオ開発のナレッジをChatGPT Projects等に移植するためのドキュメント集。

---

## 使用方法

### ChatGPT Projectsへの移植

1. 新しいProjectを作成
2. 以下のファイルをProject Instructionsとしてアップロード:
   - `00_PROJECT_INSTRUCTIONS.md` (必須)
   - `01_INDEX.md` (推奨)
3. 残りのファイルをProject Filesとしてアップロード

### Claude Projectsへの移植

1. 新しいProjectを作成
2. Project Knowledge に全ファイルをアップロード
3. `00_PROJECT_INSTRUCTIONS.md`の内容をCustom Instructionsに転記

---

## ファイル構成

```
rk10_project_pack/
├── 00_PROJECT_INSTRUCTIONS.md   # プロジェクト概要・基本原則
├── 01_INDEX.md                   # 知識ベースインデックス
├── 02_DESIGN_PATTERNS.md         # 設計パターン集
├── 03_TROUBLESHOOTING.md         # トラブルシューティング
├── 04_PLAYBOOKS/                 # 手順書
│   ├── rks_edit.md              # .rksファイル編集手順
│   ├── rakuraku_scraping.md     # 楽楽精算スクレイピング
│   ├── excel_transfer.md        # Excel転記処理
│   ├── rk10_ui_automation.md    # RK10 UI自動化
│   ├── recoru_api.md            # レコル勤怠API
│   └── cybozu_scraping.md       # サイボウズスクレイピング
├── 05_TEMPLATES/                 # テンプレート
│   ├── requirements_sheet.md    # 要件定義書
│   ├── python_cli.md            # Python CLIスクリプト
│   ├── config_xlsx.md           # 設定ファイル
│   └── case_folder.md           # ケースフォルダ構造
├── 06_SNIPPETS/                  # コードスニペット
│   ├── keyence_csharp_api.md    # Keyence C# API
│   └── python_patterns.md       # Pythonパターン
├── 90_EVIDENCE/                  # エビデンス・決定ログ
│   └── decisions_sample.md      # 決定ログサンプル
└── README.md                     # このファイル
```

---

## 主要トピック

| トピック | 参照先 |
|----------|--------|
| RK10の基本 | `00_PROJECT_INSTRUCTIONS.md` |
| .rksファイル編集 | `04_PLAYBOOKS/rks_edit.md` |
| Excel操作 | `02_DESIGN_PATTERNS.md`, `04_PLAYBOOKS/excel_transfer.md` |
| スクレイピング | `04_PLAYBOOKS/rakuraku_scraping.md`, `04_PLAYBOOKS/cybozu_scraping.md` |
| エラー対応 | `03_TROUBLESHOOTING.md` |
| C# API | `06_SNIPPETS/keyence_csharp_api.md` |
| Pythonパターン | `06_SNIPPETS/python_patterns.md` |

---

## 前提知識

- KEYENCE RK-10 3.6.x
- Python 3.11+
- Playwright/pywinauto
- openpyxl

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-22 | 初版作成 |

---

## TODO（今後の拡張）

- [ ] OCR処理パターンの追加
- [ ] PDF座標抽出の詳細手順
- [ ] エラーコード一覧の整備
- [ ] 実際のシナリオ事例の追加
