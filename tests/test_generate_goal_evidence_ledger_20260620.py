import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_goal_evidence_ledger_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_goal_evidence_ledger_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_classify_scope_keeps_hold_incomplete() -> None:
    module = load_module()

    proven_scope, evidence_strength, goal_gap = module.classify_scope(
        "HOLD_OUTLOOK_COM_NOT_READY",
        "N_A_NO_PRIMARY_RKS",
    )

    assert proven_scope == "HOLD_GATE_ONLY"
    assert evidence_strength == "BLOCKED_BY_INPUT_OR_ENVIRONMENT"
    assert "HOLD" in goal_gap


def test_build_rows_maps_grouped_rks_status() -> None:
    module = load_module()
    module.load_sample_data_statuses = lambda: {"55": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT"}
    module.load_safe_execution_statuses = lambda: {"55": "SAFE_SUITE_EXIT0_STDERR0"}
    module.load_business_cost_statuses = lambda: {"55": ("DRYRUN_BUSINESS_AMOUNT_REPORTED", 12938354)}
    module.load_final_evidence_statuses = lambda: {}
    snapshot_payload = {
        "scenarios": [
            {
                "scenario": "55",
                "current_status": "V2_DRYRUN_ERRORS_0_OVERFLOW_0",
                "source": r"C:\evidence\s55.md",
                "source_exists": True,
            }
        ]
    }
    rks_payload = {
        "rows": [
            {
                "scenario": "37/47/55/63",
                "current_rks_status": "SAFE_STOP_SCOPE_ONLY",
                "runtime_intake_status": "RKS_RUNTIME_EVIDENCE_PENDING",
                "runtime_intake_approved_count": 2,
                "runtime_intake_required_count": 4,
            }
        ]
    }

    rows = module.build_rows(snapshot_payload, rks_payload)

    assert rows[0].scenario == "55"
    assert rows[0].rks_status == "SAFE_STOP_SCOPE_ONLY"
    assert rows[0].rks_runtime_intake_status == "RKS_RUNTIME_EVIDENCE_PENDING"
    assert rows[0].rks_runtime_intake_approved == "group:2/4"
    assert rows[0].evidence_strength == "PARTIAL_EVIDENCE"
    assert rows[0].supplemental_evidence == ""
    assert rows[0].sample_data_status == "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT"
    assert rows[0].safe_execution_status == "SAFE_SUITE_EXIT0_STDERR0"
    assert rows[0].business_cost_status == "DRYRUN_BUSINESS_AMOUNT_REPORTED"
    assert rows[0].business_cost_amount_yen == 12_938_354
    assert "sample=OK" in rows[0].objective_checkpoint_summary
    assert "safe=OK" in rows[0].objective_checkpoint_summary
    assert "operator final evidence" in rows[0].missing_objective_proofs


def test_classify_scope_uses_confirmed_safe_stop_before_generic_rks_status() -> None:
    module = load_module()

    proven_scope, evidence_strength, goal_gap = module.classify_scope(
        "PYTHON_SAMPLE_OK_RKS_SAFE_STOP_SCOPE_ONLY",
        "SAFE_STOP_SCOPE_ONLY",
        "RKS_RUNTIME_EVIDENCE_CONFIRMED",
    )

    assert proven_scope == "SAFE_STOP_SCOPE_ONLY"
    assert evidence_strength == "PARTIAL_EVIDENCE"
    assert "実対象データ" in goal_gap
    assert "RK10 open/build/runtime" not in goal_gap


def test_classify_scope_reports_deferred_runtime_gate_as_entry_decision_pending() -> None:
    module = load_module()

    proven_scope, evidence_strength, goal_gap = module.classify_scope(
        "CONFIRMED_FILE_EXISTS_SCOPE_SEPARATE",
        "ENTRY_SELECTION_REQUIRED",
        "RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION",
    )

    assert proven_scope == "RKS_PREREQUISITE_OR_ENTRY_DECISION_PENDING"
    assert evidence_strength == "PARTIAL_EVIDENCE"
    assert "入口選定" in goal_gap


def test_classify_objective_checkpoints_lists_missing_proofs() -> None:
    module = load_module()

    summary, missing_proofs = module.classify_objective_checkpoints(
        status="HOLD_OUTLOOK_COM_NOT_READY",
        rks_status="N_A_NO_PRIMARY_RKS",
        rks_runtime_status="N_A_NO_PRIMARY_RKS",
        evidence_strength="BLOCKED_BY_INPUT_OR_ENVIRONMENT",
        sample_data_status="OUTLOOK_COM_HOLD_SAMPLE_REFRESH_REQUIRED",
        safe_execution_status="NOT_IN_SAFE_SUITE_OUTLOOK_COM_HOLD",
        business_cost_status="OUTLOOK_COM_HOLD_NO_COST_EXECUTION",
    )

    assert summary == "sample=HOLD; safe=HOLD; rks=N_A; cost=PENDING; final=PENDING"
    assert "current sample/dry-run refresh" in missing_proofs
    assert "safe no-side-effect execution log" in missing_proofs
    assert "HOLD release" in missing_proofs
    assert "operator final evidence" in missing_proofs


def test_classify_objective_checkpoints_treats_outlook_bundle_ready_as_sample_safe_ok() -> None:
    module = load_module()

    summary, missing_proofs = module.classify_objective_checkpoints(
        status="READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
        rks_status="N_A_NO_PRIMARY_RKS",
        rks_runtime_status="N_A_NO_PRIMARY_RKS",
        evidence_strength="PARTIAL_EVIDENCE",
        sample_data_status=module.OUTLOOK_COM_SAMPLE_READY_STATUS,
        safe_execution_status=module.OUTLOOK_COM_SAFE_READY_STATUS,
        business_cost_status="OUTLOOK_COM_HOLD_NO_COST_EXECUTION",
    )

    assert summary == "sample=OK; safe=OK; rks=N_A; cost=PENDING; final=PENDING"
    assert "current sample/dry-run refresh" not in missing_proofs
    assert "safe no-side-effect execution log" not in missing_proofs
    assert "business count/amount/difference proof" in missing_proofs
    assert "operator final evidence" in missing_proofs


def test_classify_objective_checkpoints_treats_count_only_cost_as_partial() -> None:
    module = load_module()

    summary, missing_proofs = module.classify_objective_checkpoints(
        status="READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
        rks_status="N_A_NO_PRIMARY_RKS",
        rks_runtime_status="N_A_NO_PRIMARY_RKS",
        evidence_strength="PARTIAL_EVIDENCE",
        sample_data_status=module.OUTLOOK_COM_SAMPLE_READY_STATUS,
        safe_execution_status=module.OUTLOOK_COM_SAFE_READY_STATUS,
        business_cost_status="OUTLOOK_COM_DRYRUN_COUNT_PROOF_NO_PRINT_NO_MAIL",
        final_evidence_ready=True,
    )

    assert "cost=COUNT_ONLY" in summary
    assert "final=OK" in summary
    assert "business amount proof or explicit no-amount scope" in missing_proofs
    assert "business count/amount/difference proof" not in missing_proofs
    assert "operator final evidence" not in missing_proofs


def test_classify_objective_checkpoints_treats_s47_flag_count_only_cost_as_partial() -> None:
    module = load_module()

    summary, missing_proofs = module.classify_objective_checkpoints(
        status="CONFIRMED_FILE_EXISTS_BUT_LIVE_FLAGS_UNPROVEN",
        rks_status="SAFE_STOP_SCOPE_ONLY",
        rks_runtime_status="RKS_RUNTIME_EVIDENCE_CONFIRMED",
        evidence_strength="PARTIAL_EVIDENCE",
        sample_data_status="SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
        safe_execution_status="SAFE_SUITE_EXIT0_STDERR0",
        business_cost_status="DRYRUN_FLAG_COUNT_PROOF_NO_AMOUNT_NO_UPLOAD",
    )

    assert "cost=COUNT_ONLY" in summary
    assert "business amount proof or explicit no-amount scope" in missing_proofs
    assert "operator final evidence" in missing_proofs
    assert "business count/amount/difference proof" not in missing_proofs


def test_classify_objective_checkpoints_treats_non_amount_count_proofs_as_partial() -> None:
    module = load_module()

    for cost_status in [
        "RECORU_SAMPLE_ZERO_TARGET_AND_GUARD_COUNT_PROOF_NO_AMOUNT",
        "ORDER_REGISTRATION_ONE_CASE_PROOF_NO_PROD_REGISTER_NO_AMOUNT",
        "DRIVE_REPORT_ROW_COUNT_PROOF_NO_MAINSV_WRITE",
        "S56_LOCAL_COPY_WRITE_COUNT_PROOF_NO_PRODUCTION_MAIL",
        "S57_DRYRUN_OUTPUT_PLAN_PROOF_NO_FINAL_COPY",
    ]:
        summary, missing_proofs = module.classify_objective_checkpoints(
            status="SCOPED_CONFIRMED_AFTER_FEEDBACK",
            rks_status="SAFE_STOP_SCOPE_ONLY",
            rks_runtime_status="RKS_RUNTIME_EVIDENCE_CONFIRMED",
            evidence_strength="PARTIAL_EVIDENCE",
            sample_data_status="SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
            safe_execution_status="SAFE_SUITE_EXIT0_STDERR0",
            business_cost_status=cost_status,
        )

        assert "cost=COUNT_ONLY" in summary
        assert "business amount proof or explicit no-amount scope" in missing_proofs
        assert "business count/amount/difference proof" not in missing_proofs


def test_classify_objective_checkpoints_treats_s43_temp_save_amount_as_draft_ok() -> None:
    module = load_module()

    summary, missing_proofs = module.classify_objective_checkpoints(
        status="SCOPED_CONFIRMED_AFTER_FEEDBACK",
        rks_status="NO_RKS_MATRIX_ROW",
        rks_runtime_status="NO_RKS_MATRIX_ROW",
        evidence_strength="PARTIAL_EVIDENCE",
        sample_data_status="SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
        safe_execution_status="SAFE_SUITE_EXIT0_STDERR0",
        business_cost_status="RAKURAKU_TEMP_SAVE_AMOUNT_REPORTED_FINAL_NOT_CLICKED",
    )

    assert "cost=DRAFT_OK" in summary
    assert "business count/amount/difference proof" not in missing_proofs
    assert "operator final evidence" in missing_proofs


def test_classify_objective_checkpoints_treats_s51_52_draft_save_amount_as_draft_ok() -> None:
    module = load_module()

    summary, missing_proofs = module.classify_objective_checkpoints(
        status="EXCEL_SAVE_SCOPE_SELECTED_AFTER_FEEDBACK",
        rks_status="RKS_STATUS_GATE_UNCONFIRMED",
        rks_runtime_status="RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION",
        evidence_strength="PARTIAL_EVIDENCE",
        sample_data_status="SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
        safe_execution_status="SAFE_SUITE_EXIT0_STDERR0",
        business_cost_status="RAKURAKU_DRAFT_SAVE_AMOUNT_REPORTED_NO_FINAL_SUBMIT_NO_MAIL",
    )

    assert "cost=DRAFT_OK" in summary
    assert "business count/amount/difference proof" not in missing_proofs
    assert "RK10 open/build/runtime/latest clean log or entry decision" in missing_proofs
    assert "operator final evidence" in missing_proofs


def test_build_rows_overlays_outlook_bundle_safe_evidence_without_final_approval(tmp_path: Path) -> None:
    module = load_module()
    bundle_validation = tmp_path / "bundle_validation.json"
    bundle_validation.write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "scenarios": "12/13",
                        "final_evidence_path": "",
                        "final_evidence_ready": False,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    outlook_collect = tmp_path / "outlook_collect.json"
    outlook_collect.write_text(
        json.dumps(
            {
                "status": "READY_FOR_FINAL_EVIDENCE_INTAKE",
                "ready_for_intake": True,
                "log_status": {
                    "check_exit": "0",
                    "scan_exit": "0",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    module.BUNDLE_EVIDENCE_VALIDATION_JSON = bundle_validation
    module.OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = outlook_collect
    module.load_sample_data_statuses = lambda: {"12/13": "OUTLOOK_COM_HOLD_SAMPLE_REFRESH_REQUIRED"}
    module.load_safe_execution_statuses = lambda: {"12/13": "NOT_IN_SAFE_SUITE_OUTLOOK_COM_HOLD"}
    module.load_business_cost_statuses = lambda: {"12/13": ("OUTLOOK_COM_HOLD_NO_COST_EXECUTION", None)}
    snapshot_payload = {
        "scenarios": [
            {
                "scenario": "12/13",
                "current_status": "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
                "source": r"C:\evidence\s12.py",
                "source_exists": True,
            }
        ]
    }
    rks_payload = {
        "rows": [
            {
                "scenario": "12/13",
                "current_rks_status": "N_A_NO_PRIMARY_RKS",
                "runtime_intake_status": "N_A_NO_PRIMARY_RKS",
                "runtime_intake_approved_count": 0,
                "runtime_intake_required_count": 0,
            }
        ]
    }

    rows = module.build_rows(snapshot_payload, rks_payload)

    assert rows[0].sample_data_status == module.OUTLOOK_COM_SAMPLE_READY_STATUS
    assert rows[0].safe_execution_status == module.OUTLOOK_COM_SAFE_READY_STATUS
    assert rows[0].final_evidence_ready is False
    assert rows[0].final_evidence_path == ""
    assert "sample=OK" in rows[0].objective_checkpoint_summary
    assert "safe=OK" in rows[0].objective_checkpoint_summary
    assert "final=PENDING" in rows[0].objective_checkpoint_summary
    assert "current sample/dry-run refresh" not in rows[0].missing_objective_proofs
    assert "operator final evidence" in rows[0].missing_objective_proofs


def test_load_final_evidence_statuses_maps_bundle_scenarios(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "bundle_validation.json"
    path.write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "scenarios": "43, 47, 55, 63",
                        "final_evidence_ready": False,
                        "final_evidence_path": "",
                    },
                    {
                        "scenarios": "12/13",
                        "final_evidence_ready": True,
                        "final_evidence_path": r"C:\final\scenario_12_13",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    statuses = module.load_final_evidence_statuses(path)

    assert statuses["43"] == (False, "")
    assert statuses["55"] == (False, "")
    assert statuses["12/13"] == (True, r"C:\final\scenario_12_13")


def test_classify_objective_checkpoints_treats_s63_cost_status_as_sample_ok() -> None:
    module = load_module()

    summary, missing_proofs = module.classify_objective_checkpoints(
        status="PYTHON_SAMPLE_OK_RKS_SAFE_STOP_SCOPE_ONLY",
        rks_status="SAFE_STOP_SCOPE_ONLY",
        rks_runtime_status="RKS_RUNTIME_EVIDENCE_CONFIRMED",
        evidence_strength="PARTIAL_EVIDENCE",
        sample_data_status="SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
        safe_execution_status="SAFE_SUITE_EXIT0_STDERR0",
        business_cost_status="LOCAL_DRYRUN_PAYMENT_ITEMS_AMOUNT_RECALCULATED",
    )

    assert "cost=SAMPLE_OK" in summary
    assert "business count/amount/difference proof" not in missing_proofs
    assert "operator final evidence" in missing_proofs


def test_classify_objective_checkpoints_treats_s51_52_excel_only_amount_as_sample_ok() -> None:
    module = load_module()

    summary, missing_proofs = module.classify_objective_checkpoints(
        status="EXCEL_SAVE_SCOPE_SELECTED_AFTER_FEEDBACK",
        rks_status="RKS_STATUS_GATE_UNCONFIRMED",
        rks_runtime_status="RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION",
        evidence_strength="PARTIAL_EVIDENCE",
        sample_data_status="SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
        safe_execution_status="SAFE_SUITE_EXIT0_STDERR0",
        business_cost_status="SOFTBANK_EXCEL_ONLY_AMOUNT_REPORTED_RAKURAKU_SKIPPED",
    )

    assert "cost=SAMPLE_OK" in summary
    assert "business count/amount/difference proof" not in missing_proofs
    assert "RK10 open/build/runtime/latest clean log or entry decision" in missing_proofs
    assert "operator final evidence" in missing_proofs


def test_classify_objective_checkpoints_treats_s51_52_manual_submission_amount_as_sample_ok() -> None:
    module = load_module()

    summary, missing_proofs = module.classify_objective_checkpoints(
        status="EXCEL_SAVE_SCOPE_SELECTED_AFTER_FEEDBACK",
        rks_status="RKS_STATUS_GATE_UNCONFIRMED",
        rks_runtime_status="RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION",
        evidence_strength="PARTIAL_EVIDENCE",
        sample_data_status="SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
        safe_execution_status="SAFE_SUITE_EXIT0_STDERR0",
        business_cost_status="SOFTBANK_MANUAL_SUBMISSION_AMOUNT_REPORTED_RAKURAKU_SKIPPED",
    )

    assert "cost=SAMPLE_OK" in summary
    assert "business count/amount/difference proof" not in missing_proofs
    assert "RK10 open/build/runtime/latest clean log or entry decision" in missing_proofs
    assert "operator final evidence" in missing_proofs


def test_classify_objective_checkpoints_treats_s58_test_suite_amount_as_sample_ok() -> None:
    module = load_module()

    summary, missing_proofs = module.classify_objective_checkpoints(
        status="SAFE_SAMPLE_OK_RKS_UNCONFIRMED",
        rks_status="RKS_RUNTIME_UNCONFIRMED",
        rks_runtime_status="RKS_RUNTIME_EVIDENCE_PENDING",
        evidence_strength="PARTIAL_EVIDENCE",
        sample_data_status="SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
        safe_execution_status="SAFE_SUITE_EXIT0_STDERR0",
        business_cost_status="LOCAL_SAMPLE_TEST_SUITE_AMOUNT_RECALCULATED",
    )

    assert "cost=SAMPLE_OK" in summary
    assert "business count/amount/difference proof" not in missing_proofs
    assert "RK10 open/build/runtime/latest clean log or entry decision" in missing_proofs
    assert "operator final evidence" in missing_proofs


def test_build_payload_counts_missing_sources(monkeypatch) -> None:
    module = load_module()
    snapshot_payload = {
        "scenarios": [
            {
                "scenario": "44",
                "current_status": "HOLD_NO_CONFIRMED_ROWS",
                "source": r"C:\missing\s44.csv",
                "source_exists": False,
            }
        ]
    }
    rks_payload = {"rows": []}
    monkeypatch.setattr(module, "build_snapshot_payload", lambda _exit_code: snapshot_payload)
    monkeypatch.setattr(module, "build_rks_payload", lambda: rks_payload)

    payload = module.build_payload(2)

    assert payload["overall_goal_complete"] is False
    assert payload["scenario_count"] == 1
    assert payload["complete_goal_evidence_count"] == 0
    assert payload["missing_source_count"] == 1


def test_build_markdown_includes_requirement_interpretation() -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "overall_goal_complete": False,
        "safety": "read-only evidence ledger only; no external operation",
        "scenario_count": 1,
        "complete_goal_evidence_count": 0,
        "missing_source_count": 0,
        "safe_runner_summary": r"C:\summary.md",
        "execution_packet": r"C:\packet.md",
        "sample_data_map": r"C:\sample_data_map.md",
        "safe_execution_map": r"C:\safe_execution_map.md",
        "business_cost_map": r"C:\business_cost_map.md",
        "final_evidence_ready_count": 0,
        "rows": [
            {
                "scenario": "70",
                "current_status": "HOLD_PAYMENT_EXECUTE_NOT_ALLOWED",
                "rks_status": "PAYMENT_APPROVAL_HOLD_BEFORE_RKS",
                "rks_runtime_intake_status": "RKS_RUNTIME_EVIDENCE_PENDING",
                "rks_runtime_intake_approved": "0/1",
                "proven_scope": "HOLD_GATE_ONLY",
                "evidence_strength": "BLOCKED_BY_INPUT_OR_ENVIRONMENT",
                "goal_gap": "approval missing",
                "source": r"C:\evidence\s70.csv",
                "source_exists": True,
                "supplemental_evidence": r"C:\evidence\s70_preview.md",
                "supplemental_evidence_exists": True,
                "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                "sample_data_evidence": r"C:\sample_data_map.md",
                "sample_data_evidence_exists": True,
                "safe_execution_status": "SAFE_SUITE_EXIT0_STDERR0",
                "safe_execution_evidence": r"C:\safe_execution_map.md",
                "safe_execution_evidence_exists": True,
                "business_cost_status": "SAMPLE_CONFIRM_PREVIEW_AMOUNT_RECALCULATED",
                "business_cost_amount_yen": 80235,
                "business_cost_evidence": r"C:\business_cost_map.md",
                "business_cost_evidence_exists": True,
                "final_evidence_ready": False,
                "final_evidence_path": "",
                "objective_checkpoint_summary": "sample=OK; safe=OK; rks=PENDING; cost=SAMPLE_OK; final=PENDING",
                "missing_objective_proofs": "RK10 open/build/runtime/latest clean log or entry decision, operator final evidence and approval record",
            }
        ],
    }

    markdown = module.build_markdown(payload)

    assert "# 目標証跡台帳 2026-06-20" in markdown
    assert "RKSは `OK_CANDIDATE`" in markdown
    assert "RKS_RUNTIME_EVIDENCE_PENDING" in markdown
    assert "| 70 | HOLD_PAYMENT_EXECUTE_NOT_ALLOWED" in markdown
    assert r"C:\evidence\s70_preview.md" in markdown
    assert "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT" in markdown
    assert "SAFE_SUITE_EXIT0_STDERR0" in markdown
    assert "SAMPLE_CONFIRM_PREVIEW_AMOUNT_RECALCULATED" in markdown
    assert "Final Evidence Ready" in markdown
    assert "Objective Checkpoints" in markdown
    assert "RK10 open/build/runtime/latest clean log" in markdown
