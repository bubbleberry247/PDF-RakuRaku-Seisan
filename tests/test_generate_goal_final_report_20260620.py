import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_goal_final_report_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_goal_final_report_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_build_payload_marks_incomplete_as_draft_not_final(tmp_path: Path) -> None:
    module = load_module()
    completion_gate = write_json(
        tmp_path / "completion.json",
        {
            "final_goal_complete": False,
            "gate_count": 2,
            "passed_gate_count": 1,
            "blocking_gate_count": 1,
            "gates": [
                {
                    "gate": "SAFE_RUNNER",
                    "passed": True,
                    "status": "PASSED",
                    "detail": "overall_passed=True",
                    "next_action": "",
                    "source": r"C:\safe.json",
                },
                {
                    "gate": "RKS_GATE_MATRIX",
                    "passed": False,
                    "status": "INCOMPLETE",
                    "detail": "unresolved_rks_gate_count=1",
                    "next_action": "RK10証跡を取得する",
                    "source": r"C:\rks.json",
                },
            ],
        },
    )
    requirement_trace = write_json(
        tmp_path / "requirements.json",
        {
            "requirement_count": 2,
            "rows": [
                {
                    "requirement_id": "REQ-03",
                    "requirement": "RKSファイルを実際に実行して確認する",
                    "current_status": "NOT_PROVEN",
                    "remaining_gap": "RKS runtime missing",
                    "next_evidence_needed": "open/build/runtime/latest clean log",
                    "authoritative_evidence": r"C:\rks.md",
                },
                {
                    "requirement_id": "REQ-10",
                    "requirement": "承認回数を減らして進める",
                    "current_status": "OK_FOR_BUNDLE_RUNBOOK_ONLY",
                    "remaining_gap": "external approval still needed",
                    "next_evidence_needed": "bundle approval",
                    "authoritative_evidence": r"C:\runbook.md",
                },
            ],
        },
    )
    evidence_ledger = write_json(
        tmp_path / "ledger.json",
        {
            "scenario_count": 1,
            "complete_goal_evidence_count": 0,
            "rows": [
                {
                    "scenario": "57",
                    "objective_checkpoint_summary": "sample=OK; safe=OK; rks=PENDING; cost=COUNT_ONLY; final=PENDING",
                    "missing_objective_proofs": "RK10 open/build/runtime/latest clean log",
                    "evidence_strength": "PARTIAL_EVIDENCE",
                }
            ],
        },
    )
    safe_runner = write_json(tmp_path / "safe.json", {"overall_passed": True})
    next_queue = write_json(
        tmp_path / "queue.json",
        {
            "next_bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
            "next_operator_action": "RK10 open/build/safe-stop evidence",
            "external_runbook": r"C:\runbook.md.numbered",
            "external_runbook_json": r"C:\runbook.json",
            "outlook_bundle_script": r"C:\outlook_com_bundle_dryrun.ps1",
            "outlook_recovery_checklist": r"C:\outlook_com_recovery_checklist.md",
            "rk10_recovery_checklist": r"C:\rk10_checklist.md.numbered",
            "rows": [
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "owner": "RK10操作担当者",
                    "scenarios": "57, 58",
                    "approval_boundary": "safe-stop only",
                    "forbidden": "ButtonRun",
                    "evidence_pack_path": r"C:\pack\rk10",
                    "bundle_sheet_path": r"C:\sheet.csv",
                    "after_action_command": r"C:\Python313\python.exe -X utf8 C:\repo\tools\run_safe_goal_checks_20260620.py",
                }
            ],
        },
    )
    completion_audit = write_json(
        tmp_path / "completion_audit.json",
        {
            "report_status": "CURRENT_AUDIT_NOT_FINAL",
            "overall_goal_complete": False,
            "issue_count": 3,
            "missing_source_count": 0,
            "validation_summary": {
                "packet_approved_row_count": 2,
                "packet_needs_attention_count": 1,
                "bundle_final_evidence_ready_count": 0,
                "bundle_count": 4,
                "rks_runtime_approved_count": 0,
                "rks_runtime_required_count": 2,
                "amount_verified_scenario_count": 1,
            },
            "field_export_paths": {
                "issues_csv": r"C:\audit_issues.csv",
            },
        },
    )
    bundle_validation = write_json(
        tmp_path / "bundle_validation.json",
        {
            "prepared_pack_validation_passed": True,
            "source_reference_count": 15,
            "source_reference_exists_now_count": 15,
            "source_reference_hashed_now_count": 15,
            "missing_prepared_pack_count": 0,
            "final_evidence_ready_count": 0,
            "bundle_count": 6,
        },
    )
    final_fill_queue = write_json(
        tmp_path / "final_fill_queue.json",
        {
            "active_queue_count": 6,
            "ready_or_completed_count": 0,
            "operator_attention_row_count": 20,
            "next_active_bundle": "BUSINESS_REVIEW_BUNDLE",
            "unified_input_csv": r"C:\unified_final_evidence_input.csv",
            "after_action_command": r"C:\Python313\python.exe -X utf8 C:\repo\tools\run_safe_goal_checks_20260620.py",
            "rows": [
                {
                    "bundle": "BUSINESS_REVIEW_BUNDLE",
                    "unified_entry_keys": "BUSINESS_REVIEW_BUNDLE::44",
                    "fill_only_fields": "operator_result, reviewer, reviewed_at",
                    "start_here_path": r"C:\business_review_bundle_START_HERE.md",
                    "missing_operator_fields": "OPERATOR_RESULT_BLANK",
                    "supplemental_evidence_status": "",
                    "supplemental_evidence_source": "",
                },
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "unified_entry_keys": "RK10_EDITOR_RUNTIME_BUNDLE::37 / RK10_EDITOR_RUNTIME_BUNDLE::57",
                    "fill_only_fields": "operator_result, reviewer, reviewed_at",
                    "start_here_path": r"C:\rk10_editor_runtime_bundle_START_HERE.md",
                    "missing_operator_fields": "scenario:57=REVIEWED_AT_BLANK",
                    "supplemental_evidence_status": "collector_status=READY_FOR_REVIEWER_TIMESTAMP; auto_appended_intake_rows=3",
                    "supplemental_evidence_source": r"C:\rk10_collect.json",
                    "remaining_runtime_evidence": "rks_gate_matrix_pending: 57=runtime safe-stop latest clean log",
                }
            ],
        },
    )
    rks_gate_matrix = write_json(
        tmp_path / "rks_gate_matrix.json",
        {
            "generated_at": "2026-06-22T02:22:12",
            "overall_rks_production_ready": False,
            "rows": [
                {
                    "scenario": "57",
                    "current_rks_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
                    "runtime_intake_status": "RKS_RUNTIME_EVIDENCE_PENDING",
                    "existing_evidence_search_result": "not_promotable: Python dry-run only",
                    "next_safe_action": "no-mail safe-stop latest clean log",
                }
            ],
        },
    )
    customer_safe_smoke = write_json(
        tmp_path / "customer_safe_smoke.json",
        {
            "generated_at": "2026-06-23T01:29:06",
            "run_dir": r"C:\run\customer_safe",
            "total": 22,
            "expected_ok_count": 22,
            "unexpected_count": 0,
            "timeout_count": 0,
            "cleanup_remaining_count": 0,
            "validation_json": r"C:\validation.json",
            "safety": "customer-safe BAT entries only",
            "results": [
                {
                    "name": "55_v2",
                    "exit_code": 0,
                    "expected_exit_codes": "0",
                    "expected_ok": True,
                    "timed_out": False,
                    "elapsed_seconds": 868.923,
                    "cleanup_remaining_count": 0,
                    "note": "",
                },
                {
                    "name": "70_confirm",
                    "exit_code": 3,
                    "expected_exit_codes": "0,3",
                    "expected_ok": True,
                    "timed_out": False,
                    "elapsed_seconds": 1.591,
                    "cleanup_remaining_count": 0,
                    "note": "承認前提不足は安全BLOCK 3",
                },
            ],
        },
    )
    customer_safe_smoke_md = tmp_path / "customer_safe_smoke.md.numbered"
    customer_safe_smoke_md.write_text("1: smoke\n", encoding="utf-8")
    customer_safe_actual_trace = write_json(
        tmp_path / "customer_safe_actual_trace.json",
        {
            "actual_trace_entry_count": 22,
            "actual_trace_expected_ok_count": 22,
            "actual_trace_script_missing_count": 0,
        },
    )
    customer_safe_actual_trace_md = tmp_path / "customer_safe_actual_trace.md.numbered"
    customer_safe_actual_trace_md.write_text("1: trace\n", encoding="utf-8")
    goal_evidence_actual_trace_overlay = write_json(
        tmp_path / "goal_evidence_actual_trace_overlay.json",
        {
            "generated_at": "2026-06-23T02:12:28",
            "scenario_count": 15,
            "trace_ready_scenario_count": 15,
            "trace_missing_scenario_count": 0,
            "trace_script_missing_count": 0,
            "production_completion_scope": "SAFE_TRACE_ONLY_NOT_PRODUCTION_COMPLETE",
            "safety": "read-only overlay",
        },
    )
    goal_evidence_actual_trace_overlay_md = (
        tmp_path / "goal_evidence_actual_trace_overlay.md.numbered"
    )
    goal_evidence_actual_trace_overlay_md.write_text("1: overlay\n", encoding="utf-8")
    remaining_operator_completion_simulation = write_json(
        tmp_path / "remaining_operator_input_completion_simulation.json",
        {
            "generated_at": "2026-06-23T05:06:00",
            "simulation_passed": True,
            "sample_completed_row_count": 11,
            "sync_updated_cell_count": 66,
            "sync_conflict_count": 0,
            "sync_unsafe_target_count": 0,
            "validation_all_packet_rows_approved": True,
            "validation_approved_row_count": 15,
            "validation_row_count": 15,
            "validation_needs_attention_count": 0,
            "source_files_modified": False,
            "work_reports_dir": r"C:\work\simulation",
            "sync_report_md": r"C:\work\simulation\sync.md.numbered",
            "validation_report_md": r"C:\work\simulation\validation.md.numbered",
            "safety": "isolated copied CSVs only",
        },
    )
    remaining_operator_completion_simulation_md = (
        tmp_path / "remaining_operator_input_completion_simulation.md.numbered"
    )
    remaining_operator_completion_simulation_md.write_text(
        "1: simulation\n", encoding="utf-8"
    )

    payload = module.build_payload(
        completion_gate,
        requirement_trace,
        evidence_ledger,
        safe_runner,
        next_queue,
        completion_audit,
        bundle_validation,
        final_fill_queue,
        rks_gate_matrix,
        customer_safe_smoke,
        customer_safe_smoke_md,
        customer_safe_actual_trace,
        customer_safe_actual_trace_md,
        goal_evidence_actual_trace_overlay,
        goal_evidence_actual_trace_overlay_md,
        remaining_operator_completion_simulation,
        remaining_operator_completion_simulation_md,
    )

    assert payload["report_status"] == "DRAFT_PROGRESS_REPORT_NOT_FINAL"
    assert payload["final_goal_complete"] is False
    assert payload["safe_runner_passed"] is True
    assert payload["blocking_gate_count"] == 1
    assert len(payload["blocking_gates"]) == 1
    assert payload["incomplete_requirement_count"] == 1
    assert payload["objective_progress_summary"]["sample_ready_count"] == 1
    assert payload["objective_progress_summary"]["safe_execution_ready_count"] == 1
    assert payload["objective_progress_summary"]["business_amount_or_draft_count"] == 0
    assert payload["objective_progress_summary"]["business_count_only_scope_count"] == 1
    assert payload["objective_progress_summary"]["final_evidence_ready_count"] == 0
    assert payload["next_bundle"] == "RK10_EDITOR_RUNTIME_BUNDLE"
    assert payload["completion_audit_summary"]["issue_count"] == 3
    assert payload["completion_audit_summary"]["packet_approved_row_count"] == 2
    assert payload["completion_audit_summary"]["issues_csv"] == r"C:\audit_issues.csv"
    assert payload["reference_integrity_summary"]["source_reference_exists_now_count"] == 15
    assert payload["reference_integrity_summary"]["source_reference_hashed_now_count"] == 15
    assert payload["source_paths"]["bundle_validation"] == str(bundle_validation)
    assert payload["final_evidence_fill_summary"]["next_entry_keys"] == "BUSINESS_REVIEW_BUNDLE::44"
    assert payload["final_evidence_fill_summary"]["next_fill_only_fields"] == (
        "operator_result, reviewer, reviewed_at"
    )
    assert (
        payload["final_evidence_fill_summary"]["next_supplemental_evidence_status"]
        == ""
    )
    assert (
        payload["final_evidence_fill_summary"]["next_supplemental_evidence_source"]
        == ""
    )
    assert (
        payload["final_evidence_fill_summary"]["supplemental_evidence_bundle"]
        == "RK10_EDITOR_RUNTIME_BUNDLE"
    )
    assert (
        payload["final_evidence_fill_summary"]["supplemental_evidence_status"]
        == "collector_status=READY_FOR_REVIEWER_TIMESTAMP; auto_appended_intake_rows=3"
    )
    assert (
        payload["final_evidence_fill_summary"]["supplemental_evidence_source"]
        == r"C:\rk10_collect.json"
    )
    assert (
        payload["final_evidence_fill_summary"]["supplemental_remaining_runtime_evidence"]
        == "rks_gate_matrix_pending: 57=runtime safe-stop latest clean log"
    )
    assert payload["source_paths"]["final_evidence_fill_queue"] == str(final_fill_queue)
    assert payload["source_paths"]["rks_gate_matrix"] == str(rks_gate_matrix)
    assert payload["rks_existing_evidence_search_summary"]["reviewed_non_promotable_count"] == 1
    assert payload["rks_existing_evidence_search_summary"]["rows"][0]["scenario"] == "57"
    assert payload["customer_safe_smoke_summary"]["expected_match"] == "22/22"
    assert payload["customer_safe_smoke_summary"]["unexpected_count"] == 0
    assert payload["customer_safe_smoke_summary"]["notable_rows"][0]["name"] == "55_v2"
    assert "RPA開発版AI付き" in payload["customer_safe_smoke_summary"]["license_policy"]
    assert payload["customer_safe_smoke_summary"]["actual_trace_expected_ok_count"] == 22
    assert payload["customer_safe_smoke_summary"]["actual_trace_entry_count"] == 22
    assert payload["customer_safe_smoke_summary"]["actual_trace_script_missing_count"] == 0
    assert (
        payload["customer_safe_smoke_summary"]["source_actual_execution_trace_numbered"]
        == str(customer_safe_actual_trace_md)
    )
    assert payload["source_paths"]["goal_evidence_actual_trace_overlay"] == str(
        goal_evidence_actual_trace_overlay
    )
    assert (
        payload["goal_evidence_actual_trace_overlay_summary"][
            "trace_ready_scenario_count"
        ]
        == 15
    )
    assert (
        payload["goal_evidence_actual_trace_overlay_summary"][
            "trace_script_missing_count"
        ]
        == 0
    )
    assert (
        payload["goal_evidence_actual_trace_overlay_summary"][
            "production_completion_scope"
        ]
        == "SAFE_TRACE_ONLY_NOT_PRODUCTION_COMPLETE"
    )
    assert payload["source_paths"]["remaining_operator_completion_simulation"] == str(
        remaining_operator_completion_simulation
    )
    remaining_summary = payload["remaining_operator_completion_simulation_summary"]
    assert remaining_summary["simulation_passed"] is True
    assert remaining_summary["sample_completed_row_count"] == 11
    assert remaining_summary["sync_updated_cell_count"] == 66
    assert remaining_summary["sync_conflict_count"] == 0
    assert remaining_summary["sync_unsafe_target_count"] == 0
    assert remaining_summary["validation_all_packet_rows_approved"] is True
    assert remaining_summary["validation_approved_row_count"] == 15
    assert remaining_summary["validation_needs_attention_count"] == 0
    assert remaining_summary["source_files_modified"] is False
    assert (
        remaining_summary["production_completion_scope"]
        == "SIMULATION_ONLY_NOT_ACTUAL_APPROVAL"
    )
    assert payload["next_action_summary"]["owner"] == "RK10操作担当者"
    assert payload["next_action_summary"]["evidence_pack_path"] == r"C:\pack\rk10"
    assert "run_safe_goal_checks_20260620.py" in payload["next_action_summary"]["after_action_command"]
    assert payload["next_action_summary"]["outlook_bundle_script"] == r"C:\outlook_com_bundle_dryrun.ps1"
    assert payload["next_action_summary"]["outlook_recovery_checklist"] == r"C:\outlook_com_recovery_checklist.md"


