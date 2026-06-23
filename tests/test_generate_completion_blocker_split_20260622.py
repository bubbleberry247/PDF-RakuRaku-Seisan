from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "generate_completion_blocker_split_20260622.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "generate_completion_blocker_split_20260622",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_category_for_gate_splits_aggregate_operator_and_rks() -> None:
    module = load_module()

    assert (
        module.category_for_gate("STATUS_SNAPSHOT")
        == module.AGGREGATE_BLOCKED_BY_DOWNSTREAM_GATES
    )
    assert (
        module.category_for_gate("EXECUTION_PACKET_VALIDATION")
        == module.FINAL_OPERATOR_FIELDS_REQUIRED
    )
    assert module.category_for_gate("RKS_GATE_MATRIX") == module.TRUE_TECHNICAL_RUNTIME_GAP


def test_build_boundary_rows_marks_human_approval() -> None:
    module = load_module()

    rows = module.build_boundary_rows(
        {
            "rows": [
                {
                    "bundle": "PAYMENT_APPROVAL_BUNDLE",
                    "scenario": "70",
                    "boundary_class": "HUMAN_OR_EXTERNAL_APPROVAL_REQUIRED_NO_AUTO_APPROVAL",
                    "current_status": "MISSING_FINAL_INPUT",
                    "missing_fields": "operator_result",
                    "codex_can_continue_with": "案内まで",
                    "human_or_external_input_needed": "承認者確認",
                    "forbidden_scope": "支払実行",
                    "source_intake_path": r"C:\tmp\intake.csv",
                }
            ]
        },
        1,
    )

    assert len(rows) == 1
    assert rows[0].category == module.EXTERNAL_HUMAN_APPROVAL_REQUIRED
    assert rows[0].scenarios == "70"


def test_build_rks_open_only_rows_requires_build_runtime() -> None:
    module = load_module()

    rows = module.build_rks_open_only_rows(
        {
            "rows": [
                {
                    "scenario": "57",
                    "current_rks_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
                    "runtime_intake_status": "RKS_RUNTIME_EVIDENCE_PENDING",
                    "editor_open_probe_status": "RK10_EDITOR_OPEN_CONFIRMED",
                    "editor_open_probe_build_artifact_found": False,
                    "blocked_operation": "RK10 ButtonRun",
                    "missing_gate": "runtime safe-stop latest clean log",
                    "editor_open_probe_source": r"C:\tmp\probe.json",
                }
            ]
        },
        1,
    )

    assert len(rows) == 1
    assert rows[0].category == module.TECHNICAL_EVIDENCE_COLLECTED_OPEN_ONLY
    assert "build_artifact=NO" in rows[0].blocker
    assert "runtime_intake_status=RKS_RUNTIME_EVIDENCE_PENDING" in rows[0].blocker
    assert rows[0].human_or_external_input_needed == (
        "RK10 build、runtime/safe-stop、latest clean log"
    )


def test_build_rks_open_only_rows_skips_non_blocking_runtime_statuses() -> None:
    module = load_module()

    rows = module.build_rks_open_only_rows(
        {
            "rows": [
                {
                    "scenario": "57",
                    "current_rks_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
                    "runtime_intake_status": "RKS_RUNTIME_EVIDENCE_CONFIRMED",
                    "editor_open_probe_status": "RK10_EDITOR_OPEN_CONFIRMED",
                    "editor_open_probe_build_artifact_found": False,
                    "blocked_operation": "RK10 ButtonRun",
                    "missing_gate": "runtime safe-stop latest clean log",
                    "editor_open_probe_source": r"C:\tmp\probe.json",
                },
                {
                    "scenario": "44",
                    "current_rks_status": "BUSINESS_REVIEW_HOLD_BEFORE_RKS",
                    "runtime_intake_status": "RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION",
                    "editor_open_probe_status": "RK10_EDITOR_OPEN_CONFIRMED",
                    "editor_open_probe_build_artifact_found": False,
                    "blocked_operation": "Rakuraku registration",
                    "missing_gate": "business review",
                    "editor_open_probe_source": r"C:\tmp\probe.json",
                },
            ]
        },
        1,
    )

    assert rows == []


def test_build_operator_gap_summary_separates_evidence_paths_from_operator_fields() -> None:
    module = load_module()

    summary = module.build_operator_gap_summary(
        {
            "all_packet_rows_approved": False,
            "needs_attention_count": 1,
            "rows": [
                {
                    "bundle": "PAYMENT_APPROVAL_BUNDLE",
                    "scenario": "70",
                    "status": "MISSING_OPERATOR_FIELDS",
                    "missing_fields": "operator_result, reviewer, reviewed_at",
                    "evidence_path": r"C:\evidence\scenario_70",
                    "evidence_exists": True,
                    "approved": False,
                },
                {
                    "bundle": "OUTLOOK_COM_BUNDLE",
                    "scenario": "12/13",
                    "status": "APPROVED_BY_BUNDLE_WITH_EVIDENCE",
                    "missing_fields": "",
                    "evidence_path": r"C:\evidence\scenario_12_13",
                    "evidence_exists": True,
                    "approved": True,
                },
            ],
        }
    )

    assert summary["row_count"] == 2
    assert summary["approved_row_count"] == 1
    assert summary["evidence_path_set_count"] == 2
    assert summary["evidence_exists_count"] == 2
    assert summary["missing_evidence_row_count"] == 0
    assert summary["operator_field_only_pending_count"] == 1
    assert summary["missing_operator_field_counts"] == {
        "operator_result": 1,
        "reviewed_at": 1,
        "reviewer": 1,
    }
