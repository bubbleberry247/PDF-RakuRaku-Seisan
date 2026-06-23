"""Validate remaining-operator input before running the fixed safe runner.

This tool is a preflight checker only. It reads the consolidated
remaining-operator input CSV and verifies that all rows are ready to sync into
repository-local evidence CSVs. It does not create approvals, run RK10, send
mail, print, submit, pay, call Azure, or write production systems.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_REMAINING_INPUT_CSV = (
    REPORTS / "remaining_operator_input_packet_20260623" / "remaining_operator_input.csv"
)
DEFAULT_OUT_DIR = REPORTS / "remaining_operator_input_ready_validation_20260623"
SCOPE_EXCLUSIONS_JSON = (
    REPORTS / "objective_scope_exclusions_20260623" / "objective_scope_exclusions.json"
)
OPERATOR_FIELDS = ("operator_result", "reviewer", "reviewed_at")
APPROVED_RESULTS = {
    "approved",
    "complete",
    "completed",
    "ok",
    "pass",
    "passed",
    "実施済",
    "完了",
    "承認",
    "承認済",
    "済",
}


def configure_csv_field_size_limit() -> int:
    limit = sys.maxsize
    while limit > 0:
        try:
            csv.field_size_limit(limit)
            return limit
        except OverflowError:
            limit //= 10
    return csv.field_size_limit()


CSV_FIELD_SIZE_LIMIT = configure_csv_field_size_limit()


@dataclass(frozen=True)
class RowValidation:
    bundle: str
    scenario: str
    operator_result: str
    reviewer: str
    reviewed_at: str
    approved_result: bool
    complete_operator_fields: bool
    evidence_path: str
    evidence_exists: bool
    latest_evidence_file: str
    latest_evidence_file_exists: bool
    source_packet_csv: str
    source_packet_csv_safe: bool
    source_packet_csv_has_row: bool
    source_unified_input_csv: str
    source_unified_input_csv_safe: bool
    source_unified_input_csv_has_row: bool
    blockers: str
    status: str


def normalize_result(value: str) -> str:
    return value.strip().lower()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {str(key): str(value).strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def existing_path(path_text: str) -> bool:
    return bool(path_text) and Path(path_text).exists()


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


def row_validation_is_excluded(
    row: RowValidation,
    excluded_tokens: set[str],
) -> bool:
    if not excluded_tokens:
        return False
    return bool(scenario_tokens(row.scenario) & excluded_tokens)


def safe_report_csv(path_text: str, report_root: Path = REPORTS) -> Path | None:
    if not path_text:
        return None
    try:
        path = Path(path_text).resolve()
        resolved_report_root = report_root.resolve()
    except OSError:
        return None
    if path.suffix.lower() != ".csv":
        return None
    try:
        path.relative_to(resolved_report_root)
    except ValueError:
        return None
    return path


def target_has_row(path: Path | None, bundle: str, scenario: str) -> bool:
    if path is None or not path.exists():
        return False
    for row in read_csv_rows(path):
        if row.get("bundle", "") == bundle and row.get("scenario", "") == scenario:
            return True
    return False


def missing_operator_fields(row: dict[str, str]) -> list[str]:
    return [field for field in OPERATOR_FIELDS if not row.get(field, "")]


def build_row_validation(
    row: dict[str, str],
    report_root: Path = REPORTS,
) -> RowValidation:
    bundle = row.get("bundle", "")
    scenario = row.get("scenario", "")
    operator_result = row.get("operator_result", "")
    missing_fields = missing_operator_fields(row)
    approved_result = normalize_result(operator_result) in APPROVED_RESULTS
    evidence_path = row.get("evidence_path", "")
    latest_evidence_file = row.get("latest_evidence_file", "")
    source_packet_csv = row.get("source_packet_csv", "")
    source_unified_input_csv = row.get("source_unified_input_csv", "")
    source_packet_path = safe_report_csv(source_packet_csv, report_root)
    source_unified_path = safe_report_csv(source_unified_input_csv, report_root)
    blockers: list[str] = []
    if missing_fields:
        blockers.append("MISSING_OPERATOR_FIELDS:" + ",".join(missing_fields))
    if not missing_fields and not approved_result:
        blockers.append("NON_APPROVED_OPERATOR_RESULT")
    if not existing_path(evidence_path):
        blockers.append("EVIDENCE_PATH_MISSING")
    if not existing_path(latest_evidence_file):
        blockers.append("LATEST_EVIDENCE_FILE_MISSING")
    if source_packet_path is None:
        blockers.append("UNSAFE_OR_MISSING_SOURCE_PACKET_CSV")
    elif not target_has_row(source_packet_path, bundle, scenario):
        blockers.append("SOURCE_PACKET_ROW_NOT_FOUND")
    if source_unified_path is None:
        blockers.append("UNSAFE_OR_MISSING_SOURCE_UNIFIED_INPUT_CSV")
    elif not target_has_row(source_unified_path, bundle, scenario):
        blockers.append("SOURCE_UNIFIED_ROW_NOT_FOUND")
    return RowValidation(
        bundle=bundle,
        scenario=scenario,
        operator_result=operator_result,
        reviewer=row.get("reviewer", ""),
        reviewed_at=row.get("reviewed_at", ""),
        approved_result=approved_result,
        complete_operator_fields=not missing_fields,
        evidence_path=evidence_path,
        evidence_exists=existing_path(evidence_path),
        latest_evidence_file=latest_evidence_file,
        latest_evidence_file_exists=existing_path(latest_evidence_file),
        source_packet_csv=source_packet_csv,
        source_packet_csv_safe=source_packet_path is not None,
        source_packet_csv_has_row=target_has_row(source_packet_path, bundle, scenario),
        source_unified_input_csv=source_unified_input_csv,
        source_unified_input_csv_safe=source_unified_path is not None,
        source_unified_input_csv_has_row=target_has_row(source_unified_path, bundle, scenario),
        blockers=", ".join(blockers),
        status="READY_FOR_SYNC" if not blockers else "NOT_READY",
    )


def build_payload(
    remaining_input_csv: Path = DEFAULT_REMAINING_INPUT_CSV,
    report_root: Path = REPORTS,
    scope_exclusions_json: Path = SCOPE_EXCLUSIONS_JSON,
) -> dict[str, Any]:
    remaining_input_csv_exists = remaining_input_csv.exists()
    rows = read_csv_rows(remaining_input_csv)
    all_validations = [build_row_validation(row, report_root) for row in rows]
    scope_exclusions = load_scope_exclusions(scope_exclusions_json)
    excluded_tokens = excluded_scenario_tokens(scope_exclusions)
    validations = [
        row for row in all_validations if not row_validation_is_excluded(row, excluded_tokens)
    ]
    excluded_validations = [
        row for row in all_validations if row_validation_is_excluded(row, excluded_tokens)
    ]
    blocker_count = sum(1 for row in validations if row.blockers)
    raw_blocker_count = sum(1 for row in all_validations if row.blockers)
    approved_row_count = sum(1 for row in validations if row.approved_result)
    complete_row_count = sum(1 for row in validations if row.complete_operator_fields)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "ready_to_run_after_fill": remaining_input_csv_exists and blocker_count == 0,
        "overall_goal_complete": False,
        "safety": (
            "read-only remaining operator input preflight; no approval creation, "
            "no RK10 ButtonRun, no production write, no mail, no print, no submit, "
            "no payment, no paid Azure OCR"
        ),
        "remaining_input_csv": str(remaining_input_csv),
        "remaining_input_csv_exists": remaining_input_csv_exists,
        "row_count": len(validations),
        "raw_row_count": len(all_validations),
        "raw_not_ready_row_count": raw_blocker_count,
        "scope_exclusion_count": len(scope_exclusions),
        "scope_exclusions_path": str(scope_exclusions_json),
        "scope_exclusions": scope_exclusions,
        "excluded_row_count": len(excluded_validations),
        "complete_operator_row_count": complete_row_count,
        "approved_operator_result_row_count": approved_row_count,
        "not_ready_row_count": blocker_count,
        "missing_operator_field_row_count": sum(
            1 for row in validations if not row.complete_operator_fields
        ),
        "non_approved_result_row_count": sum(
            1 for row in validations if row.complete_operator_fields and not row.approved_result
        ),
        "missing_evidence_row_count": sum(
            1
            for row in validations
            if not row.evidence_exists or not row.latest_evidence_file_exists
        ),
        "unsafe_or_missing_target_row_count": sum(
            1
            for row in validations
            if not row.source_packet_csv_safe
            or not row.source_unified_input_csv_safe
            or not row.source_packet_csv_has_row
            or not row.source_unified_input_csv_has_row
        ),
        "rows": [asdict(row) for row in validations],
        "excluded_rows": [asdict(row) for row in excluded_validations],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Remaining Operator Input Ready Validation 2026-06-23",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- ready_to_run_after_fill: `{payload['ready_to_run_after_fill']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- raw_row_count: `{payload.get('raw_row_count', payload['row_count'])}`",
        f"- raw_not_ready_row_count: `{payload.get('raw_not_ready_row_count', payload['not_ready_row_count'])}`",
        f"- scope_exclusion_count: `{payload.get('scope_exclusion_count', 0)}`",
        f"- excluded_row_count: `{payload.get('excluded_row_count', 0)}`",
        f"- scope_exclusions_path: `{payload.get('scope_exclusions_path', '')}`",
        f"- complete_operator_row_count: `{payload['complete_operator_row_count']}`",
        f"- approved_operator_result_row_count: `{payload['approved_operator_result_row_count']}`",
        f"- not_ready_row_count: `{payload['not_ready_row_count']}`",
        f"- missing_operator_field_row_count: `{payload['missing_operator_field_row_count']}`",
        f"- non_approved_result_row_count: `{payload['non_approved_result_row_count']}`",
        f"- missing_evidence_row_count: `{payload['missing_evidence_row_count']}`",
        f"- unsafe_or_missing_target_row_count: `{payload['unsafe_or_missing_target_row_count']}`",
        f"- safety: `{payload['safety']}`",
        "",
        "## Meaning",
        "",
        "- `ready_to_run_after_fill=True` means the fixed safe runner can be launched.",
        "- `row_count=0` with an existing CSV means there are no active remaining operator rows.",
        "- `HOLD` or `NG` is allowed as an operator note, but it is not a final-approved result.",
        "- This checker does not fabricate `operator_result`, `reviewer`, or `reviewed_at`.",
        "",
        "## Row Results",
        "",
        "| Bundle | Scenario | Status | Blockers | Operator Result | Reviewer | Reviewed At |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                str(row.get(key, "")).replace("|", "/")
                for key in [
                    "bundle",
                    "scenario",
                    "status",
                    "blockers",
                    "operator_result",
                    "reviewer",
                    "reviewed_at",
                ]
            )
            + " |"
        )
    excluded_rows = payload.get("excluded_rows", [])
    if excluded_rows:
        lines.extend(
            [
                "",
                "## Excluded Rows",
                "",
                "| Bundle | Scenario | Status | Blockers | Operator Result | Reviewer | Reviewed At |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for row in excluded_rows:
            lines.append(
                "| "
                + " | ".join(
                    str(row.get(key, "")).replace("|", "/")
                    for key in [
                        "bundle",
                        "scenario",
                        "status",
                        "blockers",
                        "operator_result",
                        "reviewer",
                        "reviewed_at",
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "remaining_operator_input_ready_validation.json"
    md_path = out_dir / "remaining_operator_input_ready_validation.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate remaining-operator input before running fixed safe checks."
    )
    parser.add_argument("--remaining-input-csv", type=Path, default=DEFAULT_REMAINING_INPUT_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--scope-exclusions-json", type=Path, default=SCOPE_EXCLUSIONS_JSON)
    parser.add_argument("--fail-on-not-ready", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.remaining_input_csv, scope_exclusions_json=args.scope_exclusions_json)
    write_outputs(payload, args.out_dir)
    print(
        json.dumps(
            {key: value for key, value in payload.items() if key != "rows"},
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.fail_on_not_ready and not payload["ready_to_run_after_fill"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
