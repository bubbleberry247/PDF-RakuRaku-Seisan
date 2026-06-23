"""Validate RK10 goal execution packet CSVs with scenario scope exclusions.

This wrapper keeps the locked 20260620 validator as the base implementation
and filters active rows through the current objective scope exclusions. It
does not open Outlook, RK10, Rakuraku, Azure, printers, mail clients, payment
systems, MainSV, or production files.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
LEGACY_VALIDATOR = ROOT / "tools" / "validate_goal_execution_packet_20260620.py"
DEFAULT_PACKET_DIR = REPORTS / "goal_execution_packet_20260620"
DEFAULT_OUT_DIR = REPORTS / "goal_execution_packet_validation_20260620"
DEFAULT_BUNDLE_SHEET = (
    REPORTS / "bundle_operator_sheet_20260620" / "bundle_operator_sheet.csv"
)
SCOPE_EXCLUSIONS_JSON = (
    REPORTS / "objective_scope_exclusions_20260623" / "objective_scope_exclusions.json"
)


def load_legacy_validator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_goal_execution_packet_20260620_locked",
        LEGACY_VALIDATOR,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def scenario_tokens(value: str) -> set[str]:
    tokens = {value.strip()} if value.strip() else set()
    for chunk in value.replace("、", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        tokens.add(chunk)
        if "/" in chunk and all(part.strip().isdigit() for part in chunk.split("/")):
            tokens.update(part.strip() for part in chunk.split("/") if part.strip())
    return tokens


def load_scope_exclusions(path: Path = SCOPE_EXCLUSIONS_JSON) -> list[dict[str, str]]:
    payload = read_json(path)
    raw_rows = payload.get("exclusions", [])
    if not isinstance(raw_rows, list):
        return []
    rows: list[dict[str, str]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        active = row.get("active", True)
        if active is False or str(active).strip().lower() in {"false", "0", "no"}:
            continue
        scenario = str(row.get("scenario", "")).strip()
        if not scenario:
            continue
        rows.append(
            {
                "scenario": scenario,
                "reason": str(row.get("reason", "")).strip(),
                "requested_by": str(row.get("requested_by", "")).strip(),
                "requested_at": str(row.get("requested_at", "")).strip(),
                "evidence": str(row.get("evidence", "")).strip(),
            }
        )
    return rows


def excluded_scenario_tokens(exclusions: list[dict[str, str]]) -> set[str]:
    tokens: set[str] = set()
    for row in exclusions:
        tokens.update(scenario_tokens(row.get("scenario", "")))
    return tokens


def row_is_excluded(row: dict[str, Any], excluded_tokens: set[str]) -> bool:
    if not excluded_tokens:
        return False
    return bool(scenario_tokens(str(row.get("scenario", ""))) & excluded_tokens)


def apply_scope_exclusions(
    payload: dict[str, Any],
    scope_exclusions_json: Path = SCOPE_EXCLUSIONS_JSON,
) -> dict[str, Any]:
    scope_exclusions = load_scope_exclusions(scope_exclusions_json)
    excluded_tokens = excluded_scenario_tokens(scope_exclusions)
    raw_rows = [
        dict(row)
        for row in payload.get("rows", [])
        if isinstance(row, dict)
    ]
    active_rows = [row for row in raw_rows if not row_is_excluded(row, excluded_tokens)]
    excluded_rows = [row for row in raw_rows if row_is_excluded(row, excluded_tokens)]
    approved_count = sum(1 for row in active_rows if bool(row.get("approved")))
    needs_attention_count = len(active_rows) - approved_count
    return {
        **payload,
        "all_packet_rows_approved": bool(active_rows) and needs_attention_count == 0,
        "row_count": len(active_rows),
        "raw_row_count": len(raw_rows),
        "approved_row_count": approved_count,
        "needs_attention_count": needs_attention_count,
        "scope_exclusion_count": len(scope_exclusions),
        "scope_exclusions_path": str(scope_exclusions_json),
        "scope_exclusions": scope_exclusions,
        "excluded_row_count": len(excluded_rows),
        "rows": active_rows,
        "excluded_rows": excluded_rows,
    }


def build_payload(
    packet_dir: Path = DEFAULT_PACKET_DIR,
    bundle_sheet_path: Path = DEFAULT_BUNDLE_SHEET,
    scope_exclusions_json: Path = SCOPE_EXCLUSIONS_JSON,
) -> dict[str, Any]:
    legacy = load_legacy_validator()
    payload = legacy.build_payload(packet_dir, bundle_sheet_path)
    return apply_scope_exclusions(payload, scope_exclusions_json)


def build_markdown(payload: dict[str, Any]) -> str:
    legacy = load_legacy_validator()
    lines = [
        legacy.build_markdown(payload).rstrip(),
        "",
        "## Scope Exclusion Summary",
        "",
        f"- raw_row_count: `{payload.get('raw_row_count', payload['row_count'])}`",
        f"- scope_exclusion_count: `{payload.get('scope_exclusion_count', 0)}`",
        f"- excluded_row_count: `{payload.get('excluded_row_count', 0)}`",
        f"- scope_exclusions_path: `{payload.get('scope_exclusions_path', '')}`",
    ]
    excluded_rows = payload.get("excluded_rows", [])
    if excluded_rows:
        lines.extend(
            [
                "",
                "## Excluded Row Matrix",
                "",
                "| Bundle | Scenario | Status | Missing Fields | Evidence Exists | Evidence Path | CSV |",
                "|---|---|---|---|---:|---|---|",
            ]
        )
        for row in excluded_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("bundle", "")),
                        str(row.get("scenario", "")),
                        str(row.get("status", "")),
                        str(row.get("missing_fields", "")) or "-",
                        "YES" if row.get("evidence_exists") else "NO",
                        f"`{row.get('evidence_path', '')}`" if row.get("evidence_path") else "-",
                        f"`{row.get('csv_path', '')}`",
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    legacy = load_legacy_validator()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "goal_execution_packet_validation.json"
    md_path = out_dir / "goal_execution_packet_validation.md"
    attention_csv_path = out_dir / "goal_execution_packet_attention.csv"
    attention_rows = legacy.build_attention_rows(payload)
    payload["attention_row_count"] = len(attention_rows)
    payload["attention_csv_path"] = str(attention_csv_path)
    legacy.write_attention_csv(attention_csv_path, attention_rows)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    legacy.write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate RK10 goal execution packet evidence with scope exclusions."
    )
    parser.add_argument("--packet-dir", type=Path, default=DEFAULT_PACKET_DIR)
    parser.add_argument("--bundle-sheet", type=Path, default=DEFAULT_BUNDLE_SHEET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--scope-exclusions-json", type=Path, default=SCOPE_EXCLUSIONS_JSON)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        args.packet_dir,
        args.bundle_sheet,
        args.scope_exclusions_json,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
