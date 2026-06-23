"""Sync confirmed RK10 status-gate evidence into runtime intake CSVs.

This tool imports only already-recorded status-gate reports that explicitly
prove RK10 editor open, RK10 build, runtime/safe-stop, and latest clean log.
It does not open RK10, build or run RKS files, press ButtonRun, repack RKS
files, or write production data.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_STATIC_AUDIT_JSON = (
    REPORTS / "rks_static_guard_audit_20260620" / "rks_static_guard_audit.json"
)
DEFAULT_OUT_INTAKE_CSV = (
    REPORTS / "rks_runtime_operator_pack_20260620" / "rks_runtime_operator_intake.csv"
)
DEFAULT_BUNDLE_INTAKE_CSV = (
    REPORTS
    / "bundle_evidence_packs_20260620"
    / "rk10_editor_runtime_bundle"
    / "rks_runtime_operator_intake.csv"
)
DEFAULT_OUT_DIR = REPORTS / "rks_runtime_status_gate_sync_20260620"
S57_OPEN_BUILD_SUMMARY_TSV = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\s57_current_rks_editor_open_build_probe_20260618_103111\summary.tsv"
)
DEFAULT_PARTIAL_OPEN_BUILD_TSVS = (S57_OPEN_BUILD_SUMMARY_TSV,)
REQUIRED_COLUMNS = [
    "scenario",
    "rks_path",
    "operator_decision",
    "rk10_editor_open",
    "rk10_build",
    "runtime_or_safe_stop",
    "latest_log_clean",
    "latest_log_path",
    "save_as_path",
    "operator_name",
    "checked_at",
    "notes",
]
OPERATOR_INPUT_COLUMNS = REQUIRED_COLUMNS[2:]
CONFIRMED_STATUS = "OK_FOR_SAFE_STOP_TEST"


@dataclass(frozen=True)
class StatusGateEvidence:
    scenario: str
    rks_path: str
    status_gate_path: str
    created_at: str
    final_status: str
    rk10_editor_open_confirmed: bool
    rk10_build_confirmed: bool
    runtime_or_safe_stop_confirmed: bool
    latest_log_clean: bool
    scope: str
    importable: bool
    reason: str


@dataclass(frozen=True)
class PartialOpenBuildEvidence:
    scenario: str
    rks_path: str
    evidence_path: str
    checked_at: str
    rk10_editor_open_confirmed: bool
    rk10_build_confirmed: bool
    importable: bool
    reason: str


@dataclass(frozen=True)
class SyncResult:
    intake_csv: str
    intake_exists: bool
    row_count: int
    updated_count: int
    partial_updated_count: int
    preserved_manual_count: int


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"static audit JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def match_backtick_value(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def status_line_confirmed(label: str, text: str) -> bool:
    pattern = rf"- {re.escape(label)}:\s*`confirmed`"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def parse_status_gate(scenario: str, rks_path: str, status_gate_path: str) -> StatusGateEvidence:
    path = Path(status_gate_path)
    if not path.exists():
        return StatusGateEvidence(
            scenario=scenario,
            rks_path=rks_path,
            status_gate_path=status_gate_path,
            created_at="",
            final_status="",
            rk10_editor_open_confirmed=False,
            rk10_build_confirmed=False,
            runtime_or_safe_stop_confirmed=False,
            latest_log_clean=False,
            scope="",
            importable=False,
            reason="STATUS_GATE_FILE_NOT_FOUND",
        )
    text = path.read_text(encoding="utf-8", errors="replace")
    created_at = match_backtick_value(r"Created:\s*([^\r\n]+)", text)
    final_status = match_backtick_value(r"Final status:\s*`([^`]+)`", text)
    file_path = match_backtick_value(r"File:\s*`([^`]+)`", text)
    scope = match_backtick_value(r"- Scope:\s*`([^`]+)`", text)
    editor_confirmed = status_line_confirmed("RK10 editor open", text)
    build_confirmed = status_line_confirmed("RK10 build", text)
    runtime_confirmed = status_line_confirmed("Runtime / safe-stop", text)
    latest_clean = re.search(r"- Latest log:\s*`clean`", text, flags=re.IGNORECASE) is not None
    file_matches = not file_path or file_path == rks_path
    importable = (
        final_status == CONFIRMED_STATUS
        and editor_confirmed
        and build_confirmed
        and runtime_confirmed
        and latest_clean
        and scope == "safe-stop"
        and file_matches
    )
    reason = "IMPORTABLE" if importable else "STATUS_GATE_NOT_STRONG_ENOUGH"
    if not file_matches:
        reason = "STATUS_GATE_RKS_PATH_MISMATCH"
    return StatusGateEvidence(
        scenario=scenario,
        rks_path=rks_path,
        status_gate_path=status_gate_path,
        created_at=created_at,
        final_status=final_status,
        rk10_editor_open_confirmed=editor_confirmed,
        rk10_build_confirmed=build_confirmed,
        runtime_or_safe_stop_confirmed=runtime_confirmed,
        latest_log_clean=latest_clean,
        scope=scope,
        importable=importable,
        reason=reason,
    )


def build_evidence_rows(static_audit_json: Path) -> list[StatusGateEvidence]:
    payload = read_json(static_audit_json)
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise TypeError("static audit rows must be a list")
    evidence_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("existing_status_gate_status", "")) != CONFIRMED_STATUS:
            continue
        evidence_rows.append(
            parse_status_gate(
                scenario=str(row.get("scenario", "")).strip(),
                rks_path=str(row.get("rks_path", "")).strip(),
                status_gate_path=str(row.get("existing_status_gate_evidence", "")).strip(),
            )
        )
    return evidence_rows


def truthy(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "1", "ok"}


def checked_at_from_file(path: Path) -> str:
    if not path.exists():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def build_partial_open_build_rows(tsv_paths: tuple[Path, ...]) -> list[PartialOpenBuildEvidence]:
    evidence_rows: list[PartialOpenBuildEvidence] = []
    for path in tsv_paths:
        if not path.exists():
            evidence_rows.append(
                PartialOpenBuildEvidence(
                    scenario="",
                    rks_path="",
                    evidence_path=str(path),
                    checked_at="",
                    rk10_editor_open_confirmed=False,
                    rk10_build_confirmed=False,
                    importable=False,
                    reason="PARTIAL_OPEN_BUILD_FILE_NOT_FOUND",
                )
            )
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                scenario = str(row.get("scenario", "")).strip()
                rks_path = str(row.get("rks", "")).strip()
                editor_confirmed = (
                    str(row.get("editor_status", "")).strip()
                    == "RK10_EDITOR_OPEN_CONFIRMED"
                )
                build_confirmed = truthy(str(row.get("build_artifact_found", "")))
                guard_ok = str(row.get("guard_rc", "")).strip() == "0"
                importable = bool(scenario and rks_path and guard_ok and editor_confirmed and build_confirmed)
                evidence_rows.append(
                    PartialOpenBuildEvidence(
                        scenario=scenario,
                        rks_path=rks_path,
                        evidence_path=str(path),
                        checked_at=checked_at_from_file(path),
                        rk10_editor_open_confirmed=editor_confirmed,
                        rk10_build_confirmed=build_confirmed,
                        importable=importable,
                        reason="PARTIAL_OPEN_BUILD_IMPORTABLE"
                        if importable
                        else "PARTIAL_OPEN_BUILD_NOT_STRONG_ENOUGH",
                    )
                )
    return evidence_rows


def intake_key(row: dict[str, str]) -> tuple[str, str]:
    return str(row.get("scenario", "")).strip(), str(row.get("rks_path", "")).strip()


def has_operator_input(row: dict[str, str]) -> bool:
    return any(str(row.get(field, "")).strip() for field in OPERATOR_INPUT_COLUMNS)


def evidence_to_intake_fields(evidence: StatusGateEvidence) -> dict[str, str]:
    checked_at = evidence.created_at or datetime.now().isoformat(timespec="seconds")
    return {
        "operator_decision": "SAFE_STOP_ONLY",
        "rk10_editor_open": "CONFIRMED",
        "rk10_build": "CONFIRMED",
        "runtime_or_safe_stop": "CONFIRMED",
        "latest_log_clean": "YES",
        "latest_log_path": evidence.status_gate_path,
        "save_as_path": "",
        "operator_name": "status_gate_import_20260618",
        "checked_at": checked_at,
        "notes": "Auto-imported from existing RK10 status-gate safe-stop evidence.",
    }


def partial_open_build_to_intake_fields(evidence: PartialOpenBuildEvidence) -> dict[str, str]:
    return {
        "rk10_editor_open": "CONFIRMED",
        "rk10_build": "CONFIRMED",
        "operator_name": "open_build_probe_import_20260618",
        "checked_at": evidence.checked_at,
        "notes": (
            "Partial auto-import: RK10 editor open/build confirmed only from "
            f"{evidence.evidence_path}. Runtime/safe-stop and latest clean log still required."
        ),
    }


def merge_blank_fields(row: dict[str, str], fields_to_import: dict[str, str]) -> tuple[dict[str, str], bool]:
    changed = False
    merged = dict(row)
    for field, value in fields_to_import.items():
        if not value:
            continue
        if str(merged.get(field, "")).strip():
            continue
        merged[field] = value
        changed = True
    return merged, changed


def read_intake_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {str(key): str(value or "") for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def write_intake_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(
            {column: row.get(column, "") for column in REQUIRED_COLUMNS}
            for row in rows
        )


def sync_intake(path: Path, importable_evidence: dict[tuple[str, str], StatusGateEvidence]) -> SyncResult:
    return sync_intake_with_partial(path, importable_evidence, {})


def sync_intake_with_partial(
    path: Path,
    importable_evidence: dict[tuple[str, str], StatusGateEvidence],
    partial_open_build_evidence: dict[tuple[str, str], PartialOpenBuildEvidence],
) -> SyncResult:
    if not path.exists():
        return SyncResult(str(path), False, 0, 0, 0, 0)
    rows = read_intake_rows(path)
    updated_rows = []
    updated_count = 0
    partial_updated_count = 0
    preserved_manual_count = 0
    for row in rows:
        evidence = importable_evidence.get(intake_key(row))
        if evidence is None:
            partial_evidence = partial_open_build_evidence.get(intake_key(row))
            if partial_evidence is not None:
                merged_row, changed = merge_blank_fields(
                    row,
                    partial_open_build_to_intake_fields(partial_evidence),
                )
                if changed:
                    partial_updated_count += 1
                updated_rows.append(merged_row)
                continue
            updated_rows.append(row)
            continue
        if has_operator_input(row):
            preserved_manual_count += 1
            updated_rows.append(row)
            continue
        updated_rows.append({**row, **evidence_to_intake_fields(evidence)})
        updated_count += 1
    write_intake_rows(path, updated_rows)
    return SyncResult(
        intake_csv=str(path),
        intake_exists=True,
        row_count=len(rows),
        updated_count=updated_count,
        partial_updated_count=partial_updated_count,
        preserved_manual_count=preserved_manual_count,
    )


def build_payload(
    static_audit_json: Path,
    out_intake_csv: Path,
    bundle_intake_csv: Path,
    partial_open_build_tsvs: tuple[Path, ...] = DEFAULT_PARTIAL_OPEN_BUILD_TSVS,
) -> dict[str, Any]:
    evidence_rows = build_evidence_rows(static_audit_json)
    importable = {
        (row.scenario, row.rks_path): row
        for row in evidence_rows
        if row.importable
    }
    partial_open_build_rows = build_partial_open_build_rows(partial_open_build_tsvs)
    partial_open_build_importable = {
        (row.scenario, row.rks_path): row
        for row in partial_open_build_rows
        if row.importable
    }
    sync_results = [
        sync_intake_with_partial(
            out_intake_csv,
            importable,
            partial_open_build_importable,
        ),
        sync_intake_with_partial(
            bundle_intake_csv,
            importable,
            partial_open_build_importable,
        ),
    ]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": (
            "read existing status-gate reports and update runtime intake CSVs only; "
            "no RK10 editor/build/runtime, no ButtonRun, no production write"
        ),
        "static_audit_json": str(static_audit_json),
        "candidate_status_gate_count": len(evidence_rows),
        "importable_status_gate_count": len(importable),
        "candidate_partial_open_build_count": len(partial_open_build_rows),
        "importable_partial_open_build_count": len(partial_open_build_importable),
        "updated_intake_count": sum(result.updated_count for result in sync_results),
        "partial_updated_intake_count": sum(result.partial_updated_count for result in sync_results),
        "preserved_manual_count": sum(result.preserved_manual_count for result in sync_results),
        "evidence_rows": [asdict(row) for row in evidence_rows],
        "partial_open_build_rows": [asdict(row) for row in partial_open_build_rows],
        "sync_results": [asdict(result) for result in sync_results],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# RKS Runtime Status-Gate Sync 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- candidate_status_gate_count: `{payload['candidate_status_gate_count']}`",
        f"- importable_status_gate_count: `{payload['importable_status_gate_count']}`",
        f"- candidate_partial_open_build_count: `{payload['candidate_partial_open_build_count']}`",
        f"- importable_partial_open_build_count: `{payload['importable_partial_open_build_count']}`",
        f"- updated_intake_count: `{payload['updated_intake_count']}`",
        f"- partial_updated_intake_count: `{payload['partial_updated_intake_count']}`",
        f"- preserved_manual_count: `{payload['preserved_manual_count']}`",
        f"- static_audit_json: `{payload['static_audit_json']}`",
        "",
        "## Import Rules",
        "",
        "- `Final status` must be `OK_FOR_SAFE_STOP_TEST`.",
        "- RK10 editor open, RK10 build, runtime/safe-stop, and latest clean log must all be confirmed.",
        "- Existing manual operator input is never overwritten.",
        "- This imports safe-stop evidence only; it is not production execution evidence.",
        "- Partial open/build evidence may fill only RK10 editor open/build helper fields; runtime/safe-stop and latest clean log remain required.",
        "",
        "## Evidence Rows",
        "",
        "| Scenario | Importable | Final Status | Scope | Reason | Status Gate |",
        "|---|---:|---|---|---|---|",
    ]
    for row in payload["evidence_rows"]:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    "YES" if row["importable"] else "NO",
                    str(row["final_status"]) or "-",
                    str(row["scope"]) or "-",
                    str(row["reason"]).replace("|", "/"),
                    f"`{row['status_gate_path']}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Partial Open/Build Evidence Rows",
            "",
            "| Scenario | Importable | Editor Open | Build | Reason | Evidence |",
            "|---|---:|---:|---:|---|---|",
        ]
    )
    for row in payload["partial_open_build_rows"]:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]) or "-",
                    "YES" if row["importable"] else "NO",
                    "YES" if row["rk10_editor_open_confirmed"] else "NO",
                    "YES" if row["rk10_build_confirmed"] else "NO",
                    str(row["reason"]).replace("|", "/"),
                    f"`{row['evidence_path']}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Sync Results",
            "",
            "| Intake CSV | Exists | Rows | Updated | Partial Updated | Preserved Manual |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["sync_results"]:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['intake_csv']}`",
                    "YES" if row["intake_exists"] else "NO",
                    str(row["row_count"]),
                    str(row["updated_count"]),
                    str(row["partial_updated_count"]),
                    str(row["preserved_manual_count"]),
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
    json_path = out_dir / "rks_runtime_status_gate_sync.json"
    md_path = out_dir / "rks_runtime_status_gate_sync.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync RKS status-gate evidence into runtime intake CSVs.")
    parser.add_argument("--static-audit-json", type=Path, default=DEFAULT_STATIC_AUDIT_JSON)
    parser.add_argument("--out-intake-csv", type=Path, default=DEFAULT_OUT_INTAKE_CSV)
    parser.add_argument("--bundle-intake-csv", type=Path, default=DEFAULT_BUNDLE_INTAKE_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        static_audit_json=args.static_audit_json,
        out_intake_csv=args.out_intake_csv,
        bundle_intake_csv=args.bundle_intake_csv,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
