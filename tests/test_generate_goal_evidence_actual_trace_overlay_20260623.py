from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "generate_goal_evidence_actual_trace_overlay_20260623.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "generate_goal_evidence_actual_trace_overlay_20260623",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_trace_by_scenario_groups_multiple_entries() -> None:
    module = load_module()
    trace_payload = {
        "actual_execution_trace_rows": [
            {
                "scenario": "70",
                "expected_ok": "YES",
                "bat_exists": "YES",
                "ps1_entry_resolved": "YES",
                "stdout_exists": "YES",
                "stderr_exists": "YES",
                "script_missing_count": 0,
            },
            {
                "scenario": "70",
                "expected_ok": "YES",
                "bat_exists": "YES",
                "ps1_entry_resolved": "YES",
                "stdout_exists": "YES",
                "stderr_exists": "YES",
                "script_missing_count": 0,
            },
        ]
    }

    summaries = module.build_trace_by_scenario(trace_payload)

    assert summaries["70"].status == "SAFE_ENTRY_TRACE_OK"
    assert summaries["70"].entry_count == 2
    assert summaries["70"].expected_ok_count == 2
    assert summaries["70"].script_missing_count == 0


def test_build_overlay_rows_preserves_incomplete_goal_boundary(tmp_path: Path) -> None:
    module = load_module()
    trace_markdown = tmp_path / "trace.md.numbered"
    trace_markdown.write_text("1: trace\n", encoding="utf-8")
    ledger_payload = {
        "rows": [
            {
                "scenario": "55",
                "current_status": "V2_DRYRUN_ERRORS_0_OVERFLOW_0",
                "evidence_strength": "PARTIAL_EVIDENCE",
                "objective_checkpoint_summary": "sample=OK; safe=OK; rks=SCOPED_OK; cost=SAMPLE_OK; final=PENDING",
                "missing_objective_proofs": "operator final evidence and approval record",
            }
        ]
    }
    trace_payload = {
        "actual_execution_trace_rows": [
            {
                "scenario": "55",
                "expected_ok": "YES",
                "bat_exists": "YES",
                "ps1_entry_resolved": "YES",
                "stdout_exists": "YES",
                "stderr_exists": "YES",
                "script_missing_count": 0,
            }
        ]
    }

    rows = module.build_overlay_rows(ledger_payload, trace_payload, trace_markdown)

    assert len(rows) == 1
    assert rows[0].scenario == "55"
    assert rows[0].actual_trace_status == "SAFE_ENTRY_TRACE_OK"
    assert rows[0].production_completion_scope == "SAFE_TRACE_ONLY_NOT_PRODUCTION_COMPLETE"
    assert "operator final evidence" in rows[0].missing_objective_proofs
    assert rows[0].actual_trace_evidence_exists is True


def test_build_markdown_states_primary_sources_and_boundary(tmp_path: Path) -> None:
    module = load_module()
    ledger_path = tmp_path / "ledger.json"
    trace_path = tmp_path / "trace.json"
    trace_markdown = tmp_path / "trace.md.numbered"
    ledger_path.write_text(
        '{"rows":[{"scenario":"12/13","current_status":"READY","evidence_strength":"PARTIAL_EVIDENCE"}]}',
        encoding="utf-8",
    )
    trace_path.write_text(
        '{"actual_execution_trace_rows":[{"scenario":"12/13","expected_ok":"YES","bat_exists":"YES","ps1_entry_resolved":"YES","stdout_exists":"YES","stderr_exists":"YES","script_missing_count":0}]}',
        encoding="utf-8",
    )
    trace_markdown.write_text("1: trace\n", encoding="utf-8")

    payload = module.build_payload(ledger_path, trace_path, trace_markdown)
    markdown = module.build_markdown(payload)

    assert payload["trace_ready_scenario_count"] == 1
    assert payload["trace_script_missing_count"] == 0
    assert "## Primary Source" in markdown
    assert "SAFE_TRACE_ONLY_NOT_PRODUCTION_COMPLETE" in markdown
    assert "does not close human/external production gates" in markdown
