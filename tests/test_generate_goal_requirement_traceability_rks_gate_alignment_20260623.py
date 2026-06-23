from __future__ import annotations

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
        "generate_goal_requirement_traceability_20260620_rks_gate_alignment",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_rks_requirement_separates_technical_gate_from_production_gate(
    tmp_path: Path,
) -> None:
    module = load_module()
    rks_matrix_json = tmp_path / "rks_gate_matrix.json"
    rks_matrix_md = tmp_path / "rks_gate_matrix.md.numbered"
    rks_matrix_json.write_text(
        json.dumps(
            {
                "rks_technical_gate_complete": True,
                "technical_unresolved_rks_gate_count": 0,
                "overall_rks_production_ready": False,
                "deferred_rks_gate_count": 7,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rks_matrix_md.write_text("1: rks gate matrix\n", encoding="utf-8")
    module.RKS_GATE_MATRIX_JSON = rks_matrix_json
    module.RKS_GATE_MATRIX = rks_matrix_md

    rows = {row.requirement_id: row for row in module.build_rows()}
    rks_row = rows["REQ-03"]

    assert rks_row.current_status == "NOT_PROVEN"
    assert rks_row.authoritative_evidence == str(rks_matrix_md)
    assert "rks_technical_gate_complete=True" in rks_row.remaining_gap
    assert "technical_unresolved_rks_gate_count=0" in rks_row.remaining_gap
    assert "overall_rks_production_ready=False" in rks_row.remaining_gap
    assert "deferred_rks_gate_count=7" in rks_row.remaining_gap
    assert "full production scope" in rks_row.remaining_gap
    assert "RK10 open/build" in rks_row.next_evidence_needed
    assert "safe-stop/runtime" in rks_row.next_evidence_needed
