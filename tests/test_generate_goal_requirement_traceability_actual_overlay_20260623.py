import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_goal_requirement_traceability_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_goal_requirement_traceability_20260620",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_actual_trace_overlay_updates_python_and_error_requirements(
    tmp_path: Path,
) -> None:
    module = load_module()
    overlay_json = tmp_path / "goal_evidence_actual_trace_overlay.json"
    overlay_md = tmp_path / "goal_evidence_actual_trace_overlay.md.numbered"
    overlay_json.write_text(
        json.dumps(
            {
                "scenario_count": 15,
                "trace_ready_scenario_count": 15,
                "trace_missing_scenario_count": 0,
                "trace_script_missing_count": 0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    overlay_md.write_text("1: overlay\n", encoding="utf-8")
    module.GOAL_EVIDENCE_ACTUAL_TRACE_OVERLAY_JSON = overlay_json
    module.GOAL_EVIDENCE_ACTUAL_TRACE_OVERLAY = overlay_md

    rows = {row.requirement_id: row for row in module.build_rows()}

    for requirement_id in ("REQ-02", "REQ-05"):
        assert rows[requirement_id].authoritative_evidence == str(overlay_md)
        assert "15/15シナリオ接続済み" in rows[requirement_id].remaining_gap
        assert "trace_script_missing_count=0" in rows[requirement_id].remaining_gap
