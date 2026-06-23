import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_goal_status_snapshot_rks_runtime_overlay_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_goal_status_snapshot_rks_runtime_overlay_20260623",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_overlay_scenario_updates_stale_rks_missing_status(tmp_path: Path) -> None:
    module = load_module()
    runtime_report = tmp_path / "rks_runtime.md.numbered"
    source = tmp_path / "old_source.md.numbered"
    runtime_report.write_text("runtime evidence", encoding="utf-8")
    source.write_text("old evidence", encoding="utf-8")
    scenario_row = {
        "scenario": "57",
        "current_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
        "current_scope": "old scope",
        "remaining_gate": "safe-stop clean log",
        "next_action": "rerun",
        "source": str(source),
        "source_exists": True,
    }
    runtime_rows = {
        "57": {
            "latest_log_path": r"C:\evidence\s57_status_gate.txt",
            "operator_name": "codex_safe_dryrun",
            "checked_at": "2026-06-22T20:03:06",
        }
    }

    overlaid = module.overlay_scenario(scenario_row, runtime_rows, runtime_report)

    assert overlaid["overlay_applied"] is True
    assert overlaid["current_status"] == "RKS_SAFE_STOP_CONFIRMED_SCOPE_ONLY"
    assert overlaid["source"] == str(runtime_report)
    assert overlaid["supplemental_evidence"] == str(source)


def test_build_payload_reduces_hold_count_for_confirmed_runtime(tmp_path: Path) -> None:
    module = load_module()
    status_json = tmp_path / "goal_status_snapshot.json"
    runtime_json = tmp_path / "rks_runtime.json"
    runtime_report = tmp_path / "rks_runtime.md.numbered"
    old_source = tmp_path / "old_source.md.numbered"
    runtime_report.write_text("runtime evidence", encoding="utf-8")
    old_source.write_text("old evidence", encoding="utf-8")
    status_json.write_text(
        json.dumps(
            {
                "hold_or_unconfirmed_count": 2,
                "scenarios": [
                    {
                        "scenario": "57",
                        "current_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
                        "current_scope": "old scope",
                        "remaining_gate": "safe-stop clean log",
                        "next_action": "rerun",
                        "source": str(old_source),
                        "source_exists": True,
                    },
                    {
                        "scenario": "44",
                        "current_status": "HOLD_NO_CONFIRMED_ROWS",
                        "current_scope": "hold",
                        "remaining_gate": "0 OK",
                        "next_action": "review",
                        "source": str(old_source),
                        "source_exists": True,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    runtime_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "scenario": "57",
                        "approved": True,
                        "rk10_editor_open": "CONFIRMED",
                        "rk10_build": "CONFIRMED",
                        "runtime_or_safe_stop": "CONFIRMED",
                        "latest_log_clean": "YES",
                        "latest_log_path_exists": True,
                        "latest_log_has_hard_errors": False,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = module.build_payload(status_json, runtime_json, runtime_report)

    assert payload["overlay_applied_count"] == 1
    assert payload["overlay_scenarios"] == ["57"]
    assert payload["hold_or_unconfirmed_count_before_overlay"] == 2
    assert payload["hold_or_unconfirmed_count_after_overlay"] == 1


def test_write_outputs_creates_numbered_reports(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-23T06:00:00",
        "overall_goal_complete": False,
        "safety": "read-only overlay only",
        "source_status_json": r"C:\status.json",
        "rks_runtime_json": r"C:\rks_runtime.json",
        "rks_runtime_report": r"C:\rks_runtime.md.numbered",
        "scenario_count": 1,
        "hold_or_unconfirmed_count_before_overlay": 1,
        "hold_or_unconfirmed_count_after_overlay": 0,
        "overlay_applied_count": 1,
        "overlay_scenarios": ["57"],
        "missing_source_count": 0,
        "scenarios": [
            {
                "scenario": "57",
                "overlay_applied": True,
                "current_status": "RKS_SAFE_STOP_CONFIRMED_SCOPE_ONLY",
                "remaining_gate": "operator final evidence",
                "source_exists": True,
            }
        ],
    }

    module.write_outputs(payload, tmp_path)

    assert (tmp_path / "goal_status_snapshot_rks_runtime_overlay.json.numbered").exists()
    assert (tmp_path / "goal_status_snapshot_rks_runtime_overlay.md.numbered").exists()
