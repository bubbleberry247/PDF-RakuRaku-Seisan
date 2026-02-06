# Plan: Robot 55 照合ステップ（Read-back Verification）

## Current（現状）
- Step 4「データ検証」はログ出力のみ（件数・金額を表示するだけ）
- 書き込み後のExcelを読み戻して照合していない
- 誤転記の発見は人間の手動確認に依存

## Problem（困りごと）
- Excel書き込みが途中で失敗しても検知できない
- 金額の転記ミス（型変換エラー等）が静かに混入する可能性
- Codex・私の両方が「最も投資対効果が高い改善」と評価

## Target（狙う状態）
- 書き込み後にExcelを読み戻し、件数・合計金額をクロスチェック
- 不一致時は即座にエラー（アンドン原則: 止めて通知）

## Change（今回変えること）

### 1. `excel_writer.py` に `verify_writes()` メソッド追加

```python
def verify_writes(self, expected_details: list[dict]) -> dict:
    """書き込み後のExcelを読み戻して照合

    Args:
        expected_details: success_details + not_found_suppliers
            各要素: {"row": int, "amount": int, "supplier": str}

    Returns:
        {"ok": bool, "expected_count": N, "actual_count": N,
         "expected_total": N, "actual_total": N, "mismatches": [...]}
    """
```

ロジック:
- `self.ws` は書き込み直後なのでまだ開いている
- expected_details の各 row の I列（column=9）を読み戻す
- 件数照合: len(expected_details) vs 実際に非ゼロのI列セル数
- 金額照合: sum(expected amounts) vs sum(I列の実際値)
- 行単位照合: 各行の expected amount vs actual I列値
- mismatch があれば詳細を返す

### 2. `main.py` Step 4 を実照合に置換

```python
# 4. 検証（read-back照合）
logger.info("[4/6] データ検証（read-back照合）...")
if not args.dry_run:
    # 照合対象 = 転記成功 + 未登録転記
    expected = []
    for d in result.get("success_details", []):
        expected.append({"row": d["row"], "amount": d["amount"], "supplier": d.get("supplier", "")})
    for d in result.get("not_found_suppliers", []):
        if isinstance(d, dict) and d.get("row"):
            expected.append({"row": d["row"], "amount": d.get("amount", 0), "supplier": d.get("name", "")})

    verify = writer.verify_writes(expected)

    logger.info("  照合結果: %s", "OK" if verify["ok"] else "NG")
    logger.info("  件数: 期待=%d 実際=%d", verify["expected_count"], verify["actual_count"])
    logger.info("  金額: 期待=%s 実際=%s", f'{verify["expected_total"]:,}', f'{verify["actual_total"]:,}')

    if not verify["ok"]:
        for m in verify["mismatches"]:
            logger.error("  [MISMATCH] Row %d: 期待=%s 実際=%s (%s)",
                        m["row"], m["expected"], m["actual"], m["supplier"])
        raise RuntimeError(
            f"照合NG: 期待{verify['expected_count']}件/{verify['expected_total']:,}円 "
            f"vs 実際{verify['actual_count']}件/{verify['actual_total']:,}円"
        )
else:
    logger.info("  [SKIP] ドライランのため照合スキップ")

total_amount = result.get("processed_total", 0)
logger.info("  支払総額（転記分）: %s円", f"{total_amount:,}")
```

### 3. ドライラン時の動作
- ドライランではExcelに書き込まないので照合スキップ
- ログに「[SKIP] ドライランのため照合スキップ」を出力

## Verification（検証方法）
1. `--dry-run` で実行 → 照合スキップのログが出ること
2. `--input-csv` + 実書き込みで実行 → 照合OKのログが出ること
3. テスト: 意図的に金額を書き換えて照合 → NGで停止+エラー通知が飛ぶこと

## Safety（安全性）
- 照合は「読み取り」のみ（追加の書き込みなし）
- 照合NGで `RuntimeError` → except節でエラー通知メールが飛ぶ（アンドン）
- 既存の正常系フローには影響なし（照合OKならそのまま通過）

## 変更ファイル
- `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\tools\excel_writer.py` — verify_writes() 追加
- `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\tools\main.py` — Step 4 置換
