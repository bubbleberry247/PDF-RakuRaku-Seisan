import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_remaining_operator_decision_brief_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_remaining_operator_decision_brief_20260623",
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


def test_build_payload_classifies_boundaries_without_auto_approval(tmp_path: Path) -> None:
    module = load_module()
    latest_51 = tmp_path / "s51_52.txt"
    latest_70 = tmp_path / "s70.txt"
    latest_38 = tmp_path / "s38.txt"
    for path in (latest_51, latest_70, latest_38):
        path.write_text("safe", encoding="utf-8")
    minimum_pack = tmp_path / "minimum_operator_review_pack.json"
    validation_json = tmp_path / "remaining_operator_input_ready_validation.json"
    objective_json = tmp_path / "objective_completion_audit.json"
    write_json(
        minimum_pack,
        {
            "scope_exclusion_count": 1,
            "packet_scope_excluded_scenarios": ["43"],
            "rows": [
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "scenario": "51/52",
                    "status": "NOT_READY",
                    "operator_result": "",
                    "reviewer": "",
                    "reviewed_at": "",
                    "allowed_operator_result": "OK / NG / HOLD",
                    "latest_evidence_file": str(latest_51),
                    "latest_evidence_exists": "YES",
                    "evidence_attention_signals": "RK10 open/build/runtime未確認",
                },
                {
                    "bundle": "PAYMENT_APPROVAL_BUNDLE",
                    "scenario": "70",
                    "status": "NOT_READY",
                    "operator_result": "HOLD",
                    "reviewer": "",
                    "reviewed_at": "",
                    "allowed_operator_result": "OK / NG / HOLD",
                    "latest_evidence_file": str(latest_70),
                    "latest_evidence_exists": "YES",
                    "evidence_safety_signals": "payment_execute_performed: False",
                },
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "scenario": "38",
                    "status": "NOT_READY",
                    "operator_result": "OK",
                    "reviewer": "reviewer-a",
                    "reviewed_at": "2026-06-23T15:00:00",
                    "allowed_operator_result": "OK / NG / HOLD",
                    "latest_evidence_file": str(latest_38),
                    "latest_evidence_exists": "YES",
                    "evidence_success_signals": "py_compile_exit=0",
                },
            ],
        },
    )
    write_json(
        validation_json,
        {
            "rows": [
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "scenario": "51/52",
                    "blockers": "MISSING_OPERATOR_FIELDS",
                    "missing_operator_fields": "operator_result;reviewer;reviewed_at",
                },
                {
                    "bundle": "PAYMENT_APPROVAL_BUNDLE",
                    "scenario": "70",
                    "blockers": "MISSING_OPERATOR_FIELDS",
                    "missing_operator_fields": "reviewer;reviewed_at",
                },
            ]
        },
    )
    write_json(
        objective_json,
        {"overall_goal_complete": False, "remaining_operator_not_ready_count": 10},
    )

    payload = module.build_payload(minimum_pack, validation_json, objective_json)

    assert payload["row_count"] == 3
    assert payload["blank_operator_row_count"] == 1
    assert payload["partial_operator_row_count"] == 1
    assert payload["complete_operator_row_count"] == 1
    assert payload["latest_evidence_file_exists_count"] == 3
    assert payload["scope_exclusion_count"] == 1
    assert payload["packet_scope_excluded_scenarios"] == ["43"]
    rows = {row["scenario"]: row for row in payload["rows"]}
    assert (
        rows["51/52"]["decision_boundary"]
        == "SOFTBANK_MANUAL_SUBMISSION_POLICY_REVIEW_REQUIRED"
    )
    assert "楽楽精算へ自動申請せず" in rows["51/52"]["why_not_auto_approved"]
    assert rows["70"]["decision_boundary"] == "PAYMENT_APPROVAL_REVIEW_REQUIRED"
    assert "支払実行は不可逆操作" in rows["70"]["why_not_auto_approved"]
    assert rows["38"]["decision_boundary"] == "RK10_RUNTIME_GATE_REVIEW_REQUIRED"
    assert rows["38"]["operator_result"] == "OK"
    assert rows["38"]["operator_fields_state"] == "complete"


def test_write_outputs_creates_brief_files(tmp_path: Path) -> None:
    module = load_module()
    latest_evidence = tmp_path / "latest.txt"
    latest_evidence.write_text("safe", encoding="utf-8")
    payload = {
        "generated_at": "2026-06-23T15:10:00",
        "safety": "decision brief only; no auto approval",
        "minimum_pack_json": str(tmp_path / "minimum.json"),
        "minimum_pack_json_exists": True,
        "validation_json": str(tmp_path / "validation.json"),
        "validation_json_exists": True,
        "objective_audit_json": str(tmp_path / "objective.json"),
        "objective_audit_json_exists": True,
        "row_count": 1,
        "blank_operator_row_count": 1,
        "partial_operator_row_count": 0,
        "complete_operator_row_count": 0,
        "latest_evidence_file_exists_count": 1,
        "scope_exclusion_count": 1,
        "packet_scope_excluded_scenarios": ["43"],
        "objective_overall_goal_complete": False,
        "objective_remaining_operator_not_ready_count": 10,
        "decision_boundary_counts": {"PAYMENT_APPROVAL_REVIEW_REQUIRED": 1},
        "rows": [
            {
                "row_number": 1,
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenario": "70",
                "status": "NOT_READY",
                "operator_fields_state": "blank",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "allowed_operator_result": "OK / NG / HOLD",
                "decision_boundary": "PAYMENT_APPROVAL_REVIEW_REQUIRED",
                "review_focus": "支払実行なし",
                "why_not_auto_approved": "支払実行は不可逆操作のため自動承認しない",
                "recommended_operator_action": "人が記入する",
                "latest_evidence_file": str(latest_evidence),
                "latest_evidence_exists": "YES",
                "latest_evidence_uri": latest_evidence.absolute().as_uri(),
                "evidence_success_signals": "",
                "evidence_attention_signals": "",
                "evidence_safety_signals": "payment_execute_performed: False",
                "validation_blockers": "MISSING_OPERATOR_FIELDS",
                "validation_missing_operator_fields": "operator_result;reviewer;reviewed_at",
            }
        ],
    }

    module.write_outputs(payload, tmp_path / "out")

    assert (tmp_path / "out" / "remaining_operator_decision_brief.json").exists()
    assert (tmp_path / "out" / "remaining_operator_decision_brief.csv").exists()
    assert (tmp_path / "out" / "remaining_operator_decision_brief.md").exists()
    assert (tmp_path / "out" / "remaining_operator_decision_brief.html").exists()
    assert (
        tmp_path / "out" / "remaining_operator_decision_brief_summary.md.numbered"
    ).exists()
    assert (
        tmp_path / "out" / "START_HERE_remaining_operator_decision_brief.md"
    ).exists()
    assert (tmp_path / "out" / "OPEN_remaining_operator_decision_brief.bat").exists()
    with (tmp_path / "out" / "remaining_operator_decision_brief.csv").open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))
    summary = (
        tmp_path / "out" / "remaining_operator_decision_brief_summary.md"
    ).read_text(encoding="utf-8")
    html = (tmp_path / "out" / "remaining_operator_decision_brief.html").read_text(
        encoding="utf-8"
    )
    assert rows[0]["scenario"] == "70"
    assert rows[0]["operator_result"] == ""
    assert "PAYMENT_APPROVAL_REVIEW_REQUIRED" in summary
    assert "payment_execute_performed" in html
