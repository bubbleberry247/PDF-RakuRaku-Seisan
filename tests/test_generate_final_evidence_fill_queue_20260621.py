import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_final_evidence_fill_queue_20260621.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_final_evidence_fill_queue_20260621", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_build_payload_combines_attention_rows_with_start_here_paths(tmp_path: Path) -> None:
    module = load_module()
    bundle_validation_path = tmp_path / "bundle_validation.json"
    execution_validation_path = tmp_path / "execution_validation.json"
    remaining_path = tmp_path / "remaining.json"
    bundle_sheet_path = tmp_path / "bundle_operator_sheet.csv"
    scenario_csv_path = tmp_path / "business_review_bundle.csv"

    write_json(
        bundle_validation_path,
        {
            "pack_json": str(tmp_path / "packs.json"),
            "operator_sheet": str(bundle_sheet_path),
            "checks": [
                {
                    "bundle": "BUSINESS_REVIEW_BUNDLE",
                    "scenarios": "44",
                    "final_evidence_ready": False,
                    "operator_fields_complete": False,
                    "final_evidence_path_issue": "FINAL_EVIDENCE_PATH_BLANK",
                    "final_evidence_filename_issue": "NO_FINAL_EVIDENCE_FILES",
                    "final_evidence_has_content": False,
                    "final_evidence_item_count": 0,
                    "final_evidence_dir": str(tmp_path / "final" / "business_review"),
                },
                {
                    "bundle": "OUTLOOK_COM_BUNDLE",
                    "scenarios": "12/13",
                    "final_evidence_ready": True,
                    "operator_fields_complete": True,
                    "final_evidence_has_content": True,
                    "final_evidence_item_count": 21,
                    "final_evidence_dir": str(tmp_path / "final" / "outlook"),
                },
            ],
        },
    )
    write_json(
        execution_validation_path,
        {
            "packet_dir": str(tmp_path / "packet"),
            "bundle_sheet_path": str(bundle_sheet_path),
            "bundle_approvals": [
                {
                    "bundle": "BUSINESS_REVIEW_BUNDLE",
                    "approved": False,
                    "status": "MISSING_OPERATOR_FIELDS",
                    "missing_fields": "operator_result, evidence_path",
                }
            ],
            "rows": [
                {
                    "bundle": "BUSINESS_REVIEW_BUNDLE",
                    "scenario": "44",
                    "approved": False,
                    "status": "MISSING_OPERATOR_FIELDS",
                    "missing_fields": "reviewer",
                    "csv_path": str(scenario_csv_path),
                },
                {
                    "bundle": "OUTLOOK_COM_BUNDLE",
                    "scenario": "12/13",
                    "approved": True,
                    "status": "APPROVED_WITH_EVIDENCE",
                    "missing_fields": "",
                    "csv_path": str(tmp_path / "outlook.csv"),
                },
            ],
        },
    )
    write_json(
        remaining_path,
        {
            "operator_prefill_json": str(tmp_path / "prefill.json"),
            "rows": [
                {
                    "rank": 2,
                    "bundle": "BUSINESS_REVIEW_BUNDLE",
                    "owner": "業務担当者",
                    "scenarios": "44",
                    "active": True,
                    "all_input_paths": str(tmp_path / "s44_next_steps.md"),
                    "final_evidence_dir": str(tmp_path / "final" / "business_review" / "scenario_44"),
                    "target_intake_path": str(tmp_path / "intake.csv"),
                    "filename_examples": "scenario_44_safe_run_log_YYYYMMDD_HHMMSS.txt",
                    "forbidden": "review未了の登録",
                    "next_action": "review OK/NG",
                    "after_action_command": "python fixed_runner.py",
                    "start_here_path": str(tmp_path / "business_review_START_HERE.md"),
                },
                {
                    "rank": None,
                    "bundle": "OUTLOOK_COM_BUNDLE",
                    "owner": "PC/Outlook管理者",
                    "scenarios": "12/13",
                    "active": False,
                    "start_here_path": "",
                },
            ],
        },
    )

    payload = module.build_payload(
        bundle_validation_path,
        execution_validation_path,
        remaining_path,
        tmp_path / "missing_rk10_collect.json",
        tmp_path / "missing_rks_gate_matrix.json",
        tmp_path / "missing_bundle_sync.json",
    )

    assert payload["active_queue_count"] == 1
    assert payload["ready_or_completed_count"] == 1
    assert payload["operator_attention_row_count"] == 2
    active_row = payload["rows"][0]
    assert active_row["bundle"] == "BUSINESS_REVIEW_BUNDLE"
    assert active_row["action_status"] == "NEEDS_OPERATOR_INPUT"
    assert "operator_result" in active_row["missing_operator_fields"]
    assert "reviewer" in active_row["missing_operator_fields"]
    assert "FINAL_EVIDENCE_PATH_BLANK" in active_row["final_evidence_gap"]
    assert "NO_FINAL_EVIDENCE_FILES" in active_row["final_evidence_gap"]
    assert active_row["start_here_path"].endswith("business_review_START_HERE.md")
    assert active_row["unified_entry_keys"] == "BUSINESS_REVIEW_BUNDLE::44"
    assert active_row["fill_only_fields"] == "operator_result, reviewer, reviewed_at"
    assert active_row["unified_input_csv"].endswith("unified_final_evidence_input.csv")
    assert str(bundle_sheet_path) in active_row["attention_target_csvs"]
    assert str(scenario_csv_path) in active_row["attention_target_csvs"]
    assert active_row["supplemental_evidence_status"] == ""


