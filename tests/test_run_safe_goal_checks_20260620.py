import importlib.util
import sys
from argparse import Namespace
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "run_safe_goal_checks_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("run_safe_goal_checks_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_pre_completion_steps_excludes_completion_gate() -> None:
    module = load_module()

    pre_steps = module.build_pre_completion_steps(2)
    step_names = [name for name, _command in pre_steps]

    assert "goal_completion_gate" not in step_names
    assert "rks_runtime_intake_validation" in step_names
    assert "goal_execution_packet_validation" in step_names


def test_build_steps_generates_rks_matrix_after_runtime_validation() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("rks_static_guard_audit") < step_names.index("rks_runtime_operator_pack")
    assert step_names.index("rks_static_guard_audit") < step_names.index("rks_debugger_artifact_reconcile")
    assert step_names.index("rks_debugger_artifact_reconcile") < step_names.index("rks_runtime_operator_pack")
    assert step_names.index("rks_runtime_operator_pack") < step_names.index("rks_runtime_status_gate_sync")
    assert step_names.index("rks_runtime_status_gate_sync") < step_names.index("rks_runtime_intake_validation")
    assert step_names.index("rks_runtime_intake_validation") < step_names.index("rks_gate_matrix")


def test_build_steps_refreshes_diagnosis_before_queue_prefill() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("external_approval_runbook") < step_names.index("outlook_com_environment_diagnosis")
    assert step_names.index("outlook_com_environment_diagnosis") < step_names.index("next_approval_queue")
    assert step_names.index("next_approval_queue") < step_names.index("operator_evidence_prefill")
    assert step_names.index("operator_evidence_prefill") < step_names.index("remaining_approval_next_steps")
    assert step_names.index("remaining_approval_next_steps") < step_names.index("goal_execution_packet_validation")
    assert step_names.index("goal_execution_packet_validation") < step_names.index("final_evidence_fill_queue")
    assert step_names.index("final_evidence_fill_queue") < step_names.index("prod_migration_readiness")
    assert step_names.index("operator_evidence_prefill") < step_names.index("goal_execution_packet_validation")


def test_build_steps_generates_unified_intake_before_bundle_sync() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("bundle_operator_sheet") < step_names.index(
        "final_evidence_candidate_stage"
    )
    assert step_names.index("final_evidence_candidate_stage") < step_names.index(
        "unified_final_evidence_intake_sync"
    )
    assert step_names.index("unified_final_evidence_intake_sync") < step_names.index(
        "execution_packet_candidate_path_sync"
    )
    assert step_names.index("execution_packet_candidate_path_sync") < step_names.index(
        "bundle_evidence_intake_sync"
    )
    assert step_names.index("bundle_evidence_packs") < step_names.index(
        "final_evidence_candidate_stage"
    )


def test_build_steps_stages_candidate_evidence_before_bundle_sync() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("final_evidence_candidate_stage") < step_names.index(
        "unified_final_evidence_intake_sync"
    )
    assert step_names.index("unified_final_evidence_intake_sync") < step_names.index(
        "execution_packet_candidate_path_sync"
    )
    assert step_names.index("execution_packet_candidate_path_sync") < step_names.index(
        "bundle_evidence_intake_sync"
    )


def test_build_steps_syncs_candidate_paths_before_packet_validation() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("unified_final_evidence_intake_sync") < step_names.index(
        "execution_packet_candidate_path_sync"
    )
    assert step_names.index("execution_packet_candidate_path_sync") < step_names.index(
        "goal_execution_packet_validation"
    )


def test_build_steps_collects_s44_business_review_before_bundle_sync() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("bundle_evidence_packs") < step_names.index(
        "s44_business_review_evidence_collect"
    )
    assert step_names.index("s44_business_review_evidence_collect") < step_names.index(
        "bundle_operator_sheet"
    )
    assert step_names.index("s44_business_review_evidence_collect") < step_names.index(
        "bundle_evidence_intake_sync"
    )


def test_build_steps_runs_s44_quick_bucket_simulation_after_candidate_build() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("s44_spot_check_candidates") < step_names.index(
        "s44_review_db_amount_evidence"
    )
    assert step_names.index("s44_review_db_amount_evidence") < step_names.index(
        "s44_sample_ok_shadow"
    )
    assert step_names.index("s44_review_db_amount_evidence") < step_names.index(
        "s44_quick_bucket_ok_simulation"
    )
    assert step_names.index("s44_sample_ok_shadow") < step_names.index(
        "s44_quick_bucket_ok_simulation"
    )
    assert step_names.index("s44_quick_bucket_ok_simulation") < step_names.index(
        "s70_sample_confirm_preview"
    )


