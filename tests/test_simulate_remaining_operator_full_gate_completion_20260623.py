import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "simulate_remaining_operator_full_gate_completion_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "simulate_remaining_operator_full_gate_completion_20260623",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_replace_bundle_pack_root_text_rewrites_only_pack_root(tmp_path: Path) -> None:
    module = load_module()
    work_pack_root = tmp_path / "work" / "bundle_evidence_packs_20260620"
    source_pack_root = str(module.SOURCE_PACK_ROOT)
    text = (
        f"{source_pack_root}\\business_review_bundle\\final_evidence / "
        r"C:\ProgramData\RK10\Robots\migration\reports\s44\report.md.numbered"
    )

    replaced = module.replace_bundle_pack_root_text(text, work_pack_root)

    assert str(work_pack_root) in replaced
    assert source_pack_root not in replaced
    assert r"C:\ProgramData\RK10\Robots\migration\reports\s44\report.md.numbered" in replaced


def test_replace_bundle_pack_root_text_rewrites_json_escaped_pack_root(
    tmp_path: Path,
) -> None:
    module = load_module()
    work_pack_root = tmp_path / "work" / "bundle_evidence_packs_20260620"
    source_pack_root = str(module.SOURCE_PACK_ROOT).replace("\\", "\\\\")
    text = (
        f'{{"intake_path": "{source_pack_root}\\\\business_review_bundle'
        '\\\\final_evidence_intake.csv"}}'
    )

    replaced = module.replace_bundle_pack_root_text(text, work_pack_root)

    assert str(work_pack_root).replace("\\", "\\\\") in replaced
    assert source_pack_root not in replaced


def test_write_outputs_creates_json_markdown_and_numbered(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-23T05:40:00",
        "full_chain_simulation_passed": True,
        "source_files_modified": False,
        "production_completion_scope": "SIMULATION_ONLY_NOT_ACTUAL_APPROVAL",
        "operator_completion_passed": True,
        "unified_updated_intake_count": 5,
        "bundle_ready_to_sync_count": 6,
        "bundle_count": 6,
        "bundle_final_evidence_ready_count": 6,
        "simulated_gate_final_goal_complete": False,
        "simulated_gate_passed_count": 7,
        "simulated_gate_count": 10,
        "simulated_blocking_gate_count": 3,
        "simulated_blocking_gates": ["STATUS_SNAPSHOT"],
        "operator_completion_report": r"C:\operator.md.numbered",
        "unified_sync_report": r"C:\unified.md.numbered",
        "bundle_sync_report": r"C:\bundle_sync.md.numbered",
        "bundle_validation_report": r"C:\bundle_validation.md.numbered",
        "simulated_gate_report": r"C:\gate.md.numbered",
    }

    module.write_outputs(payload, tmp_path)

    written_json = json.loads(
        (tmp_path / "remaining_operator_full_gate_simulation.json").read_text(
            encoding="utf-8",
        )
    )
    markdown = (tmp_path / "remaining_operator_full_gate_simulation.md").read_text(
        encoding="utf-8",
    )

    assert written_json["full_chain_simulation_passed"] is True
    assert "SIMULATION_ONLY_NOT_ACTUAL_APPROVAL" in markdown
    assert "STATUS_SNAPSHOT" in markdown
    assert (
        tmp_path / "remaining_operator_full_gate_simulation.md.numbered"
    ).exists()
