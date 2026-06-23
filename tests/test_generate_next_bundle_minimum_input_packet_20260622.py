import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_next_bundle_minimum_input_packet_20260622.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_next_bundle_minimum_input_packet_20260622",
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


def test_build_payload_selects_active_bundle_without_prefilling_approval(tmp_path: Path) -> None:
    module = load_module()
    fill_queue = tmp_path / "final_evidence_fill_queue.csv"
    write_csv(
        fill_queue,
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenarios": "44",
                "owner": "業務担当者",
                "active": "True",
                "unified_entry_keys": "BUSINESS_REVIEW_BUNDLE::44",
                "suggested_final_evidence_path": str(tmp_path / "final" / "scenario_44"),
                "unified_input_csv": str(tmp_path / "unified.csv"),
                "target_intake_path": str(tmp_path / "intake.csv"),
                "start_here_path": str(tmp_path / "START_HERE.md"),
                "forbidden": "review未了のままRakuraku登録",
                "after_action_command": "python fixed_runner.py",
            }
        ],
    )

    payload = module.build_payload(fill_queue, tmp_path / "packs")

    assert payload["selected_bundle"] == "BUSINESS_REVIEW_BUNDLE"
    assert payload["selected_scenarios"] == "44"
    assert payload["operator_fields_prefilled"] == 0
    row = payload["rows"][0]
    assert row["entry_key"] == "BUSINESS_REVIEW_BUNDLE::44"
    assert row["operator_result"] == ""
    assert row["reviewer"] == ""
    assert row["reviewed_at"] == ""
    assert row["allowed_operator_result_values"] == "OK / NG / HOLD"
    assert row["do_not_change"] == "final_evidence_path unless the evidence folder changes"


def test_write_outputs_creates_minimum_csv_and_numbered_report(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-22T21:30:00",
        "safety": "operator aid only",
        "selected_bundle": "BUSINESS_REVIEW_BUNDLE",
        "selected_scenarios": "44",
        "row_count": 1,
        "operator_fields_prefilled": 0,
        "blank_operator_fields": ["operator_result", "reviewer", "reviewed_at"],
        "output_dir": str(tmp_path / "out"),
        "source_fill_queue_csv": str(tmp_path / "fill.csv"),
        "rows": [
            {
                "entry_key": "BUSINESS_REVIEW_BUNDLE::44",
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "final_evidence_path": str(tmp_path / "final"),
                "source_unified_input_csv": str(tmp_path / "unified.csv"),
                "source_bundle_intake_csv": str(tmp_path / "intake.csv"),
                "start_here_path": str(tmp_path / "START_HERE.md"),
                "allowed_operator_result_values": "OK / NG / HOLD",
                "hard_stop": "review未了",
                "do_not_change": "final_evidence_path unless the evidence folder changes",
                "after_action_command": "python fixed_runner.py",
            }
        ],
    }

    out_dir = tmp_path / "out"
    module.write_outputs(payload, out_dir)

    csv_text = (out_dir / "minimum_input.csv").read_text(encoding="utf-8-sig")
    markdown = (out_dir / "minimum_input_packet.md").read_text(encoding="utf-8")
    assert "operator_result,reviewer,reviewed_at" in csv_text
    assert "BUSINESS_REVIEW_BUNDLE::44" in csv_text
    assert "Fill only `operator_result`, `reviewer`, and `reviewed_at`" in markdown
    assert (out_dir / "minimum_input_packet.json").exists()
    assert (out_dir / "minimum_input_packet.md.numbered").exists()
    assert (out_dir / "minimum_input.csv.numbered").exists()


