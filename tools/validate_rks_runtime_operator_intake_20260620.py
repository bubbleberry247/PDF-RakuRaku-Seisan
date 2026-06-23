"""Validate RK10 RKS runtime operator evidence intake.

This checker only reads the generated RKS operator pack and intake CSV. It
does not open RK10, run RKS files, press ButtonRun, repack RKS ZIP files, or
write production data.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_PACK_JSON = (
    REPORTS / "rks_runtime_operator_pack_20260620" / "rks_runtime_operator_pack.json"
)
DEFAULT_INTAKE_CSV = (
    REPORTS
    / "bundle_evidence_packs_20260620"
    / "rk10_editor_runtime_bundle"
    / "rks_runtime_operator_intake.csv"
)
DEFAULT_OUT_DIR = REPORTS / "rks_runtime_operator_intake_validation_20260620"
ALLOWED_DECISIONS = {
    "OPEN_BUILD_ONLY",
    "SAFE_STOP_ONLY",
    "REGENERATE_SAVE_AS_REQUIRED",
}
CONFIRMED = "CONFIRMED"
YES = "YES"
HARD_ERROR_MARKERS = (
    "Traceback",
    "Unhandled",
    "FATAL",
    "ERROR:",
    "Exception:",
    "RK10_BUILD_NG",
    "LATEST_RUN_ERROR_NG",
)


@dataclass(frozen=True)
class IntakeValidationRow:
    scenario: str
    rks_path: str
    source_status: str
    requires_rk10_evidence: bool
    operator_decision: str
    rk10_editor_open: str
    rk10_build: str
    runtime_or_safe_stop: str
    latest_log_clean: str
    latest_log_path: str
    latest_log_path_exists: bool
    latest_log_has_hard_errors: bool
    save_as_path: str
    save_as_path_exists: bool
    operator_name: str
    checked_at: str
    approved: bool
    issue_codes: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"RKS runtime operator pack JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_intake(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            (
                str(row.get("scenario", "")).strip(),
                str(row.get("rks_path", "")).strip(),
            ): {
                str(key): str(value).strip()
                for key, value in row.items()
                if key is not None
            }
            for row in csv.DictReader(handle)
            if str(row.get("scenario", "")).strip()
        }


def path_exists(value: str) -> bool:
    return bool(value.strip()) and Path(value).exists()


def log_has_hard_errors(value: str) -> bool:
    if not value.strip():
        return False
    path = Path(value)
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return any(marker in text for marker in HARD_ERROR_MARKERS)


def append_if(condition: bool, issues: list[str], code: str) -> None:
    if condition:
        issues.append(code)


def validate_row(source: dict[str, Any], intake_rows: dict[tuple[str, str], dict[str, str]]) -> IntakeValidationRow:
    scenario = str(source.get("scenario", "")).strip()
    rks_path = str(source.get("rks_path", "")).strip()
    key = (scenario, rks_path)
    intake = intake_rows.get(key, {})
    requires_evidence = bool(source.get("requires_rk10_evidence"))
    operator_decision = intake.get("operator_decision", "")
    rk10_editor_open = intake.get("rk10_editor_open", "")
    rk10_build = intake.get("rk10_build", "")
    runtime_or_safe_stop = intake.get("runtime_or_safe_stop", "")
    latest_log_clean = intake.get("latest_log_clean", "")
    latest_log_path = intake.get("latest_log_path", "")
    save_as_path = intake.get("save_as_path", "")
    operator_name = intake.get("operator_name", "")
    checked_at = intake.get("checked_at", "")
    latest_log_exists = path_exists(latest_log_path)
    has_hard_errors = log_has_hard_errors(latest_log_path)
    save_as_exists = path_exists(save_as_path)
    issues: list[str] = []
    if requires_evidence:
        append_if(operator_decision not in ALLOWED_DECISIONS, issues, "OPERATOR_DECISION_MISSING_OR_INVALID")
        append_if(rk10_editor_open != CONFIRMED, issues, "RK10_EDITOR_OPEN_NOT_CONFIRMED")
        append_if(rk10_build != CONFIRMED, issues, "RK10_BUILD_NOT_CONFIRMED")
        append_if(runtime_or_safe_stop != CONFIRMED, issues, "RUNTIME_OR_SAFE_STOP_NOT_CONFIRMED")
        append_if(latest_log_clean != YES, issues, "LATEST_LOG_NOT_MARKED_CLEAN")
        append_if(not latest_log_exists, issues, "LATEST_LOG_PATH_MISSING_OR_NOT_FOUND")
        append_if(has_hard_errors, issues, "LATEST_LOG_HAS_HARD_ERROR_MARKER")
        append_if(not operator_name, issues, "OPERATOR_NAME_MISSING")
        append_if(not checked_at, issues, "CHECKED_AT_MISSING")
        if operator_decision == "REGENERATE_SAVE_AS_REQUIRED":
            append_if(not save_as_exists, issues, "SAVE_AS_PATH_MISSING_OR_NOT_FOUND")
            append_if(save_as_path == rks_path, issues, "SAVE_AS_PATH_SAME_AS_SOURCE_RKS")
    return IntakeValidationRow(
        scenario=scenario,
        rks_path=rks_path,
        source_status=str(source.get("status", "")),
        requires_rk10_evidence=requires_evidence,
        operator_decision=operator_decision,
        rk10_editor_open=rk10_editor_open,
        rk10_build=rk10_build,
        runtime_or_safe_stop=runtime_or_safe_stop,
        latest_log_clean=latest_log_clean,
        latest_log_path=latest_log_path,
        latest_log_path_exists=latest_log_exists,
        latest_log_has_hard_errors=has_hard_errors,
        save_as_path=save_as_path,
        save_as_path_exists=save_as_exists,
        operator_name=operator_name,
        checked_at=checked_at,
        approved=requires_evidence and not issues,
        issue_codes=", ".join(issues),
    )


def build_payload(pack_json: Path, intake_csv: Path) -> dict[str, Any]:
    pack_payload = read_json(pack_json)
    intake_rows = read_intake(intake_csv)
    rows = [
        validate_row(row, intake_rows)
        for row in pack_payload.get("rows", [])
        if isinstance(row, dict)
    ]
    required_rows = [row for row in rows if row.requires_rk10_evidence]
    approved_count = sum(1 for row in required_rows if row.approved)
    needs_attention_count = sum(1 for row in required_rows if not row.approved)
    hard_error_count = sum(1 for row in required_rows if row.latest_log_has_hard_errors)
    missing_latest_log_count = sum(1 for row in required_rows if not row.latest_log_path_exists)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "overall_rks_runtime_evidence_complete": (
            bool(required_rows)
            and approved_count == len(required_rows)
            and hard_error_count == 0
            and missing_latest_log_count == 0
        ),
        "safety": (
            "read-only RKS runtime intake validation only; no RK10 editor/build/runtime, "
            "no ButtonRun, no production write"
        ),
        "pack_json": str(pack_json),
        "intake_csv": str(intake_csv),
        "row_count": len(rows),
        "required_row_count": len(required_rows),
        "approved_row_count": approved_count,
        "needs_attention_count": needs_attention_count,
        "hard_error_count": hard_error_count,
        "missing_latest_log_count": missing_latest_log_count,
        "rows": [asdict(row) for row in rows],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# RKS Runtime Operator Intake Validation 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- overall_rks_runtime_evidence_complete: `{payload['overall_rks_runtime_evidence_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- required_row_count: `{payload['required_row_count']}`",
        f"- approved_row_count: `{payload['approved_row_count']}`",
        f"- needs_attention_count: `{payload['needs_attention_count']}`",
        f"- hard_error_count: `{payload['hard_error_count']}`",
        f"- missing_latest_log_count: `{payload['missing_latest_log_count']}`",
        f"- pack_json: `{payload['pack_json']}`",
        f"- intake_csv: `{payload['intake_csv']}`",
        "",
        "## Strict Rules",
        "",
        "- `OK_CANDIDATE` alone is not accepted as runtime evidence.",
        "- Required rows need RK10 editor open, build, runtime/safe-stop, latest clean log, operator, and checked_at.",
        "- A latest log path must exist and must not contain hard error markers.",
        "- Save As regeneration requires a different existing RKS path.",
        "",
        "## Validation Rows",
        "",
        "| Scenario | Required | Approved | Decision | Latest Log Exists | Hard Errors | Issues |",
        "|---|---:|---:|---|---:|---:|---|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    "YES" if row["requires_rk10_evidence"] else "NO",
                    "YES" if row["approved"] else "NO",
                    str(row["operator_decision"]) or "-",
                    "YES" if row["latest_log_path_exists"] else "NO",
                    "YES" if row["latest_log_has_hard_errors"] else "NO",
                    str(row["issue_codes"]).replace("|", "/") or "-",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "rks_runtime_operator_intake_validation.json"
    md_path = out_dir / "rks_runtime_operator_intake_validation.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate RK10 RKS runtime operator intake.")
    parser.add_argument("--pack-json", type=Path, default=DEFAULT_PACK_JSON)
    parser.add_argument("--intake-csv", type=Path, default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.pack_json, args.intake_csv)
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
