import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_objective_completion_audit_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_objective_completion_audit_20260623",
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


def configure_sources(module, tmp_path: Path) -> dict[str, Path]:
    paths = {
        "ledger": tmp_path / "ledger.json",
        "gate": tmp_path / "gate.json",
        "safe": tmp_path / "safe.json",
        "ready": tmp_path / "ready.json",
        "backup": tmp_path / "backup.json",
        "sync": tmp_path / "sync.json",
        "final_sync": tmp_path / "final_sync.json",
        "distribution": tmp_path / "distribution.json",
        "scope": tmp_path / "scope.json",
    }
    module.GOAL_EVIDENCE_LEDGER_JSON = paths["ledger"]
    module.GOAL_COMPLETION_GATE_JSON = paths["gate"]
    module.SAFE_GOAL_CHECKS_JSON = paths["safe"]
    module.REMAINING_OPERATOR_READY_JSON = paths["ready"]
    module.GOAL_CODE_BACKUP_JSON = paths["backup"]
    module.SYNC_MANIFEST_JSON = paths["sync"]
    module.FINAL_FRONT_DOOR_SYNC_MANIFEST_JSON = paths["final_sync"]
    module.FINAL_FRONT_DOOR_DISTRIBUTION_CHECK_JSON = paths["distribution"]
    module.SCOPE_EXCLUSIONS_JSON = paths["scope"]
    return paths


def test_build_payload_marks_current_partial_and_blocked_requirements(
    tmp_path: Path,
) -> None:
    module = load_module()
    paths = configure_sources(module, tmp_path)
    write_json(
        paths["ledger"],
        {
            "scenario_count": 2,
            "rows": [
                {
                    "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                    "safe_execution_status": "SAFE_SUITE_EXIT0_STDERR0",
                    "business_cost_status": "AMOUNT_DRYRUN_RECALCULATED",
                    "rks_runtime_intake_status": "RKS_TECHNICAL_GATE_COMPLETE",
                    "final_evidence_ready": True,
                },
                {
                    "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                    "safe_execution_status": "SAFE_SUITE_EXIT0_STDERR0",
                    "business_cost_status": "DRYRUN_FLAG_COUNT_PROOF_NO_AMOUNT_NO_UPLOAD",
                    "rks_runtime_intake_status": "RKS_RUNTIME_PENDING",
                    "final_evidence_ready": False,
                },
            ],
        },
    )
    write_json(
        paths["gate"],
        {
            "final_goal_complete": False,
            "blocking_gate_count": 5,
            "passed_gate_count": 5,
            "gate_count": 10,
        },
    )
    write_json(paths["safe"], {"overall_passed": True})
    write_json(paths["ready"], {"row_count": 11, "not_ready_row_count": 11})
    write_json(
        paths["backup"],
        {"backup_complete": True, "missing_count": 0, "snapshot_id": "20260623_093108"},
    )
    write_json(
        paths["sync"],
        {
            "copy_result_count": 62,
            "all_requested_destinations_available": True,
            "all_available_copy_hashes_match": True,
        },
    )

    payload = module.build_payload()

    assert payload["overall_goal_complete"] is False
    assert payload["scenario_count"] == 2
    assert payload["sample_ready_count"] == 2
    assert payload["safe_execution_ready_count"] == 2
    assert payload["business_cost_ready_count"] == 2
    assert payload["rks_runtime_resolved_count"] == 1
    assert payload["final_evidence_ready_count"] == 1
    rows_by_id = {row["requirement_id"]: row for row in payload["rows"]}
    assert rows_by_id["REQ-01"]["status"] == "PROVED"
    assert rows_by_id["REQ-02"]["status"] == "PROVED"
    assert rows_by_id["REQ-03"]["status"] == "PARTIAL"
    assert rows_by_id["REQ-09"]["status"] == "NOT_PROVED"
    assert "残11行" in rows_by_id["REQ-09"]["next_action"]