def test_build_all_active_payloads_keeps_operator_fields_blank(tmp_path: Path) -> None:
    module = load_module()
    fill_queue = tmp_path / "final_evidence_fill_queue.csv"
    write_csv(
        fill_queue,
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenarios": "44",
                "owner": "業務担当者",
                "active": "True",
                "unified_entry_keys": "BUSINESS_REVIEW_BUNDLE::44",
                "suggested_final_evidence_path": str(tmp_path / "final" / "scenario_44"),
                "unified_input_csv": str(tmp_path / "unified.csv"),
                "target_intake_path": str(tmp_path / "business_review" / "intake.csv"),
                "start_here_path": str(tmp_path / "business_review_START_HERE.md"),
                "forbidden": "review未了のままRakuraku登録",
                "after_action_command": "python fixed_runner.py",
            },
            {
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenarios": "70",
                "owner": "経理担当者",
                "active": "True",
                "unified_entry_keys": "PAYMENT_APPROVAL_BUNDLE::70",
                "suggested_final_evidence_path": str(tmp_path / "final" / "scenario_70"),
                "unified_input_csv": str(tmp_path / "unified.csv"),
                "target_intake_path": str(tmp_path / "payment" / "intake.csv"),
                "start_here_path": str(tmp_path / "payment_START_HERE.md"),
                "forbidden": "payment承認前の支払実行",
                "after_action_command": "python fixed_runner.py",
            },
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "scenarios": "12/13",
                "owner": "メール担当者",
                "active": "False",
                "unified_entry_keys": "OUTLOOK_COM_BUNDLE::12/13",
                "suggested_final_evidence_path": str(tmp_path / "final" / "scenario_12_13"),
                "unified_input_csv": str(tmp_path / "unified.csv"),
                "target_intake_path": str(tmp_path / "outlook" / "intake.csv"),
                "start_here_path": "",
                "forbidden": "実送信",
                "after_action_command": "python fixed_runner.py",
            },
        ],
    )

    payloads = module.build_all_active_payloads(fill_queue, tmp_path / "packs")

    assert [payload["selected_bundle"] for payload in payloads] == [
        "BUSINESS_REVIEW_BUNDLE",
        "PAYMENT_APPROVAL_BUNDLE",
    ]
    assert payloads[0]["output_dir"].endswith(
        "business_review_bundle\\supporting_materials\\scenario_44_minimum_input_packet_20260622"
    )
    assert payloads[1]["output_dir"].endswith(
        "payment_approval_bundle\\supporting_materials\\payment_approval_minimum_input_packet_20260622"
    )
    for payload in payloads:
        assert payload["operator_fields_prefilled"] == 0
        for row in payload["rows"]:
            assert row["operator_result"] == ""
            assert row["reviewer"] == ""
            assert row["reviewed_at"] == ""


def test_write_all_active_index_creates_canonical_packet_index(tmp_path: Path) -> None:
    module = load_module()
    payloads = [
        {
            "generated_at": "2026-06-23T03:00:00",
            "safety": "operator aid only",
            "selected_bundle": "BUSINESS_REVIEW_BUNDLE",
            "selected_scenarios": "44",
            "row_count": 1,
            "operator_fields_prefilled": 0,
            "blank_operator_fields": ["operator_result", "reviewer", "reviewed_at"],
            "output_dir": str(tmp_path / "business_review_packet"),
            "source_fill_queue_csv": str(tmp_path / "fill.csv"),
            "rows": [],
        },
        {
            "generated_at": "2026-06-23T03:00:00",
            "safety": "operator aid only",
            "selected_bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
            "selected_scenarios": "37, 38",
            "row_count": 2,
            "operator_fields_prefilled": 0,
            "blank_operator_fields": ["operator_result", "reviewer", "reviewed_at"],
            "output_dir": str(tmp_path / "rk10_packet"),
            "source_fill_queue_csv": str(tmp_path / "fill.csv"),
            "rows": [],
        },
    ]

    out_dir = tmp_path / "index"
    module.write_all_active_index(payloads, out_dir)

    index_json = json.loads(
        (out_dir / "next_bundle_minimum_input_packet_index.json").read_text(
            encoding="utf-8",
        )
    )
    index_md = (out_dir / "next_bundle_minimum_input_packet_index.md").read_text(
        encoding="utf-8",
    )

    assert index_json["packet_count"] == 2
    assert index_json["operator_fields_prefilled"] == 0
    assert index_json["blank_operator_fields"] == [
        "operator_result",
        "reviewer",
        "reviewed_at",
    ]
    assert index_json["packets"][0]["minimum_input_csv"].endswith("minimum_input.csv")
    assert "RPA開発版AI付き" in index_md
    assert "press OK only" in index_md
    assert (out_dir / "next_bundle_minimum_input_packet_index.md.numbered").exists()