def test_next_action_summary_adds_business_review_supporting_inputs() -> None:
    module = load_module()

    summary = module.build_next_action_summary(
        {
            "next_bundle": "BUSINESS_REVIEW_BUNDLE",
            "rows": [
                {
                    "bundle": "BUSINESS_REVIEW_BUNDLE",
                    "owner": "業務担当者",
                    "scenarios": "44",
                    "evidence_pack_path": r"C:\pack\business_review",
                }
            ],
        }
    )

    supporting_paths = summary["supporting_input_paths"]
    assert supporting_paths[0]["label"] == "scenario44_single_entry_input_csv"
    assert supporting_paths[0]["path"].endswith("s44_business_review_single_entry_input.csv")
    assert supporting_paths[1]["label"] == "scenario44_next_steps_md"
    assert supporting_paths[1]["path"].endswith(
        (
            "s44_business_review_next_steps.md",
            "s44_business_review_next_steps.md.locked_copy",
        )
    )
    assert supporting_paths[2]["label"] == "scenario44_decision_input_csv"
    assert supporting_paths[2]["path"].endswith("s44_business_review_decision_input.csv")
    assert supporting_paths[3]["label"] == "scenario44_bucket_decision_input_csv"
    assert supporting_paths[3]["path"].endswith("s44_business_review_bucket_decision_input.csv")
    assert supporting_paths[4]["label"] == "scenario44_priority_queue_csv"
    assert supporting_paths[4]["path"].endswith("s44_business_review_priority_queue.csv")
    assert supporting_paths[5]["label"] == "scenario44_amount_zero_review_csv"
    assert supporting_paths[5]["path"].endswith("s44_review_01_amount_zero_review.csv")
    assert supporting_paths[6]["label"] == "scenario44_amount_mismatch_review_csv"
    assert supporting_paths[6]["path"].endswith("s44_review_02_amount_mismatch_review.csv")
    assert supporting_paths[7]["label"] == "scenario44_amount_match_quick_review_csv"
    assert supporting_paths[7]["path"].endswith("s44_review_03_amount_match_quick_review.csv")
    assert supporting_paths[8]["label"] == "scenario44_review_aid_csv"
    assert supporting_paths[8]["path"].endswith("s44_business_review_aid.csv")
    assert supporting_paths[9]["label"] == "scenario44_source_spot_check_csv"