def test_build_steps_collects_business_data_approval_before_bundle_sync() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("bundle_evidence_packs") < step_names.index(
        "business_data_approval_evidence_collect"
    )
    assert step_names.index("business_data_approval_evidence_collect") < step_names.index(
        "bundle_operator_sheet"
    )
    assert step_names.index("business_data_approval_evidence_collect") < step_names.index(
        "bundle_evidence_intake_sync"
    )


def test_build_steps_collects_rk10_runtime_before_bundle_sync() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("bundle_evidence_packs") < step_names.index(
        "rk10_runtime_bundle_evidence_collect"
    )
    assert step_names.index("rk10_runtime_bundle_evidence_collect") < step_names.index(
        "bundle_operator_sheet"
    )
    assert step_names.index("rk10_runtime_bundle_evidence_collect") < step_names.index(
        "bundle_evidence_intake_sync"
    )


def test_build_steps_collects_s70_payment_approval_before_bundle_sync() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("bundle_evidence_packs") < step_names.index(
        "s70_payment_approval_evidence_collect"
    )
    assert step_names.index("s70_payment_approval_evidence_collect") < step_names.index(
        "bundle_operator_sheet"
    )
    assert step_names.index("s70_payment_approval_evidence_collect") < step_names.index(
        "bundle_evidence_intake_sync"
    )


def test_build_steps_collects_s71_paid_azure_before_bundle_sync() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("bundle_evidence_packs") < step_names.index(
        "s71_paid_azure_ocr_evidence_collect"
    )
    assert step_names.index("s71_paid_azure_ocr_evidence_collect") < step_names.index(
        "bundle_operator_sheet"
    )
    assert step_names.index("s71_paid_azure_ocr_evidence_collect") < step_names.index(
        "bundle_evidence_intake_sync"
    )


def test_build_steps_generates_completion_audit_before_traceability() -> None:
    module = load_module()

    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("goal_evidence_ledger") < step_names.index("goal_completion_audit")
    assert step_names.index("goal_completion_audit") < step_names.index("goal_requirement_traceability")


def test_build_payload_counts_appended_completion_gate(tmp_path: Path) -> None:
    module = load_module()
    args = Namespace(s12_exit_code=2)
    results = [
        module.StepResult("py_compile", ["python"], 0, 0.1, str(tmp_path / "out"), str(tmp_path / "err")),
        module.StepResult("goal_completion_gate", ["python"], 0, 0.1, str(tmp_path / "out2"), str(tmp_path / "err2")),
    ]

    payload = module.build_payload(args, results)

    assert payload["overall_passed"] is True
    assert [row["name"] for row in payload["steps"]] == ["py_compile", "goal_completion_gate"]


def test_build_payload_fails_when_completion_gate_fails(tmp_path: Path) -> None:
    module = load_module()
    args = Namespace(s12_exit_code=2)
    results = [
        module.StepResult("py_compile", ["python"], 0, 0.1, str(tmp_path / "out"), str(tmp_path / "err")),
        module.StepResult("goal_completion_gate", ["python"], 1, 0.1, str(tmp_path / "out2"), str(tmp_path / "err2")),
    ]

    payload = module.build_payload(args, results)

    assert payload["overall_passed"] is False


def test_write_summary_updates_json_and_markdown_numbered_copies(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-21T12:00:00",
        "overall_passed": True,
        "s12_exit_code_input": 0,
        "safety": "read-only",
        "fixed_runner_command": "python runner.py",
        "steps": [],
    }

    module.write_summary(payload, tmp_path)

    assert (tmp_path / "safe_goal_checks_summary.json.numbered").exists()
    assert (tmp_path / "safe_goal_checks_summary.md.numbered").exists()
    assert '"overall_passed": true' in (
        tmp_path / "safe_goal_checks_summary.json.numbered"
    ).read_text(encoding="utf-8")


def test_clean_previous_step_logs_removes_only_numbered_stdout_stderr(tmp_path: Path) -> None:
    module = load_module()
    stale_stdout = tmp_path / "18_goal_unblock_board.stdout.txt"
    stale_stderr = tmp_path / "18_goal_unblock_board.stderr.txt"
    keep_summary = tmp_path / "safe_goal_checks_summary.md"
    keep_unrelated = tmp_path / "goal_unblock_board.stdout.txt"
    stale_stdout.write_text("old stdout", encoding="utf-8")
    stale_stderr.write_text("old stderr", encoding="utf-8")
    keep_summary.write_text("summary", encoding="utf-8")
    keep_unrelated.write_text("not a numbered step log", encoding="utf-8")

    removed = module.clean_previous_step_logs(tmp_path)

    assert removed == [
        "18_goal_unblock_board.stderr.txt",
        "18_goal_unblock_board.stdout.txt",
    ]
    assert not stale_stdout.exists()
    assert not stale_stderr.exists()
    assert keep_summary.exists()
    assert keep_unrelated.exists()
