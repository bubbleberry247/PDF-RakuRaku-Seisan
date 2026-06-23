import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_goal_completion_gate_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_goal_completion_gate_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
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
                "requirement_count": 12,
                "complete_or_safe_count": 12,
                "missing_source_count": 0,
            },
        ),
        "packet_validation": write_json(
            tmp_path / "packet.json",
            {
                "all_packet_rows_approved": True,
                "row_count": 15,
                "approved_row_count": 15,
                "needs_attention_count": 0,
            },
        ),
        "bundle_evidence_pack_validation": write_json(
            tmp_path / "bundle_pack_validation.json",
            {
                "prepared_pack_validation_passed": True,
                "final_evidence_complete": True,
                "bundle_count": 6,
                "final_evidence_ready_count": 6,
                "missing_prepared_pack_count": 0,
            },
        ),
        "code_artifact_backup": write_json(
            tmp_path / "code_backup.json",
            {
                "backup_complete": True,
                "artifact_count": 48,
                "missing_count": 0,
            },
        ),
        "evidence_ledger": write_json(
            tmp_path / "ledger.json",
            {
                "overall_goal_complete": True,
                "scenario_count": 15,
                "complete_goal_evidence_count": 15,
                "missing_source_count": 0,
            },
        ),
        "rks_matrix": write_json(
            tmp_path / "rks.json",
            {
                "overall_rks_production_ready": True,
                "row_count": 11,
                "unresolved_rks_gate_count": 0,
                "technical_unresolved_rks_gate_count": 0,
                "deferred_rks_gate_count": 0,
                "rks_technical_gate_complete": True,
                "missing_source_count": 0,
            },
        ),
        "rks_runtime_intake_validation": write_json(
            tmp_path / "rks_runtime_intake.json",
            {
                "overall_rks_runtime_evidence_complete": True,
                "required_row_count": 13,
                "approved_row_count": 13,
                "needs_attention_count": 0,
                "hard_error_count": 0,
                "missing_latest_log_count": 0,
            },
        ),
    }


def test_build_payload_marks_complete_when_all_gates_pass(tmp_path: Path) -> None:
    module = load_module()

    payload = module.build_payload(complete_sources(tmp_path))

    assert payload["final_goal_complete"] is True
    assert payload["passed_gate_count"] == 9
    assert payload["blocking_gate_count"] == 0


def test_final_evidence_chain_completes_derived_summary_gates(tmp_path: Path) -> None:
    module = load_module()
    sources = complete_sources(tmp_path)
    write_json(
        sources["status_snapshot"],
        {
            "overall_goal_complete": False,
            "hold_or_unconfirmed_count": 5,
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


def test_build_payload_blocks_when_packet_rows_are_unapproved(tmp_path: Path) -> None:
    module = load_module()
    sources = complete_sources(tmp_path)
    write_json(
        sources["packet_validation"],
        {
            "all_packet_rows_approved": False,
            "row_count": 15,
            "approved_row_count": 14,
            "needs_attention_count": 1,
        },
    )

    payload = module.build_payload(sources)

    assert payload["final_goal_complete"] is False
    assert payload["blocking_gate_count"] == 1
    packet_gate = [gate for gate in payload["gates"] if gate["gate"] == "EXECUTION_PACKET_VALIDATION"][0]
    assert packet_gate["passed"] is False
    assert "needs_attention_count=1" in packet_gate["detail"]
    assert "remaining_operator_input.csv" in packet_gate["next_action"]
    assert "operator_result/reviewer/reviewed_at" in packet_gate["next_action"]


def test_build_payload_blocks_when_bundle_final_evidence_is_missing(tmp_path: Path) -> None:
    module = load_module()
    sources = complete_sources(tmp_path)
    write_json(
        sources["bundle_evidence_pack_validation"],
        {
            "prepared_pack_validation_passed": True,
            "final_evidence_complete": False,
            "bundle_count": 6,
            "final_evidence_ready_count": 5,
            "missing_prepared_pack_count": 0,
        },
    )

    payload = module.build_payload(sources)

    assert payload["final_goal_complete"] is False
    assert payload["blocking_gate_count"] == 1
    bundle_gate = [gate for gate in payload["gates"] if gate["gate"] == "BUNDLE_EVIDENCE_PACK_VALIDATION"][0]
    assert bundle_gate["passed"] is False
    assert "final_evidence_ready_count=5/6" in bundle_gate["detail"]
    assert "remaining_operator_input.csv" in bundle_gate["next_action"]


def test_build_payload_blocks_missing_source(tmp_path: Path) -> None:
    module = load_module()
    sources = complete_sources(tmp_path)
    sources["rks_matrix"] = tmp_path / "missing_rks.json"

    payload = module.build_payload(sources)

    assert payload["final_goal_complete"] is False
    assert payload["blocking_gate_count"] == 1
    rks_gate = [gate for gate in payload["gates"] if gate["gate"] == "RKS_GATE_MATRIX"][0]
    assert rks_gate["status"] == "MISSING_SOURCE"


def test_build_payload_blocks_when_code_backup_is_incomplete(tmp_path: Path) -> None:
    module = load_module()
    sources = complete_sources(tmp_path)
    write_json(
        sources["code_artifact_backup"],
        {
            "backup_complete": False,
            "artifact_count": 48,
            "missing_count": 1,
        },
    )

    payload = module.build_payload(sources)

    assert payload["final_goal_complete"] is False
    assert payload["blocking_gate_count"] == 1
    backup_gate = [gate for gate in payload["gates"] if gate["gate"] == "CODE_ARTIFACT_BACKUP"][0]
    assert backup_gate["passed"] is False
    assert "missing_count=1" in backup_gate["detail"]
    assert "別名保存" in backup_gate["next_action"]


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


def test_build_payload_blocks_when_rks_runtime_intake_is_incomplete(tmp_path: Path) -> None:
    module = load_module()
    sources = complete_sources(tmp_path)
    write_json(
        sources["rks_runtime_intake_validation"],
        {
            "overall_rks_runtime_evidence_complete": False,
            "required_row_count": 13,
            "approved_row_count": 12,
            "needs_attention_count": 1,
            "hard_error_count": 0,
            "missing_latest_log_count": 1,
        },
    )

    payload = module.build_payload(sources)

    assert payload["final_goal_complete"] is False
    assert payload["blocking_gate_count"] == 1
    rks_runtime_gate = [
        gate for gate in payload["gates"] if gate["gate"] == "RKS_RUNTIME_INTAKE_VALIDATION"
    ][0]
    assert rks_runtime_gate["passed"] is False
    assert "approved_row_count=12/13" in rks_runtime_gate["detail"]
    assert "latest clean log" in rks_runtime_gate["next_action"]


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


def test_build_markdown_includes_gate_matrix(tmp_path: Path) -> None:
    module = load_module()
    payload = module.build_payload(complete_sources(tmp_path))

    markdown = module.build_markdown(payload)

    assert "# 目標最終完了ゲート 2026-06-20" in markdown
    assert "final_goal_complete" in markdown
    assert "BUNDLE_EVIDENCE_PACK_VALIDATION" in markdown
    assert "CODE_ARTIFACT_BACKUP" in markdown
    assert "RKS_GATE_MATRIX" in markdown
    assert "RKS_RUNTIME_INTAKE_VALIDATION" in markdown
