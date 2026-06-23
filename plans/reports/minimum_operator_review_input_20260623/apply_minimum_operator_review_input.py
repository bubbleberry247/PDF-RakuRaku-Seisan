"""Apply minimum operator-review input to the full remaining-operator CSV.

This helper only copies filled operator_result/reviewer/reviewed_at values
from minimum_operator_review_input.csv into exact bundle+scenario rows in
remaining_operator_input.csv. It creates a backup before writing and never
creates approval values by itself.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
REPORTS = SCRIPT_DIR.parent
ROOT = REPORTS.parent.parent
VALIDATION_TOOL = ROOT / "tools" / "validate_remaining_operator_input_ready_20260623.py"
DEFAULT_MINIMUM_CSV = SCRIPT_DIR / "minimum_operator_review_input.csv"
DEFAULT_TARGET_CSV = REPORTS / "remaining_operator_input_packet_20260623" / "remaining_operator_input.csv"
DEFAULT_OUT_DIR = SCRIPT_DIR / "apply_results"
OPERATOR_FIELDS = ("operator_result", "reviewer", "reviewed_at")
ALLOWED_RESULTS = {"OK", "NG", "HOLD"}


@dataclass(frozen=True)
class ApplyRowResult:
    bundle: str
    scenario: str
    status: str
    updated_fields: str
    reason: str


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {str(key): str(value).strip() for key, value in row.items() if key is not None}
            for row in reader
        ]
    return fieldnames, rows


def write_csv_rows(path: Path, fieldnames: Sequence[str], rows: Sequence[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def key_for(row: dict[str, str]) -> tuple[str, str]:
    return row.get("bundle", "").strip(), row.get("scenario", "").strip()


def complete_operator_fields(row: dict[str, str]) -> bool:
    return all(row.get(field, "").strip() for field in OPERATOR_FIELDS)


def any_operator_fields(row: dict[str, str]) -> bool:
    return any(row.get(field, "").strip() for field in OPERATOR_FIELDS)


def apply_rows(
    minimum_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    apply_updates: bool,
) -> tuple[list[dict[str, str]], list[ApplyRowResult]]:
    target_by_key = {key_for(row): row for row in target_rows}
    next_rows = [dict(row) for row in target_rows]
    next_by_key = {key_for(row): row for row in next_rows}
    results: list[ApplyRowResult] = []

    for minimum_row in minimum_rows:
        bundle, scenario = key_for(minimum_row)
        if not bundle or not scenario:
            continue
        target_row = next_by_key.get((bundle, scenario))
        if target_row is None:
            results.append(ApplyRowResult(bundle, scenario, "SKIPPED", "", "TARGET_ROW_NOT_FOUND"))
            continue
        if not any_operator_fields(minimum_row):
            results.append(ApplyRowResult(bundle, scenario, "SKIPPED", "", "NO_OPERATOR_FIELDS_FILLED"))
            continue
        if not complete_operator_fields(minimum_row):
            results.append(ApplyRowResult(bundle, scenario, "ERROR", "", "PARTIAL_OPERATOR_FIELDS"))
            continue
        result_value = minimum_row.get("operator_result", "").strip()
        if result_value not in ALLOWED_RESULTS:
            results.append(ApplyRowResult(bundle, scenario, "ERROR", "", f"INVALID_OPERATOR_RESULT:{result_value}"))
            continue
        updated_fields: list[str] = []
        conflict_field = ""
        for field in OPERATOR_FIELDS:
            current_value = target_row.get(field, "").strip()
            next_value = minimum_row.get(field, "").strip()
            if current_value and current_value != next_value:
                conflict_field = field
                break
            if not current_value and next_value:
                updated_fields.append(field)
        if conflict_field:
            results.append(ApplyRowResult(bundle, scenario, "ERROR", "", f"CONFLICT_{conflict_field}"))
            continue
        if apply_updates:
            for field in OPERATOR_FIELDS:
                target_row[field] = minimum_row.get(field, "").strip()
        results.append(
            ApplyRowResult(
                bundle=bundle,
                scenario=scenario,
                status="UPDATED" if updated_fields else "UNCHANGED",
                updated_fields=",".join(updated_fields),
                reason="",
            )
        )
    return next_rows, results


def build_apply_summary(
    minimum_rows: list[dict[str, str]],
    row_results: list[ApplyRowResult],
    target_row_count: int | None = None,
) -> dict[str, int | bool]:
    error_count = sum(1 for row in row_results if row.status == "ERROR")
    skipped_count = sum(1 for row in row_results if row.status == "SKIPPED")
    blocking_result_count = error_count + skipped_count
    updated_count = sum(1 for row in row_results if row.status == "UPDATED")
    complete_input_count = sum(1 for row in minimum_rows if complete_operator_fields(row))
    incomplete_input_count = len(minimum_rows) - complete_input_count
    no_remaining_rows = not minimum_rows and target_row_count == 0
    ready_to_apply = (
        no_remaining_rows
        or (bool(minimum_rows) and blocking_result_count == 0 and incomplete_input_count == 0)
    )
    return {
        "error_count": error_count,
        "skipped_count": skipped_count,
        "blocking_result_count": blocking_result_count,
        "updated_count": updated_count,
        "target_row_count": target_row_count if target_row_count is not None else -1,
        "complete_input_count": complete_input_count,
        "incomplete_input_count": incomplete_input_count,
        "ready_to_apply": ready_to_apply,
    }


def run_validation(target_csv: Path, out_dir: Path) -> dict[str, str | int]:
    validation_stdout = out_dir / "post_apply_validation.stdout.txt"
    validation_stderr = out_dir / "post_apply_validation.stderr.txt"
    if not VALIDATION_TOOL.exists():
        validation_stdout.write_text("", encoding="utf-8")
        validation_stderr.write_text(
            f"VALIDATION_TOOL_NOT_FOUND: {VALIDATION_TOOL}\n",
            encoding="utf-8",
        )
        write_numbered_copy(validation_stdout)
        write_numbered_copy(validation_stderr)
        return {
            "validation_exit_code": 2,
            "validation_stdout": str(validation_stdout),
            "validation_stderr": str(validation_stderr),
        }

    command = [
        sys.executable,
        "-X",
        "utf8",
        str(VALIDATION_TOOL),
        "--remaining-input-csv",
        str(target_csv),
        "--out-dir",
        str(out_dir / "validation"),
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    validation_stdout.write_text(completed.stdout, encoding="utf-8")
    validation_stderr.write_text(completed.stderr, encoding="utf-8")
    write_numbered_copy(validation_stdout)
    write_numbered_copy(validation_stderr)
    return {
        "validation_exit_code": completed.returncode,
        "validation_stdout": str(validation_stdout),
        "validation_stderr": str(validation_stderr),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply minimum operator review input.")
    parser.add_argument("--minimum-csv", type=Path, default=DEFAULT_MINIMUM_CSV)
    parser.add_argument("--target-csv", type=Path, default=DEFAULT_TARGET_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    minimum_fieldnames, minimum_rows = read_csv_rows(args.minimum_csv)
    target_fieldnames, target_rows = read_csv_rows(args.target_csv)
    next_rows, row_results = apply_rows(minimum_rows, target_rows, apply_updates=not args.dry_run)
    summary = build_apply_summary(minimum_rows, row_results, len(target_rows))
    error_count = int(summary["error_count"])
    updated_count = int(summary["updated_count"])
    ready_to_apply = bool(summary["ready_to_apply"])
    backup_path = ""

    if ready_to_apply and not args.dry_run and updated_count:
        backup = args.target_csv.with_name(
            args.target_csv.name + ".before_minimum_review_apply_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        shutil.copy2(args.target_csv, backup)
        backup_path = str(backup)
        write_csv_rows(args.target_csv, target_fieldnames, next_rows)
        write_numbered_copy(args.target_csv)

    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": "copies filled operator fields only; no approval creation inside apply; no RK10 run; no mail; no print; no submit; no payment",
        "dry_run": args.dry_run,
        "minimum_csv": str(args.minimum_csv),
        "target_csv": str(args.target_csv),
        "minimum_row_count": len(minimum_rows),
        "target_row_count": len(target_rows),
        "complete_input_count": summary["complete_input_count"],
        "incomplete_input_count": summary["incomplete_input_count"],
        "skipped_count": summary["skipped_count"],
        "blocking_result_count": summary["blocking_result_count"],
        "ready_to_apply": ready_to_apply,
        "updated_count": updated_count if not args.dry_run and ready_to_apply else 0,
        "would_update_count": updated_count if args.dry_run and ready_to_apply else 0,
        "error_count": error_count,
        "backup_path": backup_path,
        "row_results": [asdict(row) for row in row_results],
    }
    result.update(run_validation(args.target_csv, args.out_dir))
    json_path = args.out_dir / "minimum_operator_review_apply_result.json"
    md_path = args.out_dir / "minimum_operator_review_apply_result.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Minimum Operator Review Apply Result",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- dry_run: `{result['dry_run']}`",
        f"- minimum_row_count: `{result['minimum_row_count']}`",
        f"- complete_input_count: `{result['complete_input_count']}`",
        f"- incomplete_input_count: `{result['incomplete_input_count']}`",
        f"- skipped_count: `{result['skipped_count']}`",
        f"- blocking_result_count: `{result['blocking_result_count']}`",
        f"- ready_to_apply: `{result['ready_to_apply']}`",
        f"- updated_count: `{result['updated_count']}`",
        f"- would_update_count: `{result['would_update_count']}`",
        f"- error_count: `{result['error_count']}`",
        f"- backup_path: `{result['backup_path']}`",
        f"- validation_exit_code: `{result['validation_exit_code']}`",
        "",
        "## Row Results",
        "| bundle | scenario | status | updated_fields | reason |",
        "|---|---|---|---|---|",
    ]
    for row in row_results:
        lines.append(f"| `{row.bundle}` | `{row.scenario}` | `{row.status}` | `{row.updated_fields}` | `{row.reason}` |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ready_to_apply and result["validation_exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
