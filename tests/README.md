# tests/ — テストスイート

`pytest` で実行するユニットテスト・統合テスト。

## テスト一覧

<!-- AUTO-GENERATED:START -->
| ファイル | テスト対象 |
|---|---|
| `test_evidence_ledger.py` | 証跡台帳 |
| `test_jp_field_pack.py` | 日本語フィールドパック |
| `test_outlook_save_pdf_and_batch_print_extract_invoice_fields.py` | Outlook PDF 保存・請求書フィールド抽出 |
| `test_reconcile.py` | 照合処理 |
| `test_rpa_drift_watchdog.py` | RPA ドリフト監視 |
| `test_session_briefing.py` | セッションブリーフィング |
| `test_wiki_lint.py` | Wiki リント |
<!-- AUTO-GENERATED:END -->

## 実行方法

```bash
uv run pytest -v
uv run pytest tests/test_wiki_lint.py -v   # 単体
uv run pytest --cov=tools --cov-report=term-missing  # カバレッジ
```

[← ルートに戻る](../README.md)