def test_build_supporting_input_paths_prefers_locked_copy_and_includes_s71_environment(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    canonical = tmp_path / "s71_azure_ocr_environment_presence.csv"
    locked_copy = Path(str(canonical) + ".locked_copy")
    canonical.write_text("old\n", encoding="utf-8")
    locked_copy.write_text("new\n", encoding="utf-8")
    smoke_template = tmp_path / "s71_paid_azure_one_pdf_smoke_summary_template.json"

    monkeypatch.setitem(
        module.SUPPORTING_INPUT_PATHS_BY_BUNDLE,
        "PAID_AZURE_OCR_BUNDLE",
        [
            ("scenario71_environment_presence_csv", canonical),
            ("scenario71_paid_smoke_template_json", smoke_template),
        ],
    )

    supporting_paths = module.build_supporting_input_paths("PAID_AZURE_OCR_BUNDLE")

    assert supporting_paths[0] == {
        "label": "scenario71_environment_presence_csv",
        "path": str(locked_copy),
    }
    assert supporting_paths[1] == {
        "label": "scenario71_paid_smoke_template_json",
        "path": str(smoke_template),
    }


def test_build_markdown_includes_strict_boundary_and_sources() -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "report_status": "DRAFT_PROGRESS_REPORT_NOT_FINAL",
        "final_goal_complete": False,
        "safety": "read-only",
        "safe_runner_passed": True,
        "gate_count": 2,
        "passed_gate_count": 1,
        "blocking_gate_count": 1,
        "requirement_count": 1,
        "incomplete_requirement_count": 1,
        "scenario_count": 1,
        "complete_goal_evidence_count": 0,
        "objective_progress_summary": {
            "scenario_count": 1,
            "sample_ready_count": 1,
            "safe_execution_ready_count": 1,
            "rks_scoped_or_not_applicable_count": 0,
            "business_amount_or_draft_count": 0,
            "business_count_only_scope_count": 1,
            "final_evidence_ready_count": 0,
        },
        "blocking_gates": [
            {
                "gate": "RKS_GATE_MATRIX",
                "status": "INCOMPLETE",
                "detail": "unresolved",
                "next_action": "get RK10 log",
                "source": r"C:\rks.json",
            }
        ],
        "incomplete_requirements": [
            {
                "requirement_id": "REQ-03",
                "requirement": "RKSファイルを実際に実行して確認する",
                "current_status": "NOT_PROVEN",
                "remaining_gap": "runtime missing",
                "next_evidence_needed": "latest clean log",
                "authoritative_evidence": r"C:\rks.md",
            }
        ],
        "ledger_rows": [
            {
                "scenario": "57",
                "objective_checkpoint_summary": "sample=OK; safe=OK; rks=PENDING; cost=COUNT_ONLY; final=PENDING",
                "missing_objective_proofs": "latest clean log",
                "evidence_strength": "PARTIAL_EVIDENCE",
            }
        ],
        "next_bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
        "next_operator_action": "get evidence",
        "next_action_summary": {
            "owner": "RK10操作担当者",
            "scenarios": "57, 58",
            "approval_boundary": "safe-stop only",
            "forbidden": "ButtonRun",
            "evidence_pack_path": r"C:\pack\rk10",
            "bundle_sheet_path": r"C:\sheet.csv",
            "external_runbook": r"C:\runbook.md.numbered",
            "external_runbook_json": r"C:\runbook.json",
            "outlook_bundle_script": r"C:\outlook_com_bundle_dryrun.ps1",
            "outlook_recovery_checklist": r"C:\outlook_com_recovery_checklist.md",
            "outlook_com_diagnosis_report": "",
            "rk10_recovery_checklist": r"C:\rk10_checklist.md.numbered",
            "after_action_command": r"C:\Python313\python.exe -X utf8 C:\repo\tools\run_safe_goal_checks_20260620.py",
            "supporting_input_paths": [
                {
                    "label": "scenario44_review_aid_csv",
                    "path": r"C:\review\s44_business_review_aid.csv",
                }
            ],
        },
        "completion_audit_summary": {
            "report_status": "CURRENT_AUDIT_NOT_FINAL",
            "overall_goal_complete": False,
            "issue_count": 3,
            "missing_source_count": 0,
            "packet_approved_row_count": 2,
            "packet_needs_attention_count": 1,
            "bundle_final_evidence_ready_count": 0,
            "bundle_count": 4,
            "rks_runtime_approved_count": 0,
            "rks_runtime_required_count": 2,
            "amount_verified_scenario_count": 1,
            "issues_csv": r"C:\audit_issues.csv",
        },
        "reference_integrity_summary": {
            "prepared_pack_validation_passed": True,
            "source_reference_count": 15,
            "source_reference_exists_now_count": 15,
            "source_reference_hashed_now_count": 15,
            "missing_prepared_pack_count": 0,
            "final_evidence_ready_count": 0,
            "bundle_count": 6,
        },
        "final_evidence_fill_summary": {
            "active_queue_count": 6,
            "ready_or_completed_count": 0,
            "operator_attention_row_count": 20,
            "next_active_bundle": "BUSINESS_REVIEW_BUNDLE",
            "unified_input_csv": r"C:\unified_final_evidence_input.csv",
            "after_action_command": r"C:\Python313\python.exe -X utf8 C:\repo\tools\run_safe_goal_checks_20260620.py",
            "next_entry_keys": "BUSINESS_REVIEW_BUNDLE::44",
            "next_fill_only_fields": "operator_result, reviewer, reviewed_at",
            "next_start_here_path": r"C:\business_review_bundle_START_HERE.md",
            "next_missing_operator_fields": "OPERATOR_RESULT_BLANK",
            "next_supplemental_evidence_status": "",
            "next_supplemental_evidence_source": "",
            "supplemental_evidence_bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
            "supplemental_evidence_status": "collector_status=READY_FOR_REVIEWER_TIMESTAMP; auto_appended_intake_rows=3",
            "supplemental_evidence_source": r"C:\rk10_collect.json",
            "supplemental_remaining_runtime_evidence": "rks_gate_matrix_pending: 57=runtime safe-stop latest clean log",
        },
        "rks_existing_evidence_search_summary": {
            "source_generated_at": "2026-06-22T02:22:12",
            "overall_rks_production_ready": False,
            "reviewed_non_promotable_count": 1,
            "rows": [
                {
                    "scenario": "57",
                    "current_rks_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
                    "runtime_intake_status": "RKS_RUNTIME_EVIDENCE_PENDING",
                    "existing_evidence_search_result": "not_promotable: Python dry-run only",
                    "next_safe_action": "no-mail safe-stop latest clean log",
                }
            ],
        },
        "remaining_operator_completion_simulation_summary": {
            "source_exists": True,
            "source_json": r"C:\simulation\remaining_operator_input_completion_simulation.json",
            "source_markdown_numbered": r"C:\simulation\remaining_operator_input_completion_simulation.md.numbered",
            "source_markdown_exists": True,
            "generated_at": "2026-06-23T05:06:00",
            "simulation_passed": True,
            "sample_completed_row_count": 11,
            "sync_updated_cell_count": 66,
            "sync_conflict_count": 0,
            "sync_unsafe_target_count": 0,
            "validation_all_packet_rows_approved": True,
            "validation_approved_row_count": 15,
            "validation_row_count": 15,
            "validation_needs_attention_count": 0,
            "source_files_modified": False,
            "validation_report_md": r"C:\simulation\validation.md.numbered",
            "safety": "isolated copied CSVs only",
            "production_completion_scope": "SIMULATION_ONLY_NOT_ACTUAL_APPROVAL",
        },
        "source_paths": {"completion_gate": r"C:\completion.json"},
        "source_exists": {"completion_gate": True},
    }

    markdown = module.build_markdown(payload)

    assert "未完了（ドラフト）" in markdown
    assert "not a production completion report" in markdown
    assert "## Objective Progress Summary" in markdown
    assert "sample_ready_count: `1/1`" in markdown
    assert "safe_execution_ready_count: `1/1`" in markdown
    assert "business_amount_or_draft_count: `0/1`" in markdown
    assert "business_count_only_scope_count: `1/1`" in markdown
    assert "business_cost_scope_count: `1/1`" in markdown
    assert "final_evidence_ready_count: `0/1`" in markdown
    assert "## Remaining Operator Input Completion Simulation" in markdown
    assert "simulation_passed: `True`" in markdown
    assert "sample_completed_row_count: `11`" in markdown
    assert "validation_approved_row_count: `15/15`" in markdown
    assert "source_files_modified: `False`" in markdown
    assert "SIMULATION_ONLY_NOT_ACTUAL_APPROVAL" in markdown
    assert "does not replace actual customer/operator approval" in markdown
    assert "## RKS Existing Evidence Search" in markdown
    assert "reviewed_non_promotable_count: `1`" in markdown
    assert "not_promotable: Python dry-run only" in markdown
    assert "RKS_GATE_MATRIX" in markdown
    assert "REQ-03" in markdown
    assert "RK10_EDITOR_RUNTIME_BUNDLE" in markdown
    assert "## Completion Audit" in markdown
    assert "issue_count: `3`" in markdown
    assert "## Reference Evidence Integrity" in markdown
    assert "source_reference_hashed_now_count: `15/15`" in markdown
    assert "## Final Evidence Fill Queue" in markdown
    assert "next_entry_keys: `BUSINESS_REVIEW_BUNDLE::44`" in markdown
    assert "next_fill_only_fields: `operator_result, reviewer, reviewed_at`" in markdown
    assert "next_supplemental_evidence_status: ``" in markdown
    assert "supplemental_evidence_bundle: `RK10_EDITOR_RUNTIME_BUNDLE`" in markdown
    assert "supplemental_evidence_status: `collector_status=READY_FOR_REVIEWER_TIMESTAMP; auto_appended_intake_rows=3`" in markdown
    assert "rks_gate_matrix_pending: 57=runtime safe-stop latest clean log" in markdown
    assert r"C:\rk10_collect.json" in markdown
    assert r"C:\audit_issues.csv" in markdown
    assert "## Next Action Detail" in markdown
    assert r"C:\pack\rk10" in markdown
    assert "outlook_com_bundle_dryrun.ps1" in markdown
    assert "outlook_com_recovery_checklist.md" in markdown
    assert "run_safe_goal_checks_20260620.py" in markdown
    assert "scenario44_review_aid_csv" in markdown
    assert r"C:\review\s44_business_review_aid.csv" in markdown
    assert r"C:\completion.json" in markdown