def test_build_payload_uses_intake_sync_evidence_when_operator_fields_are_missing(tmp_path: Path) -> None:
    module = load_module()
    bundle_validation_path = tmp_path / "bundle_validation.json"
    execution_validation_path = tmp_path / "execution_validation.json"
    remaining_path = tmp_path / "remaining.json"
    bundle_sync_path = tmp_path / "bundle_sync.json"
    intake_path = tmp_path / "outlook_final_evidence_intake.csv"

    write_json(
        bundle_validation_path,
        {
            "checks": [
                {
                    "bundle": "OUTLOOK_COM_BUNDLE",
                    "scenarios": "12/13",
                    "final_evidence_ready": False,
                    "operator_fields_complete": False,
                    "final_evidence_path_issue": "FINAL_EVIDENCE_PATH_BLANK",
                    "final_evidence_filename_issue": "NO_FINAL_EVIDENCE_FILES",
                    "final_evidence_has_content": False,
                    "final_evidence_item_count": 0,
                    "final_evidence_dir": str(tmp_path / "final" / "outlook"),
                }
            ],
        },
    )
    write_json(execution_validation_path, {"rows": []})
    write_json(
        remaining_path,
        {
            "rows": [
                {
                    "rank": 7,
                    "bundle": "OUTLOOK_COM_BUNDLE",
                    "owner": "PC/Outlook管理者",
                    "scenarios": "12/13",
                    "active": True,
                    "target_intake_path": str(intake_path),
                    "start_here_path": str(tmp_path / "outlook_START_HERE.md"),
                }
            ]
        },
    )
    write_json(
        bundle_sync_path,
        {
            "results": [
                {
                    "bundle": "OUTLOOK_COM_BUNDLE",
                    "intake_path": str(intake_path),
                    "ready_to_sync": False,
                    "blockers": "NOT_ALL_ROWS_READY, OPERATOR_RESULT_BLANK, REVIEWER_BLANK, REVIEWED_AT_BLANK",
                    "rows": [
                        {
                            "scenario": "12/13",
                            "status": "BLOCKED",
                            "blockers": "OPERATOR_RESULT_BLANK, REVIEWER_BLANK, REVIEWED_AT_BLANK",
                            "final_evidence_exists": True,
                            "final_evidence_has_content": True,
                            "final_evidence_filenames_match": True,
                            "final_evidence_filename_match_count": 22,
                        }
                    ],
                }
            ]
        },
    )

    payload = module.build_payload(
        bundle_validation_path,
        execution_validation_path,
        remaining_path,
        tmp_path / "missing_rk10_collect.json",
        tmp_path / "missing_rks_gate_matrix.json",
        bundle_sync_path,
    )

    row = payload["rows"][0]
    assert row["bundle"] == "OUTLOOK_COM_BUNDLE"
    assert row["unified_entry_keys"] == "OUTLOOK_COM_BUNDLE::12/13"
    assert row["final_evidence_item_count"] == 22
    assert row["final_evidence_gap"] == "OPERATOR_FIELDS_INCOMPLETE"
    assert "FINAL_EVIDENCE_PATH_BLANK" not in row["final_evidence_gap"]
    assert "NO_FINAL_EVIDENCE_FILES" not in row["final_evidence_gap"]
    assert "scenario:12/13=OPERATOR_RESULT_BLANK" in row["missing_operator_fields"]
    assert str(intake_path) in row["attention_target_csvs"]


