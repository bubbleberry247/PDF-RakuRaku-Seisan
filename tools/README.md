# tools/ — ユーティリティスクリプト

再利用する Python スクリプトの最終版（canonical）を格納。

## 主要スクリプト

### OCR・PDF 処理

| スクリプト | 用途 |
|---|---|
| `vision_ocr.py` | GPT-4o Vision OCR メイン |
| `pdf_ocr.py` | PDF テキスト抽出（従来版） |
| `pdf_ocr_yomitoku.py` | YomiToku OCR |
| `pdf_ocr_gemini.py` | Gemini OCR |
| `pdf_ocr_smart.py` | スマート OCR（エンジン自動選択） |
| `pdf_preprocess.py` | PDF 前処理（傾き補正・影除去） |
| `pdf_rotation_detect.py` | PDF 回転検出 |
| `pdf_renamer.py` | OCR 結果でファイル名自動変更 |
| `pdf_transcribe_to_docx.py` | PDF → DOCX 変換 |

### バッチ・評価

| スクリプト | 用途 |
|---|---|
| `batch_ocr_with_preprocess.py` | 前処理付きバッチ OCR |
| `score_ocr_bench.py` | OCR ベンチマークスコアリング |
| `run_full_vision_bench.py` | Vision OCR フルベンチ |
| `compare_ocr_engines.py` | OCR エンジン比較 |
| `test_ocr_all.py` | 全 OCR テスト実行 |
| `ground_truth.py` | ゴールデンデータセット管理 |
| `build_bench_eval_assets.py` | ベンチ評価アセット構築 |

### RPA・業務自動化

| スクリプト | 用途 |
|---|---|
| `main_44.py` | シナリオ 44 メイン |
| `main_44_rk10.py` | シナリオ 44 RK10 連携版 |
| `rakuraku_upload.py` | 楽楽精算アップロード |
| `rakuraku_payment_confirm.py` | 楽楽精算支払確認 |
| `outlook_save_pdf_and_batch_print.py` | Outlook PDF 保存 + 一括印刷 |
| `web_invoice_downloader.py` | Web 請求書ダウンロード |

### マスタ・データ管理

| スクリプト | 用途 |
|---|---|
| `build_project_master_from_export.py` | 工事マスタ構築 |
| `sync_project_master.py` | 工事マスタ同期 |
| `build_vendor_hints.py` | 業者名ヒント構築 |
| `vendor_matching.py` | 業者名マッチング |
| `training_data.py` | 学習データ管理 |

### ユーティリティ

| スクリプト | 用途 |
|---|---|
| `clipboard_screenshot.py` | クリップボードスクリーンショット |
| `fix_xpath_zip.py` | RKS XPath 修正 |
| `fix_edge_launch.py` | Edge 起動修正 |
| `rpa_drift_watchdog.py` | RPA ドリフト監視 |
| `session_briefing.py` | セッションブリーフィング |
| `wiki_lint.py` | Wiki リント |

## サブディレクトリ

| ディレクトリ | 内容 |
|---|---|
| `video2pdd/` | Video/Robin → PDD パイプライン |
| `mcp-land-registry/` | 土地台帳 MCP サーバー |
| `review_helper/` | コードレビュー支援 |
| `agent-browser/` | ブラウザ自動化 |
| `common/` | 共通モジュール |
| `prompts/` | プロンプトテンプレート |
| `hitl_patches/` | HITL パッチ |
| `realesrgan/` | 画像超解像（コミット非推奨） |
| `_wip/` | 作業中（コミット禁止） |

## 命名規約

- `_DISABLED_*.py` — 無効化済み（参考保持）
- `tmp*.py` はルートに置く（tools/ に入れない）

[← ルートに戻る](../README.md)
