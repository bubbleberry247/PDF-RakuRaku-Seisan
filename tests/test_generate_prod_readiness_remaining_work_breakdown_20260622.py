import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_prod_readiness_remaining_work_breakdown_20260622.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_prod_readiness_remaining_work_breakdown_20260622",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_payload_classifies_human_input_and_ready_bundles(tmp_path: Path) -> None:
    module = load_module()
    final_folder = tmp_path / "final" / "scenario_44"
    final_folder.mkdir(parents=True)
    fill_queue = tmp_path / "final_evidence_fill_queue.csv"
    cost_csv = tmp_path / "business_cost.csv"
    rks_csv = tmp_path / "rks_intake.csv"
    rks_validation = tmp_path / "rks_validation.md.numbered"
    goal_gate = tmp_path / "goal_gate.md.numbered"
    goal_final = tmp_path / "goal_final.md.numbered"
    safe_runner = tmp_path / "safe_runner.md.numbered"

    write_csv(
        fill_queue,
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenarios": "44",
                "owner": "業務担当者",
                "active": "True",
                "final_evidence_ready": "False",
                "action_status": "NEEDS_OPERATOR_INPUT",
                "missing_operator_fields": "OPERATOR_RESULT_BLANK, REVIEWER_BLANK",
                "remaining_runtime_evidence": "",
                "suggested_final_evidence_path": str(final_folder),
                "forbidden": "review未了の登録",
                "start_here_path": str(tmp_path / "start.md"),
                "target_intake_path": str(tmp_path / "intake.csv"),
                "next_action": "spot check",
            },
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "scenarios": "12/13",
                "owner": "PC/Outlook管理者",
                "active": "False",
                "final_evidence_ready": "True",
                "action_status": "READY",
                "missing_operator_fields": "",
                "remaining_runtime_evidence": "",
                "suggested_final_evidence_path": str(tmp_path / "outlook"),
                "forbidden": "",
                "start_here_path": "",
                "target_intake_path": "",
                "next_action": "",
            },
        ],
    )
    write_csv(
        cost_csv,
        [
            {
                "scenario": "44",
                "cost_evidence_status": "SAMPLE_SHADOW_HANDOFF_AMOUNT_RECALCULATED",
                "item_count": "3",
                "total_amount_yen": "20054",
                "validation_result": "PASS",
                "safety_scope": "LOCAL shadow handoff only",
            },
            {
                "scenario": "12/13",
                "cost_evidence_status": "OUTLOOK_COM_DRYRUN_COUNT_PROOF_NO_PRINT_NO_MAIL",
                "item_count": "0",
                "total_amount_yen": "",
                "validation_result": "PASS_COUNT_ONLY",
                "safety_scope": "Outlook COM scan-only dry-run",
            },
        ],
    )
    write_csv(
        rks_csv,
        [
            {
                "scenario": "44",
                "operator_decision": "",
                "rk10_editor_open": "",
                "rk10_build": "",
                "runtime_or_safe_stop": "",
                "latest_log_clean": "",
            }
        ],
    )
    write_text(rks_validation, "    5: - overall_rks_runtime_evidence_complete: `True`\n")
    write_text(goal_gate, "    8: - blocking_gate_count: `6`\n")
    write_text(goal_final, "    5: - final_goal_complete: `False`\n")
    write_text(safe_runner, "    3: - generated_at: `2026-06-22T21:17:40`\n    4: - overall_passed: `True`\n")

    payload = module.build_payload(
        fill_queue,
        cost_csv,
        rks_csv,
        rks_validation,
        goal_gate,
        goal_final,
        safe_runner,
    )

    assert payload["summary"]["active_bundle_count"] == 1
    assert payload["summary"]["human_input_bundle_count"] == 1
    assert payload["summary"]["scenario_count"] == 2
    assert payload["summary"]["safe_runner_line"].endswith("overall_passed: `True`")
    business_row = payload["bundles"][0]
    assert business_row["bundle"] == "BUSINESS_REVIEW_BUNDLE"
    assert business_row["category"] == "HUMAN_FINAL_EVIDENCE_INPUT_REQUIRED"
    assert business_row["final_evidence_folder_exists"] == "YES"
    assert business_row["human_or_external_input_needed"] == "operator_result/reviewer/reviewed_at の記入"
    ready_row = payload["bundles"][1]
    assert ready_row["category"] == "COMPLETE_OR_READY"
    scenario_row = payload["scenarios"][0]
    assert scenario_row["total_amount_yen"] == "20054"
    assert scenario_row["cost_validation"] == "PASS"


