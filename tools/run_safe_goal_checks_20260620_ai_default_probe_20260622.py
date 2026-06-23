"""Run fixed read-only RK10 goal checks with one approved command.

This runner intentionally does not open Outlook, RK10, Rakuraku, Azure,
printers, mail clients, payment systems, or production Excel/MainSV paths.
It only compiles local checker scripts, runs local unit tests, executes
read-only evidence checkers, and writes reports inside this repository.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "safe_goal_checks_20260620"

CHECK_HOLD = ROOT / "tools" / "check_hold_release_gates_20260620.py"
CHECK_OUTLOOK_SAVE_PDF = ROOT / "tools" / "outlook_save_pdf_and_batch_print.py"
CHECK_SNAPSHOT = ROOT / "tools" / "generate_goal_status_snapshot_20260620.py"
CHECK_RUNNER = ROOT / "tools" / "run_safe_goal_checks_20260620_ai_default_probe_20260622.py"
CHECK_S44_SPOT = ROOT / "tools" / "build_s44_spot_check_handoff_candidates_20260620.py"
CHECK_S44_REVIEW_DB_AMOUNT_EVIDENCE = ROOT / "tools" / "analyze_s44_review_db_amount_evidence_20260622.py"
CHECK_S44_SAMPLE_OK = ROOT / "tools" / "run_s44_sample_ok_shadow_20260620.py"
CHECK_S44_QUICK_BUCKET_SIMULATION = ROOT / "tools" / "run_s44_quick_bucket_ok_simulation_20260621.py"
CHECK_S70_SAMPLE_PREVIEW = ROOT / "tools" / "run_s70_sample_confirm_preview_20260620.py"
CHECK_S71_SAMPLE_MOCK_OCR = ROOT / "tools" / "validate_s71_sample_mock_ocr_apply_20260620.py"
CHECK_S71_PAID_AZURE_OCR_EVIDENCE_COLLECT = (
    ROOT / "tools" / "collect_s71_paid_azure_ocr_evidence_20260620.py"
)
CHECK_RKS_MATRIX = ROOT / "tools" / "generate_rks_gate_matrix_20260620.py"
CHECK_RKS_STATIC_GUARD = ROOT / "tools" / "generate_rks_static_guard_audit_20260620.py"
CHECK_RKS_DEBUGGER_RECONCILE = ROOT / "tools" / "generate_rks_debugger_artifact_reconcile_20260620.py"
CHECK_RKS_EDITOR_OPEN_BUILD_PROBE = ROOT / "tools" / "run_rks_editor_open_build_probe_20260620_safe_exe_default_20260622.py"
CHECK_RKS_RUNTIME_OPERATOR_PACK = ROOT / "tools" / "generate_rks_runtime_operator_pack_20260620.py"
CHECK_RKS_RUNTIME_STATUS_GATE_SYNC = ROOT / "tools" / "sync_rks_runtime_evidence_from_status_gates_20260620.py"
CHECK_RKS_RUNTIME_INTAKE_VALIDATION = ROOT / "tools" / "validate_rks_runtime_operator_intake_20260620.py"
CHECK_RKS_MATRIX_OPEN_PROBE = ROOT / "tools" / "generate_rks_gate_matrix_20260620_open_probe_20260622.py"
CHECK_SAMPLE_DATA_MAP = ROOT / "tools" / "generate_sample_data_evidence_map_20260620.py"
CHECK_SAFE_EXECUTION_MAP = ROOT / "tools" / "generate_safe_execution_evidence_map_20260620.py"
CHECK_BUSINESS_COST_MAP = ROOT / "tools" / "generate_business_cost_evidence_map_20260620.py"
CHECK_UNBLOCK_BOARD = ROOT / "tools" / "generate_goal_unblock_board_20260620_ai_default_probe_20260622.py"
CHECK_EXECUTION_PACKET = ROOT / "tools" / "generate_goal_execution_packet_20260620_ai_default_probe_20260622.py"
CHECK_BUNDLE_EVIDENCE_PACKS = ROOT / "tools" / "generate_bundle_evidence_packs_20260620.py"
CHECK_RK10_RUNTIME_BUNDLE_EVIDENCE_COLLECT = (
    ROOT / "tools" / "collect_rk10_runtime_bundle_evidence_20260620.py"
)
CHECK_BUSINESS_DATA_APPROVAL_EVIDENCE_COLLECT = (
    ROOT / "tools" / "collect_business_data_approval_evidence_20260620.py"
)
CHECK_S44_BUSINESS_REVIEW_EVIDENCE_COLLECT = ROOT / "tools" / "collect_s44_business_review_evidence_20260620.py"
CHECK_S70_PAYMENT_APPROVAL_EVIDENCE_COLLECT = ROOT / "tools" / "collect_s70_payment_approval_evidence_20260620.py"
CHECK_OUTLOOK_BUNDLE_EVIDENCE_COLLECT = ROOT / "tools" / "collect_outlook_bundle_evidence_20260620.py"
CHECK_BUNDLE_OPERATOR_SHEET = ROOT / "tools" / "generate_bundle_operator_sheet_20260620.py"
CHECK_UNIFIED_FINAL_EVIDENCE_INTAKE_SYNC = ROOT / "tools" / "sync_unified_final_evidence_intake_20260621.py"
CHECK_FINAL_EVIDENCE_CANDIDATE_STAGE = ROOT / "tools" / "stage_final_evidence_candidates_20260621.py"
CHECK_EXECUTION_PACKET_CANDIDATE_PATH_SYNC = (
    ROOT / "tools" / "sync_execution_packet_candidate_evidence_paths_20260621.py"
)
CHECK_BUNDLE_EVIDENCE_INTAKE_SYNC = ROOT / "tools" / "sync_bundle_evidence_intake_20260620.py"
CHECK_BUNDLE_EVIDENCE_PACK_VALIDATION = ROOT / "tools" / "validate_bundle_evidence_packs_20260620.py"
CHECK_CODE_BACKUP = ROOT / "tools" / "backup_goal_code_artifacts_20260620_ai_default_probe_20260622.py"
CHECK_EXTERNAL_APPROVAL_RUNBOOK = ROOT / "tools" / "generate_external_approval_runbook_20260620_ai_default_probe_20260622.py"
CHECK_NEXT_APPROVAL_QUEUE = ROOT / "tools" / "generate_next_approval_queue_20260620_ai_default_probe_20260622.py"
CHECK_OUTLOOK_COM_ENV = ROOT / "tools" / "diagnose_outlook_com_environment_20260620.py"
CHECK_OPERATOR_EVIDENCE_PREFILL = ROOT / "tools" / "generate_operator_evidence_prefill_20260620.py"
CHECK_REMAINING_APPROVAL_NEXT_STEPS = ROOT / "tools" / "generate_remaining_approval_next_steps_20260621.py"
CHECK_EXECUTION_PACKET_VALIDATION = (
    ROOT / "tools" / "validate_goal_execution_packet_scope_exclusions_20260623.py"
)
CHECK_FINAL_EVIDENCE_FILL_QUEUE = ROOT / "tools" / "generate_final_evidence_fill_queue_20260621.py"
CHECK_NEXT_BUNDLE_MINIMUM_INPUT_PACKET = ROOT / "tools" / "generate_next_bundle_minimum_input_packet_20260622.py"
CHECK_REMAINING_OPERATOR_INPUT_PACKET = ROOT / "tools" / "generate_remaining_operator_input_packet_20260623.py"
CHECK_REMAINING_OPERATOR_INPUT_READY_VALIDATION = (
    ROOT / "tools" / "validate_remaining_operator_input_ready_20260623.py"
)
CHECK_REMAINING_OPERATOR_FINAL_REVIEW_PACK = (
    ROOT / "tools" / "generate_remaining_operator_final_review_pack_20260623.py"
)
CHECK_MINIMUM_OPERATOR_REVIEW_INPUT = (
    ROOT / "tools" / "generate_minimum_operator_review_input_20260623.py"
)
CHECK_AUTO_FILL_MINIMUM_OPERATOR_REVIEW_INPUT = (
    ROOT / "tools" / "auto_fill_minimum_operator_review_input_20260623.py"
)
CHECK_REMAINING_OPERATOR_DECISION_BRIEF = (
    ROOT / "tools" / "generate_remaining_operator_decision_brief_20260623.py"
)
CHECK_REMAINING_OPERATOR_INPUT_PACKET_SYNC = ROOT / "tools" / "sync_remaining_operator_input_packet_20260623.py"
CHECK_REMAINING_OPERATOR_INPUT_COMPLETION_SIMULATION = ROOT / "tools" / "simulate_remaining_operator_input_completion_20260623.py"
CHECK_REMAINING_OPERATOR_FULL_GATE_SIMULATION = (
    ROOT / "tools" / "simulate_remaining_operator_full_gate_completion_20260623.py"
)
CHECK_REMAINING_OPERATOR_EVIDENCE_DIGEST = (
    ROOT / "tools" / "generate_remaining_operator_evidence_digest_20260623.py"
)
CHECK_PROD_MIGRATION_READINESS = ROOT / "tools" / "generate_prod_migration_readiness_20260620.py"
CHECK_EVIDENCE_LEDGER = ROOT / "tools" / "generate_goal_evidence_ledger_20260620.py"
CHECK_OBJECTIVE_COMPLETION_AUDIT = (
    ROOT / "tools" / "generate_objective_completion_audit_20260623.py"
)
CHECK_EVIDENCE_ACTUAL_TRACE_OVERLAY = (
    ROOT / "tools" / "generate_goal_evidence_actual_trace_overlay_20260623.py"
)
CHECK_STATUS_RKS_RUNTIME_OVERLAY = (
    ROOT / "tools" / "generate_goal_status_snapshot_rks_runtime_overlay_20260623.py"
)
CHECK_COMPLETION_AUDIT = ROOT / "tools" / "generate_goal_completion_audit_20260620.py"
CHECK_REQUIREMENT_TRACE = ROOT / "tools" / "generate_goal_requirement_traceability_20260620.py"
CHECK_COMPLETION_GATE = ROOT / "tools" / "generate_goal_completion_gate_20260620_open_probe_20260622.py"
CHECK_FINAL_REPORT = ROOT / "tools" / "generate_goal_final_report_20260620.py"
CHECK_PROD_READINESS_BREAKDOWN = ROOT / "tools" / "generate_prod_readiness_remaining_work_breakdown_20260622.py"
CHECK_FINAL_INPUT_AUTONOMOUS_BOUNDARY = ROOT / "tools" / "generate_final_input_autonomous_boundary_20260622.py"
CHECK_COMPLETION_BLOCKER_SPLIT = ROOT / "tools" / "generate_completion_blocker_split_20260622.py"
CHECK_CUSTOMER_SAFE_SCENARIO_MATRIX = ROOT / "tools" / "generate_customer_safe_entries_full_smoke_report_20260622.py"
TEST_HOLD = ROOT / "tests" / "test_check_hold_release_gates_20260620.py"
TEST_OUTLOOK_EXTRACT_INVOICE_FIELDS = ROOT / "tests" / "test_outlook_save_pdf_and_batch_print_extract_invoice_fields.py"
TEST_RUNNER = ROOT / "tests" / "test_run_safe_goal_checks_20260620.py"
TEST_RUNNER_AI_DEFAULT_OPEN_PROBE = ROOT / "tests" / "test_run_safe_goal_checks_ai_default_open_probe_20260622.py"
TEST_SNAPSHOT = ROOT / "tests" / "test_generate_goal_status_snapshot_20260620.py"
TEST_S44_SPOT = ROOT / "tests" / "test_build_s44_spot_check_handoff_candidates_20260620.py"
TEST_S44_REVIEW_DB_AMOUNT_EVIDENCE = ROOT / "tests" / "test_analyze_s44_review_db_amount_evidence_20260622.py"
TEST_S44_SAMPLE_OK = ROOT / "tests" / "test_run_s44_sample_ok_shadow_20260620.py"
TEST_S44_QUICK_BUCKET_SIMULATION = ROOT / "tests" / "test_run_s44_quick_bucket_ok_simulation_20260621.py"
TEST_S70_SAMPLE_PREVIEW = ROOT / "tests" / "test_run_s70_sample_confirm_preview_20260620.py"
TEST_S71_SAMPLE_MOCK_OCR = ROOT / "tests" / "test_validate_s71_sample_mock_ocr_apply_20260620.py"
TEST_S71_PAID_AZURE_OCR_EVIDENCE_COLLECT = (
    ROOT / "tests" / "test_collect_s71_paid_azure_ocr_evidence_20260620.py"
)
TEST_RKS_MATRIX = ROOT / "tests" / "test_generate_rks_gate_matrix_20260620.py"
TEST_RKS_STATIC_GUARD = ROOT / "tests" / "test_generate_rks_static_guard_audit_20260620.py"
TEST_RKS_DEBUGGER_RECONCILE = ROOT / "tests" / "test_generate_rks_debugger_artifact_reconcile_20260620.py"
TEST_RKS_EDITOR_OPEN_BUILD_PROBE = ROOT / "tests" / "test_run_rks_editor_open_build_probe_20260620.py"
TEST_RKS_EDITOR_OPEN_BUILD_PROBE_SAFE_EXE = (
    ROOT / "tests" / "test_run_rks_editor_open_build_probe_safe_exe_20260622.py"
)
TEST_RK10_LICENSE_DEFAULT_OK_POLICY = ROOT / "tests" / "test_rk10_license_default_ok_policy_20260622.py"
TEST_RKS_RUNTIME_OPERATOR_PACK = ROOT / "tests" / "test_generate_rks_runtime_operator_pack_20260620.py"
TEST_RKS_RUNTIME_STATUS_GATE_SYNC = ROOT / "tests" / "test_sync_rks_runtime_evidence_from_status_gates_20260620.py"
TEST_RKS_RUNTIME_INTAKE_VALIDATION = ROOT / "tests" / "test_validate_rks_runtime_operator_intake_20260620.py"
TEST_RKS_MATRIX_OPEN_PROBE = ROOT / "tests" / "test_generate_rks_gate_matrix_open_probe_20260622.py"
TEST_SAMPLE_DATA_MAP = ROOT / "tests" / "test_generate_sample_data_evidence_map_20260620.py"
TEST_SAFE_EXECUTION_MAP = ROOT / "tests" / "test_generate_safe_execution_evidence_map_20260620.py"
TEST_BUSINESS_COST_MAP = ROOT / "tests" / "test_generate_business_cost_evidence_map_20260620.py"
TEST_UNBLOCK_BOARD = ROOT / "tests" / "test_generate_goal_unblock_board_20260620.py"
TEST_EXECUTION_PACKET = ROOT / "tests" / "test_generate_goal_execution_packet_20260620.py"
TEST_BUNDLE_EVIDENCE_PACKS = ROOT / "tests" / "test_generate_bundle_evidence_packs_20260620.py"
TEST_RK10_RUNTIME_BUNDLE_EVIDENCE_COLLECT = (
    ROOT / "tests" / "test_collect_rk10_runtime_bundle_evidence_20260620.py"
)
TEST_BUSINESS_DATA_APPROVAL_EVIDENCE_COLLECT = (
    ROOT / "tests" / "test_collect_business_data_approval_evidence_20260620.py"
)
TEST_S44_BUSINESS_REVIEW_EVIDENCE_COLLECT = ROOT / "tests" / "test_collect_s44_business_review_evidence_20260620.py"
TEST_S70_PAYMENT_APPROVAL_EVIDENCE_COLLECT = ROOT / "tests" / "test_collect_s70_payment_approval_evidence_20260620.py"
TEST_OUTLOOK_BUNDLE_EVIDENCE_COLLECT = ROOT / "tests" / "test_collect_outlook_bundle_evidence_20260620.py"
TEST_BUNDLE_OPERATOR_SHEET = ROOT / "tests" / "test_generate_bundle_operator_sheet_20260620.py"
TEST_UNIFIED_FINAL_EVIDENCE_INTAKE_SYNC = ROOT / "tests" / "test_sync_unified_final_evidence_intake_20260621.py"
TEST_FINAL_EVIDENCE_CANDIDATE_STAGE = ROOT / "tests" / "test_stage_final_evidence_candidates_20260621.py"
TEST_EXECUTION_PACKET_CANDIDATE_PATH_SYNC = (
    ROOT / "tests" / "test_sync_execution_packet_candidate_evidence_paths_20260621.py"
)
TEST_EXECUTION_PACKET_OPERATOR_FIELD_SYNC = (
    ROOT / "tests" / "test_sync_execution_packet_operator_fields_20260623.py"
)
TEST_BUNDLE_EVIDENCE_INTAKE_SYNC = ROOT / "tests" / "test_sync_bundle_evidence_intake_20260620.py"
TEST_BUNDLE_EVIDENCE_SCOPE_EXCLUSION = (
    ROOT / "tests" / "test_sync_bundle_evidence_scope_exclusion_20260623.py"
)
TEST_BUNDLE_EVIDENCE_INTAKE_LARGE_CSV = ROOT / "tests" / "test_sync_bundle_evidence_intake_large_csv_20260622.py"
TEST_CSV_FIELD_SIZE_LIMIT_EVIDENCE_TOOLS = ROOT / "tests" / "test_csv_field_size_limit_evidence_tools_20260622.py"
TEST_BUNDLE_EVIDENCE_PACK_VALIDATION = ROOT / "tests" / "test_validate_bundle_evidence_packs_20260620.py"
TEST_CODE_BACKUP = ROOT / "tests" / "test_backup_goal_code_artifacts_20260620.py"
TEST_EXTERNAL_APPROVAL_RUNBOOK = ROOT / "tests" / "test_generate_external_approval_runbook_20260620.py"
TEST_NEXT_APPROVAL_QUEUE = ROOT / "tests" / "test_generate_next_approval_queue_20260620.py"
TEST_OUTLOOK_COM_ENV = ROOT / "tests" / "test_diagnose_outlook_com_environment_20260620.py"
TEST_OPERATOR_EVIDENCE_PREFILL = ROOT / "tests" / "test_generate_operator_evidence_prefill_20260620.py"
TEST_REMAINING_APPROVAL_NEXT_STEPS = ROOT / "tests" / "test_generate_remaining_approval_next_steps_20260621.py"
TEST_EXECUTION_PACKET_VALIDATION = (
    ROOT / "tests" / "test_validate_goal_execution_packet_scope_exclusions_20260623.py"
)
TEST_FINAL_EVIDENCE_FILL_QUEUE = ROOT / "tests" / "test_generate_final_evidence_fill_queue_20260621.py"
TEST_FINAL_EVIDENCE_FILL_QUEUE_RKS_COMPLETE_GUARD = (
    ROOT
    / "tests"
    / "test_final_evidence_fill_queue_rks_complete_guard_20260623.py"
)
TEST_FINAL_EVIDENCE_FILL_QUEUE_OPEN_PROBE = (
    ROOT / "tests" / "test_final_evidence_fill_queue_open_probe_20260622.py"
)
TEST_NEXT_BUNDLE_MINIMUM_INPUT_PACKET = ROOT / "tests" / "test_generate_next_bundle_minimum_input_packet_20260622.py"
TEST_REMAINING_OPERATOR_INPUT_PACKET = ROOT / "tests" / "test_generate_remaining_operator_input_packet_20260623.py"
TEST_REMAINING_OPERATOR_INPUT_READY_VALIDATION = (
    ROOT / "tests" / "test_validate_remaining_operator_input_ready_20260623.py"
)
TEST_REMAINING_OPERATOR_FINAL_REVIEW_PACK = (
    ROOT / "tests" / "test_generate_remaining_operator_final_review_pack_20260623.py"
)
TEST_MINIMUM_OPERATOR_REVIEW_INPUT = (
    ROOT / "tests" / "test_generate_minimum_operator_review_input_20260623.py"
)
TEST_AUTO_FILL_MINIMUM_OPERATOR_REVIEW_INPUT = (
    ROOT / "tests" / "test_auto_fill_minimum_operator_review_input_20260623.py"
)
TEST_APPLY_MINIMUM_OPERATOR_REVIEW_INPUT = (
    ROOT / "tests" / "test_apply_minimum_operator_review_input_20260623.py"
)
TEST_REMAINING_OPERATOR_DECISION_BRIEF = (
    ROOT / "tests" / "test_generate_remaining_operator_decision_brief_20260623.py"
)
TEST_REMAINING_OPERATOR_INPUT_PACKET_SYNC = ROOT / "tests" / "test_sync_remaining_operator_input_packet_20260623.py"
TEST_REMAINING_OPERATOR_INPUT_COMPLETION_SIMULATION = ROOT / "tests" / "test_simulate_remaining_operator_input_completion_20260623.py"
TEST_REMAINING_OPERATOR_SCOPE_EXCLUSION_SIMULATION = (
    ROOT / "tests" / "test_simulate_remaining_operator_scope_exclusion_20260623.py"
)
TEST_REMAINING_OPERATOR_FULL_GATE_SIMULATION = (
    ROOT / "tests" / "test_simulate_remaining_operator_full_gate_completion_20260623.py"
)
TEST_REMAINING_OPERATOR_EVIDENCE_DIGEST = (
    ROOT / "tests" / "test_generate_remaining_operator_evidence_digest_20260623.py"
)
TEST_REMAINING_OPERATOR_EVIDENCE_DIGEST_ORDER = (
    ROOT / "tests" / "test_run_safe_goal_checks_remaining_operator_digest_order_20260623.py"
)
TEST_PROD_MIGRATION_READINESS = ROOT / "tests" / "test_generate_prod_migration_readiness_20260620.py"
TEST_EVIDENCE_LEDGER = ROOT / "tests" / "test_generate_goal_evidence_ledger_20260620.py"
TEST_OBJECTIVE_COMPLETION_AUDIT = (
    ROOT / "tests" / "test_generate_objective_completion_audit_20260623.py"
)
TEST_EVIDENCE_ACTUAL_TRACE_OVERLAY = (
    ROOT / "tests" / "test_generate_goal_evidence_actual_trace_overlay_20260623.py"
)
TEST_STATUS_RKS_RUNTIME_OVERLAY = (
    ROOT / "tests" / "test_generate_goal_status_snapshot_rks_runtime_overlay_20260623.py"
)
TEST_REQUIREMENT_TRACE_ACTUAL_OVERLAY = (
    ROOT
    / "tests"
    / "test_generate_goal_requirement_traceability_actual_overlay_20260623.py"
)
TEST_REQUIREMENT_TRACE_RKS_GATE_ALIGNMENT = (
    ROOT
    / "tests"
    / "test_generate_goal_requirement_traceability_rks_gate_alignment_20260623.py"
)
TEST_REQUIREMENT_TRACE_MULTI_EVIDENCE = (
    ROOT
    / "tests"
    / "test_goal_requirement_traceability_multi_evidence_20260623.py"
)
TEST_COMPLETION_AUDIT = ROOT / "tests" / "test_generate_goal_completion_audit_20260620.py"
TEST_REQUIREMENT_TRACE = ROOT / "tests" / "test_generate_goal_requirement_traceability_20260620.py"
TEST_COMPLETION_GATE = ROOT / "tests" / "test_generate_goal_completion_gate_20260620.py"
TEST_COMPLETION_GATE_OPEN_PROBE = ROOT / "tests" / "test_generate_goal_completion_gate_open_probe_20260622.py"
TEST_FINAL_REPORT = ROOT / "tests" / "test_generate_goal_final_report_20260620.py"
TEST_PROD_READINESS_BREAKDOWN = ROOT / "tests" / "test_generate_prod_readiness_remaining_work_breakdown_20260622.py"
TEST_FINAL_INPUT_AUTONOMOUS_BOUNDARY = ROOT / "tests" / "test_generate_final_input_autonomous_boundary_20260622.py"
TEST_COMPLETION_BLOCKER_SPLIT = ROOT / "tests" / "test_generate_completion_blocker_split_20260622.py"
TEST_CUSTOMER_SAFE_SCENARIO_MATRIX = ROOT / "tests" / "test_generate_customer_safe_entries_full_smoke_report_20260622.py"


@dataclass(frozen=True)
class StepResult:
    name: str
    command: list[str]
    return_code: int
    duration_seconds: float
    stdout_path: str
    stderr_path: str

    @property
    def passed(self) -> bool:
        return self.return_code == 0


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    target = Path(str(path) + ".numbered")
    try:
        target.write_text(numbered_text + "\n", encoding="utf-8")
    except PermissionError:
        Path(str(path) + ".numbered.locked_copy").write_text(
            numbered_text + "\n",
            encoding="utf-8",
        )


def run_step(name: str, command: list[str], out_dir: Path, index: int) -> StepResult:
    started = time.monotonic()
    env = {**os.environ, "PYTHONUTF8": "1"}
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    duration = round(time.monotonic() - started, 3)
    safe_name = name.lower().replace(" ", "_").replace("/", "_")
    stdout_path = out_dir / f"{index:02}_{safe_name}.stdout.txt"
    stderr_path = out_dir / f"{index:02}_{safe_name}.stderr.txt"
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    return StepResult(
        name=name,
        command=command,
        return_code=completed.returncode,
        duration_seconds=duration,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )


def clean_previous_step_logs(out_dir: Path) -> list[str]:
    if not out_dir.exists():
        return []
    removed: list[str] = []
    for path in out_dir.iterdir():
        name = path.name
        is_step_log = (
            path.is_file()
            and len(name) > 3
            and name[:2].isdigit()
            and name[2] == "_"
            and (name.endswith(".stdout.txt") or name.endswith(".stderr.txt"))
        )
        if not is_step_log:
            continue
        path.unlink()
        removed.append(name)
    return sorted(removed)


def build_steps(s12_exit_code: int) -> list[tuple[str, list[str]]]:
    python = sys.executable
    return [
        (
            "py_compile",
            [
                python,
                "-X",
                "utf8",
                "-m",
                "py_compile",
                str(CHECK_HOLD),
                str(CHECK_OUTLOOK_SAVE_PDF),
                str(CHECK_SNAPSHOT),
                str(CHECK_RUNNER),
                str(CHECK_S44_SPOT),
                str(CHECK_S44_REVIEW_DB_AMOUNT_EVIDENCE),
                str(CHECK_S44_SAMPLE_OK),
                str(CHECK_S44_QUICK_BUCKET_SIMULATION),
                str(CHECK_S70_SAMPLE_PREVIEW),
                str(CHECK_S71_SAMPLE_MOCK_OCR),
                str(CHECK_S71_PAID_AZURE_OCR_EVIDENCE_COLLECT),
                str(CHECK_RKS_MATRIX),
                str(CHECK_RKS_STATIC_GUARD),
                str(CHECK_RKS_DEBUGGER_RECONCILE),
                str(CHECK_RKS_EDITOR_OPEN_BUILD_PROBE),
                str(CHECK_RKS_RUNTIME_OPERATOR_PACK),
                str(CHECK_RKS_RUNTIME_STATUS_GATE_SYNC),
                str(CHECK_RKS_RUNTIME_INTAKE_VALIDATION),
                str(CHECK_RKS_MATRIX_OPEN_PROBE),
                str(CHECK_SAMPLE_DATA_MAP),
                str(CHECK_SAFE_EXECUTION_MAP),
                str(CHECK_BUSINESS_COST_MAP),
                str(CHECK_UNBLOCK_BOARD),
                str(CHECK_EXECUTION_PACKET),
                str(CHECK_BUNDLE_EVIDENCE_PACKS),
                str(CHECK_RK10_RUNTIME_BUNDLE_EVIDENCE_COLLECT),
                str(CHECK_BUSINESS_DATA_APPROVAL_EVIDENCE_COLLECT),
                str(CHECK_S44_BUSINESS_REVIEW_EVIDENCE_COLLECT),
                str(CHECK_S70_PAYMENT_APPROVAL_EVIDENCE_COLLECT),
                str(CHECK_OUTLOOK_BUNDLE_EVIDENCE_COLLECT),
                str(CHECK_BUNDLE_OPERATOR_SHEET),
                str(CHECK_UNIFIED_FINAL_EVIDENCE_INTAKE_SYNC),
                str(CHECK_FINAL_EVIDENCE_CANDIDATE_STAGE),
                str(CHECK_EXECUTION_PACKET_CANDIDATE_PATH_SYNC),
                str(CHECK_BUNDLE_EVIDENCE_INTAKE_SYNC),
                str(CHECK_BUNDLE_EVIDENCE_PACK_VALIDATION),
                str(CHECK_CODE_BACKUP),
                str(CHECK_EXTERNAL_APPROVAL_RUNBOOK),
                str(CHECK_NEXT_APPROVAL_QUEUE),
                str(CHECK_OUTLOOK_COM_ENV),
                str(CHECK_OPERATOR_EVIDENCE_PREFILL),
                str(CHECK_REMAINING_APPROVAL_NEXT_STEPS),
                str(CHECK_EXECUTION_PACKET_VALIDATION),
                str(CHECK_FINAL_EVIDENCE_FILL_QUEUE),
                str(TEST_FINAL_EVIDENCE_FILL_QUEUE_RKS_COMPLETE_GUARD),
                str(CHECK_NEXT_BUNDLE_MINIMUM_INPUT_PACKET),
                str(CHECK_REMAINING_OPERATOR_INPUT_PACKET),
                str(CHECK_REMAINING_OPERATOR_INPUT_READY_VALIDATION),
                str(CHECK_REMAINING_OPERATOR_FINAL_REVIEW_PACK),
                str(CHECK_MINIMUM_OPERATOR_REVIEW_INPUT),
                str(CHECK_AUTO_FILL_MINIMUM_OPERATOR_REVIEW_INPUT),
                str(CHECK_REMAINING_OPERATOR_DECISION_BRIEF),
                str(CHECK_REMAINING_OPERATOR_INPUT_PACKET_SYNC),
                str(CHECK_REMAINING_OPERATOR_INPUT_COMPLETION_SIMULATION),
                str(CHECK_REMAINING_OPERATOR_FULL_GATE_SIMULATION),
                str(CHECK_REMAINING_OPERATOR_EVIDENCE_DIGEST),
                str(CHECK_PROD_MIGRATION_READINESS),
                str(CHECK_EVIDENCE_LEDGER),
                str(CHECK_OBJECTIVE_COMPLETION_AUDIT),
                str(CHECK_EVIDENCE_ACTUAL_TRACE_OVERLAY),
                str(CHECK_STATUS_RKS_RUNTIME_OVERLAY),
                str(CHECK_COMPLETION_AUDIT),
                str(CHECK_REQUIREMENT_TRACE),
                str(CHECK_COMPLETION_GATE),
                str(CHECK_CUSTOMER_SAFE_SCENARIO_MATRIX),
                str(CHECK_FINAL_REPORT),
                str(CHECK_PROD_READINESS_BREAKDOWN),
                str(CHECK_FINAL_INPUT_AUTONOMOUS_BOUNDARY),
                str(CHECK_COMPLETION_BLOCKER_SPLIT),
            ],
        ),
        (
            "pytest",
            [
                python,
                "-X",
                "utf8",
                "-m",
                "pytest",
                str(TEST_HOLD),
                str(TEST_OUTLOOK_EXTRACT_INVOICE_FIELDS),
                str(TEST_RUNNER),
                str(TEST_RUNNER_AI_DEFAULT_OPEN_PROBE),
                str(TEST_SNAPSHOT),
                str(TEST_S44_SPOT),
                str(TEST_S44_REVIEW_DB_AMOUNT_EVIDENCE),
                str(TEST_S44_SAMPLE_OK),
                str(TEST_S44_QUICK_BUCKET_SIMULATION),
                str(TEST_S70_SAMPLE_PREVIEW),
                str(TEST_S71_SAMPLE_MOCK_OCR),
                str(TEST_S71_PAID_AZURE_OCR_EVIDENCE_COLLECT),
                str(TEST_RKS_MATRIX),
                str(TEST_RKS_STATIC_GUARD),
                str(TEST_RKS_DEBUGGER_RECONCILE),
                str(TEST_RKS_EDITOR_OPEN_BUILD_PROBE),
                str(TEST_RKS_EDITOR_OPEN_BUILD_PROBE_SAFE_EXE),
                str(TEST_RK10_LICENSE_DEFAULT_OK_POLICY),
                str(TEST_RKS_RUNTIME_OPERATOR_PACK),
                str(TEST_RKS_RUNTIME_STATUS_GATE_SYNC),
                str(TEST_RKS_RUNTIME_INTAKE_VALIDATION),
                str(TEST_RKS_MATRIX_OPEN_PROBE),
                str(TEST_SAMPLE_DATA_MAP),
                str(TEST_SAFE_EXECUTION_MAP),
                str(TEST_BUSINESS_COST_MAP),
                str(TEST_UNBLOCK_BOARD),
                str(TEST_EXECUTION_PACKET),
                str(TEST_BUNDLE_EVIDENCE_PACKS),
                str(TEST_RK10_RUNTIME_BUNDLE_EVIDENCE_COLLECT),
                str(TEST_BUSINESS_DATA_APPROVAL_EVIDENCE_COLLECT),
                str(TEST_S44_BUSINESS_REVIEW_EVIDENCE_COLLECT),
                str(TEST_S70_PAYMENT_APPROVAL_EVIDENCE_COLLECT),
                str(TEST_OUTLOOK_BUNDLE_EVIDENCE_COLLECT),
                str(TEST_BUNDLE_OPERATOR_SHEET),
                str(TEST_UNIFIED_FINAL_EVIDENCE_INTAKE_SYNC),
                str(TEST_FINAL_EVIDENCE_CANDIDATE_STAGE),
                str(TEST_EXECUTION_PACKET_CANDIDATE_PATH_SYNC),
                str(TEST_EXECUTION_PACKET_OPERATOR_FIELD_SYNC),
                str(TEST_BUNDLE_EVIDENCE_INTAKE_SYNC),
                str(TEST_BUNDLE_EVIDENCE_SCOPE_EXCLUSION),
                str(TEST_BUNDLE_EVIDENCE_INTAKE_LARGE_CSV),
                str(TEST_CSV_FIELD_SIZE_LIMIT_EVIDENCE_TOOLS),
                str(TEST_BUNDLE_EVIDENCE_PACK_VALIDATION),
                str(TEST_CODE_BACKUP),
                str(TEST_EXTERNAL_APPROVAL_RUNBOOK),
                str(TEST_NEXT_APPROVAL_QUEUE),
                str(TEST_OUTLOOK_COM_ENV),
                str(TEST_OPERATOR_EVIDENCE_PREFILL),
                str(TEST_REMAINING_APPROVAL_NEXT_STEPS),
                str(TEST_EXECUTION_PACKET_VALIDATION),
                str(TEST_FINAL_EVIDENCE_FILL_QUEUE),
                str(TEST_FINAL_EVIDENCE_FILL_QUEUE_RKS_COMPLETE_GUARD),
                str(TEST_FINAL_EVIDENCE_FILL_QUEUE_OPEN_PROBE),
                str(TEST_NEXT_BUNDLE_MINIMUM_INPUT_PACKET),
                str(TEST_REMAINING_OPERATOR_INPUT_PACKET),
                str(TEST_REMAINING_OPERATOR_INPUT_READY_VALIDATION),
                str(TEST_REMAINING_OPERATOR_FINAL_REVIEW_PACK),
                str(TEST_MINIMUM_OPERATOR_REVIEW_INPUT),
                str(TEST_AUTO_FILL_MINIMUM_OPERATOR_REVIEW_INPUT),
                str(TEST_APPLY_MINIMUM_OPERATOR_REVIEW_INPUT),
                str(TEST_REMAINING_OPERATOR_DECISION_BRIEF),
                str(TEST_REMAINING_OPERATOR_INPUT_PACKET_SYNC),
                str(TEST_REMAINING_OPERATOR_INPUT_COMPLETION_SIMULATION),
                str(TEST_REMAINING_OPERATOR_SCOPE_EXCLUSION_SIMULATION),
                str(TEST_REMAINING_OPERATOR_FULL_GATE_SIMULATION),
                str(TEST_REMAINING_OPERATOR_EVIDENCE_DIGEST),
                str(TEST_REMAINING_OPERATOR_EVIDENCE_DIGEST_ORDER),
                str(TEST_PROD_MIGRATION_READINESS),
                str(TEST_EVIDENCE_LEDGER),
                str(TEST_OBJECTIVE_COMPLETION_AUDIT),
                str(TEST_EVIDENCE_ACTUAL_TRACE_OVERLAY),
                str(TEST_STATUS_RKS_RUNTIME_OVERLAY),
                str(TEST_REQUIREMENT_TRACE_ACTUAL_OVERLAY),
                str(TEST_REQUIREMENT_TRACE_RKS_GATE_ALIGNMENT),
                str(TEST_REQUIREMENT_TRACE_MULTI_EVIDENCE),
                str(TEST_COMPLETION_AUDIT),
                str(TEST_REQUIREMENT_TRACE),
                str(TEST_COMPLETION_GATE),
                str(TEST_COMPLETION_GATE_OPEN_PROBE),
                str(TEST_CUSTOMER_SAFE_SCENARIO_MATRIX),
                str(TEST_FINAL_REPORT),
                str(TEST_PROD_READINESS_BREAKDOWN),
                str(TEST_FINAL_INPUT_AUTONOMOUS_BOUNDARY),
                str(TEST_COMPLETION_BLOCKER_SPLIT),
                "-v",
            ],
        ),
        (
            "s44_spot_check_candidates",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_S44_SPOT),
            ],
        ),
        (
            "s44_review_db_amount_evidence",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_S44_REVIEW_DB_AMOUNT_EVIDENCE),
            ],
        ),
        (
            "s44_sample_ok_shadow",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_S44_SAMPLE_OK),
            ],
        ),
        (
            "s44_quick_bucket_ok_simulation",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_S44_QUICK_BUCKET_SIMULATION),
            ],
        ),
        (
            "s70_sample_confirm_preview",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_S70_SAMPLE_PREVIEW),
            ],
        ),
        (
            "s71_sample_mock_ocr_apply",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_S71_SAMPLE_MOCK_OCR),
            ],
        ),
        (
            "rks_static_guard_audit",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_RKS_STATIC_GUARD),
            ],
        ),
        (
            "rks_debugger_artifact_reconcile",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_RKS_DEBUGGER_RECONCILE),
            ],
        ),
        (
            "rks_runtime_operator_pack",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_RKS_RUNTIME_OPERATOR_PACK),
            ],
        ),
        (
            "rks_runtime_status_gate_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_RKS_RUNTIME_STATUS_GATE_SYNC),
            ],
        ),
        (
            "rks_runtime_intake_validation",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_RKS_RUNTIME_INTAKE_VALIDATION),
            ],
        ),
        (
            "rks_gate_matrix",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_RKS_MATRIX),
            ],
        ),
        (
            "rks_gate_matrix_open_probe",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_RKS_MATRIX_OPEN_PROBE),
                "--out-dir",
                str(ROOT / "plans" / "reports" / "rks_gate_matrix_open_probe_20260622"),
            ],
        ),
        (
            "sample_data_evidence_map",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_SAMPLE_DATA_MAP),
            ],
        ),
        (
            "safe_execution_evidence_map",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_SAFE_EXECUTION_MAP),
            ],
        ),
        (
            "business_cost_evidence_map",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_BUSINESS_COST_MAP),
            ],
        ),
        (
            "hold_gate_check",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_HOLD),
                "--s12-exit-code",
                str(s12_exit_code),
            ],
        ),
        (
            "goal_status_snapshot",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_SNAPSHOT),
                "--s12-exit-code",
                str(s12_exit_code),
            ],
        ),
        (
            "goal_unblock_board",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_UNBLOCK_BOARD),
                "--s12-exit-code",
                str(s12_exit_code),
            ],
        ),
        (
            "goal_execution_packet",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_EXECUTION_PACKET),
                "--s12-exit-code",
                str(s12_exit_code),
            ],
        ),
        (
            "bundle_evidence_packs",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_BUNDLE_EVIDENCE_PACKS),
            ],
        ),
        (
            "rk10_runtime_bundle_evidence_collect",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_RK10_RUNTIME_BUNDLE_EVIDENCE_COLLECT),
            ],
        ),
        (
            "business_data_approval_evidence_collect",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_BUSINESS_DATA_APPROVAL_EVIDENCE_COLLECT),
            ],
        ),
        (
            "s44_business_review_evidence_collect",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_S44_BUSINESS_REVIEW_EVIDENCE_COLLECT),
            ],
        ),
        (
            "s70_payment_approval_evidence_collect",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_S70_PAYMENT_APPROVAL_EVIDENCE_COLLECT),
            ],
        ),
        (
            "s71_paid_azure_ocr_evidence_collect",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_S71_PAID_AZURE_OCR_EVIDENCE_COLLECT),
            ],
        ),
        (
            "outlook_bundle_evidence_collect",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_OUTLOOK_BUNDLE_EVIDENCE_COLLECT),
            ],
        ),
        (
            "bundle_operator_sheet",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_BUNDLE_OPERATOR_SHEET),
            ],
        ),
        (
            "final_evidence_candidate_stage",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_FINAL_EVIDENCE_CANDIDATE_STAGE),
            ],
        ),
        (
            "unified_final_evidence_intake_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_UNIFIED_FINAL_EVIDENCE_INTAKE_SYNC),
            ],
        ),
        (
            "execution_packet_candidate_path_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_EXECUTION_PACKET_CANDIDATE_PATH_SYNC),
            ],
        ),
        (
            "bundle_evidence_intake_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_BUNDLE_EVIDENCE_INTAKE_SYNC),
            ],
        ),
        (
            "bundle_evidence_pack_validation",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_BUNDLE_EVIDENCE_PACK_VALIDATION),
            ],
        ),
        (
            "goal_code_artifact_backup",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_CODE_BACKUP),
            ],
        ),
        (
            "external_approval_runbook",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_EXTERNAL_APPROVAL_RUNBOOK),
            ],
        ),
        (
            "outlook_com_environment_diagnosis",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_OUTLOOK_COM_ENV),
            ],
        ),
        (
            "next_approval_queue",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_NEXT_APPROVAL_QUEUE),
                "--s12-exit-code",
                str(s12_exit_code),
            ],
        ),
        (
            "operator_evidence_prefill",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_OPERATOR_EVIDENCE_PREFILL),
            ],
        ),
        (
            "remaining_approval_next_steps",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_APPROVAL_NEXT_STEPS),
            ],
        ),
        (
            "goal_execution_packet_validation",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_EXECUTION_PACKET_VALIDATION),
            ],
        ),
        (
            "final_evidence_fill_queue",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_FINAL_EVIDENCE_FILL_QUEUE),
            ],
        ),
        (
            "final_input_autonomous_boundary_for_operator_packet",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_FINAL_INPUT_AUTONOMOUS_BOUNDARY),
            ],
        ),
        (
            "remaining_operator_evidence_digest",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_EVIDENCE_DIGEST),
            ],
        ),
        (
            "next_bundle_minimum_input_packet",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_NEXT_BUNDLE_MINIMUM_INPUT_PACKET),
                "--all-active",
            ],
        ),
        (
            "remaining_operator_input_packet",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_INPUT_PACKET),
            ],
        ),
        (
            "remaining_operator_input_ready_validation",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_INPUT_READY_VALIDATION),
            ],
        ),
        (
            "remaining_operator_final_review_pack",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_FINAL_REVIEW_PACK),
            ],
        ),
        (
            "minimum_operator_review_input",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_MINIMUM_OPERATOR_REVIEW_INPUT),
            ],
        ),
        (
            "remaining_operator_decision_brief",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_DECISION_BRIEF),
            ],
        ),
        (
            "remaining_operator_input_packet_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_INPUT_PACKET_SYNC),
            ],
        ),
        (
            "goal_execution_packet_validation_after_remaining_operator_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_EXECUTION_PACKET_VALIDATION),
            ],
        ),
        (
            "final_evidence_fill_queue_after_remaining_operator_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_FINAL_EVIDENCE_FILL_QUEUE),
            ],
        ),
        (
            "remaining_operator_input_packet_after_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_INPUT_PACKET),
            ],
        ),
        (
            "remaining_operator_input_ready_validation_after_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_INPUT_READY_VALIDATION),
            ],
        ),
        (
            "remaining_operator_final_review_pack_after_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_FINAL_REVIEW_PACK),
            ],
        ),
        (
            "minimum_operator_review_input_after_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_MINIMUM_OPERATOR_REVIEW_INPUT),
            ],
        ),
        (
            "remaining_operator_decision_brief_after_sync",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_DECISION_BRIEF),
            ],
        ),
        (
            "remaining_operator_input_completion_simulation",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_INPUT_COMPLETION_SIMULATION),
            ],
        ),
        (
            "remaining_operator_full_gate_simulation",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_OPERATOR_FULL_GATE_SIMULATION),
            ],
        ),
        (
            "remaining_approval_next_steps_after_minimum_packet",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REMAINING_APPROVAL_NEXT_STEPS),
            ],
        ),
        (
            "customer_safe_scenario_matrix",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_CUSTOMER_SAFE_SCENARIO_MATRIX),
            ],
        ),
        (
            "prod_migration_readiness",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_PROD_MIGRATION_READINESS),
            ],
        ),
        (
            "goal_evidence_ledger",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_EVIDENCE_LEDGER),
                "--s12-exit-code",
                str(s12_exit_code),
            ],
        ),
        (
            "goal_evidence_actual_trace_overlay",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_EVIDENCE_ACTUAL_TRACE_OVERLAY),
            ],
        ),
        (
            "goal_status_rks_runtime_overlay",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_STATUS_RKS_RUNTIME_OVERLAY),
            ],
        ),
        (
            "goal_completion_audit",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_COMPLETION_AUDIT),
            ],
        ),
        (
            "goal_requirement_traceability",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_REQUIREMENT_TRACE),
            ],
        ),
        (
            "goal_completion_gate",
            [python, "-X", "utf8", str(CHECK_COMPLETION_GATE)],
        ),
        (
            "objective_completion_audit",
            [
                python,
                "-X",
                "utf8",
                str(CHECK_OBJECTIVE_COMPLETION_AUDIT),
            ],
        ),
    ]


def build_pre_completion_steps(s12_exit_code: int) -> list[tuple[str, list[str]]]:
    return [
        (name, command)
        for name, command in build_steps(s12_exit_code)
        if name not in {"goal_completion_gate", "objective_completion_audit"}
    ]


def build_markdown(payload: dict[str, object]) -> str:
    steps = payload["steps"]
    assert isinstance(steps, list)
    lines = [
        "# 承認最小化 安全一括チェック 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_passed: `{payload['overall_passed']}`",
        f"- s12_exit_code_input: `{payload['s12_exit_code_input']}`",
        f"- safety: `{payload['safety']}`",
        "",
        "## Command Results",
        "",
        "| Step | Passed | Exit | Seconds | Stdout | Stderr |",
        "|---|---:|---:|---:|---|---|",
    ]
    for step in steps:
        assert isinstance(step, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(step["name"]),
                    "YES" if step["passed"] else "NO",
                    str(step["return_code"]),
                    str(step["duration_seconds"]),
                    f"`{step['stdout_path']}`",
                    f"`{step['stderr_path']}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Approval Reduction",
            "",
            "- Future checks should run this fixed runner instead of approving each Python/test command separately.",
            "- The runner now includes a strict final completion gate, so a green runner does not mean the business goal is complete unless `goal_completion_gate` also reports `final_goal_complete=True`.",
            "- The runner remains read-only for external systems and writes only under this repository's report directory.",
            "- Separate approval is still required for GUI apps, Outlook COM recovery, RK10 editor/build/runtime, real mail, real print, final submit, payment execution, MainSV production writes, or paid Azure OCR.",
            "",
            "## Fixed Runner Command",
            "",
            f"`{payload['fixed_runner_command']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def build_payload(args: argparse.Namespace, results: list[StepResult]) -> dict[str, object]:
    fixed_runner_command = (
        f"{sys.executable} -X utf8 {CHECK_RUNNER} "
        f"--s12-exit-code {args.s12_exit_code}"
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_passed": all(result.passed for result in results),
        "s12_exit_code_input": args.s12_exit_code,
        "safety": (
            "local compile, local unit tests, read-only evidence checkers, "
            "repository report writes only"
        ),
        "fixed_runner_command": fixed_runner_command,
        "steps": [
            {**asdict(result), "passed": result.passed}
            for result in results
        ],
    }


def write_summary(payload: dict[str, object], out_dir: Path) -> None:
    json_path = out_dir / "safe_goal_checks_summary.json"
    md_path = out_dir / "safe_goal_checks_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fixed read-only RK10 goal checks.")
    parser.add_argument(
        "--s12-exit-code",
        type=int,
        default=2,
        help="Latest known 12/13 Outlook COM probe exit code. Use 0 only after a fresh successful COM check.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Report output directory inside the repository.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    clean_previous_step_logs(args.out_dir)
    results = [
        run_step(name, command, args.out_dir, index)
        for index, (name, command) in enumerate(build_pre_completion_steps(args.s12_exit_code), 1)
    ]
    payload = build_payload(args, results)
    write_summary(payload, args.out_dir)
    python = sys.executable
    results.append(
        run_step(
            "goal_completion_gate",
            [python, "-X", "utf8", str(CHECK_COMPLETION_GATE)],
            args.out_dir,
            len(results) + 1,
        )
    )
    payload = build_payload(args, results)
    write_summary(payload, args.out_dir)
    results.append(
        run_step(
            "objective_completion_audit",
            [python, "-X", "utf8", str(CHECK_OBJECTIVE_COMPLETION_AUDIT)],
            args.out_dir,
            len(results) + 1,
        )
    )
    payload = build_payload(args, results)
    write_summary(payload, args.out_dir)
    results.append(
        run_step(
            "goal_final_report",
            [python, "-X", "utf8", str(CHECK_FINAL_REPORT)],
            args.out_dir,
            len(results) + 1,
        )
    )
    payload = build_payload(args, results)
    write_summary(payload, args.out_dir)
    results.append(
        run_step(
            "prod_readiness_remaining_work_breakdown",
            [python, "-X", "utf8", str(CHECK_PROD_READINESS_BREAKDOWN)],
            args.out_dir,
            len(results) + 1,
        )
    )
    payload = build_payload(args, results)
    write_summary(payload, args.out_dir)
    results.append(
        run_step(
            "final_input_autonomous_boundary",
            [python, "-X", "utf8", str(CHECK_FINAL_INPUT_AUTONOMOUS_BOUNDARY)],
            args.out_dir,
            len(results) + 1,
        )
    )
    payload = build_payload(args, results)
    write_summary(payload, args.out_dir)
    results.append(
        run_step(
            "completion_blocker_split",
            [python, "-X", "utf8", str(CHECK_COMPLETION_BLOCKER_SPLIT)],
            args.out_dir,
            len(results) + 1,
        )
    )
    payload = build_payload(args, results)
    write_summary(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