def test_write_outputs_creates_field_csv_exports(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "report_status": "DRAFT_PROGRESS_REPORT_NOT_FINAL",
        "final_goal_complete": False,
        "safety": "read-only",
        "safe_runner_passed": True,
        "gate_count": 2,
        "passed_gate_count": 1,
        "blocking_gate_count": 1,
        "requirement_count": 1,
        "incomplete_requirement_count": 1,
        "scenario_count": 1,
        "complete_goal_evidence_count": 0,
        "blocking_gates": [
            {
                "gate": "RKS_GATE_MATRIX",
                "status": "INCOMPLETE",
                "detail": "unresolved",
                "next_action": "get RK10 log",
                "source": r"C:\rks.json",
            }
        ],
        "incomplete_requirements": [
            {
                "requirement_id": "REQ-03",
                "requirement": "RKSファイルを実際に実行して確認する",
                "current_status": "NOT_PROVEN",
                "remaining_gap": "runtime missing",
                "next_evidence_needed": "latest clean log",
                "authoritative_evidence": r"C:\rks.md",
            }
        ],
        "ledger_rows": [
            {
                "scenario": "57",
                "objective_checkpoint_summary": "sample=OK; safe=OK; rks=PENDING; final=PENDING",
                "missing_objective_proofs": "latest clean log",
                "evidence_strength": "PARTIAL_EVIDENCE",
            }
        ],
        "next_bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
        "next_operator_action": "get evidence",
        "source_paths": {"completion_gate": r"C:\completion.json"},
        "source_exists": {"completion_gate": True},
    }

    outputs = module.write_outputs(payload, tmp_path)

    assert Path(outputs["blocking_gates_csv"]).exists()
    assert Path(outputs["incomplete_requirements_csv"]).exists()
    assert Path(outputs["scenario_snapshot_csv"]).exists()
    with Path(outputs["blocking_gates_csv"]).open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        blocking_rows = list(csv.DictReader(handle))
    with Path(outputs["incomplete_requirements_csv"]).open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        requirement_rows = list(csv.DictReader(handle))
    with Path(outputs["scenario_snapshot_csv"]).open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        scenario_rows = list(csv.DictReader(handle))
    written_json = json.loads(
        (tmp_path / "goal_final_report.json").read_text(encoding="utf-8")
    )
    written_markdown = (tmp_path / "goal_final_report.md").read_text(encoding="utf-8")

    assert blocking_rows[0]["gate"] == "RKS_GATE_MATRIX"
    assert requirement_rows[0]["requirement_id"] == "REQ-03"
    assert scenario_rows[0]["scenario"] == "57"
    assert written_json["field_export_paths"]["blocking_gates_csv"] == outputs["blocking_gates_csv"]
    assert "## Field Exports" in written_markdown
