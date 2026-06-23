import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_goal_completion_audit_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_goal_completion_audit_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def build_sources(tmp_path: Path) -> dict[str, Path]:
    return {
        "status_snapshot": write_json(
            tmp_path / "status.json",
            {
                "overall_goal_complete": False,
                "scenario_count": 2,
                "hold_or_unconfirmed_count": 1,
                "scenarios": [
                    {
                        "scenario": "12/13",
                        "current_status": "HOLD_OUTLOOK_COM_NOT_READY",
                        "remaining_gate": "latest --check-outlook-com exit_code=2",
                        "next_action": "Recover Classic Outlook COM.",
                        "source": r"C:\tool.py",
                        "source_exists": True,
                    },
                    {
                        "scenario": "55",
                        "current_status": "PYTHON_SAMPLE_OK_RKS_SAFE_STOP_SCOPE_ONLY",
                        "remaining_gate": "operator final evidence",
                        "next_action": "Attach final evidence.",
                        "source": r"C:\s55.md",
                        "source_exists": True,
                    },
                ],
            },
        ),
        "evidence_ledger": write_json(
            tmp_path / "ledger.json",
            {
                "overall_goal_complete": False,
                "scenario_count": 2,
                "complete_goal_evidence_count": 0,
            },
        ),
        "packet_validation": write_json(
            tmp_path / "packet.json",
            {"approved_row_count": 0, "needs_attention_count": 2},
        ),
        "bundle_evidence_pack_validation": write_json(
            tmp_path / "bundle.json",
            {"bundle_count": 1, "final_evidence_ready_count": 0},
        ),
        "rks_matrix": write_json(
            tmp_path / "rks.json",
            {"unresolved_rks_gate_count": 1},
        ),
        "rks_runtime_intake_validation": write_json(
            tmp_path / "rks_runtime.json",
            {
                "approved_row_count": 0,
                "required_row_count": 1,
                "hard_error_count": 0,
            },
        ),
        "business_cost_map": write_json(
            tmp_path / "cost.json",
            {
                "rows": [
                    {"scenario": "55", "validation_result": "PASS"},
                    {"scenario": "12/13", "validation_result": "HOLD"},
                ]
            },
        ),
        "code_artifact_backup": write_json(
            tmp_path / "backup.json",
            {
                "backup_complete": True,
                "artifact_count": 3,
                "missing_count": 0,
            },
        ),
    }


def test_build_payload_classifies_current_issues(tmp_path: Path) -> None:
    module = load_module()
    sources = build_sources(tmp_path)

    payload = module.build_payload(sources)

    assert payload["report_status"] == "CURRENT_AUDIT_NOT_FINAL"
    assert payload["overall_goal_complete"] is False
    assert payload["scenario_count"] == 2
    assert payload["issue_count"] == 2
    assert payload["validation_summary"]["amount_verified_scenario_count"] == 1
    assert payload["validation_summary"]["code_backup_complete"] is True
    assert payload["issues"][0]["root_cause_class"] == "OUTLOOK_COM_ENVIRONMENT_HOLD"


def test_build_markdown_includes_strict_boundaries(tmp_path: Path) -> None:
    module = load_module()
    payload = module.build_payload(build_sources(tmp_path))

    markdown = module.build_markdown(payload)

    assert "CURRENT_AUDIT_NOT_FINAL" in markdown
    assert "OK_CANDIDATE" in markdown
    assert "OUTLOOK_COM_ENVIRONMENT_HOLD" in markdown
    assert "No Outlook, RK10" in markdown


def test_write_outputs_creates_numbered_and_issue_csv(tmp_path: Path) -> None:
    module = load_module()
    payload = module.build_payload(build_sources(tmp_path))

    outputs = module.write_outputs(payload, tmp_path)

    assert Path(outputs["json"]).exists()
    assert Path(outputs["markdown"]).exists()
    assert Path(outputs["issues_csv"]).exists()
    assert Path(outputs["json"] + ".numbered").exists()
    assert Path(outputs["markdown"] + ".numbered").exists()
    with Path(outputs["issues_csv"]).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["scenario"] == "12/13"
    assert rows[0]["root_cause_class"] == "OUTLOOK_COM_ENVIRONMENT_HOLD"