def test_build_payload_adds_rk10_collected_and_remaining_runtime_summary(tmp_path: Path) -> None:
    module = load_module()
    bundle_validation_path = tmp_path / "bundle_validation.json"
    execution_validation_path = tmp_path / "execution_validation.json"
    remaining_path = tmp_path / "remaining.json"
    rk10_collect_path = tmp_path / "rk10_collect.json"
    rks_validation_path = tmp_path / "rks_validation.json"
    rks_gate_matrix_path = tmp_path / "rks_gate_matrix.json"
    bundle_sync_path = tmp_path / "bundle_sync.json"

    write_json(
        bundle_validation_path,
        {
            "checks": [
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "scenarios": "37, 47, 55, 57, 58, 63",
                    "final_evidence_ready": False,
                    "operator_fields_complete": False,
                    "final_evidence_has_content": False,
                }
            ]
        },
    )
    write_json(
        execution_validation_path,
        {
            "rows": [
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "scenario": "37",
                    "approved": False,
                    "status": "MISSING_OPERATOR_FIELDS",
                    "missing_fields": "operator_result",
                    "csv_path": str(tmp_path / "rk10_editor_runtime_bundle.csv"),
                },
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "scenario": "57",
                    "approved": False,
                    "status": "MISSING_OPERATOR_FIELDS",
                    "missing_fields": "operator_result, evidence_path",
                    "csv_path": str(tmp_path / "rk10_editor_runtime_bundle.csv"),
                }
            ]
        },
    )
    write_json(
        remaining_path,
        {
            "rows": [
                {
                    "rank": 6,
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "owner": "RK10操作担当者",
                    "scenarios": "37, 38, 57, 58",
                    "active": True,
                    "after_action_command": "python fixed_runner.py",
                    "start_here_path": str(tmp_path / "rk10_START_HERE.md"),
                }
            ]
        },
    )
    write_json(
        rks_validation_path,
        {
            "rows": [
                {
                    "scenario": "37",
                    "requires_rk10_evidence": True,
                    "approved": True,
                    "issue_codes": "",
                },
                {
                    "scenario": "57",
                    "requires_rk10_evidence": True,
                    "approved": False,
                    "issue_codes": "RUNTIME_OR_SAFE_STOP_NOT_CONFIRMED, LATEST_LOG_PATH_MISSING_OR_NOT_FOUND",
                },
                {
                    "scenario": "58",
                    "requires_rk10_evidence": True,
                    "approved": False,
                    "issue_codes": "RK10_EDITOR_OPEN_NOT_CONFIRMED, RK10_BUILD_NOT_CONFIRMED",
                },
            ]
        },
    )
    write_json(
        rks_gate_matrix_path,
        {
            "rows": [
                {
                    "scenario": "38",
                    "current_rks_status": "PRIMARY_RKS_EDITOR_OPEN_NG",
                    "missing_gate": "RK10 Editor Save As再生成 / open/build/runtime/latest clean log",
                },
                {
                    "scenario": "57",
                    "current_rks_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
                    "missing_gate": "runtime safe-stop latest clean log",
                },
                {
                    "scenario": "58",
                    "current_rks_status": "RKS_RUNTIME_UNCONFIRMED",
                    "missing_gate": "operator-select / no-mail runtime evidence",
                },
                {
                    "scenario": "71",
                    "current_rks_status": "AZURE_OCR_GATE_HOLD_BEFORE_RKS",
                    "missing_gate": "paid OCR approval",
                },
            ]
        },
    )
    write_json(
        rk10_collect_path,
        {
            "status": "READY_FOR_REVIEWER_TIMESTAMP",
            "validation_json": str(rks_validation_path),
            "approved_validator_count": 4,
            "appended_intake_row_count": 3,
            "collected_count": 4,
            "skipped_count": 0,
            "scenarios": [
                {"scenario": "37", "status": "READY_FOR_REVIEWER_TIMESTAMP"},
                {"scenario": "47", "status": "READY_FOR_REVIEWER_TIMESTAMP"},
                {"scenario": "55", "status": "READY_FOR_REVIEWER_TIMESTAMP"},
                {"scenario": "63", "status": "READY_FOR_REVIEWER_TIMESTAMP"},
            ],
        },
    )
    write_json(
        bundle_sync_path,
        {
            "results": [
                {
                    "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                    "intake_path": str(tmp_path / "rk10_editor_runtime_bundle_intake.csv"),
                    "ready_to_sync": False,
                    "blockers": "NOT_ALL_ROWS_READY",
                    "rows": [
                        {
                            "scenario": "37",
                            "status": "READY",
                            "blockers": "",
                        },
                        {
                            "scenario": "57",
                            "status": "BLOCKED",
                            "blockers": "OPERATOR_RESULT_BLANK, REVIEWER_BLANK, REVIEWED_AT_BLANK",
                        },
                    ],
                }
            ]
        },
    )

    payload = module.build_payload(
        bundle_validation_path,
        execution_validation_path,
        remaining_path,
        rk10_collect_path,
        rks_gate_matrix_path,
        bundle_sync_path,
    )

    rk10_row = payload["rows"][0]
    assert rk10_row["bundle"] == "RK10_EDITOR_RUNTIME_BUNDLE"
    assert "RK10_EDITOR_RUNTIME_BUNDLE::37" in rk10_row["unified_entry_keys"]
    assert "RK10_EDITOR_RUNTIME_BUNDLE::58" in rk10_row["unified_entry_keys"]
    assert "collector_status=READY_FOR_REVIEWER_TIMESTAMP" in rk10_row["supplemental_evidence_status"]
    assert "collected=4/4" in rk10_row["supplemental_evidence_status"]
    assert "auto_appended_intake_rows=3" in rk10_row["supplemental_evidence_status"]
    assert "collected_scenarios=37, 47, 55, 63" in rk10_row["supplemental_evidence_status"]
    assert "57=RUNTIME_OR_SAFE_STOP_NOT_CONFIRMED" in rk10_row["remaining_runtime_evidence"]
    assert "58=RK10_EDITOR_OPEN_NOT_CONFIRMED" in rk10_row["remaining_runtime_evidence"]
    assert "38=PRIMARY_RKS_EDITOR_OPEN_NG" in rk10_row["remaining_runtime_evidence"]
    assert "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING" in rk10_row["remaining_runtime_evidence"]
    assert "71=AZURE_OCR_GATE_HOLD_BEFORE_RKS" not in rk10_row["remaining_runtime_evidence"]
    assert "scenario:37" not in rk10_row["missing_operator_fields"]
    assert "scenario:57=OPERATOR_RESULT_BLANK" in rk10_row["missing_operator_fields"]
    assert str(tmp_path / "rk10_editor_runtime_bundle_intake.csv") in rk10_row["attention_target_csvs"]
    assert str(rk10_collect_path) in rk10_row["supplemental_evidence_source"]
    assert str(rks_validation_path) in rk10_row["supplemental_evidence_source"]
    assert str(rks_gate_matrix_path) in rk10_row["supplemental_evidence_source"]


