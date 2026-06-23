from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
    module_path = repo_root / "tools" / "generate_goal_completion_gate_20260620_open_probe_20260622.py"
    spec = importlib.util.spec_from_file_location(
        "generate_goal_completion_gate_20260620_open_probe_20260622",
        module_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def complete_sources(tmp_path: Path) -> dict[str, Path]:
    return {
        "safe_runner": write_json(tmp_path / "safe.json", {"overall_passed": True}),
        "status_snapshot": write_json(
            tmp_path / "snapshot.json",
            {"overall_goal_complete": True, "hold_or_unconfirmed_count": 0},
        ),
        "requirement_trace": write_json(
            tmp_path / "requirements.json",
            {
                "overall_goal_complete": True,
                "complete_or_safe_count": 12,
                "requirement_count": 12,
                "missing_source_count": 0,
            },
        ),
        "packet_validation": write_json(
            tmp_path / "packet.json",
            {
                "all_packet_rows_approved": True,
                "row_count": 15,
                "approved_row_count": 15,
                "packet_row_count": 15,
                "needs_attention_count": 0,
            },
        ),
        "bundle_evidence_pack_validation": write_json(
            tmp_path / "bundle_pack_validation.json",
            {
                "prepared_pack_validation_passed": True,
                "final_evidence_complete": True,
                "final_evidence_ready_count": 6,
                "bundle_count": 6,
                "missing_prepared_pack_count": 0,
            },
        ),
        "code_artifact_backup": write_json(
            tmp_path / "code_backup.json",
            {
                "backup_complete": True,
                "artifact_count": 2,
                "missing_count": 0,
            },
        ),
        "evidence_ledger": write_json(
            tmp_path / "ledger.json",
            {
                "overall_goal_complete": True,
                "complete_goal_evidence_count": 15,
                "scenario_count": 15,
                "missing_source_count": 0,
            },
        ),
        "rks_matrix": write_json(
            tmp_path / "rks.json",
            {
                "overall_rks_production_ready": True,
                "row_count": 10,
                "runtime_intake_validation_complete": True,
                "unresolved_rks_gate_count": 0,
                "technical_unresolved_rks_gate_count": 0,
                "deferred_rks_gate_count": 0,
                "rks_technical_gate_complete": True,
                "missing_source_count": 0,
            },
        ),
        "rks_matrix_open_probe": write_json(
            tmp_path / "rks_open_probe.json",
            {
                "overall_rks_production_ready": False,
                "editor_open_probe_confirmed_count": 2,
                "rows": [
                    {
                        "editor_open_probe_status": "RK10_EDITOR_OPEN_CONFIRMED",
                        "editor_open_probe_build_artifact_found": False,
                        "editor_open_probe_button_run_clicked": False,
                    }
                ],
            },
        ),
        "rks_runtime_intake_validation": write_json(
            tmp_path / "rks_runtime_intake.json",
            {
                "overall_rks_runtime_evidence_complete": True,
                "approved_row_count": 13,
                "required_row_count": 13,
                "needs_attention_count": 0,
                "hard_error_count": 0,
                "missing_latest_log_count": 0,
            },
        ),
    }


def test_build_payload_includes_open_probe_supplement_gate(tmp_path: Path) -> None:
    module = load_module()
    payload = module.build_payload(complete_sources(tmp_path))

    assert payload["final_goal_complete"] is True
    assert payload["gate_count"] == 10
    gate = [row for row in payload["gates"] if row["gate"] == "RKS_GATE_OPEN_PROBE_SUPPLEMENT"][0]
    assert gate["passed"] is True
    assert "editor_open_probe_confirmed_count=2" in gate["detail"]
    assert "unsafe_open_probe_count=0" in gate["detail"]


def test_final_evidence_chain_completes_derived_summary_gates(tmp_path: Path) -> None:
    module = load_module()
    sources = complete_sources(tmp_path)
    write_json(
        sources["status_snapshot"],
        {
            "overall_goal_complete": False,
            "hold_or_unconfirmed_count_after_overlay": 5,
            "hold_or_unconfirmed_count_before_overlay": 7,
            "overlay_applied_count": 2,
        },
    )
    write_json(
        sources["requirement_trace"],
        {
            "overall_goal_complete": False,
            "requirement_count": 12,
            "complete_or_safe_count": 1,
            "missing_source_count": 0,
        },
    )
    write_json(
        sources["evidence_ledger"],
        {
            "overall_goal_complete": False,
            "scenario_count": 15,
            "complete_goal_evidence_count": 0,
            "missing_source_count": 0,
            "final_evidence_ready_count": 15,
        },
    )

    payload = module.build_payload(sources)

    assert payload["final_goal_complete"] is True
    for gate_name in {"STATUS_SNAPSHOT", "REQUIREMENT_TRACE", "EVIDENCE_LEDGER"}:
        gate = [row for row in payload["gates"] if row["gate"] == gate_name][0]
        assert gate["passed"] is True
        assert gate["status"] == "COMPLETE_BY_FINAL_OPERATOR_EVIDENCE"
        assert "final_evidence_chain=complete" in gate["detail"]


def test_open_probe_supplement_blocks_when_buttonrun_was_clicked(tmp_path: Path) -> None:
    module = load_module()
    sources = complete_sources(tmp_path)
    write_json(
        sources["rks_matrix_open_probe"],
        {
            "overall_rks_production_ready": False,
            "editor_open_probe_confirmed_count": 1,
            "rows": [
                {
                    "editor_open_probe_status": "RK10_EDITOR_OPEN_CONFIRMED",
                    "editor_open_probe_build_artifact_found": False,
                    "editor_open_probe_button_run_clicked": True,
                }
            ],
        },
    )

    payload = module.build_payload(sources)
    gate = [row for row in payload["gates"] if row["gate"] == "RKS_GATE_OPEN_PROBE_SUPPLEMENT"][0]

    assert payload["final_goal_complete"] is False
    assert gate["passed"] is False
    assert "unsafe_open_probe_count=1" in gate["detail"]


def test_status_snapshot_gate_uses_rks_runtime_overlay_count(tmp_path: Path) -> None:
    module = load_module()
    gate = module.build_status_snapshot_gate(
        write_json(
            tmp_path / "status_overlay.json",
            {
                "overall_goal_complete": False,
                "hold_or_unconfirmed_count_before_overlay": 7,
                "hold_or_unconfirmed_count_after_overlay": 5,
                "overlay_applied_count": 2,
            },
        )
    )

    assert gate.passed is False
    assert "hold_or_unconfirmed_count=5" in gate.detail
    assert "before_overlay=7" in gate.detail
    assert "overlay_applied_count=2" in gate.detail


def test_rks_gate_passes_when_only_deferred_rows_remain(tmp_path: Path) -> None:
    module = load_module()
    gate = module.build_rks_gate(
        write_json(
            tmp_path / "rks_deferred.json",
            {
                "overall_rks_production_ready": False,
                "row_count": 11,
                "runtime_intake_validation_complete": True,
                "unresolved_rks_gate_count": 7,
                "technical_unresolved_rks_gate_count": 0,
                "deferred_rks_gate_count": 7,
                "rks_technical_gate_complete": True,
                "missing_source_count": 0,
            },
        )
    )

    assert gate.passed is True
    assert gate.status == "COMPLETE"
    assert "overall_rks_production_ready=False" in gate.detail
    assert "technical_unresolved_rks_gate_count=0" in gate.detail
    assert "deferred_rks_gate_count=7" in gate.detail


def test_evidence_ledger_gate_reports_objective_checkpoint_counts(tmp_path: Path) -> None:
    module = load_module()
    gate = module.build_evidence_ledger_gate(
        write_json(
            tmp_path / "ledger.json",
            {
                "overall_goal_complete": False,
                "scenario_count": 2,
                "complete_goal_evidence_count": 0,
                "missing_source_count": 0,
                "final_evidence_ready_count": 1,
                "rows": [
                    {
                        "objective_checkpoint_summary": "sample=OK; safe=OK; rks=SCOPED_OK; cost=SAMPLE_OK; final=OK",
                    },
                    {
                        "objective_checkpoint_summary": "sample=OK; safe=OK; rks=PENDING; cost=COUNT_ONLY; final=PENDING",
                    },
                ],
            },
        )
    )

    assert gate.passed is False
    assert "sample_ready_count=2/2" in gate.detail
    assert "safe_execution_ready_count=2/2" in gate.detail
    assert "business_amount_or_draft_count=1/2" in gate.detail
    assert "business_count_only_scope_count=1/2" in gate.detail
    assert "business_cost_scope_count=2/2" in gate.detail
    assert "final_evidence_ready_count=1/2" in gate.detail


def test_markdown_includes_open_probe_supplement_gate(tmp_path: Path) -> None:
    module = load_module()
    markdown = module.build_markdown(module.build_payload(complete_sources(tmp_path)))

    assert "RKS_GATE_OPEN_PROBE_SUPPLEMENT" in markdown
    assert "open証跡は補助扱い" in markdown
