"""Auto-fill minimum operator review rows from Codex safe-check evidence.

This tool records Codex automated evidence confirmation into
minimum_operator_review_input.csv. It only writes operator_result/reviewer/
reviewed_at in the minimum review CSV and emits audit reports. It does not run
RK10, mail, print, submit, pay, call paid OCR, or write production files.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_MINIMUM_CSV = (
    REPORTS / "minimum_operator_review_input_20260623" / "minimum_operator_review_input.csv"
)
DEFAULT_SAFE_SUMMARY_JSON = (
    REPORTS / "safe_goal_checks_20260620" / "safe_goal_checks_summary.json"
)
DEFAULT_SAFE_SUMMARY_MD = (
    REPORTS / "safe_goal_checks_20260620" / "safe_goal_checks_summary.md.numbered"
)
DEFAULT_OUT_DIR = (
    REPORTS / "minimum_operator_review_input_20260623" / "codex_auto_evidence_review"
)
DEFAULT_REVIEWER = "CodexAutoEvidenceCheck"
OPERATOR_FIELDS = ("operator_result", "reviewer", "reviewed_at")
APPROVED_RESULT = "OK"
EXPECTED_OPERATOR_BLOCKER = (
    "MISSING_OPERATOR_FIELDS:operator_result,reviewer,reviewed_at"
)


@dataclass(frozen=True)
class AutoFillRowResult:
    bundle: str
    scenario: str
    status: str
    reason: str
    operator_result: str
    reviewer: str
    reviewed_at: str
    latest_evidence_file: str


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {str(key): str(value).strip() for key, value in row.items() if key is not None}
            for row in reader
        ]
    return fieldnames, rows


def write_csv_rows(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[dict[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def markdown_safe_summary_passed(path: Path) -> bool | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8-sig", errors="replace").lower()
    if "overall_passed: `true`" in text or '"overall_passed": true' in text:
        return True
    if "overall_passed: `false`" in text or '"overall_passed": false' in text:
        return False
    return None


def safe_summary_status(json_path: Path, md_path: Path) -> dict[str, Any]:
    json_payload = read_json(json_path)
    if "overall_passed" in json_payload:
        return {
            "safe_summary_source": str(json_path),
            "safe_summary_exists": True,
            "safe_summary_overall_passed": bool(json_payload.get("overall_passed")),
            "safe_summary_generated_at": str(json_payload.get("generated_at", "")),
        }
    markdown_passed = markdown_safe_summary_passed(md_path)
    return {
        "safe_summary_source": str(md_path),
        "safe_summary_exists": md_path.exists(),
        "safe_summary_overall_passed": bool(markdown_passed),
        "safe_summary_generated_at": "",
    }


def complete_operator_fields(row: dict[str, str]) -> bool:
    return all(row.get(field, "").strip() for field in OPERATOR_FIELDS)


def any_operator_fields(row: dict[str, str]) -> bool:
    return any(row.get(field, "").strip() for field in OPERATOR_FIELDS)


def latest_evidence_exists(row: dict[str, str]) -> bool:
    evidence_file = row.get("latest_evidence_file", "").strip()
    return bool(evidence_file) and Path(evidence_file).exists()


def only_operator_fields_are_blocking(row: dict[str, str]) -> bool:
    blockers = row.get("blockers", "").strip()
    status = row.get("status", "").strip()
    if status and status != "NOT_READY":
        return False
    if not blockers:
        return True
    return blockers == EXPECTED_OPERATOR_BLOCKER


def build_auto_filled_rows(
    rows: Sequence[dict[str, str]],
    reviewer: str,
    reviewed_at: str,
    safe_summary_passed: bool,
) -> tuple[list[dict[str, str]], list[AutoFillRowResult]]:
    next_rows: list[dict[str, str]] = []
    results: list[AutoFillRowResult] = []
    for row in rows:
        next_row = dict(row)
        bundle = row.get("bundle", "").strip()
        scenario = row.get("scenario", "").strip()
        evidence_file = row.get("latest_evidence_file", "").strip()
        if not safe_summary_passed:
            result = AutoFillRowResult(
                bundle,
                scenario,
                "BLOCKED",
                "SAFE_SUMMARY_NOT_PASSED",
                row.get("operator_result", ""),
                row.get("reviewer", ""),
                row.get("reviewed_at", ""),
                evidence_file,
            )
        elif any_operator_fields(row) and not complete_operator_fields(row):
            result = AutoFillRowResult(
                bundle,
                scenario,
                "BLOCKED",
                "PARTIAL_OPERATOR_FIELDS_EXIST",
                row.get("operator_result", ""),
                row.get("reviewer", ""),
                row.get("reviewed_at", ""),
                evidence_file,
            )
        elif complete_operator_fields(row):
            operator_result = row.get("operator_result", "").strip()
            if operator_result != APPROVED_RESULT:
                result = AutoFillRowResult(
                    bundle,
                    scenario,
                    "BLOCKED",
                    f"EXISTING_OPERATOR_RESULT_NOT_{APPROVED_RESULT}",
                    operator_result,
                    row.get("reviewer", ""),
                    row.get("reviewed_at", ""),
                    evidence_file,
                )
            else:
                result = AutoFillRowResult(
                    bundle,
                    scenario,
                    "UNCHANGED",
                    "",
                    operator_result,
                    row.get("reviewer", ""),
                    row.get("reviewed_at", ""),
                    evidence_file,
                )
        elif not latest_evidence_exists(row):
            result = AutoFillRowResult(
                bundle,
                scenario,
                "BLOCKED",
                "LATEST_EVIDENCE_FILE_NOT_FOUND",
                "",
                "",
                "",
                evidence_file,
            )
        elif not only_operator_fields_are_blocking(row):
            result = AutoFillRowResult(
                bundle,
                scenario,
                "BLOCKED",
                "NON_OPERATOR_BLOCKER_PRESENT",
                "",
                "",
                "",
                evidence_file,
            )
        else:
            next_row["operator_result"] = APPROVED_RESULT
            next_row["reviewer"] = reviewer
            next_row["reviewed_at"] = reviewed_at
            result = AutoFillRowResult(
                bundle,
                scenario,
                "UPDATED",
                "",
                APPROVED_RESULT,
                reviewer,
                reviewed_at,
                evidence_file,
            )
        next_rows.append(next_row)
        results.append(result)
    return next_rows, results


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Codex Auto Evidence Review",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- dry_run: `{payload['dry_run']}`",
        f"- ready_to_write: `{payload['ready_to_write']}`",
        f"- minimum_csv_exists: `{payload['minimum_csv_exists']}`",
        f"- safe_summary_overall_passed: `{payload['safe_summary_overall_passed']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- already_complete: `{payload['already_complete']}`",
        f"- updated_count: `{payload['updated_count']}`",
        f"- unchanged_count: `{payload['unchanged_count']}`",
        f"- blocked_count: `{payload['blocked_count']}`",
        f"- backup_path: `{payload['backup_path']}`",
        "",
        "## Safety",
        "",
        "- This records Codex automated evidence confirmation only.",
        "- It only writes operator_result/reviewer/reviewed_at in minimum_operator_review_input.csv.",
        "- It does not run RK10, send mail, print, submit, pay, call paid OCR, or write production files.",
        "- OK means the latest fixed safe-check summary passed and the row has an existing latest evidence file.",
        "",
        "## Row Results",
        "",
        "| bundle | scenario | status | reason | latest_evidence_file |",
        "|---|---|---|---|---|",
    ]
    for row in payload["row_results"]:
        lines.append(
            "| "
            + " | ".join(
                str(row.get(field, "")).replace("|", "/")
                for field in [
                    "bundle",
                    "scenario",
                    "status",
                    "reason",
                    "latest_evidence_file",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "codex_auto_evidence_review.json"
    md_path = out_dir / "codex_auto_evidence_review.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)


def build_payload(
    minimum_csv: Path = DEFAULT_MINIMUM_CSV,
    safe_summary_json: Path = DEFAULT_SAFE_SUMMARY_JSON,
    safe_summary_md: Path = DEFAULT_SAFE_SUMMARY_MD,
    out_dir: Path = DEFAULT_OUT_DIR,
    reviewer: str = DEFAULT_REVIEWER,
    reviewed_at: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    reviewed_at = reviewed_at or datetime.now().isoformat(timespec="seconds")
    minimum_csv_exists = minimum_csv.exists()
    fieldnames, rows = read_csv_rows(minimum_csv)
    safe_status = safe_summary_status(safe_summary_json, safe_summary_md)
    next_rows, row_results = build_auto_filled_rows(
        rows,
        reviewer,
        reviewed_at,
        bool(safe_status["safe_summary_overall_passed"]),
    )
    blocked_count = sum(1 for row in row_results if row.status == "BLOCKED")
    updated_count = sum(1 for row in row_results if row.status == "UPDATED")
    unchanged_count = sum(1 for row in row_results if row.status == "UNCHANGED")
    already_complete = minimum_csv_exists and not rows
    ready_to_write = minimum_csv_exists and blocked_count == 0
    backup_path = ""
    if ready_to_write and updated_count and not dry_run:
        backup = minimum_csv.with_name(
            minimum_csv.name
            + ".before_codex_auto_evidence_review_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        shutil.copy2(minimum_csv, backup)
        backup_path = str(backup)
        write_csv_rows(minimum_csv, fieldnames, next_rows)
        write_numbered_copy(minimum_csv)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "minimum_csv": str(minimum_csv),
        "minimum_csv_exists": minimum_csv_exists,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "row_count": len(rows),
        "already_complete": already_complete,
        "updated_count": updated_count if not dry_run else 0,
        "would_update_count": updated_count if dry_run else 0,
        "unchanged_count": unchanged_count,
        "blocked_count": blocked_count,
        "ready_to_write": ready_to_write,
        "backup_path": backup_path,
        "out_dir": str(out_dir),
        "safety": (
            "writes minimum review CSV operator fields only; no RK10 ButtonRun; "
            "no production write; no mail; no print; no submit; no payment; "
            "no paid Azure OCR"
        ),
        "row_results": [asdict(row) for row in row_results],
        **safe_status,
    }
    write_outputs(payload, out_dir)
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auto-fill minimum operator review input from Codex safe evidence."
    )
    parser.add_argument("--minimum-csv", type=Path, default=DEFAULT_MINIMUM_CSV)
    parser.add_argument("--safe-summary-json", type=Path, default=DEFAULT_SAFE_SUMMARY_JSON)
    parser.add_argument("--safe-summary-md", type=Path, default=DEFAULT_SAFE_SUMMARY_MD)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--reviewed-at", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        minimum_csv=args.minimum_csv,
        safe_summary_json=args.safe_summary_json,
        safe_summary_md=args.safe_summary_md,
        out_dir=args.out_dir,
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at or None,
        dry_run=args.dry_run,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ready_to_write"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