def test_write_outputs_creates_json_csv_markdown_and_numbered(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-21T12:00:00",
        "overall_goal_complete": False,
        "active_queue_count": 1,
        "ready_or_completed_count": 0,
        "operator_attention_row_count": 1,
        "next_active_bundle": "PAYMENT_APPROVAL_BUNDLE",
        "after_action_command": "python fixed_runner.py",
        "safety": "read-only queue generation only",
        "bundle_validation_json": str(tmp_path / "bundle.json"),
        "execution_validation_json": str(tmp_path / "execution.json"),
        "remaining_next_steps_json": str(tmp_path / "remaining.json"),
        "rk10_collect_json": str(tmp_path / "rk10_collect.json"),
        "rks_gate_matrix_json": str(tmp_path / "rks_gate_matrix.json"),
        "bundle_sync_json": str(tmp_path / "bundle_sync.json"),
        "unified_input_csv": str(tmp_path / "unified_final_evidence_input.csv"),
        "rows": [
            {
                "rank": 3,
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenarios": "70",
                "owner": "支払承認者",
                "active": True,
                "final_evidence_ready": False,
                "action_status": "NEEDS_OPERATOR_INPUT",
                "missing_operator_fields": "bundle:*=operator_result, evidence_path",
                "operator_attention_count": 1,
                "final_evidence_gap": "FINAL_EVIDENCE_PATH_BLANK",
                "final_evidence_item_count": 0,
                "start_here_path": str(tmp_path / "payment_START_HERE.md"),
                "unified_input_csv": str(tmp_path / "unified_final_evidence_input.csv"),
                "unified_entry_keys": "PAYMENT_APPROVAL_BUNDLE::70",
                "fill_only_fields": "operator_result, reviewer, reviewed_at",
                "supporting_input_paths": str(tmp_path / "payment_prefill.csv"),
                "suggested_final_evidence_path": str(tmp_path / "final" / "scenario_70"),
                "target_intake_path": str(tmp_path / "intake.csv"),
                "attention_target_csvs": str(tmp_path / "bundle_operator_sheet.csv"),
                "filename_examples": "scenario_70_safe_run_log_YYYYMMDD_HHMMSS.txt",
                "forbidden": "--execute・支払実行・RK10 ButtonRun",
                "next_action": "confirm-preview only",
                "after_action_command": "python fixed_runner.py",
                "supplemental_evidence_status": "",
                "remaining_runtime_evidence": "",
                "supplemental_evidence_source": "",
                "validation_source": str(tmp_path / "source.json"),
            }
        ],
    }

    module.write_outputs(payload, tmp_path / "out")

    markdown = (tmp_path / "out" / "final_evidence_fill_queue.md").read_text(encoding="utf-8")
    csv_text = (tmp_path / "out" / "final_evidence_fill_queue.csv").read_text(encoding="utf-8-sig")
    json_payload = json.loads(
        (tmp_path / "out" / "final_evidence_fill_queue.json").read_text(encoding="utf-8")
    )

    assert "Final evidence fill queue" in markdown
    assert "PAYMENT_APPROVAL_BUNDLE" in markdown
    assert "PAYMENT_APPROVAL_BUNDLE::70" in markdown
    assert "operator_result, reviewer, reviewed_at" in markdown
    assert "operator_result" in markdown
    assert "--execute・支払実行・RK10 ButtonRun" in markdown
    assert "does not approve completion" in markdown
    assert "PAYMENT_APPROVAL_BUNDLE" in csv_text
    assert json_payload["active_queue_count"] == 1
    assert (tmp_path / "out" / "final_evidence_fill_queue.md.numbered").exists()
    assert (tmp_path / "out" / "final_evidence_fill_queue.csv.numbered").exists()
