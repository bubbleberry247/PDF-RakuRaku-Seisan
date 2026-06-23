"""Generate the active RK10 goal evidence ledger.

This report consolidates current scenario evidence, RKS gate status, and the
remaining proof gap for the user's full goal. It is read-only: no Outlook,
RK10, Rakuraku, Azure, printing, mail, payment, MainSV, or production files are
opened or modified.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from generate_goal_status_snapshot_20260620 import build_payload as build_snapshot_payload
from generate_rks_gate_matrix_20260620 import build_payload as build_rks_payload


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "goal_evidence_ledger_20260620"
SAFE_RUNNER_SUMMARY = ROOT / "plans" / "reports" / "safe_goal_checks_20260620" / "safe_goal_checks_summary.md.numbered"
EXECUTION_PACKET = ROOT / "plans" / "reports" / "goal_execution_packet_20260620" / "goal_execution_packet.md.numbered"
SAMPLE_DATA_MAP = (
    ROOT
    / "plans"
    / "reports"
    / "sample_data_evidence_map_20260620"
    / "sample_data_evidence_map.md.numbered"
)
SAMPLE_DATA_MAP_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "sample_data_evidence_map_20260620"
    / "sample_data_evidence_map.json"
)
SAFE_EXECUTION_MAP = (
    ROOT
    / "plans"
    / "reports"
    / "safe_execution_evidence_map_20260620"
    / "safe_execution_evidence_map.md.numbered"
)
SAFE_EXECUTION_MAP_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "safe_execution_evidence_map_20260620"
    / "safe_execution_evidence_map.json"
)
BUSINESS_COST_MAP = (
    ROOT
    / "plans"
    / "reports"
    / "business_cost_evidence_map_20260620"
    / "business_cost_evidence_map.md.numbered"
)
BUSINESS_COST_MAP_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "business_cost_evidence_map_20260620"
    / "business_cost_evidence_map.json"
)
BUNDLE_EVIDENCE_VALIDATION_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_pack_validation_20260620"
    / "bundle_evidence_pack_validation.json"
)
OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "outlook_bundle_evidence_collect_20260620"
    / "outlook_bundle_evidence_collect.json"
)
OUTLOOK_COM_SAMPLE_READY_STATUS = "OUTLOOK_COM_BUNDLE_DRYRUN_SAMPLE_REFRESH_READY"
OUTLOOK_COM_SAFE_READY_STATUS = "OUTLOOK_COM_BUNDLE_DRYRUN_NO_PRINT_NO_MAIL_EXIT0"
COUNT_ONLY_BUSINESS_COST_STATUSES = {
    "OUTLOOK_COM_DRYRUN_COUNT_PROOF_NO_PRINT_NO_MAIL",
    "RECORU_SAMPLE_ZERO_TARGET_AND_GUARD_COUNT_PROOF_NO_AMOUNT",
    "ORDER_REGISTRATION_ONE_CASE_PROOF_NO_PROD_REGISTER_NO_AMOUNT",
    "DRIVE_REPORT_ROW_COUNT_PROOF_NO_MAINSV_WRITE",
    "DRYRUN_FLAG_COUNT_PROOF_NO_AMOUNT_NO_UPLOAD",
    "S56_LOCAL_COPY_WRITE_COUNT_PROOF_NO_PRODUCTION_MAIL",
    "S57_DRYRUN_OUTPUT_PLAN_PROOF_NO_FINAL_COPY",
}
DRAFT_SAVE_BUSINESS_COST_STATUSES = {
    "RAKURAKU_TEMP_SAVE_AMOUNT_REPORTED_FINAL_NOT_CLICKED",
    "RAKURAKU_DRAFT_SAVE_AMOUNT_REPORTED_NO_FINAL_SUBMIT_NO_MAIL",
}
AMOUNT_VERIFIED_BUSINESS_COST_STATUSES = {
    "DRYRUN_BUSINESS_AMOUNT_REPORTED",
    "SAMPLE_SHADOW_HANDOFF_AMOUNT_RECALCULATED",
    "SAMPLE_CONFIRM_PREVIEW_AMOUNT_RECALCULATED",
    "REAL_PDF_MOCK_OCR_APPLY_AMOUNT_RECALCULATED",
    "AMOUNT_PARSER_TEST_CASES_PRESENT",
    "LOCAL_DRYRUN_PAYMENT_ITEMS_AMOUNT_RECALCULATED",
    "LOCAL_SAMPLE_TEST_SUITE_AMOUNT_RECALCULATED",
    "SOFTBANK_EXCEL_ONLY_AMOUNT_REPORTED_RAKURAKU_SKIPPED",
    "SOFTBANK_MANUAL_SUBMISSION_AMOUNT_REPORTED_RAKURAKU_SKIPPED",
}


@dataclass(frozen=True)
class EvidenceLedgerRow:
    scenario: str
    current_status: str
    rks_status: str
    rks_runtime_intake_status: str
    rks_runtime_intake_approved: str
    proven_scope: str
    evidence_strength: str
    goal_gap: str
    source: str
    source_exists: bool
    supplemental_evidence: str
    supplemental_evidence_exists: bool
    sample_data_status: str
    sample_data_evidence: str
    sample_data_evidence_exists: bool
    safe_execution_status: str
    safe_execution_evidence: str
    safe_execution_evidence_exists: bool
    business_cost_status: str
    business_cost_amount_yen: int | None
    business_cost_evidence: str
    business_cost_evidence_exists: bool
    final_evidence_ready: bool
    final_evidence_path: str
    objective_checkpoint_summary: str
    missing_objective_proofs: str


def split_grouped_scenarios(value: str) -> set[str]:
    return {part.strip() for part in value.split("/") if part.strip()}


def find_rks_row(scenario: str, rks_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rks_rows:
        row_scenario = str(row["scenario"])
        if scenario == row_scenario:
            return row
        if scenario in split_grouped_scenarios(row_scenario):
            return row
    return None


def find_rks_status(scenario: str, rks_rows: list[dict[str, Any]]) -> str:
    row = find_rks_row(scenario, rks_rows)
    if row is not None:
        return str(row["current_rks_status"])
    return "NO_RKS_MATRIX_ROW"


def runtime_intake_approved_text(scenario: str, rks_row: dict[str, Any] | None) -> str:
    if rks_row is None:
        return "n/a"
    required_count = int(rks_row.get("runtime_intake_required_count", 0))
    if required_count == 0:
        return "n/a"
    approved_text = f"{int(rks_row.get('runtime_intake_approved_count', 0))}/{required_count}"
    row_scenario = str(rks_row.get("scenario", ""))
    if scenario != row_scenario and scenario in split_grouped_scenarios(row_scenario):
        return f"group:{approved_text}"
    return approved_text


def classify_scope(status: str, rks_status: str, rks_runtime_status: str = "") -> tuple[str, str, str]:
    if status.startswith("HOLD_"):
        return (
            "HOLD_GATE_ONLY",
            "BLOCKED_BY_INPUT_OR_ENVIRONMENT",
            "HOLD解除入力または外部環境復旧が必要",
        )
    if "EDITOR_OPEN_NG" in status or "EDITOR_OPEN_NG" in rks_status:
        return (
            "PYTHON_SAFE_ONLY_RKS_NG",
            "PYTHON_EVIDENCE_STRONG_RKS_WEAK",
            "RKSを使うならRK10 Editor Save As再生成とopen/build/runtime証跡が必要",
        )
    if rks_runtime_status.startswith("RKS_RUNTIME_DEFERRED"):
        return (
            "RKS_PREREQUISITE_OR_ENTRY_DECISION_PENDING",
            "PARTIAL_EVIDENCE",
            "RKS実行前の業務前提条件または入口選定が未確定",
        )
    if rks_runtime_status == "RKS_RUNTIME_EVIDENCE_CONFIRMED" and "SAFE_STOP_SCOPE_ONLY" in rks_status:
        return (
            "SAFE_STOP_SCOPE_ONLY",
            "PARTIAL_EVIDENCE",
            "実対象データ・承認・本番前停止位置・latest clean logが不足",
        )
    if "RKS" in status or "UNCONFIRMED" in status or "NOT_CONFIRMED" in status:
        return (
            "SAFE_OR_FILE_SCOPE_ONLY",
            "PARTIAL_EVIDENCE",
            "RK10 open/build/runtime/latest clean logまたは本番停止条件証跡が不足",
        )
    if "SAFE_STOP_SCOPE_ONLY" in rks_status:
        return (
            "SAFE_STOP_SCOPE_ONLY",
            "PARTIAL_EVIDENCE",
            "実対象データ・承認・本番前停止位置・latest clean logが不足",
        )
    if rks_runtime_status == "RKS_RUNTIME_EVIDENCE_PENDING":
        return (
            "RKS_RUNTIME_INTAKE_PENDING",
            "PARTIAL_EVIDENCE",
            "RKS入力CSVのopen/build/runtime/latest clean log証跡が不足",
        )
    return (
        "SCOPED_SAFE_EVIDENCE",
        "PARTIAL_EVIDENCE",
        "本番業務費用の全量実行と不可逆操作の証跡は別ゲート",
    )


def classify_objective_checkpoints(
    status: str,
    rks_status: str,
    rks_runtime_status: str,
    evidence_strength: str,
    sample_data_status: str,
    safe_execution_status: str,
    business_cost_status: str,
    final_evidence_ready: bool = False,
) -> tuple[str, str]:
    sample_state = "OK" if is_sample_data_ready(sample_data_status) else "HOLD"
    safe_state = "OK" if is_safe_execution_ready(safe_execution_status) else "HOLD"
    if rks_status.startswith("N_A"):
        rks_state = "N_A"
    elif rks_runtime_status == "RKS_RUNTIME_EVIDENCE_CONFIRMED":
        rks_state = "SCOPED_OK"
    else:
        rks_state = "PENDING"
    if business_cost_status in AMOUNT_VERIFIED_BUSINESS_COST_STATUSES:
        cost_state = "SAMPLE_OK"
    elif business_cost_status in DRAFT_SAVE_BUSINESS_COST_STATUSES:
        cost_state = "DRAFT_OK"
    elif business_cost_status in COUNT_ONLY_BUSINESS_COST_STATUSES:
        cost_state = "COUNT_ONLY"
    elif business_cost_status:
        cost_state = "PENDING"
    else:
        cost_state = "MISSING"
    final_state = (
        "OK"
        if evidence_strength == "COMPLETE_GOAL_EVIDENCE" or final_evidence_ready
        else "PENDING"
    )
    missing_proofs = []
    if sample_state != "OK":
        missing_proofs.append("current sample/dry-run refresh")
    if safe_state != "OK":
        missing_proofs.append("safe no-side-effect execution log")
    if rks_state == "PENDING":
        missing_proofs.append("RK10 open/build/runtime/latest clean log or entry decision")
    if cost_state == "COUNT_ONLY":
        missing_proofs.append("business amount proof or explicit no-amount scope")
    elif cost_state not in {"SAMPLE_OK", "DRAFT_OK"}:
        missing_proofs.append("business count/amount/difference proof")
    if status.startswith("HOLD_"):
        missing_proofs.append("HOLD release or external environment recovery")
    if final_state != "OK":
        missing_proofs.append("operator final evidence and approval record")
    return (
        f"sample={sample_state}; safe={safe_state}; rks={rks_state}; cost={cost_state}; final={final_state}",
        ", ".join(missing_proofs),
    )


def is_sample_data_ready(status: str) -> bool:
    return status.startswith("SAFE_SUITE_") or status == OUTLOOK_COM_SAMPLE_READY_STATUS


def is_safe_execution_ready(status: str) -> bool:
    return status in {"SAFE_SUITE_EXIT0_STDERR0", OUTLOOK_COM_SAFE_READY_STATUS}


def is_outlook_com_bundle_final_evidence_ready(path: Path | None = None) -> bool:
    target_path = path or BUNDLE_EVIDENCE_VALIDATION_JSON
    if not target_path.exists():
        return False
    payload = json.loads(target_path.read_text(encoding="utf-8"))
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return False
    return any(
        isinstance(item, dict)
        and item.get("bundle") == "OUTLOOK_COM_BUNDLE"
        and item.get("final_evidence_ready") is True
        for item in checks
    )


def is_outlook_com_bundle_safe_evidence_ready(path: Path | None = None) -> bool:
    target_path = path or OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON
    if not target_path.exists():
        return False
    payload = json.loads(target_path.read_text(encoding="utf-8"))
    log_status = payload.get("log_status", {})
    if not isinstance(log_status, dict):
        log_status = {}
    return (
        payload.get("status") == "READY_FOR_FINAL_EVIDENCE_INTAKE"
        and payload.get("ready_for_intake") is True
        and str(log_status.get("check_exit", "")).strip() == "0"
        and str(log_status.get("scan_exit", "")).strip() == "0"
    )


def split_bundle_scenarios(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def load_final_evidence_statuses(
    path: Path | None = None,
) -> dict[str, tuple[bool, str]]:
    target_path = path or BUNDLE_EVIDENCE_VALIDATION_JSON
    if not target_path.exists():
        return {}
    payload = json.loads(target_path.read_text(encoding="utf-8"))
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return {}
    statuses: dict[str, tuple[bool, str]] = {}
    for item in checks:
        if not isinstance(item, dict):
            continue
        scenarios = split_bundle_scenarios(str(item.get("scenarios", "")))
        final_evidence_ready = item.get("final_evidence_ready") is True
        final_evidence_path = str(item.get("final_evidence_path", ""))
        for scenario in scenarios:
            statuses[scenario] = (final_evidence_ready, final_evidence_path)
    return statuses


def load_safe_execution_statuses(path: Path = SAFE_EXECUTION_MAP_JSON) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return {}
    statuses: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        scenario = str(row.get("scenario", ""))
        if scenario:
            statuses[scenario] = str(row.get("safe_suite_status", ""))
    return statuses


def load_sample_data_statuses(path: Path = SAMPLE_DATA_MAP_JSON) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return {}
    statuses: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        scenario = str(row.get("scenario", ""))
        if scenario:
            statuses[scenario] = str(row.get("sample_data_status", ""))
    return statuses


def load_business_cost_statuses(path: Path = BUSINESS_COST_MAP_JSON) -> dict[str, tuple[str, int | None]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return {}
    statuses: dict[str, tuple[str, int | None]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        scenario = str(row.get("scenario", ""))
        if scenario:
            amount = row.get("total_amount_yen")
            statuses[scenario] = (
                str(row.get("cost_evidence_status", "")),
                amount if isinstance(amount, int) else None,
            )
    return statuses


def build_rows(snapshot_payload: dict[str, Any], rks_payload: dict[str, Any]) -> list[EvidenceLedgerRow]:
    rks_rows = list(rks_payload["rows"])
    sample_data_statuses = load_sample_data_statuses()
    safe_execution_statuses = load_safe_execution_statuses()
    business_cost_statuses = load_business_cost_statuses()
    final_evidence_statuses = load_final_evidence_statuses()
    outlook_bundle_safe_evidence_ready = is_outlook_com_bundle_safe_evidence_ready()
    rows = []
    for item in snapshot_payload["scenarios"]:
        scenario = str(item["scenario"])
        status = str(item["current_status"])
        rks_row = find_rks_row(scenario, rks_rows)
        rks_status = str(rks_row["current_rks_status"]) if rks_row is not None else "NO_RKS_MATRIX_ROW"
        rks_runtime_status = (
            str(rks_row.get("runtime_intake_status", ""))
            if rks_row is not None
            else "NO_RKS_MATRIX_ROW"
        )
        proven_scope, evidence_strength, goal_gap = classify_scope(status, rks_status, rks_runtime_status)
        business_cost_status, business_cost_amount = business_cost_statuses.get(scenario, ("", None))
        sample_data_status = sample_data_statuses.get(scenario, "")
        safe_execution_status = safe_execution_statuses.get(scenario, "")
        final_evidence_ready, final_evidence_path = final_evidence_statuses.get(
            scenario,
            (False, ""),
        )
        if scenario == "12/13" and outlook_bundle_safe_evidence_ready:
            sample_data_status = OUTLOOK_COM_SAMPLE_READY_STATUS
            safe_execution_status = OUTLOOK_COM_SAFE_READY_STATUS
        objective_checkpoint_summary, missing_objective_proofs = classify_objective_checkpoints(
            status=status,
            rks_status=rks_status,
            rks_runtime_status=rks_runtime_status,
            evidence_strength=evidence_strength,
            sample_data_status=sample_data_status,
            safe_execution_status=safe_execution_status,
            business_cost_status=business_cost_status,
            final_evidence_ready=final_evidence_ready,
        )
        rows.append(
            EvidenceLedgerRow(
                scenario=scenario,
                current_status=status,
                rks_status=rks_status,
                rks_runtime_intake_status=rks_runtime_status,
                rks_runtime_intake_approved=runtime_intake_approved_text(scenario, rks_row),
                proven_scope=proven_scope,
                evidence_strength=evidence_strength,
                goal_gap=goal_gap,
                source=str(item["source"]),
                source_exists=bool(item["source_exists"]),
                supplemental_evidence=str(item.get("supplemental_evidence", "")),
                supplemental_evidence_exists=bool(item.get("supplemental_evidence_exists")),
                sample_data_status=sample_data_status,
                sample_data_evidence=str(SAMPLE_DATA_MAP),
                sample_data_evidence_exists=SAMPLE_DATA_MAP.exists(),
                safe_execution_status=safe_execution_status,
                safe_execution_evidence=str(SAFE_EXECUTION_MAP),
                safe_execution_evidence_exists=SAFE_EXECUTION_MAP.exists(),
                business_cost_status=business_cost_status,
                business_cost_amount_yen=business_cost_amount,
                business_cost_evidence=str(BUSINESS_COST_MAP),
                business_cost_evidence_exists=BUSINESS_COST_MAP.exists(),
                final_evidence_ready=final_evidence_ready,
                final_evidence_path=final_evidence_path,
                objective_checkpoint_summary=objective_checkpoint_summary,
                missing_objective_proofs=missing_objective_proofs,
            )
        )
    return rows


def build_payload(s12_exit_code: int | None) -> dict[str, Any]:
    snapshot_payload = build_snapshot_payload(s12_exit_code)
    rks_payload = build_rks_payload()
    rows = build_rows(snapshot_payload, rks_payload)
    complete_rows = [
        row for row in rows
        if row.evidence_strength == "COMPLETE_GOAL_EVIDENCE"
    ]
    missing_sources = [row for row in rows if not row.source_exists]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": len(complete_rows) == len(rows),
        "safety": "read-only evidence ledger only; no external operation",
        "scenario_count": len(rows),
        "complete_goal_evidence_count": len(complete_rows),
        "missing_source_count": len(missing_sources),
        "safe_runner_summary": str(SAFE_RUNNER_SUMMARY),
        "execution_packet": str(EXECUTION_PACKET),
        "sample_data_map": str(SAMPLE_DATA_MAP),
        "safe_execution_map": str(SAFE_EXECUTION_MAP),
        "business_cost_map": str(BUSINESS_COST_MAP),
        "final_evidence_ready_count": sum(1 for row in rows if row.final_evidence_ready),
        "rows": [asdict(row) for row in rows],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# 目標証跡台帳 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- complete_goal_evidence_count: `{payload['complete_goal_evidence_count']}`",
        f"- missing_source_count: `{payload['missing_source_count']}`",
        f"- safe_runner_summary: `{payload['safe_runner_summary']}`",
        f"- execution_packet: `{payload['execution_packet']}`",
        f"- sample_data_map: `{payload['sample_data_map']}`",
        f"- safe_execution_map: `{payload['safe_execution_map']}`",
        f"- business_cost_map: `{payload['business_cost_map']}`",
        f"- final_evidence_ready_count: `{payload.get('final_evidence_ready_count', 0)}`",
        "",
        "## Requirement Interpretation",
        "",
        "- `SCOPED_SAFE_EVIDENCE` や `SAFE_STOP_SCOPE_ONLY` は進捗証跡であり、全目標完了ではない。",
        "- RKSは `OK_CANDIDATE` やファイル存在だけでは実行OKにしない。",
        "- 実送信・実印刷・支払実行・本番書込・最終申請は、証跡と承認が揃うまで未完了扱いにする。",
        "",
        "## Scenario Evidence Ledger",
        "",
        "| Scenario | Current Status | RKS Status | RKS Runtime Intake | RKS Runtime Approved | Proven Scope | Evidence Strength | Goal Gap | Objective Checkpoints | Missing Objective Proofs | Final Evidence Ready | Final Evidence Path | Source Exists | Source | Supplemental Evidence | Sample Data | Safe Execution | Business Cost |",
        "|---|---|---|---|---|---|---|---|---|---|---:|---|---:|---|---|---|---|---|",
    ]
    for item in rows:
        assert isinstance(item, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["scenario"]),
                    str(item["current_status"]).replace("|", "/"),
                    str(item["rks_status"]).replace("|", "/"),
                    str(item.get("rks_runtime_intake_status") or "-").replace("|", "/"),
                    str(item.get("rks_runtime_intake_approved") or "n/a"),
                    str(item["proven_scope"]).replace("|", "/"),
                    str(item["evidence_strength"]).replace("|", "/"),
                    str(item["goal_gap"]).replace("|", "/"),
                    str(item.get("objective_checkpoint_summary") or "-").replace("|", "/"),
                    str(item.get("missing_objective_proofs") or "-").replace("|", "/"),
                    "YES" if item.get("final_evidence_ready") else "NO",
                    f"`{item['final_evidence_path']}`" if item.get("final_evidence_path") else "-",
                    "YES" if item["source_exists"] else "NO",
                    f"`{item['source']}`",
                    f"`{item['supplemental_evidence']}`" if item.get("supplemental_evidence") else "-",
                    str(item.get("sample_data_status") or "-").replace("|", "/"),
                    str(item.get("safe_execution_status") or "-").replace("|", "/"),
                    str(item.get("business_cost_status") or "-").replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Sample Data Map", ""])
    lines.append(f"- source: `{payload['sample_data_map']}`")
    lines.append("- scope: sample/test/review/dry-run artifact presence only; not production completion evidence.")
    lines.extend(["", "## Safe Execution Map", ""])
    lines.append(f"- source: `{payload['safe_execution_map']}`")
    lines.append("- scope: safe sample/dry-run/self-test only; not production completion evidence.")
    lines.extend(["", "## Business Cost Map", ""])
    lines.append(f"- source: `{payload['business_cost_map']}`")
    lines.append("- scope: sample/dry-run/mock-apply/draft-save count and amount evidence only; not final irreversible execution evidence.")
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RK10 goal evidence ledger.")
    parser.add_argument(
        "--s12-exit-code",
        type=int,
        default=2,
        help="Latest known 12/13 Outlook COM probe exit code.",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.s12_exit_code)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "goal_evidence_ledger.json"
    md_path = args.out_dir / "goal_evidence_ledger.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
