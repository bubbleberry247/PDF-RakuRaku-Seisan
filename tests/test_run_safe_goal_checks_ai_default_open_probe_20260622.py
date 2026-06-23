from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
    module_path = repo_root / "tools" / "run_safe_goal_checks_20260620_ai_default_probe_20260622.py"
    spec = importlib.util.spec_from_file_location(
        "run_safe_goal_checks_20260620_ai_default_probe_20260622",
        module_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_steps_runs_open_probe_matrix_after_standard_matrix() -> None:
    module = load_module()
    step_names = [name for name, _command in module.build_steps(2)]

    assert "rks_gate_matrix_open_probe" in step_names
    assert step_names.index("rks_runtime_intake_validation") < step_names.index("rks_gate_matrix")
    assert step_names.index("rks_gate_matrix") < step_names.index("rks_gate_matrix_open_probe")
    assert step_names.index("rks_gate_matrix_open_probe") < step_names.index("sample_data_evidence_map")


def test_py_compile_and_pytest_include_open_probe_artifacts() -> None:
    module = load_module()
    steps = dict(module.build_steps(2))
    py_compile_command = "\n".join(steps["py_compile"])
    pytest_command = "\n".join(steps["pytest"])

    assert "generate_rks_gate_matrix_20260620_open_probe_20260622.py" in py_compile_command
    assert "generate_goal_completion_gate_20260620_open_probe_20260622.py" in py_compile_command
    assert "generate_completion_blocker_split_20260622.py" in py_compile_command
    assert "generate_customer_safe_entries_full_smoke_report_20260622.py" in py_compile_command
    assert "generate_goal_evidence_actual_trace_overlay_20260623.py" in py_compile_command
    assert "test_generate_rks_gate_matrix_open_probe_20260622.py" in pytest_command
    assert "test_generate_goal_completion_gate_open_probe_20260622.py" in pytest_command
    assert "test_generate_completion_blocker_split_20260622.py" in pytest_command
    assert "test_generate_customer_safe_entries_full_smoke_report_20260622.py" in pytest_command
    assert "test_generate_goal_evidence_actual_trace_overlay_20260623.py" in pytest_command
    assert (
        "test_generate_goal_requirement_traceability_actual_overlay_20260623.py"
        in pytest_command
    )
    assert (
        "test_generate_goal_requirement_traceability_rks_gate_alignment_20260623.py"
        in pytest_command
    )
    assert "test_rk10_license_default_ok_policy_20260622.py" in pytest_command
    assert "test_final_evidence_fill_queue_open_probe_20260622.py" in pytest_command


def test_open_probe_step_writes_to_dedicated_report_dir() -> None:
    module = load_module()
    steps = dict(module.build_steps(2))
    command = steps["rks_gate_matrix_open_probe"]

    assert "--out-dir" in command
    out_dir = command[command.index("--out-dir") + 1]
    assert out_dir.endswith(r"plans\reports\rks_gate_matrix_open_probe_20260622")


def test_completion_gate_uses_open_probe_aware_candidate() -> None:
    module = load_module()
    steps = dict(module.build_steps(2))
    command = steps["goal_completion_gate"]

    assert "generate_goal_completion_gate_20260620_open_probe_20260622.py" in "\n".join(command)


def test_customer_safe_matrix_runs_before_goal_ledger() -> None:
    module = load_module()
    step_names = [name for name, _command in module.build_steps(2)]

    assert step_names.index("customer_safe_scenario_matrix") < step_names.index(
        "goal_evidence_ledger"
    )
    assert step_names.index("goal_evidence_ledger") < step_names.index(
        "goal_evidence_actual_trace_overlay"
    )
    assert step_names.index("goal_evidence_actual_trace_overlay") < step_names.index(
        "goal_completion_audit"
    )
