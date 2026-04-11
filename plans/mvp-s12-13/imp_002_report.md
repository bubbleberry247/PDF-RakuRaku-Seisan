# IMP-002 Report: bool 厳格化 + preflight チェック

- Task ID: IMP-002
- Status: Done
- 実施者: T0 (Claude) — Codex が2回ともプロジェクト外書き込みブロックのため直接適用
- Summary: `bool(raw.get(...))` の型変換バグを `_load_bool_safe()` に置き換え、`tool_config.json` に不足キーを追加。構文確認 PASS。

---

## 変更内容

### 1. `_load_bool_safe()` ヘルパー関数追加
**ファイル**: `tools/outlook_save_pdf_and_batch_print.py`
**挿入位置**: line 1793（`_move_file()` の直前）

```python
def _load_bool_safe(raw: dict, key: str, default: bool = False) -> bool:
    """JSON config から bool を安全に読み込む。
    文字列 "false" を bool(False) に変換し、意図しないデフォルト True を防ぐ。
    """
    if key not in raw:
        return default
    value = raw[key]
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise ValueError(f"config.{key} must be bool or 'true'/'false' string, got: {value!r}")
```

### 2. 3行置き換え
**ファイル**: `tools/outlook_save_pdf_and_batch_print.py`
**位置**: lines 1972/1974/1975（行番号は関数追加後）

| 変更前 | 変更後 |
|--------|--------|
| `fail_on_url_only_mail=bool(raw.get("fail_on_url_only_mail", True))` | `fail_on_url_only_mail=_load_bool_safe(raw, "fail_on_url_only_mail", default=False)` |
| `enable_zip_processing=bool(raw.get("enable_zip_processing", True))` | `enable_zip_processing=_load_bool_safe(raw, "enable_zip_processing", default=False)` |
| `enable_pdf_decryption=bool(raw.get("enable_pdf_decryption", True))` | `enable_pdf_decryption=_load_bool_safe(raw, "enable_pdf_decryption", default=False)` |

**変更理由**: `bool("false") == True` のため、文字列でconfigに書いた場合に意図が逆転するバグ。また、キーが存在しない場合のデフォルトを `True → False` に変更してMVP仕様（全機能オフ）に合致させる。

### 3. `tool_config.json` に不足キー追加
**ファイル**: `config/tool_config.json`
**追加位置**: `fail_on_url_only_mail` の直後（line 33-34）

```json
"enable_zip_processing":  false,
"enable_pdf_decryption":  false,
```

**変更理由**: 旧設定ファイルにキー自体が存在しなかった。`_load_bool_safe()` はデフォルト `False` を返すが、明示的に記載することで設定の意図を明確化。

---

## 検証結果

| 検証項目 | 結果 |
|---------|------|
| `ast.parse()` 構文検査 | PASS |
| `_load_bool_safe` 関数の存在確認 | line 1793 に確認済み |
| 3行置き換え確認 | lines 1972/1974/1975 に確認済み |
| JSON 整合性 | `tool_config.json` に2キー追加済み |

---

## リスク残存

- `tool_config.json` は旧設定ファイルであり `fail_on_url_only_mail: true` のまま（テスト/本番では prod/test JSON を使用するため影響なし）
- `_load_bool_safe()` は MVP の3フィールドのみに適用。Outlook設定の `bool(outlook_raw.get(...))` は対象外（MVP scope外）

---

## 次アクション

1. QA-002: `1_テスト実行.bat --scan-only` でOutlook接続確認
2. ORCH-002: Go/No-Go 判定（QA-002結果後）