def test_build_payload_excludes_user_skipped_scenario_from_active_counts(
    tmp_path: Path,
) -> None:
    module = load_module()
    paths = configure_sources(module, tmp_path)
    write_json(
        paths["ledger"],
        {
            "scenario_count": 3,
            "rows": [
                {
                    "scenario": "42",
                    "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                    "safe_execution_status": "SAFE_SUITE_EXIT0_STDERR0",
                    "business_cost_status": "COUNT_ONLY",
                    "rks_runtime_intake_status": "RKS_RUNTIME_EVIDENCE_CONFIRMED",
                    "final_evidence_ready": True,
                },
                {
                    "scenario": "43",
                    "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                    "safe_execution_status": "SAFE_SUITE_EXIT0_STDERR0",
                    "business_cost_status": "DRAFT_OK",
                    "rks_runtime_intake_status": "NO_RKS_MATRIX_ROW",
                    "final_evidence_ready": False,
                },
                {
                    "scenario": "44",
                    "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                    "safe_execution_status": "SAFE_SUITE_EXIT0_STDERR0",
                    "business_cost_status": "COUNT_ONLY",
                    "rks_runtime_intake_status": "RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION",
                    "final_evidence_ready": False,
                },
            ],
        },
    )
    write_json(
        paths["scope"],
        {
            "exclusions": [
                {
                    "scenario": "43",
                    "reason": "別システム修正中のためユーザー指示でスキップ",
                    "requested_by": "user",
                    "requested_at": "2026-06-23T10:05:00",
                    "active": True,
                }
            ]
        },
    )
    write_json(paths["gate"], {"final_goal_complete": False, "passed_gate_count": 5, "gate_count": 10})
    write_json(paths["safe"], {"overall_passed": True})
    write_json(
        paths["ready"],
        {
            "row_count": 3,
            "not_ready_row_count": 2,
            "rows": [
                {"scenario": "42", "status": "READY_FOR_SYNC", "blockers": ""},
                {"scenario": "43", "status": "NOT_READY", "blockers": "MISSING_OPERATOR_FIELDS"},
                {"scenario": "44", "status": "NOT_READY", "blockers": "MISSING_OPERATOR_FIELDS"},
            ],
        },
    )
    write_json(paths["backup"], {"backup_complete": True, "missing_count": 0, "snapshot_id": "s"})
    write_json(
        paths["sync"],
        {
            "copy_result_count": 1,
            "all_requested_destinations_available": True,
            "all_available_copy_hashes_match": True,
        },
    )

    payload = module.build_payload()

    assert payload["total_scenario_count"] == 3
    assert payload["scenario_count"] == 2
    assert payload["scope_exclusion_count"] == 1
    assert payload["rks_runtime_resolved_count"] == 2
    assert payload["remaining_operator_not_ready_count"] == 1
    assert payload["raw_remaining_operator_not_ready_count"] == 2
    rows_by_id = {row["requirement_id"]: row for row in payload["rows"]}
    assert rows_by_id["REQ-03"]["status"] == "PROVED"
    assert "excluded_scope_count=1" in rows_by_id["REQ-03"]["current_value"]
    assert rows_by_id["REQ-09"]["status"] == "NOT_PROVED"
    assert "残1行" in rows_by_id["REQ-09"]["next_action"]


def test_build_payload_does_not_count_invalid_business_cost_evidence(
    tmp_path: Path,
) -> None:
    module = load_module()
    paths = configure_sources(module, tmp_path)
    write_json(
        paths["ledger"],
        {
            "scenario_count": 2,
            "rows": [
                {
                    "scenario": "51/52",
                    "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                    "safe_execution_status": "SAFE_SUITE_EXIT0_STDERR0",
                    "business_cost_status": "INVALID_COST_EVIDENCE",
                    "business_cost_evidence_exists": True,
                    "objective_checkpoint_summary": "sample=OK; safe=OK; cost=PENDING",
                    "rks_runtime_intake_status": "RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION",
                    "final_evidence_ready": False,
                },
                {
                    "scenario": "55",
                    "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                    "safe_execution_status": "SAFE_SUITE_EXIT0_STDERR0",
                    "business_cost_status": "DRYRUN_BUSINESS_AMOUNT_REPORTED",
                    "business_cost_evidence_exists": True,
                    "objective_checkpoint_summary": "sample=OK; safe=OK; cost=SAMPLE_OK",
                    "rks_runtime_intake_status": "RKS_RUNTIME_EVIDENCE_CONFIRMED",
                    "final_evidence_ready": False,
                },
            ],
        },
    )
    write_json(paths["gate"], {"final_goal_complete": False, "passed_gate_count": 5, "gate_count": 10})
    write_json(paths["safe"], {"overall_passed": True})
    write_json(paths["ready"], {"row_count": 2, "not_ready_row_count": 2})
    write_json(paths["backup"], {"backup_complete": True, "missing_count": 0, "snapshot_id": "s"})
    write_json(
        paths["sync"],
        {
            "copy_result_count": 1,
            "all_requested_destinations_available": True,
            "all_available_copy_hashes_match": True,
        },
    )

    payload = module.build_payload()

    assert payload["business_cost_ready_count"] == 1
    rows_by_id = {row["requirement_id"]: row for row in payload["rows"]}
    assert rows_by_id["REQ-04"]["status"] == "PARTIAL"
    assert rows_by_id["REQ-04"]["remaining_gap"] == "business cost proof missing"


