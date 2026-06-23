import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_final_evidence_fill_queue_20260621.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_final_evidence_fill_queue_20260621",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_hides_stale_gate_pending_when_rks_runtime_intake_is_complete(
    tmp_path: Path,
) -> None:
    module = load_module()
    bundle_validation_path = tmp_path / "bundle_validation.json"
    execution_validation_path = tmp_path / "execution_validation.json"
    remaining_path = tmp_path / "remaining.json"
    rk10_collect_path = tmp_path / "rk10_collect.json"
    rks_validation_path = tmp_path / "rks_validation.json"
    rks_gate_matrix_path = tmp_path / "rks_gate_matrix.json"
    bundle_sync_path = tmp_path / "bundle_sync.json"

    write_json(
        bundle_validation_path,
        {
            "checks": [
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "scenarios": "38, 42, 57, 58",
                    "final_evidence_ready": False,
                    "operator_fields_complete": False,
                    "final_evidence_has_content": True,
                }
            ]
        },
    )
    write_json(
        execution_validation_path,
        {
            "rows": [
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "scenario": "38",
                    "approved": False,
                    "status": "MISSING_OPERATOR_FIELDS",
                    "missing_fields": "operator_result",
                    "csv_path": str(tmp_path / "rk10_editor_runtime_bundle.csv"),
                }
            ]
        },
    )
    write_json(
        remaining_path,
        {
            "rows": [
                {
                    "rank": 6,
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "owner": "RK10操作担当者",
                    "scenarios": "38, 42, 57, 58",
                    "active": True,
                    "after_action_command": "python fixed_runner.py",
                    "start_here_path": str(tmp_path / "rk10_START_HERE.md"),
                }
            ]
        },
    )
    write_json(
        rks_validation_path,
        {
            "overall_rks_runtime_evidence_complete": True,
            "required_row_count": 2,
            "approved_row_count": 2,
            "needs_attention_count": 0,
            "hard_error_count": 0,
            "missing_latest_log_count": 0,
            "rows": [
                {
                    "scenario": "57",
                    "requires_rk10_evidence": True,
                    "approved": True,
                    "issue_codes": "",
                },
                {
                    "scenario": "58",
                    "requires_rk10_evidence": True,
                    "approved": True,
                    "issue_codes": "",
                },
            ],
        },
    )
    write_json(
        rks_gate_matrix_path,
        {
            "rows": [
                {
                    "scenario": "38",
                    "current_rks_status": "PRIMARY_RKS_EDITOR_OPEN_NG",
                    "missing_gate": "stale open probe should not be reported",
                },
                {
                    "scenario": "57",
                    "current_rks_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
                    "missing_gate": "stale runtime log gap",
                },
            ]
        },
    )
    write_json(
        rk10_collect_path,
        {
            "status": "READY_FOR_REVIEWER_TIMESTAMP",
            "validation_json": str(rks_validation_path),
            "approved_validator_count": 2,
            "appended_intake_row_count": 0,
            "collected_count": 2,
            "skipped_count": 0,
            "scenarios": [
                {"scenario": "57", "status": "READY_FOR_REVIEWER_TIMESTAMP"},
                {"scenario": "58", "status": "READY_FOR_REVIEWER_TIMESTAMP"},
            ],
        },
    )
    write_json(
        bundle_sync_path,
        {
            "results": [
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "intake_path": str(tmp_path / "rk10_editor_runtime_bundle_intake.csv"),
                    "ready_to_sync": False,
                    "blockers": "OPERATOR_RESULT_BLANK",
                    "rows": [
                        {
                            "scenario": "38",
                            "status": "BLOCKED",
                            "blockers": "OPERATOR_RESULT_BLANK",
                        }
                    ],
                }
            ]
        },
    )

    payload = module.build_payload(
        bundle_validation_path,
        execution_validation_path,
        remaining_path,
        rk10_collect_path,
        rks_gate_matrix_path,
        bundle_sync_path,
    )

    rk10_row = payload["rows"][0]
    assert "rks_runtime_intake=COMPLETE" in rk10_row["supplemental_evidence_status"]
    assert rk10_row["remaining_runtime_evidence"] == ""
    assert "PRIMARY_RKS_EDITOR_OPEN_NG" not in rk10_row["remaining_runtime_evidence"]
    assert "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING" not in rk10_row["remaining_runtime_evidence"]