def test_build_payload_marks_open_probe_without_promoting_build_runtime(tmp_path: Path) -> None:
    module = load_module()
    fill_queue = tmp_path / "final_evidence_fill_queue.csv"
    cost_csv = tmp_path / "business_cost.csv"
    rks_csv = tmp_path / "rks_intake.csv"
    rks_validation = tmp_path / "rks_validation.md.numbered"
    goal_gate = tmp_path / "goal_gate.md.numbered"
    goal_final = tmp_path / "goal_final.md.numbered"
    safe_runner = tmp_path / "safe_runner.md.numbered"
    open_probe_json = tmp_path / "rks_open_probe.json"
    write_csv(
        fill_queue,
        [
            {
                "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                "scenarios": "42",
                "owner": "RK10操作担当者",
                "active": "True",
                "action_status": "NEEDS_OPERATOR_INPUT",
                "missing_operator_fields": "OPERATOR_RESULT_BLANK",
                "remaining_runtime_evidence": "rks gate pending",
                "final_evidence_ready": "False",
                "suggested_final_evidence_path": "",
                "target_intake_path": str(tmp_path / "intake.csv"),
                "next_action": "continue safe evidence",
                "forbidden": "ButtonRun",
                "start_here_path": "",
            }
        ],
    )
    write_csv(
        cost_csv,
        [
            {
                "scenario": "42",
                "cost_evidence_status": "DRIVE_REPORT_ROW_COUNT_PROOF_NO_MAINSV_WRITE",
                "item_count": "554",
                "total_amount_yen": "",
                "validation_result": "PASS_COUNT_ONLY",
                "safety_scope": "no-write",
            }
        ],
    )
    write_csv(
        rks_csv,
        [
            {
                "scenario": "42",
                "operator_decision": "",
                "rk10_editor_open": "",
                "rk10_build": "",
                "runtime_or_safe_stop": "",
                "latest_log_clean": "",
            }
        ],
    )
    open_probe_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "scenario": "42",
                        "editor_open_probe_status": "RK10_EDITOR_OPEN_CONFIRMED",
                        "editor_open_probe_build_artifact_found": False,
                        "editor_open_probe_button_run_clicked": False,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_text(rks_validation, "    5: - overall_rks_runtime_evidence_complete: `True`\n")
    write_text(goal_gate, "    8: - blocking_gate_count: `6`\n")
    write_text(goal_final, "    5: - final_goal_complete: `False`\n")
    write_text(safe_runner, "    3: - generated_at: `now`\n    4: - overall_passed: `True`\n")

    payload = module.build_payload(
        fill_queue,
        cost_csv,
        rks_csv,
        rks_validation,
        goal_gate,
        goal_final,
        safe_runner,
        open_probe_json,
    )

    scenario_row = payload["scenarios"][0]
    assert scenario_row["rks_editor_open"] == "RK10_EDITOR_OPEN_CONFIRMED_ONLY"
    assert scenario_row["rks_build"] == ""
    assert scenario_row["rks_runtime_or_safe_stop"] == ""
    assert payload["summary"]["open_probe_confirmed_scenario_count"] == 1


def test_write_outputs_creates_csv_markdown_json_and_numbered_files(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "summary": {
            "generated_at": "2026-06-22T21:18:43",
            "goal_complete_line": "5: - final_goal_complete: `False`",
            "safe_runner_generated_at": "3: - generated_at: `2026-06-22T21:17:40`",
            "safe_runner_line": "4: - overall_passed: `True`",
            "blocking_gate_line": "8: - blocking_gate_count: `6`",
            "rks_validation_line": "5: - overall_rks_runtime_evidence_complete: `True`",
            "active_bundle_count": 1,
            "human_input_bundle_count": 1,
            "scenario_count": 1,
            "open_probe_confirmed_scenario_count": 0,
            "safety": "no production registration",
            "sources": {
                "fill_queue_csv": str(tmp_path / "fill.csv"),
                "business_cost_csv": str(tmp_path / "cost.csv"),
                "rks_open_probe_matrix_json": str(tmp_path / "rks_open.json"),
            },
        },
        "bundles": [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenarios": "44",
                "owner": "業務担当者",
                "active_queue": "YES",
                "action_status": "NEEDS_OPERATOR_INPUT",
                "category": "HUMAN_FINAL_EVIDENCE_INPUT_REQUIRED",
                "final_evidence_folder_exists": "YES",
                "missing_operator_fields": "OPERATOR_RESULT_BLANK",
                "remaining_runtime_evidence": "",
                "codex_can_continue_with": "証跡整理",
                "human_or_external_input_needed": "operator_result/reviewer/reviewed_at の記入",
                "hard_stop": "review未了の登録",
                "start_here_path": str(tmp_path / "start.md"),
                "target_intake_path": str(tmp_path / "intake.csv"),
                "suggested_final_evidence_path": str(tmp_path / "final"),
            }
        ],
        "scenarios": [
            {
                "scenario": "44",
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "cost_status": "SAMPLE",
                "item_count": "3",
                "total_amount_yen": "20054",
                "cost_validation": "PASS",
                "cost_scope": "LOCAL",
                "rks_operator_decision": "",
                "rks_editor_open": "",
                "rks_build": "",
                "rks_runtime_or_safe_stop": "",
                "rks_latest_log_clean": "",
                "next_action": "spot check",
            }
        ],
    }

    out_dir = tmp_path / "out"
    module.write_outputs(payload, out_dir)

    markdown = (out_dir / "prod_readiness_remaining_work_breakdown.md").read_text(
        encoding="utf-8"
    )
    assert "固定ランナーは通過していますが、最終ゴールは未完了です。" in markdown
    assert "BUSINESS_REVIEW_BUNDLE" in markdown
    assert (out_dir / "prod_readiness_remaining_work_breakdown.json").exists()
    assert (out_dir / "remaining_bundle_work.csv").exists()
    assert (out_dir / "remaining_scenario_work.csv").exists()
    assert (out_dir / "prod_readiness_remaining_work_breakdown.md.numbered").exists()
    assert (out_dir / "remaining_bundle_work.csv.numbered").exists()
    assert (out_dir / "remaining_scenario_work.csv.numbered").exists()
