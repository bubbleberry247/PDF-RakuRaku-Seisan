# CHANGELOG - RK10ナレッジ移植パック

## [1.0.0] - 2026-01-22

### 追加
- 初版作成：RK10 RPAシナリオ開発のナレッジをChatGPT Projects等に移植するためのドキュメント集
- **00_PROJECT_INSTRUCTIONS.md** - プロジェクト概要・基本原則
- **01_INDEX.md** - 知識ベースインデックス（キーワード→参照先マップ）
- **02_DESIGN_PATTERNS.md** - 設計パターン集（環境切替、リトライ、Excel操作等）
- **03_TROUBLESHOOTING.md** - トラブルシューティング（10カテゴリ）
- **04_PLAYBOOKS/** - 手順書（6ファイル）
  - rks_edit.md - .rksファイル編集手順
  - rakuraku_scraping.md - 楽楽精算スクレイピング
  - excel_transfer.md - Excel転記処理
  - rk10_ui_automation.md - RK10 UI自動化
  - recoru_api.md - レコル勤怠API
  - cybozu_scraping.md - サイボウズスクレイピング
- **05_TEMPLATES/** - テンプレート（6ファイル）
  - requirements_sheet.md - 要件定義書テンプレート
  - python_cli.md - Python CLIスクリプトテンプレート
  - config_xlsx.md - 設定ファイル構造
  - case_folder.md - ケースフォルダ構造
  - customer_handover_doc.md - 客先引継ぎ資料テンプレート（Markdown）
  - customer_handover_doc.xlsx - 客先引継ぎ資料テンプレート（Excel）
- **06_SNIPPETS/** - コードスニペット（2ファイル）
  - keyence_csharp_api.md - Keyence C# APIリファレンス
  - python_patterns.md - Pythonパターン集
- **90_EVIDENCE/** - エビデンス・決定ログ
  - decisions_sample.md - 決定ログサンプル
- **README.md** - 使用方法・ファイル構成

---

## 更新ルール

ナレッジ追加時の推奨順序:
1. **03_TROUBLESHOOTING.md** に該当カテゴリがあれば追記
2. **04_PLAYBOOKS/** に詳細手順が必要なら新規/追記
3. **01_INDEX.md** にキーワード→参照先を追加

重大な変更時:
- このCHANGELOGに日付とともに記録
- バージョンはセマンティックバージョニング（MAJOR.MINOR.PATCH）

---

## 今後の拡張予定

- [ ] OCR処理パターンの追加
- [ ] PDF座標抽出の詳細手順
- [ ] エラーコード一覧の整備
- [ ] 実際のシナリオ事例の追加
