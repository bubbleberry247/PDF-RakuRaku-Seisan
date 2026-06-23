import json
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_remaining_approval_next_steps_20260621.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_remaining_approval_next_steps_20260621", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_build_payload_orders_active_bundles_and_excludes_outlook_without_sync_status() -> None:
    module = load_module()
    operator_prefill = {
        "rows": [
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "owner": "PC/Outlook管理者",
                "scenarios": "12/13",
                "current_queue_rank": "",
                "current_status": "OUTLOOK_COM_READY",
                "supporting_input_paths": r"C:\outlook.ps1",
                "target_intake_path": r"C:\outlook_intake.csv",
                "next_action": "already done",
            },
            {
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "owner": "支払承認者",
                "scenarios": "70",
                "current_queue_rank": "3",
                "current_status": "WAITING_OPERATOR_OR_BUSINESS_APPROVAL",
                "supporting_input_paths": (
                    r"C:\s70_prefill.csv / C:\second.csv"
                ),
                "suggested_scenario_folders": r"C:\final\scenario_70",
                "target_intake_path": r"C:\payment_intake.csv",
                "filename_examples": "scenario_70_safe_run_log_YYYYMMDD_HHMMSS.txt",
                "next_action": "confirm-preview only",
            },
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "owner": "業務担当者",
                "scenarios": "44",
                "current_queue_rank": "2",
                "current_status": "WAITING_OPERATOR_OR_BUSINESS_APPROVAL",
                "supporting_input_paths": r"C:\s44_next_steps.md",
                "suggested_scenario_folders": r"C:\final\scenario_44",
                "target_intake_path": r"C:\review_intake.csv",
                "filename_examples": "scenario_44_safe_run_log_YYYYMMDD_HHMMSS.txt",
                "next_action": "review OK/NG",
            },
        ]
    }
    next_queue = {
        "rows": [
            {
                "rank": 2,
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "forbidden": "review未了の登録",
                "after_action_command": "python fixed_runner.py",
            },
            {
                "rank": 3,
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "forbidden": "--execute・支払実行・RK10 ButtonRun",
                "after_action_command": "python fixed_runner.py",
            },
        ]
    }
    rows = module.build_rows(operator_prefill, next_queue)

    assert [row.bundle for row in rows] == [
        "BUSINESS_REVIEW_BUNDLE",
        "PAYMENT_APPROVAL_BUNDLE",
        "OUTLOOK_COM_BUNDLE",
    ]
    assert rows[0].first_input_path == r"C:\s44_next_steps.md"
    assert rows[1].first_input_path == r"C:\s70_prefill.csv"
    assert rows[1].additional_input_count == 1
    assert rows[1].all_input_paths == r"C:\s70_prefill.csv / C:\second.csv"
    assert rows[1].forbidden == "--execute・支払実行・RK10 ButtonRun"
    assert rows[1].unified_entry_keys == "PAYMENT_APPROVAL_BUNDLE::70"
    assert rows[2].first_input_path == r"C:\outlook_intake.csv"
    assert r"C:\outlook.ps1" not in rows[2].all_input_paths
    assert rows[2].active is False


def test_build_rows_keeps_outlook_active_when_bundle_sync_not_ready() -> None:
    module = load_module()
    operator_prefill = {
        "rows": [
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "owner": "PC/Outlook管理者",
                "scenarios": "12/13",
                "current_queue_rank": "",
                "current_status": "OUTLOOK_COM_READY",
                "supporting_input_paths": r"C:\outlook.ps1",
                "suggested_scenario_folders": r"C:\final\scenario_12_13",
                "target_intake_path": r"C:\outlook_intake.csv",
                "next_action": "fill operator fields",
            }
        ]
    }
    bundle_sync = {
        "results": [
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "ready_to_sync": False,
                "blockers": "OPERATOR_RESULT_BLANK, REVIEWER_BLANK, REVIEWED_AT_BLANK",
            }
        ]
    }

    rows = module.build_rows(operator_prefill, {"rows": []}, bundle_sync)

    assert rows[0].bundle == "OUTLOOK_COM_BUNDLE"
    assert rows[0].active is True
    assert rows[0].first_input_path == r"C:\outlook_intake.csv"
    assert rows[0].all_input_paths == (
        r"C:\outlook_intake.csv / C:\final\scenario_12_13"
    )
    assert r"C:\outlook.ps1" not in rows[0].all_input_paths


def test_build_rows_excludes_outlook_when_bundle_sync_ready() -> None:
    module = load_module()
    operator_prefill = {
        "rows": [
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "owner": "PC/Outlook管理者",
                "scenarios": "12/13",
                "current_queue_rank": "",
                "current_status": "OUTLOOK_COM_READY",
                "supporting_input_paths": r"C:\outlook.ps1",
                "target_intake_path": r"C:\outlook_intake.csv",
            }
        ]
    }
    bundle_sync = {
        "results": [
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "ready_to_sync": True,
                "blockers": "",
            }
        ]
    }

    rows = module.build_rows(operator_prefill, {"rows": []}, bundle_sync)

    assert rows[0].active is False


