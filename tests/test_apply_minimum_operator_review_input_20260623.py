import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = (
        repo_root
        / "plans"
        / "reports"
        / "minimum_operator_review_input_20260623"
        / "apply_minimum_operator_review_input.py"
    )
    spec = importlib.util.spec_from_file_location(
        "apply_minimum_operator_review_input_20260623",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_apply_summary_blocks_blank_rows() -> None:
    module = load_module()
    minimum_rows = [
        {
            "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
            "scenario": "55",
            "operator_result": "",
            "reviewer": "",
            "reviewed_at": "",
        }
    ]
    row_results = [
        module.ApplyRowResult(
            "BUSINESS_DATA_APPROVAL_BUNDLE",
            "55",
            "SKIPPED",
            "",
            "NO_OPERATOR_FIELDS_FILLED",
        )
    ]

    summary = module.build_apply_summary(minimum_rows, row_results)

    assert summary["ready_to_apply"] is False
    assert summary["incomplete_input_count"] == 1
    assert summary["skipped_count"] == 1
    assert summary["blocking_result_count"] == 1


def test_build_apply_summary_allows_complete_rows() -> None:
    module = load_module()
    minimum_rows = [
        {
            "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
            "scenario": "55",
            "operator_result": "OK",
            "reviewer": "reviewer-a",
            "reviewed_at": "2026-06-23T15:35:00",
        }
    ]
    row_results = [
        module.ApplyRowResult(
            "BUSINESS_DATA_APPROVAL_BUNDLE",
            "55",
            "UPDATED",
            "operator_result,reviewer,reviewed_at",
            "",
        )
    ]

    summary = module.build_apply_summary(minimum_rows, row_results)

    assert summary["ready_to_apply"] is True
    assert summary["incomplete_input_count"] == 0
    assert summary["skipped_count"] == 0
    assert summary["blocking_result_count"] == 0


def test_build_apply_summary_allows_no_remaining_rows() -> None:
    module = load_module()

    summary = module.build_apply_summary([], [], target_row_count=0)

    assert summary["ready_to_apply"] is True
    assert summary["complete_input_count"] == 0
    assert summary["incomplete_input_count"] == 0
    assert summary["target_row_count"] == 0


def test_default_paths_follow_script_location() -> None:
    module = load_module()
    script_dir = Path(module.__file__).resolve().parent

    assert module.DEFAULT_MINIMUM_CSV == script_dir / "minimum_operator_review_input.csv"
    assert module.DEFAULT_OUT_DIR == script_dir / "apply_results"
    assert module.DEFAULT_TARGET_CSV == (
        script_dir.parent
        / "remaining_operator_input_packet_20260623"
        / "remaining_operator_input.csv"
    )


def test_run_validation_reports_missing_tool(tmp_path, monkeypatch) -> None:
    module = load_module()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(module, "VALIDATION_TOOL", tmp_path / "missing_validator.py")

    result = module.run_validation(tmp_path / "target.csv", out_dir)

    assert result["validation_exit_code"] == 2
    stderr_path = Path(str(result["validation_stderr"]))
    assert "VALIDATION_TOOL_NOT_FOUND" in stderr_path.read_text(encoding="utf-8")
