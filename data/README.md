# data/ — テストデータ・OCR サンプル

OCR 精度検証・前処理テスト用の PDF サンプルデータ。

## ディレクトリ構成

<!-- AUTO-GENERATED:START -->
| ディレクトリ | 内容 |
|---|---|
| `MOCK_FAX/` | シナリオ 44 用モック FAX PDF（領収書・請求書） |
| `batch_preproc/` | 前処理済み PDF（`_preproc_` プレフィックス） |
| `preprocess_test/` | 前処理パラメータ検証用 |
| `preprocess_v2/` | 前処理 v2 出力 |
| `rotation_test/` | 回転補正テスト用 |
<!-- AUTO-GENERATED:END -->

## 注意

- 本番データ（顧客情報含む）はコミット禁止
- テスト用モックデータのみ格納
- 大量 PDF の追加前に `.gitignore` 確認

[← ルートに戻る](../README.md)
