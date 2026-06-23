"""Generate a current completion audit for the active RK10 validation goal.

This report replaces the older static audit with a generated, source-backed
snapshot. It reads repository reports only and writes repository reports only;
it does not operate Outlook, RK10, Rakuraku, Azure, printers, mail, payment
systems, MainSV, or production files.
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
DEFAULT_OUT_DIR = REPORTS / "goal_completion_audit_20260620"

DEFAULT_SOURCES = {
    "status_snapshot": REPORTS / "goal_status_snapshot_20260620" / "goal_status_snapshot.json",
    "evidence_ledger": REPORTS / "goal_evidence_ledger_20260620" / "goal_evidence_ledger.json",
    "packet_validation": REPORTS
    / "goal_execution_packet_validation_20260620"
    / "goal_execution_packet_validation.json",
    "bundle_evidence_pack_validation": REPORTS
    / "bundle_evidence_pack_validation_20260620"
    / "bundle_evidence_pack_validation.json",
    "rks_matrix": REPORTS / "rks_gate_matrix_20260620" / "rks_gate_matrix.json",
    "rks_runtime_intake_validation": REPORTS
    / "rks_runtime_operator_intake_validation_20260620"
    / "rks_runtime_operator_intake_validation.json",
    "business_cost_map": REPORTS
    / "business_cost_evidence_map_20260620"
    / "business_cost_evidence_map.json",
    "code_artifact_backup": REPORTS
    / "goal_code_artifact_backups_20260620"
    / "goal_code_artifact_backups.json",
}

ISSUE_CSV_FIELDS = [
    "scenario",
    "current_status",
    "root_cause_class",
    "countermeasure_or_next_verification",
    "source",
    "source_exists",
]


@dataclass(frozen=True)
class IssueAuditRow:
    scenario: str
    current_status: str
    root_cause_class: str
    countermeasure_or_next_verification: str
    source: str
    source_exists: bool


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def classify_root_cause(scenario: str, current_status: str, remaining_gate: str) -> str:
    status_text = f"{current_status} {remaining_gate}".upper()
    if scenario == "12/13" or "OUTLOOK" in status_text or "COM" in status_text:
        return "OUTLOOK_COM_ENVIRONMENT_HOLD"
    if "RKS" in status_text and ("NG" in status_text or "UNCONFIRMED" in status_text):
        return "RKS_OPEN_BUILD_RUNTIME_EVIDENCE_GAP"
    if "NO_CONFIRMED_ROWS" in status_text or "REVIEW" in status_text:
        return "BUSINESS_REVIEW_INPUT_MISSING"
    if "PAYMENT" in status_text or "BANK" in status_text or "APPROVER" in status_text:
        return "PAYMENT_APPROVAL_EVIDENCE_MISSING"
    if "AZURE" in status_text or "OCR" in status_text:
        return "PAID_OCR_CREDENTIAL_OR_BUDGET_GATE"
    if "FINAL" in status_text or "PENDING" in status_text:
        return "FINAL_OPERATOR_EVIDENCE_MISSING"
    return "OPEN_PROOF_GAP"


def build_issue_rows(status_snapshot: dict[str, Any]) -> list[IssueAuditRow]:
    rows: list[IssueAuditRow] = []
    for item in status_snapshot.get("scenarios", []):
        if not isinstance(item, dict):
            continue
        scenario = str(item.get("scenario", ""))
        current_status = str(item.get("current_status", ""))
        remaining_gate = str(item.get("remaining_gate", ""))
        next_action = str(item.get("next_action", ""))
        if not scenario or current_status in {"COMPLETE", "GOAL_COMPLETE"}:
            continue
        rows.append(
            IssueAuditRow(
                scenario=scenario,
                current_status=current_status,
                root_cause_class=classify_root_cause(scenario, current_status, remaining_gate),
                countermeasure_or_next_verification=next_action or remaining_gate,
                source=str(item.get("source", "")),
                source_exists=bool(item.get("source_exists", False)),
            )
        )
    return rows


def build_validation_summary(
    packet_validation: dict[str, Any],
    bundle_validation: dict[str, Any],
    rks_matrix: dict[str, Any],
    rks_runtime_validation: dict[str, Any],
    business_cost_map: dict[str, Any],
    code_backup: dict[str, Any],
) -> dict[str, Any]:
    business_rows = business_cost_map.get("rows", [])
    amount_verified_count = sum(
        1
        for row in business_rows
        if isinstance(row, dict) and row.get("validation_result") == "PASS"
    )
    return {
        "packet_approved_row_count": int(packet_validation.get("approved_row_count", 0) or 0),
        "packet_needs_attention_count": int(packet_validation.get("needs_attention_count", 0) or 0),
        "bundle_final_evidence_ready_count": int(bundle_validation.get("final_evidence_ready_count", 0) or 0),
        "bundle_count": int(bundle_validation.get("bundle_count", 0) or 0),
        "rks_unresolved_gate_count": int(rks_matrix.get("unresolved_rks_gate_count", 0) or 0),
        "rks_runtime_approved_count": int(rks_runtime_validation.get("approved_row_count", 0) or 0),
        "rks_runtime_required_count": int(rks_runtime_validation.get("required_row_count", 0) or 0),
        "rks_runtime_hard_error_count": int(rks_runtime_validation.get("hard_error_count", 0) or 0),
        "amount_verified_scenario_count": amount_verified_count,
        "code_backup_complete": code_backup.get("backup_complete") is True,
        "code_backup_artifact_count": int(code_backup.get("artifact_count", 0) or 0),
        "code_backup_missing_count": int(code_backup.get("missing_count", 0) or 0),
    }


def build_payload(sources: dict[str, Path] | None = None) -> dict[str, Any]:
    source_paths = sources or DEFAULT_SOURCES
    status_snapshot = read_json(source_paths["status_snapshot"])
    evidence_ledger = read_json(source_paths["evidence_ledger"])
    packet_validation = read_json(source_paths["packet_validation"])
    bundle_validation = read_json(source_paths["bundle_evidence_pack_validation"])
    rks_matrix = read_json(source_paths["rks_matrix"])
    rks_runtime_validation = read_json(source_paths["rks_runtime_intake_validation"])
    business_cost_map = read_json(source_paths["business_cost_map"])
    code_backup = read_json(source_paths["code_artifact_backup"])
    issue_rows = build_issue_rows(status_snapshot)
    validation_summary = build_validation_summary(
        packet_validation,
        bundle_validation,
        rks_matrix,
        rks_runtime_validation,
        business_cost_map,
        code_backup,
    )
    missing_sources = [
        {"label": label, "path": str(path)}
        for label, path in source_paths.items()
        if not path.exists()
    ]
    final_goal_complete = (
        status_snapshot.get("overall_goal_complete") is True
        and evidence_ledger.get("overall_goal_complete") is True
        and not issue_rows
        and not missing_sources
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": final_goal_complete,
        "report_status": "FINAL_AUDIT_COMPLETE" if final_goal_complete else "CURRENT_AUDIT_NOT_FINAL",
        "safety": "read-only completion audit; repository report writes only",
        "scenario_count": int(status_snapshot.get("scenario_count", evidence_ledger.get("scenario_count", 0)) or 0),
        "hold_or_unconfirmed_count": int(status_snapshot.get("hold_or_unconfirmed_count", len(issue_rows)) or 0),
        "issue_count": len(issue_rows),
        "missing_source_count": len(missing_sources),
        "complete_goal_evidence_count": int(evidence_ledger.get("complete_goal_evidence_count", 0) or 0),
        "validation_summary": validation_summary,
        "issues": [asdict(row) for row in issue_rows],
        "source_paths": {label: str(path) for label, path in source_paths.items()},
        "source_exists": {label: path.exists() for label, path in source_paths.items()},
        "missing_sources": missing_sources,
    }


def build_markdown(payload: dict[str, Any]) -> str:
    validation = payload["validation_summary"]
    assert isinstance(validation, dict)
    issues = payload["issues"]
    assert isinstance(issues, list)
    lines = [
        "# 目標完了監査 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- report_status: `{payload['report_status']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- complete_goal_evidence_count: `{payload['complete_goal_evidence_count']}`",
        f"- hold_or_unconfirmed_count: `{payload['hold_or_unconfirmed_count']}`",
        f"- issue_count: `{payload['issue_count']}`",
        f"- missing_source_count: `{payload['missing_source_count']}`",
        "",
        "## Strict Verdict",
        "",
        "- This audit is not a production completion report unless `overall_goal_complete=True`.",
        "- Safe sample, dry-run, static guard, or `OK_CANDIDATE` evidence is not treated as final runtime completion.",
        "- No Outlook, RK10, Rakuraku, Azure, mail, print, payment, MainSV, or production write operation is performed by this audit.",
        "",
        "## Validation Summary",
        "",
        f"- packet_approved_row_count: `{validation['packet_approved_row_count']}`",
        f"- packet_needs_attention_count: `{validation['packet_needs_attention_count']}`",
        f"- bundle_final_evidence_ready_count: `{validation['bundle_final_evidence_ready_count']}/{validation['bundle_count']}`",
        f"- rks_unresolved_gate_count: `{validation['rks_unresolved_gate_count']}`",
        f"- rks_runtime_approved_count: `{validation['rks_runtime_approved_count']}/{validation['rks_runtime_required_count']}`",
        f"- rks_runtime_hard_error_count: `{validation['rks_runtime_hard_error_count']}`",
        f"- amount_verified_scenario_count: `{validation['amount_verified_scenario_count']}`",
        f"- code_backup_complete: `{validation['code_backup_complete']}`",
        f"- code_backup_artifact_count: `{validation['code_backup_artifact_count']}`",
        f"- code_backup_missing_count: `{validation['code_backup_missing_count']}`",
        "",
        "## Root Cause / Countermeasure Audit",
        "",
        "| Scenario | Current Status | Root Cause Class | Countermeasure / Next Verification | Source Exists | Source |",
        "|---|---|---|---|---:|---|",
    ]
    for issue in issues:
        assert isinstance(issue, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(issue["scenario"]),
                    str(issue["current_status"]).replace("|", "/"),
                    str(issue["root_cause_class"]).replace("|", "/"),
                    str(issue["countermeasure_or_next_verification"]).replace("|", "/"),
                    "YES" if issue["source_exists"] else "NO",
                    f"`{issue['source']}`",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Reports", ""])
    for label, source_path in payload["source_paths"].items():
        exists = payload["source_exists"].get(label)
        lines.append(f"- {label}: `{source_path}` exists=`{exists}`")
    lines.extend(["", "## Field Export", ""])
    field_export_paths = payload.get("field_export_paths", {})
    if isinstance(field_export_paths, dict) and field_export_paths.get("issues_csv"):
        lines.append(f"- issues_csv: `{field_export_paths['issues_csv']}`")
    else:
        lines.append(f"- issues_csv: `{DEFAULT_OUT_DIR / 'goal_completion_audit_issues.csv'}`")
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_issues_csv(path: Path, issues: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ISSUE_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(issues)


def write_outputs(payload: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "goal_completion_audit.json"
    md_path = out_dir / "goal_completion_audit.md"
    issues_csv_path = out_dir / "goal_completion_audit_issues.csv"
    payload_to_write = {
        **payload,
        "field_export_paths": {"issues_csv": str(issues_csv_path)},
    }
    json_path.write_text(json.dumps(payload_to_write, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload_to_write), encoding="utf-8")
    write_issues_csv(issues_csv_path, list(payload_to_write.get("issues", [])))
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "issues_csv": str(issues_csv_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate current RK10 goal completion audit.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