def test_build_payload_prefers_final_front_door_sync_manifest(
    tmp_path: Path,
) -> None:
    module = load_module()
    paths = configure_sources(module, tmp_path)
    write_json(
        paths["ledger"],
        {
            "scenario_count": 1,
            "rows": [
                {
                    "scenario": "55",
                    "sample_data_status": "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
                    "safe_execution_status": "SAFE_SUITE_EXIT0_STDERR0",
                    "business_cost_status": "DRYRUN_BUSINESS_AMOUNT_REPORTED",
                    "business_cost_evidence_exists": True,
                    "rks_runtime_intake_status": "RKS_RUNTIME_EVIDENCE_CONFIRMED",
                    "final_evidence_ready": False,
                }
            ],
        },
    )
    write_json(paths["gate"], {"final_goal_complete": False, "passed_gate_count": 5, "gate_count": 10})
    write_json(paths["safe"], {"overall_passed": True})
    write_json(paths["ready"], {"row_count": 1, "not_ready_row_count": 1})
    write_json(paths["backup"], {"backup_complete": True, "missing_count": 0, "snapshot_id": "s"})
    write_json(
        paths["sync"],
        {
            "copy_result_count": 1,
            "all_requested_destinations_available": True,
            "all_available_copy_hashes_match": True,
        },
    )
    write_json(
        paths["final_sync"],
        {
            "source_count": 47,
            "copy_result_count": 96,
            "all_hashes_match": True,
            "relative_inner_apply_fix": True,
        },
    )
    write_json(paths["distribution"], {"all_distribution_checks_pass": True})

    payload = module.build_payload()
    rows_by_id = {row["requirement_id"]: row for row in payload["rows"]}

    assert rows_by_id["REQ-08"]["status"] == "PROVED"
    assert "source_count=47" in rows_by_id["REQ-08"]["current_value"]
    assert "copy_result_count=96" in rows_by_id["REQ-08"]["current_value"]
    assert "relative_inner_apply_fix=True" in rows_by_id["REQ-08"]["current_value"]
    assert str(paths["final_sync"]) in rows_by_id["REQ-08"]["evidence"]


def test_write_outputs_creates_json_markdown_csv_and_numbered(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-23T10:00:00",
        "overall_goal_complete": False,
        "safety": "read-only objective audit",
        "requirement_count": 1,
        "proved_count": 0,
        "partial_count": 1,
        "not_proved_count": 0,
        "scenario_count": 1,
        "sample_ready_count": 1,
        "safe_execution_ready_count": 1,
        "business_cost_ready_count": 1,
        "rks_runtime_resolved_count": 0,
        "final_evidence_ready_count": 0,
        "remaining_operator_not_ready_count": 1,
        "rows": [
            {
                "requirement_id": "REQ-03",
                "requirement": "RKS証跡",
                "status": "PARTIAL",
                "evidence": str(tmp_path / "ledger.json"),
                "current_value": "rks_runtime_resolved_count=0/1",
                "remaining_gap": "missing",
                "next_action": "collect evidence",
            }
        ],
    }

    module.write_outputs(payload, tmp_path / "out")

    assert (tmp_path / "out" / "objective_completion_audit.json").exists()
    assert (tmp_path / "out" / "objective_completion_audit.json.numbered").exists()
    assert (tmp_path / "out" / "objective_completion_audit.md").exists()
    assert (tmp_path / "out" / "objective_completion_audit.md.numbered").exists()
    assert (tmp_path / "out" / "objective_completion_audit.csv").exists()
    assert (tmp_path / "out" / "objective_completion_audit.csv.numbered").exists()
    markdown = (tmp_path / "out" / "objective_completion_audit.md").read_text(
        encoding="utf-8",
    )
    assert "Objective Completion Audit" in markdown
    assert "REQ-03" in markdown