def test_write_outputs_creates_markdown_json_csv_and_numbered(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    operator_path = tmp_path / "operator.json"
    queue_path = tmp_path / "queue.json"
    gate_path = tmp_path / "gate.json"
    bundle_sync_path = tmp_path / "bundle_sync.json"
    out_dir = tmp_path / "out"
    bundle_pack_root = tmp_path / "bundle_packs"
    supporting_dir = (
        bundle_pack_root
        / "payment_approval_bundle"
        / "supporting_materials"
        / "scenario_70_operator_decision_sheet_20260622"
    )
    supporting_dir.mkdir(parents=True)
    (supporting_dir / "report.md").write_text("ok", encoding="utf-8")
    monkeypatch.setattr(module, "DEFAULT_BUNDLE_PACK_ROOT", bundle_pack_root)
    write_json(
        operator_path,
        {
            "rows": [
                {
                    "bundle": "PAYMENT_APPROVAL_BUNDLE",
                    "owner": "支払承認者",
                    "scenarios": "70",
                    "current_queue_rank": "3",
                    "current_status": "WAITING_OPERATOR_OR_BUSINESS_APPROVAL",
                    "supporting_input_paths": r"C:\s70_prefill.csv",
                    "suggested_scenario_folders": r"C:\final\scenario_70",
                    "target_intake_path": r"C:\payment_intake.csv",
                    "filename_examples": "scenario_70_safe_run_log_YYYYMMDD_HHMMSS.txt",
                    "next_action": "expected_count/amountを記録",
                }
            ]
        },
    )
    write_json(
        queue_path,
        {
            "rows": [
                {
                    "rank": 3,
                    "bundle": "PAYMENT_APPROVAL_BUNDLE",
                    "forbidden": "--execute・支払実行・RK10 ButtonRun",
                    "after_action_command": "python fixed_runner.py",
                }
            ]
        },
    )
    write_json(gate_path, {"final_goal_complete": False})
    write_json(bundle_sync_path, {"results": []})

    payload = module.build_payload(operator_path, queue_path, gate_path, bundle_sync_path)
    module.write_outputs(payload, out_dir)

    markdown = (out_dir / "remaining_approval_next_steps.md").read_text(encoding="utf-8")
    csv_text = (out_dir / "remaining_approval_next_steps.csv").read_text(encoding="utf-8-sig")
    json_payload = json.loads(
        (out_dir / "remaining_approval_next_steps.json").read_text(encoding="utf-8")
    )
    start_here = (
        out_dir
        / "active_bundle_start_here"
        / "payment_approval_bundle_START_HERE.md"
    )
    start_here_text = start_here.read_text(encoding="utf-8")

    assert payload["active_bundle_count"] == 1
    assert payload["next_active_bundle"] == "PAYMENT_APPROVAL_BUNDLE"
    assert "C:\\s70_prefill.csv" in markdown
    assert str(start_here) in markdown
    assert "--execute・支払実行・RK10 ButtonRun" in markdown
    assert "PAYMENT_APPROVAL_BUNDLE" in csv_text
    assert json_payload["rows"][0]["start_here_path"] == str(start_here)
    assert json_payload["bundle_sync_json"] == str(bundle_sync_path)
    assert "unified_final_evidence_input.csv" in json_payload["unified_input_csv"]
    assert "next_bundle_minimum_input_packet_index.md.numbered" in json_payload[
        "minimum_input_index"
    ]
    assert "Minimum input packet index" in markdown
    assert "next_bundle_minimum_input_packet_index.md.numbered" in markdown
    assert "## 1. Complete Input Files" in start_here_text
    assert "## 1.5 Prepared Supporting Materials" in start_here_text
    assert str(supporting_dir) in start_here_text
    assert "## 0. Minimum Input Shortcut" in start_here_text
    assert "unified_input_csv" in start_here_text
    assert "PAYMENT_APPROVAL_BUNDLE::70" in start_here_text
    assert "fill_only: `operator_result`, `reviewer`, `reviewed_at`" in start_here_text
    assert "C:\\s70_prefill.csv" in start_here_text
    assert "required_fields" in start_here_text
    assert (out_dir / "remaining_approval_next_steps.json").exists()
    assert (out_dir / "remaining_approval_next_steps.md.numbered").exists()
    assert (out_dir / "remaining_approval_next_steps.csv.numbered").exists()
    assert Path(str(start_here) + ".numbered").exists()
