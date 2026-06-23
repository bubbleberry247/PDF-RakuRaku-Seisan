import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_goal_status_snapshot_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_goal_status_snapshot_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_scenario_records_source_existence(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")

    result = module.scenario(
        "55",
        "dry-run",
        "V2_DRYRUN_ERRORS_0_OVERFLOW_0",
        "production payment-day gate",
        "confirm payment-day inputs",
        str(source),
    )

    assert result.source_exists is True
    assert result.scenario == "55"


def test_build_payload_counts_hold_unconfirmed_and_missing_sources(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    present = tmp_path / "present.txt"
    missing = tmp_path / "missing.txt"
    present.write_text("evidence", encoding="utf-8")

    gate_scenarios = [
        module.ScenarioSnapshot(
            scenario="44",
            current_scope="gate",
            current_status="HOLD_NO_CONFIRMED_ROWS",
            remaining_gate="0 OK rows",
            next_action="fill spot check",
            source=str(present),
            source_exists=True,
        ),
        module.ScenarioSnapshot(
            scenario="12/13",
            current_scope="gate",
            current_status="READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
            remaining_gate="COM ok",
            next_action="dry-run only",
            source=str(present),
            source_exists=True,
        ),
    ]
    static_scenarios = [
        module.ScenarioSnapshot(
            scenario="55",
            current_scope="dry-run",
            current_status="V2_DRYRUN_ERRORS_0_OVERFLOW_0",
            remaining_gate="production execution separate",
            next_action="confirm inputs",
            source=str(present),
            source_exists=True,
        ),
        module.ScenarioSnapshot(
            scenario="58",
            current_scope="safe sample",
            current_status="SAFE_SAMPLE_OK_RKS_UNCONFIRMED",
            remaining_gate="runtime log",
            next_action="safe-stop rerun",
            source=str(missing),
            source_exists=False,
        ),
    ]

    monkeypatch.setattr(module, "build_gate_scenarios", lambda _exit_code: gate_scenarios)
    monkeypatch.setattr(module, "build_static_scenarios", lambda: static_scenarios)

    payload = module.build_payload(0)

    assert payload["overall_goal_complete"] is False
    assert payload["scenario_count"] == 4
    assert payload["hold_or_unconfirmed_count"] == 2
    assert payload["missing_source_count"] == 1
    assert payload["supplemental_evidence_count"] == 0


def test_build_markdown_includes_matrix_and_sources() -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "overall_goal_complete": False,
        "safety": "read-only evidence snapshot only",
        "scenario_count": 1,
        "hold_or_unconfirmed_count": 1,
        "missing_source_count": 0,
        "supplemental_evidence_count": 0,
        "scenarios": [
            {
                "scenario": "70",
                "current_status": "HOLD_PAYMENT_EXECUTE_NOT_ALLOWED",
                "remaining_gate": "approval missing",
                "next_action": "confirm-preview only",
                "source": r"C:\evidence\s70.csv",
                "source_exists": True,
                "supplemental_evidence": "",
                "supplemental_evidence_exists": False,
            }
        ],
    }

    markdown = module.build_markdown(payload)

    assert "# 全シナリオ現況スナップショット 2026-06-20" in markdown
    assert "| 70 | HOLD_PAYMENT_EXECUTE_NOT_ALLOWED | approval missing | confirm-preview only | YES | NO |" in markdown
    assert r"C:\evidence\s70.csv" in markdown
