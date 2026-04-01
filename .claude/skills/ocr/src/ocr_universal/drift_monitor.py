"""drift_monitor.py — バッチテスト結果から drift_gate 用 CSV を生成・検証する。"""
from __future__ import annotations

import csv, io, re, sys
from pathlib import Path
from typing import Any

_DRIFT_GATE_DIR = r"C:\tmp"
if _DRIFT_GATE_DIR not in sys.path:
    sys.path.insert(0, _DRIFT_GATE_DIR)
from .jp_norm import normalize_amount

_COMPANY_ABBR = [
    ("㈱", "株式会社"), ("㈲", "有限会社"), ("(株)", "株式会社"),
    ("(有)", "有限会社"), ("（株）", "株式会社"), ("（有）", "有限会社"),
]

def _norm_vendor(raw: str | None) -> str:
    if not raw:
        return ""
    text = str(raw).strip()
    for abbr, full in _COMPANY_ABBR:
        text = text.replace(abbr, full)
    return re.sub(r"\s+", "", text)

def _norm_date(raw: str | None) -> str:
    if not raw:
        return ""
    text = str(raw).strip().replace("-", "").replace("/", "").replace(".", "")
    return re.sub(r"[年月日\s]", "", text)

def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return normalize_amount(str(val))

def append_result(
    doc_id: str, golden_record: dict[str, str],
    pipeline_result: dict[str, Any], csv_path: str | Path,
) -> None:
    """golden vs pipeline を比較し drift_gate 用 CSV に追記する。"""
    path = Path(csv_path)
    write_header = not path.exists() or path.stat().st_size == 0
    g_v = _norm_vendor(golden_record.get("vendor"))
    p_v = _norm_vendor(pipeline_result.get("vendor_name"))
    g_d = _norm_date(golden_record.get("issue_date"))
    p_d = _norm_date(pipeline_result.get("issue_date"))
    g_a = _safe_int(golden_record.get("amount"))
    p_a = _safe_int(pipeline_result.get("total_amount"))
    v_m = 1 if g_v and g_v == p_v else 0
    d_m = 1 if g_d and g_d == p_d else 0
    a_ex = 1 if g_a is not None and g_a == p_a else 0
    a_10 = a_ex
    if not a_ex and g_a and p_a:
        a_10 = 1 if abs(p_a - g_a) <= g_a * 0.10 else 0
    rows = [
        (doc_id, "vendor", v_m), (doc_id, "date", d_m),
        (doc_id, "amount_exact", a_ex), (doc_id, "amount_10pct", a_10),
    ]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["doc_id", "field", "match"])
        w.writerows(rows)

def run_drift_gate(
    csv_path: str | Path, field: str, baseline: float, delta: float,
    boots: int = 2000, alpha: float = 0.05,
) -> tuple[int, str]:
    """drift_gate.py の main() をプログラム的に呼び出す。"""
    import drift_gate  # type: ignore[import-untyped]
    argv = [
        "--input", str(csv_path), "--field", field,
        "--baseline", str(baseline), "--delta", str(delta),
        "--boots", str(boots), "--alpha", str(alpha),
    ]
    buf = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buf
        exit_code = drift_gate.main(argv)
    finally:
        sys.stdout = old_stdout
    return exit_code, buf.getvalue()

_FIELD_PARAMS: dict[str, tuple[float, float]] = {
    "vendor": (0.776, 0.05), "date": (0.638, 0.05),
    "amount_exact": (0.440, 0.05), "amount_10pct": (0.786, 0.05),
}

def run_all_checks(csv_path: str | Path) -> dict[str, dict[str, Any]]:
    """4 フィールド全ての drift_gate 検証を一括実行する。"""
    results: dict[str, dict[str, Any]] = {}
    for name, (bl, dl) in _FIELD_PARAMS.items():
        ec, out = run_drift_gate(csv_path, name, bl, dl)
        results[name] = {"exit_code": ec, "output": out}
    return results
