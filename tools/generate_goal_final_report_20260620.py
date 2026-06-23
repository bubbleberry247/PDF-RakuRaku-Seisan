"""Generate a current final-report draft for the active RK10 goal.

The report is intentionally strict: when the completion gate is false it is a
draft/progress report, not a production completion report. It only reads
repository reports and writes repository reports.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "goal_final_report_20260620"
COMPLETION_GATE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "goal_completion_gate_20260620"
    / "goal_completion_gate.json"
)
REQUIREMENT_TRACE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "goal_requirement_traceability_20260620"
    / "goal_requirement_traceability.json"
)
EVIDENCE_LEDGER_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "goal_evidence_ledger_20260620"
    / "goal_evidence_ledger.json"
)
SAFE_RUNNER_SUMMARY_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "safe_goal_checks_20260620"
    / "safe_goal_checks_summary.json"
)
NEXT_APPROVAL_QUEUE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "next_approval_queue_20260620"
    / "next_approval_queue.json"
)
S44_REVIEW_AID_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_aid.csv"
)
S44_PRIORITY_QUEUE_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_priority_queue.csv"
)
S44_NEXT_STEPS_MD = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_next_steps.md"
)
S44_SINGLE_ENTRY_INPUT_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_single_entry_input.csv"
)
S44_AMOUNT_ZERO_REVIEW_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_review_01_amount_zero_review.csv"
)
S44_AMOUNT_MISMATCH_REVIEW_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_review_02_amount_mismatch_review.csv"
)
S44_AMOUNT_MATCH_QUICK_REVIEW_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_review_03_amount_match_quick_review.csv"
)
S44_DECISION_INPUT_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_decision_input.csv"
)
S44_BUCKET_DECISION_INPUT_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_bucket_decision_input.csv"
)
S44_SPOT_CHECK_CSV = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\s44_business_spot_check_sheet_20260619_1240\s44_business_spot_check_26.csv"
)
BUSINESS_DATA_APPROVAL_CHECKLIST_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "business_data_approval_bundle"
    / "business_data_approval_checklist.csv"
)
S70_PAYMENT_PREFILL_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s70_payment_approval_evidence_collect_20260620"
    / "s70_payment_confirmation_gate_checklist_prefill.csv"
)
S71_PAID_SMOKE_TEMPLATE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "s71_paid_azure_ocr_evidence_collect_20260620"
    / "s71_paid_azure_one_pdf_smoke_summary_template.json"
)
S71_ENVIRONMENT_PRESENCE_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s71_paid_azure_ocr_evidence_collect_20260620"
    / "s71_azure_ocr_environment_presence.csv"
)
COMPLETION_AUDIT_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "goal_completion_audit_20260620"
    / "goal_completion_audit.json"
)
BUNDLE_VALIDATION_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_pack_validation_20260620"
    / "bundle_evidence_pack_validation.json"
)
FINAL_EVIDENCE_FILL_QUEUE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "final_evidence_fill_queue_20260621"
    / "final_evidence_fill_queue.json"
)
RKS_GATE_MATRIX_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "rks_gate_matrix_20260620"
    / "rks_gate_matrix.json"
)
CUSTOMER_SAFE_SMOKE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "customer_safe_entries_full_smoke_20260622"
    / "customer_safe_entries_full_smoke_20260622.json"
)
CUSTOMER_SAFE_SMOKE_MD = (
    ROOT
    / "plans"
    / "reports"
    / "customer_safe_entries_full_smoke_20260622"
    / "customer_safe_entries_full_smoke_20260622.md.numbered"
)
CUSTOMER_SAFE_SCENARIO_MATRIX_MD = (
    ROOT
    / "plans"
    / "reports"
    / "customer_safe_entries_full_smoke_20260622"
    / "customer_safe_entries_scenario_matrix_20260622.md.numbered"
)
CUSTOMER_SAFE_ACTUAL_EXECUTION_TRACE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "customer_safe_entries_full_smoke_20260622"
    / "customer_safe_entries_actual_execution_trace_20260623.json"
)
CUSTOMER_SAFE_ACTUAL_EXECUTION_TRACE_MD = (
    ROOT
    / "plans"
    / "reports"
    / "customer_safe_entries_full_smoke_20260622"
    / "customer_safe_entries_actual_execution_trace_20260623.md.numbered"
)
GOAL_EVIDENCE_ACTUAL_TRACE_OVERLAY_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "goal_evidence_actual_trace_overlay_20260623"
    / "goal_evidence_actual_trace_overlay.json"
)
GOAL_EVIDENCE_ACTUAL_TRACE_OVERLAY_MD = (
    ROOT
    / "plans"
    / "reports"
    / "goal_evidence_actual_trace_overlay_20260623"
    / "goal_evidence_actual_trace_overlay.md.numbered"
)
REMAINING_OPERATOR_COMPLETION_SIMULATION_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "remaining_operator_input_completion_simulation_20260623"
    / "remaining_operator_input_completion_simulation.json"
)
REMAINING_OPERATOR_COMPLETION_SIMULATION_MD = (
    ROOT
    / "plans"
    / "reports"
    / "remaining_operator_input_completion_simulation_20260623"
    / "remaining_operator_input_completion_simulation.md.numbered"
)
BLOCKING_GATE_CSV_FIELDS = ["gate", "status", "detail", "next_action", "source"]
INCOMPLETE_REQUIREMENT_CSV_FIELDS = [
    "requirement_id",
    "requirement",
    "current_status",
    "remaining_gap",
    "next_evidence_needed",
    "authoritative_evidence",
]
SCENARIO_SNAPSHOT_CSV_FIELDS = [
    "scenario",
    "objective_checkpoint_summary",
    "missing_objective_proofs",
    "evidence_strength",
]
SUPPORTING_INPUT_PATHS_BY_BUNDLE: dict[str, list[tuple[str, Path]]] = {
    "BUSINESS_REVIEW_BUNDLE": [
        ("scenario44_single_entry_input_csv", S44_SINGLE_ENTRY_INPUT_CSV),
        ("scenario44_next_steps_md", S44_NEXT_STEPS_MD),
        ("scenario44_decision_input_csv", S44_DECISION_INPUT_CSV),
        ("scenario44_bucket_decision_input_csv", S44_BUCKET_DECISION_INPUT_CSV),
        ("scenario44_priority_queue_csv", S44_PRIORITY_QUEUE_CSV),
        ("scenario44_amount_zero_review_csv", S44_AMOUNT_ZERO_REVIEW_CSV),
        ("scenario44_amount_mismatch_review_csv", S44_AMOUNT_MISMATCH_REVIEW_CSV),
        (
            "scenario44_amount_match_quick_review_csv",
            S44_AMOUNT_MATCH_QUICK_REVIEW_CSV,
        ),
        ("scenario44_review_aid_csv", S44_REVIEW_AID_CSV),
        ("scenario44_source_spot_check_csv", S44_SPOT_CHECK_CSV),
    ],
    "BUSINESS_DATA_APPROVAL_BUNDLE": [
        ("business_data_approval_checklist_csv", BUSINESS_DATA_APPROVAL_CHECKLIST_CSV),
    ],
    "PAYMENT_APPROVAL_BUNDLE": [
        ("scenario70_payment_prefill_csv", S70_PAYMENT_PREFILL_CSV),
    ],
    "PAID_AZURE_OCR_BUNDLE": [
        ("scenario71_environment_presence_csv", S71_ENVIRONMENT_PRESENCE_CSV),
        ("scenario71_paid_smoke_template_json", S71_PAID_SMOKE_TEMPLATE_JSON),
    ],
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def is_complete_requirement(row: dict[str, Any]) -> bool:
    return str(row.get("current_status", "")) in {
        "COMPLETE",
        "OK",
        "OK_FOR_SAFE_CHECKS_ONLY",
        "OK_FOR_BUNDLE_RUNBOOK_ONLY",
    }


def incomplete_requirements(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if not is_complete_requirement(row)]


def blocking_gates(gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [gate for gate in gates if gate.get("passed") is not True]


def first_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return rows[:limit]


def objective_summary_has_state(summary: str, key: str, accepted_states: set[str]) -> bool:
    parts = [part.strip() for part in summary.split(";")]
    prefix = f"{key}="
    for part in parts:
        if part.startswith(prefix):
            return part.removeprefix(prefix) in accepted_states
    return False


def count_objective_checkpoint(
    rows: list[Any],
    key: str,
    accepted_states: set[str],
) -> int:
    return sum(
        1
        for row in rows
        if isinstance(row, dict)
        and objective_summary_has_state(
            str(row.get("objective_checkpoint_summary", "")),
            key,
            accepted_states,
        )
    )


def build_objective_progress_summary(
    evidence_ledger: dict[str, Any],
    rows: list[Any],
) -> dict[str, int]:
    scenario_count = int(evidence_ledger.get("scenario_count", len(rows)) or 0)
    return {
        "scenario_count": scenario_count,
        "sample_ready_count": count_objective_checkpoint(rows, "sample", {"OK"}),
        "safe_execution_ready_count": count_objective_checkpoint(rows, "safe", {"OK"}),
        "rks_scoped_or_not_applicable_count": count_objective_checkpoint(
            rows,
            "rks",
            {"SCOPED_OK", "N_A"},
        ),
        "business_amount_or_draft_count": count_objective_checkpoint(
            rows,
            "cost",
            {"SAMPLE_OK", "DRAFT_OK"},
        ),
        "business_count_only_scope_count": count_objective_checkpoint(
            rows,
            "cost",
            {"COUNT_ONLY"},
        ),
        "final_evidence_ready_count": int(
            evidence_ledger.get("final_evidence_ready_count", 0) or 0
        ),
    }


def build_completion_audit_summary(completion_audit: dict[str, Any]) -> dict[str, Any]:
    validation_summary = completion_audit.get("validation_summary", {})
    if not isinstance(validation_summary, dict):
        validation_summary = {}
    field_export_paths = completion_audit.get("field_export_paths", {})
    if not isinstance(field_export_paths, dict):
        field_export_paths = {}
    return {
        "report_status": str(completion_audit.get("report_status", "")),
        "overall_goal_complete": completion_audit.get("overall_goal_complete") is True,
        "issue_count": int(completion_audit.get("issue_count", 0) or 0),
        "missing_source_count": int(completion_audit.get("missing_source_count", 0) or 0),
        "packet_approved_row_count": int(validation_summary.get("packet_approved_row_count", 0) or 0),
        "packet_needs_attention_count": int(validation_summary.get("packet_needs_attention_count", 0) or 0),
        "bundle_final_evidence_ready_count": int(validation_summary.get("bundle_final_evidence_ready_count", 0) or 0),
        "bundle_count": int(validation_summary.get("bundle_count", 0) or 0),
        "rks_runtime_approved_count": int(validation_summary.get("rks_runtime_approved_count", 0) or 0),
        "rks_runtime_required_count": int(validation_summary.get("rks_runtime_required_count", 0) or 0),
        "amount_verified_scenario_count": int(validation_summary.get("amount_verified_scenario_count", 0) or 0),
        "issues_csv": str(field_export_paths.get("issues_csv", "")),
    }


def build_reference_integrity_summary(bundle_validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "prepared_pack_validation_passed": bundle_validation.get("prepared_pack_validation_passed") is True,
        "source_reference_count": int(bundle_validation.get("source_reference_count", 0) or 0),
        "source_reference_exists_now_count": int(
            bundle_validation.get("source_reference_exists_now_count", 0) or 0
        ),
        "source_reference_hashed_now_count": int(
            bundle_validation.get("source_reference_hashed_now_count", 0) or 0
        ),
        "missing_prepared_pack_count": int(bundle_validation.get("missing_prepared_pack_count", 0) or 0),
        "final_evidence_ready_count": int(bundle_validation.get("final_evidence_ready_count", 0) or 0),
        "bundle_count": int(bundle_validation.get("bundle_count", 0) or 0),
    }


def build_final_evidence_fill_summary(fill_queue: dict[str, Any]) -> dict[str, Any]:
    rows = fill_queue.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    next_active_bundle = str(fill_queue.get("next_active_bundle", ""))
    next_row: dict[str, Any] = {}
    supplemental_row: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        supplemental_status = str(row.get("supplemental_evidence_status", "")).strip()
        supplemental_source = str(row.get("supplemental_evidence_source", "")).strip()
        if not supplemental_row and (supplemental_status or supplemental_source):
            supplemental_row = row
        if str(row.get("bundle", "")) == next_active_bundle:
            next_row = row
    return {
        "active_queue_count": int(fill_queue.get("active_queue_count", 0) or 0),
        "ready_or_completed_count": int(fill_queue.get("ready_or_completed_count", 0) or 0),
        "operator_attention_row_count": int(fill_queue.get("operator_attention_row_count", 0) or 0),
        "next_active_bundle": next_active_bundle,
        "unified_input_csv": str(fill_queue.get("unified_input_csv", "")),
        "after_action_command": str(fill_queue.get("after_action_command", "")),
        "next_entry_keys": str(next_row.get("unified_entry_keys", "")),
        "next_fill_only_fields": str(next_row.get("fill_only_fields", "")),
        "next_start_here_path": str(next_row.get("start_here_path", "")),
        "next_missing_operator_fields": str(next_row.get("missing_operator_fields", "")),
        "next_supplemental_evidence_status": str(
            next_row.get("supplemental_evidence_status", "")
        ),
        "next_supplemental_evidence_source": str(
            next_row.get("supplemental_evidence_source", "")
        ),
        "supplemental_evidence_bundle": str(supplemental_row.get("bundle", "")),
        "supplemental_evidence_status": str(
            supplemental_row.get("supplemental_evidence_status", "")
        ),
        "supplemental_evidence_source": str(
            supplemental_row.get("supplemental_evidence_source", "")
        ),
        "supplemental_remaining_runtime_evidence": str(
            supplemental_row.get("remaining_runtime_evidence", "")
        ),
    }


def build_rks_existing_evidence_search_summary(
    rks_gate_matrix: dict[str, Any],
) -> dict[str, Any]:
    rows = rks_gate_matrix.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    non_promotable_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        search_result = str(row.get("existing_evidence_search_result", ""))
        if not search_result or search_result == "not_applicable":
            continue
        non_promotable_rows.append(
            {
                "scenario": str(row.get("scenario", "")),
                "current_rks_status": str(row.get("current_rks_status", "")),
                "runtime_intake_status": str(row.get("runtime_intake_status", "")),
                "existing_evidence_search_result": search_result,
                "next_safe_action": str(row.get("next_safe_action", "")),
            }
        )
    return {
        "source_generated_at": str(rks_gate_matrix.get("generated_at", "")),
        "overall_rks_production_ready": rks_gate_matrix.get(
            "overall_rks_production_ready"
        )
        is True,
        "reviewed_non_promotable_count": len(non_promotable_rows),
        "rows": non_promotable_rows,
    }

def build_customer_safe_smoke_summary(
    smoke_payload: dict[str, Any],
    smoke_json_path: Path,
    smoke_markdown_path: Path,
    actual_execution_trace_path: Path = CUSTOMER_SAFE_ACTUAL_EXECUTION_TRACE_JSON,
    actual_execution_trace_markdown_path: Path = CUSTOMER_SAFE_ACTUAL_EXECUTION_TRACE_MD,
) -> dict[str, Any]:
    rows = smoke_payload.get("results", [])
    if not isinstance(rows, list):
        rows = []
    notable_names = {"55_v2", "58_gui", "70_confirm"}
    notable_rows: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", ""))
        if name not in notable_names:
            continue
        notable_rows.append(
            {
                "name": name,
                "exit_code": str(row.get("exit_code", "")),
                "expected_exit_codes": str(row.get("expected_exit_codes", "")),
                "expected_ok": "YES" if row.get("expected_ok") is True else "NO",
                "timed_out": "YES" if row.get("timed_out") is True else "NO",
                "elapsed_seconds": str(row.get("elapsed_seconds", "")),
                "cleanup_remaining_count": str(row.get("cleanup_remaining_count", "")),
                "note": str(row.get("note", "")),
            }
        )
    total = to_int(smoke_payload.get("total"))
    expected_ok_count = to_int(smoke_payload.get("expected_ok_count"))
    unexpected_count = to_int(smoke_payload.get("unexpected_count"))
    timeout_count = to_int(smoke_payload.get("timeout_count"))
    cleanup_remaining_count = to_int(smoke_payload.get("cleanup_remaining_count"))
    actual_execution_trace = read_json(actual_execution_trace_path)
    return {
        "source_exists": smoke_json_path.exists(),
        "source_json": str(smoke_json_path),
        "source_markdown_numbered": str(smoke_markdown_path),
        "source_scenario_matrix_numbered": str(CUSTOMER_SAFE_SCENARIO_MATRIX_MD),
        "source_scenario_matrix_exists": CUSTOMER_SAFE_SCENARIO_MATRIX_MD.exists(),
        "source_actual_execution_trace_json": str(actual_execution_trace_path),
        "source_actual_execution_trace_numbered": str(actual_execution_trace_markdown_path),
        "source_actual_execution_trace_exists": actual_execution_trace_markdown_path.exists(),
        "actual_trace_entry_count": to_int(
            actual_execution_trace.get("actual_trace_entry_count")
        ),
        "actual_trace_expected_ok_count": to_int(
            actual_execution_trace.get("actual_trace_expected_ok_count")
        ),
        "actual_trace_script_missing_count": to_int(
            actual_execution_trace.get("actual_trace_script_missing_count")
        ),
        "generated_at": str(smoke_payload.get("generated_at", "")),
        "run_dir": str(smoke_payload.get("run_dir", "")),
        "validation_json": str(smoke_payload.get("validation_json", "")),
        "total": total,
        "expected_ok_count": expected_ok_count,
        "unexpected_count": unexpected_count,
        "timeout_count": timeout_count,
        "cleanup_remaining_count": cleanup_remaining_count,
        "expected_match": f"{expected_ok_count}/{total}" if total else "",
        "safety": str(smoke_payload.get("safety", "")),
        "license_policy": "RK10ライセンス画面は既定のRPA開発版AI付きのまま、ラジオボタンを変更せずOKのみ押す。",
        "notable_rows": notable_rows,
    }


def build_goal_evidence_actual_trace_overlay_summary(
    overlay_payload: dict[str, Any],
    overlay_json_path: Path,
    overlay_markdown_path: Path,
) -> dict[str, Any]:
    return {
        "source_exists": overlay_json_path.exists(),
        "source_json": str(overlay_json_path),
        "source_markdown_numbered": str(overlay_markdown_path),
        "source_markdown_exists": overlay_markdown_path.exists(),
        "generated_at": str(overlay_payload.get("generated_at", "")),
        "scenario_count": to_int(overlay_payload.get("scenario_count")),
        "trace_ready_scenario_count": to_int(
            overlay_payload.get("trace_ready_scenario_count")
        ),
        "trace_missing_scenario_count": to_int(
            overlay_payload.get("trace_missing_scenario_count")
        ),
        "trace_script_missing_count": to_int(
            overlay_payload.get("trace_script_missing_count")
        ),
        "production_completion_scope": str(
            overlay_payload.get("production_completion_scope", "")
        ),
        "safety": str(overlay_payload.get("safety", "")),
    }


def build_remaining_operator_completion_simulation_summary(
    simulation_payload: dict[str, Any],
    simulation_path: Path,
    simulation_markdown_path: Path,
) -> dict[str, Any]:
    return {
        "source_exists": simulation_path.exists(),
        "source_json": str(simulation_path),
        "source_markdown_numbered": str(simulation_markdown_path),
        "source_markdown_exists": simulation_markdown_path.exists(),
        "generated_at": str(simulation_payload.get("generated_at", "")),
        "simulation_passed": simulation_payload.get("simulation_passed") is True,
        "sample_completed_row_count": to_int(
            simulation_payload.get("sample_completed_row_count")
        ),
        "sync_updated_cell_count": to_int(
            simulation_payload.get("sync_updated_cell_count")
        ),
        "sync_conflict_count": to_int(simulation_payload.get("sync_conflict_count")),
        "sync_unsafe_target_count": to_int(
            simulation_payload.get("sync_unsafe_target_count")
        ),
        "validation_all_packet_rows_approved": (
            simulation_payload.get("validation_all_packet_rows_approved") is True
        ),
        "validation_approved_row_count": to_int(
            simulation_payload.get("validation_approved_row_count")
        ),
        "validation_row_count": to_int(simulation_payload.get("validation_row_count")),
        "validation_needs_attention_count": to_int(
            simulation_payload.get("validation_needs_attention_count")
        ),
        "source_files_modified": simulation_payload.get("source_files_modified")
        is True,
        "work_reports_dir": str(simulation_payload.get("work_reports_dir", "")),
        "sync_report_md": str(simulation_payload.get("sync_report_md", "")),
        "validation_report_md": str(simulation_payload.get("validation_report_md", "")),
        "safety": str(simulation_payload.get("safety", "")),
        "production_completion_scope": "SIMULATION_ONLY_NOT_ACTUAL_APPROVAL",
    }


def display_supporting_path(path: Path) -> Path:
    locked_copy = Path(str(path) + ".locked_copy")
    if locked_copy.exists():
        return locked_copy
    return path


def build_supporting_input_paths(next_bundle: str) -> list[dict[str, str]]:
    return [
        {"label": label, "path": str(display_supporting_path(path))}
        for label, path in SUPPORTING_INPUT_PATHS_BY_BUNDLE.get(next_bundle, [])
    ]


def build_next_action_summary(next_queue: dict[str, Any]) -> dict[str, Any]:
    next_bundle = str(next_queue.get("next_bundle", ""))
    queue_rows = next_queue.get("rows", [])
    if not isinstance(queue_rows, list):
        queue_rows = []
    next_row = {}
    for row in queue_rows:
        if isinstance(row, dict) and str(row.get("bundle", "")) == next_bundle:
            next_row = row
            break
    return {
        "next_bundle": next_bundle,
        "next_operator_action": str(next_queue.get("next_operator_action", "")),
        "external_runbook": str(next_queue.get("external_runbook", "")),
        "external_runbook_json": str(next_queue.get("external_runbook_json", "")),
        "outlook_bundle_script": str(next_queue.get("outlook_bundle_script", "")),
        "outlook_recovery_checklist": str(
            next_queue.get("outlook_recovery_checklist", "")
        ),
        "outlook_com_diagnosis_report": str(
            next_queue.get("outlook_com_diagnosis_report", "")
        ),
        "rk10_recovery_checklist": str(next_queue.get("rk10_recovery_checklist", "")),
        "owner": str(next_row.get("owner", "")),
        "scenarios": str(next_row.get("scenarios", "")),
        "approval_boundary": str(next_row.get("approval_boundary", "")),
        "forbidden": str(next_row.get("forbidden", "")),
        "evidence_pack_path": str(next_row.get("evidence_pack_path", "")),
        "bundle_sheet_path": str(next_row.get("bundle_sheet_path", "")),
        "after_action_command": str(next_row.get("after_action_command", "")),
        "supporting_input_paths": build_supporting_input_paths(next_bundle),
    }


def build_payload(
    completion_gate_path: Path = COMPLETION_GATE_JSON,
    requirement_trace_path: Path = REQUIREMENT_TRACE_JSON,
    evidence_ledger_path: Path = EVIDENCE_LEDGER_JSON,
    safe_runner_summary_path: Path = SAFE_RUNNER_SUMMARY_JSON,
    next_approval_queue_path: Path = NEXT_APPROVAL_QUEUE_JSON,
    completion_audit_path: Path = COMPLETION_AUDIT_JSON,
    bundle_validation_path: Path = BUNDLE_VALIDATION_JSON,
    final_evidence_fill_queue_path: Path = FINAL_EVIDENCE_FILL_QUEUE_JSON,
    rks_gate_matrix_path: Path = RKS_GATE_MATRIX_JSON,
    customer_safe_smoke_path: Path = CUSTOMER_SAFE_SMOKE_JSON,
    customer_safe_smoke_markdown_path: Path = CUSTOMER_SAFE_SMOKE_MD,
    customer_safe_actual_execution_trace_path: Path = CUSTOMER_SAFE_ACTUAL_EXECUTION_TRACE_JSON,
    customer_safe_actual_execution_trace_markdown_path: Path = CUSTOMER_SAFE_ACTUAL_EXECUTION_TRACE_MD,
    goal_evidence_actual_trace_overlay_path: Path = GOAL_EVIDENCE_ACTUAL_TRACE_OVERLAY_JSON,
    goal_evidence_actual_trace_overlay_markdown_path: Path = GOAL_EVIDENCE_ACTUAL_TRACE_OVERLAY_MD,
    remaining_operator_completion_simulation_path: Path = REMAINING_OPERATOR_COMPLETION_SIMULATION_JSON,
    remaining_operator_completion_simulation_markdown_path: Path = REMAINING_OPERATOR_COMPLETION_SIMULATION_MD,
) -> dict[str, Any]:
    completion_gate = read_json(completion_gate_path)
    requirement_trace = read_json(requirement_trace_path)
    evidence_ledger = read_json(evidence_ledger_path)
    safe_runner = read_json(safe_runner_summary_path)
    next_queue = read_json(next_approval_queue_path)
    completion_audit = read_json(completion_audit_path)
    bundle_validation = read_json(bundle_validation_path)
    final_evidence_fill_queue = read_json(final_evidence_fill_queue_path)
    rks_gate_matrix = read_json(rks_gate_matrix_path)
    customer_safe_smoke = read_json(customer_safe_smoke_path)
    goal_evidence_actual_trace_overlay = read_json(
        goal_evidence_actual_trace_overlay_path
    )
    remaining_operator_completion_simulation = read_json(
        remaining_operator_completion_simulation_path
    )
    gates = list(completion_gate.get("gates", []))
    requirement_rows = list(requirement_trace.get("rows", []))
    ledger_rows = list(evidence_ledger.get("rows", []))
    incomplete_requirement_rows = incomplete_requirements(requirement_rows)
    blocking_gate_rows = blocking_gates(gates)
    final_goal_complete = bool(completion_gate.get("final_goal_complete", False))
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "report_status": "FINAL_COMPLETE_REPORT" if final_goal_complete else "DRAFT_PROGRESS_REPORT_NOT_FINAL",
        "final_goal_complete": final_goal_complete,
        "safety": "read-only report consolidation only; no external operation",
        "source_paths": {
            "completion_gate": str(completion_gate_path),
            "requirement_trace": str(requirement_trace_path),
            "evidence_ledger": str(evidence_ledger_path),
            "safe_runner_summary": str(safe_runner_summary_path),
            "next_approval_queue": str(next_approval_queue_path),
            "completion_audit": str(completion_audit_path),
            "bundle_validation": str(bundle_validation_path),
            "final_evidence_fill_queue": str(final_evidence_fill_queue_path),
            "rks_gate_matrix": str(rks_gate_matrix_path),
            "customer_safe_smoke": str(customer_safe_smoke_path),
            "customer_safe_smoke_markdown": str(customer_safe_smoke_markdown_path),
            "customer_safe_actual_execution_trace": str(
                customer_safe_actual_execution_trace_path
            ),
            "customer_safe_actual_execution_trace_markdown": str(
                customer_safe_actual_execution_trace_markdown_path
            ),
            "goal_evidence_actual_trace_overlay": str(
                goal_evidence_actual_trace_overlay_path
            ),
            "goal_evidence_actual_trace_overlay_markdown": str(
                goal_evidence_actual_trace_overlay_markdown_path
            ),
            "remaining_operator_completion_simulation": str(
                remaining_operator_completion_simulation_path
            ),
            "remaining_operator_completion_simulation_markdown": str(
                remaining_operator_completion_simulation_markdown_path
            ),
        },
        "source_exists": {
            "completion_gate": completion_gate_path.exists(),
            "requirement_trace": requirement_trace_path.exists(),
            "evidence_ledger": evidence_ledger_path.exists(),
            "safe_runner_summary": safe_runner_summary_path.exists(),
            "next_approval_queue": next_approval_queue_path.exists(),
            "completion_audit": completion_audit_path.exists(),
            "bundle_validation": bundle_validation_path.exists(),
            "final_evidence_fill_queue": final_evidence_fill_queue_path.exists(),
            "rks_gate_matrix": rks_gate_matrix_path.exists(),
            "customer_safe_smoke": customer_safe_smoke_path.exists(),
            "customer_safe_smoke_markdown": customer_safe_smoke_markdown_path.exists(),
            "customer_safe_actual_execution_trace": (
                customer_safe_actual_execution_trace_path.exists()
            ),
            "customer_safe_actual_execution_trace_markdown": (
                customer_safe_actual_execution_trace_markdown_path.exists()
            ),
            "goal_evidence_actual_trace_overlay": (
                goal_evidence_actual_trace_overlay_path.exists()
            ),
            "goal_evidence_actual_trace_overlay_markdown": (
                goal_evidence_actual_trace_overlay_markdown_path.exists()
            ),
            "remaining_operator_completion_simulation": (
                remaining_operator_completion_simulation_path.exists()
            ),
            "remaining_operator_completion_simulation_markdown": (
                remaining_operator_completion_simulation_markdown_path.exists()
            ),
        },
        "safe_runner_passed": safe_runner.get("overall_passed") is True,
        "completion_audit_summary": build_completion_audit_summary(completion_audit),
        "reference_integrity_summary": build_reference_integrity_summary(bundle_validation),
        "final_evidence_fill_summary": build_final_evidence_fill_summary(final_evidence_fill_queue),
        "rks_existing_evidence_search_summary": build_rks_existing_evidence_search_summary(
            rks_gate_matrix
        ),
        "customer_safe_smoke_summary": build_customer_safe_smoke_summary(
            customer_safe_smoke,
            customer_safe_smoke_path,
            customer_safe_smoke_markdown_path,
            customer_safe_actual_execution_trace_path,
            customer_safe_actual_execution_trace_markdown_path,
        ),
        "goal_evidence_actual_trace_overlay_summary": (
            build_goal_evidence_actual_trace_overlay_summary(
                goal_evidence_actual_trace_overlay,
                goal_evidence_actual_trace_overlay_path,
                goal_evidence_actual_trace_overlay_markdown_path,
            )
        ),
        "remaining_operator_completion_simulation_summary": (
            build_remaining_operator_completion_simulation_summary(
                remaining_operator_completion_simulation,
                remaining_operator_completion_simulation_path,
                remaining_operator_completion_simulation_markdown_path,
            )
        ),
        "gate_count": int(completion_gate.get("gate_count", 0) or 0),
        "passed_gate_count": int(completion_gate.get("passed_gate_count", 0) or 0),
        "blocking_gate_count": int(completion_gate.get("blocking_gate_count", len(blocking_gate_rows)) or 0),
        "blocking_gates": blocking_gate_rows,
        "requirement_count": int(requirement_trace.get("requirement_count", len(requirement_rows)) or 0),
        "incomplete_requirement_count": len(incomplete_requirement_rows),
        "incomplete_requirements": incomplete_requirement_rows,
        "scenario_count": int(evidence_ledger.get("scenario_count", len(ledger_rows)) or 0),
        "complete_goal_evidence_count": int(evidence_ledger.get("complete_goal_evidence_count", 0) or 0),
        "objective_progress_summary": build_objective_progress_summary(
            evidence_ledger,
            ledger_rows,
        ),
        "ledger_rows": ledger_rows,
        "next_bundle": str(next_queue.get("next_bundle", "")),
        "next_operator_action": str(next_queue.get("next_operator_action", "")),
        "next_action_summary": build_next_action_summary(next_queue),
    }


def build_markdown(payload: dict[str, Any]) -> str:
    status = "完了" if payload["final_goal_complete"] else "未完了（ドラフト）"
    lines = [
        "# 全シナリオ稼働確認 最終報告ドラフト 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- report_status: `{payload['report_status']}`",
        f"- final_goal_complete: `{payload['final_goal_complete']}`",
        f"- verdict: `{status}`",
        f"- safety: `{payload['safety']}`",
        f"- safe_runner_passed: `{payload['safe_runner_passed']}`",
        f"- gate_progress: `{payload['passed_gate_count']}/{payload['gate_count']}`",
        f"- blocking_gate_count: `{payload['blocking_gate_count']}`",
        f"- requirement_progress: `{payload['requirement_count'] - payload['incomplete_requirement_count']}/{payload['requirement_count']}`",
        f"- scenario_goal_evidence: `{payload['complete_goal_evidence_count']}/{payload['scenario_count']}`",
        "",
        "## Boundary",
        "",
        "- This is not a production completion report until `final_goal_complete=True`.",
        "- It does not run Outlook, RK10, Rakuraku, Azure, mail, print, payment, MainSV, or production writes.",
        "- RKS `OK_CANDIDATE`, static guard, or safe-stop evidence is not treated as production runtime completion.",
        "",
    ]
    objective_progress = payload.get("objective_progress_summary", {})
    if isinstance(objective_progress, dict):
        scenario_count = int(objective_progress.get("scenario_count", 0) or 0)
        lines.extend(
            [
                "## Objective Progress Summary",
                "",
                f"- sample_ready_count: `{objective_progress.get('sample_ready_count', 0)}/{scenario_count}`",
                f"- safe_execution_ready_count: `{objective_progress.get('safe_execution_ready_count', 0)}/{scenario_count}`",
                f"- rks_scoped_or_not_applicable_count: `{objective_progress.get('rks_scoped_or_not_applicable_count', 0)}/{scenario_count}`",
                f"- business_amount_or_draft_count: `{objective_progress.get('business_amount_or_draft_count', 0)}/{scenario_count}`",
                f"- business_count_only_scope_count: `{objective_progress.get('business_count_only_scope_count', 0)}/{scenario_count}`",
                f"- business_cost_scope_count: `{objective_progress.get('business_amount_or_draft_count', 0) + objective_progress.get('business_count_only_scope_count', 0)}/{scenario_count}`",
                f"- final_evidence_ready_count: `{objective_progress.get('final_evidence_ready_count', 0)}/{scenario_count}`",
                "- These counts are progress evidence only; they do not override `final_goal_complete=False`.",
                "",
            ]
        )
    remaining_simulation = payload.get(
        "remaining_operator_completion_simulation_summary", {}
    )
    if (
        isinstance(remaining_simulation, dict)
        and remaining_simulation.get("source_exists")
    ):
        lines.extend(
            [
                "## Remaining Operator Input Completion Simulation",
                "",
                f"- source_generated_at: `{remaining_simulation.get('generated_at', '')}`",
                f"- simulation_passed: `{remaining_simulation.get('simulation_passed', False)}`",
                f"- sample_completed_row_count: `{remaining_simulation.get('sample_completed_row_count', 0)}`",
                f"- sync_updated_cell_count: `{remaining_simulation.get('sync_updated_cell_count', 0)}`",
                f"- sync_conflict_count: `{remaining_simulation.get('sync_conflict_count', 0)}`",
                f"- sync_unsafe_target_count: `{remaining_simulation.get('sync_unsafe_target_count', 0)}`",
                f"- validation_all_packet_rows_approved: `{remaining_simulation.get('validation_all_packet_rows_approved', False)}`",
                f"- validation_approved_row_count: `{remaining_simulation.get('validation_approved_row_count', 0)}/{remaining_simulation.get('validation_row_count', 0)}`",
                f"- validation_needs_attention_count: `{remaining_simulation.get('validation_needs_attention_count', 0)}`",
                f"- source_files_modified: `{remaining_simulation.get('source_files_modified', True)}`",
                f"- production_completion_scope: `{remaining_simulation.get('production_completion_scope', '')}`",
                f"- safety: `{remaining_simulation.get('safety', '')}`",
                f"- source_json: `{remaining_simulation.get('source_json', '')}`",
                f"- source_markdown_numbered: `{remaining_simulation.get('source_markdown_numbered', '')}`",
                f"- validation_report_md: `{remaining_simulation.get('validation_report_md', '')}`",
                "- This simulation proves the input/sync/validation route on copied CSVs only; it does not replace actual customer/operator approval.",
                "",
            ]
        )
    customer_safe_smoke = payload.get("customer_safe_smoke_summary", {})
    if isinstance(customer_safe_smoke, dict) and customer_safe_smoke.get("source_exists"):
        lines.extend(
            [
                "## Customer Safe Entry Full Smoke",
                "",
                f"- source_generated_at: `{customer_safe_smoke.get('generated_at', '')}`",
                f"- expected_exit_code_match: `{customer_safe_smoke.get('expected_match', '')}`",
                f"- unexpected_count: `{customer_safe_smoke.get('unexpected_count', 0)}`",
                f"- timeout_count: `{customer_safe_smoke.get('timeout_count', 0)}`",
                f"- cleanup_remaining_count: `{customer_safe_smoke.get('cleanup_remaining_count', 0)}`",
                f"- run_dir: `{customer_safe_smoke.get('run_dir', '')}`",
                f"- validation_json: `{customer_safe_smoke.get('validation_json', '')}`",
                f"- safety: `{customer_safe_smoke.get('safety', '')}`",
                f"- license_policy: `{customer_safe_smoke.get('license_policy', '')}`",
                f"- source_json: `{customer_safe_smoke.get('source_json', '')}`",
                f"- source_markdown_numbered: `{customer_safe_smoke.get('source_markdown_numbered', '')}`",
                f"- source_scenario_matrix_numbered: `{customer_safe_smoke.get('source_scenario_matrix_numbered', '')}`",
                f"- source_scenario_matrix_exists: `{customer_safe_smoke.get('source_scenario_matrix_exists', False)}`",
                f"- source_actual_execution_trace_numbered: `{customer_safe_smoke.get('source_actual_execution_trace_numbered', '')}`",
                f"- source_actual_execution_trace_exists: `{customer_safe_smoke.get('source_actual_execution_trace_exists', False)}`",
                f"- actual_trace_expected_ok: `{customer_safe_smoke.get('actual_trace_expected_ok_count', 0)}/{customer_safe_smoke.get('actual_trace_entry_count', 0)}`",
                f"- actual_trace_script_missing_count: `{customer_safe_smoke.get('actual_trace_script_missing_count', 0)}`",
                "",
            ]
        )
        notable_rows = customer_safe_smoke.get("notable_rows", [])
        if isinstance(notable_rows, list) and notable_rows:
            lines.extend(
                [
                    "| Entry | Exit | Expected | Expected OK | Timeout | Seconds | Cleanup Remaining | Note |",
                    "|---|---:|---|---|---|---:|---:|---|",
                ]
            )
            for row in notable_rows:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            str(row.get("name", "")),
                            str(row.get("exit_code", "")),
                            str(row.get("expected_exit_codes", "")),
                            str(row.get("expected_ok", "")),
                            str(row.get("timed_out", "")),
                            str(row.get("elapsed_seconds", "")),
                            str(row.get("cleanup_remaining_count", "")),
                            str(row.get("note", "")).replace("|", "/") or "-",
                        ]
                    )
                    + " |"
                )
            lines.append("")
    goal_trace_overlay = payload.get("goal_evidence_actual_trace_overlay_summary", {})
    if isinstance(goal_trace_overlay, dict) and goal_trace_overlay.get("source_exists"):
        lines.extend(
            [
                "## Goal Evidence Actual Trace Overlay",
                "",
                f"- source_generated_at: `{goal_trace_overlay.get('generated_at', '')}`",
                f"- scenario_trace_ready: `{goal_trace_overlay.get('trace_ready_scenario_count', 0)}/{goal_trace_overlay.get('scenario_count', 0)}`",
                f"- trace_missing_scenario_count: `{goal_trace_overlay.get('trace_missing_scenario_count', 0)}`",
                f"- trace_script_missing_count: `{goal_trace_overlay.get('trace_script_missing_count', 0)}`",
                f"- production_completion_scope: `{goal_trace_overlay.get('production_completion_scope', '')}`",
                f"- source_json: `{goal_trace_overlay.get('source_json', '')}`",
                f"- source_markdown_numbered: `{goal_trace_overlay.get('source_markdown_numbered', '')}`",
                f"- source_markdown_exists: `{goal_trace_overlay.get('source_markdown_exists', False)}`",
                f"- safety: `{goal_trace_overlay.get('safety', '')}`",
                "",
            ]
        )
    rks_existing_search = payload.get("rks_existing_evidence_search_summary", {})
    if isinstance(rks_existing_search, dict):
        lines.extend(
            [
                "## RKS Existing Evidence Search",
                "",
                f"- source_generated_at: `{rks_existing_search.get('source_generated_at', '')}`",
                f"- overall_rks_production_ready: `{rks_existing_search.get('overall_rks_production_ready', False)}`",
                f"- reviewed_non_promotable_count: `{rks_existing_search.get('reviewed_non_promotable_count', 0)}`",
                "",
            ]
        )
        search_rows = rks_existing_search.get("rows", [])
        if isinstance(search_rows, list) and search_rows:
            lines.extend(
                [
                    "| Scenario | Current RKS Status | Runtime Intake Status | Existing Evidence Search Result | Next Safe Action |",
                    "|---|---|---|---|---|",
                ]
            )
            for row in search_rows:
                if isinstance(row, dict):
                    lines.append(
                        "| "
                        + " | ".join(
                            [
                                str(row.get("scenario", "")),
                                str(row.get("current_rks_status", "")).replace("|", "/"),
                                str(row.get("runtime_intake_status", "")).replace("|", "/"),
                                str(row.get("existing_evidence_search_result", "")).replace("|", "/"),
                                str(row.get("next_safe_action", "")).replace("|", "/"),
                            ]
                        )
                        + " |"
                    )
            lines.append("")
    lines.extend(
        [
            "## Completion Audit",
            "",
        ]
    )
    audit_summary = payload.get("completion_audit_summary", {})
    if isinstance(audit_summary, dict):
        lines.extend(
            [
                f"- audit_status: `{audit_summary.get('report_status', '')}`",
                f"- audit_goal_complete: `{audit_summary.get('overall_goal_complete', False)}`",
                f"- issue_count: `{audit_summary.get('issue_count', 0)}`",
                f"- missing_source_count: `{audit_summary.get('missing_source_count', 0)}`",
                f"- packet_approved_row_count: `{audit_summary.get('packet_approved_row_count', 0)}`",
                f"- packet_needs_attention_count: `{audit_summary.get('packet_needs_attention_count', 0)}`",
                f"- bundle_final_evidence_ready_count: `{audit_summary.get('bundle_final_evidence_ready_count', 0)}/{audit_summary.get('bundle_count', 0)}`",
                f"- rks_runtime_approved_count: `{audit_summary.get('rks_runtime_approved_count', 0)}/{audit_summary.get('rks_runtime_required_count', 0)}`",
                f"- amount_verified_scenario_count: `{audit_summary.get('amount_verified_scenario_count', 0)}`",
                f"- issues_csv: `{audit_summary.get('issues_csv', '')}`",
                "",
            ]
        )
    reference_integrity = payload.get("reference_integrity_summary", {})
    if isinstance(reference_integrity, dict):
        lines.extend(
            [
                "## Reference Evidence Integrity",
                "",
                f"- prepared_pack_validation_passed: `{reference_integrity.get('prepared_pack_validation_passed', False)}`",
                f"- source_reference_exists_now_count: `{reference_integrity.get('source_reference_exists_now_count', 0)}/{reference_integrity.get('source_reference_count', 0)}`",
                f"- source_reference_hashed_now_count: `{reference_integrity.get('source_reference_hashed_now_count', 0)}/{reference_integrity.get('source_reference_count', 0)}`",
                f"- missing_prepared_pack_count: `{reference_integrity.get('missing_prepared_pack_count', 0)}`",
                f"- final_evidence_ready_count: `{reference_integrity.get('final_evidence_ready_count', 0)}/{reference_integrity.get('bundle_count', 0)}`",
                "",
            ]
        )
    fill_summary = payload.get("final_evidence_fill_summary", {})
    if isinstance(fill_summary, dict):
        lines.extend(
            [
                "## Final Evidence Fill Queue",
                "",
                f"- active_queue_count: `{fill_summary.get('active_queue_count', 0)}`",
                f"- ready_or_completed_count: `{fill_summary.get('ready_or_completed_count', 0)}`",
                f"- operator_attention_row_count: `{fill_summary.get('operator_attention_row_count', 0)}`",
                f"- next_active_bundle: `{fill_summary.get('next_active_bundle', '')}`",
                f"- unified_input_csv: `{fill_summary.get('unified_input_csv', '')}`",
                f"- next_entry_keys: `{fill_summary.get('next_entry_keys', '')}`",
                f"- next_fill_only_fields: `{fill_summary.get('next_fill_only_fields', '')}`",
                f"- next_start_here_path: `{fill_summary.get('next_start_here_path', '')}`",
                f"- next_missing_operator_fields: `{fill_summary.get('next_missing_operator_fields', '')}`",
                f"- next_supplemental_evidence_status: `{fill_summary.get('next_supplemental_evidence_status', '')}`",
                f"- next_supplemental_evidence_source: `{fill_summary.get('next_supplemental_evidence_source', '')}`",
                f"- supplemental_evidence_bundle: `{fill_summary.get('supplemental_evidence_bundle', '')}`",
                f"- supplemental_evidence_status: `{fill_summary.get('supplemental_evidence_status', '')}`",
                f"- supplemental_evidence_source: `{fill_summary.get('supplemental_evidence_source', '')}`",
                f"- supplemental_remaining_runtime_evidence: `{fill_summary.get('supplemental_remaining_runtime_evidence', '')}`",
                f"- after_action_command: `{fill_summary.get('after_action_command', '')}`",
                "",
            ]
        )
    lines.extend(
        [
        "## Blocking Gates",
        "",
        "| Gate | Status | Detail | Next Action | Source |",
        "|---|---|---|---|---|",
        ]
    )
    for gate in payload["blocking_gates"]:
        assert isinstance(gate, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(gate.get("gate", "")),
                    str(gate.get("status", "")),
                    str(gate.get("detail", "")).replace("|", "/"),
                    str(gate.get("next_action", "")).replace("|", "/"),
                    f"`{gate.get('source', '')}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Incomplete Requirements",
            "",
            "| ID | Requirement | Status | Remaining Gap | Next Evidence Needed | Evidence |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in payload["incomplete_requirements"]:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("requirement_id", "")),
                    str(row.get("requirement", "")).replace("|", "/"),
                    str(row.get("current_status", "")),
                    str(row.get("remaining_gap", "")).replace("|", "/"),
                    str(row.get("next_evidence_needed", "")).replace("|", "/"),
                    f"`{row.get('authoritative_evidence', '')}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Scenario Snapshot",
            "",
            "| Scenario | Checkpoints | Missing Proofs | Evidence Strength |",
            "|---|---|---|---|",
        ]
    )
    for row in first_rows(payload["ledger_rows"], 15):
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("scenario", "")),
                    str(row.get("objective_checkpoint_summary", "")).replace("|", "/"),
                    str(row.get("missing_objective_proofs", "")).replace("|", "/"),
                    str(row.get("evidence_strength", "")).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Next Bundle",
            "",
            f"- next_bundle: `{payload['next_bundle']}`",
            f"- next_operator_action: {payload['next_operator_action'] or '-'}",
            "",
            "## Next Action Detail",
            "",
        ]
    )
    next_action_summary = payload.get("next_action_summary", {})
    if isinstance(next_action_summary, dict):
        lines.extend(
            [
                f"- owner: `{next_action_summary.get('owner', '')}`",
                f"- scenarios: `{next_action_summary.get('scenarios', '')}`",
                f"- approval_boundary: `{next_action_summary.get('approval_boundary', '')}`",
                f"- forbidden: `{next_action_summary.get('forbidden', '')}`",
                f"- evidence_pack_path: `{next_action_summary.get('evidence_pack_path', '')}`",
                f"- bundle_sheet_path: `{next_action_summary.get('bundle_sheet_path', '')}`",
                f"- external_runbook: `{next_action_summary.get('external_runbook', '')}`",
                f"- external_runbook_json: `{next_action_summary.get('external_runbook_json', '')}`",
                f"- outlook_bundle_script: `{next_action_summary.get('outlook_bundle_script', '')}`",
                f"- outlook_recovery_checklist: `{next_action_summary.get('outlook_recovery_checklist', '')}`",
                f"- outlook_com_diagnosis_report: `{next_action_summary.get('outlook_com_diagnosis_report', '')}`",
                f"- rk10_recovery_checklist: `{next_action_summary.get('rk10_recovery_checklist', '')}`",
                f"- after_action_command: `{next_action_summary.get('after_action_command', '')}`",
            ]
        )
        supporting_input_paths = next_action_summary.get("supporting_input_paths", [])
        if isinstance(supporting_input_paths, list) and supporting_input_paths:
            lines.append("- supporting_input_paths:")
            for row in supporting_input_paths:
                if isinstance(row, dict):
                    lines.append(
                        f"  - {row.get('label', '')}: `{row.get('path', '')}`"
                    )
        lines.append("")
    lines.extend(
        [
            "## Source Reports",
            "",
        ]
    )
    for label, source_path in payload["source_paths"].items():
        exists = payload["source_exists"].get(label)
        lines.append(f"- {label}: `{source_path}` exists=`{exists}`")
    field_export_paths = payload.get("field_export_paths", {})
    if isinstance(field_export_paths, dict) and field_export_paths:
        lines.extend(["", "## Field Exports", ""])
        for label, export_path in field_export_paths.items():
            lines.append(f"- {label}: `{export_path}`")
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def project_csv_rows(
    rows: list[dict[str, Any]],
    fieldnames: list[str],
) -> list[dict[str, str]]:
    return [
        {fieldname: str(row.get(fieldname, "")) for fieldname in fieldnames}
        for row in rows
    ]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(project_csv_rows(rows, fieldnames))


def write_field_export_csvs(payload: dict[str, Any], out_dir: Path) -> dict[str, str]:
    exports = {
        "blocking_gates_csv": out_dir / "goal_final_report_blocking_gates.csv",
        "incomplete_requirements_csv": out_dir
        / "goal_final_report_incomplete_requirements.csv",
        "scenario_snapshot_csv": out_dir / "goal_final_report_scenario_snapshot.csv",
    }
    write_csv(
        exports["blocking_gates_csv"],
        BLOCKING_GATE_CSV_FIELDS,
        list(payload.get("blocking_gates", [])),
    )
    write_csv(
        exports["incomplete_requirements_csv"],
        INCOMPLETE_REQUIREMENT_CSV_FIELDS,
        list(payload.get("incomplete_requirements", [])),
    )
    write_csv(
        exports["scenario_snapshot_csv"],
        SCENARIO_SNAPSHOT_CSV_FIELDS,
        list(payload.get("ledger_rows", [])),
    )
    return {label: str(path) for label, path in exports.items()}


def write_outputs(payload: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    field_export_paths = write_field_export_csvs(payload, out_dir)
    payload_to_write = {**payload, "field_export_paths": field_export_paths}
    json_path = out_dir / "goal_final_report.json"
    md_path = out_dir / "goal_final_report.md"
    json_path.write_text(json.dumps(payload_to_write, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload_to_write), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    return {"json": str(json_path), "markdown": str(md_path), **field_export_paths}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate current goal final-report draft.")
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
