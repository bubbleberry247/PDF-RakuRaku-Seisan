import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_goal_execution_packet_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_goal_execution_packet_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_board_payload() -> dict:
    return {
        "generated_at": "2026-06-20T00:00:00",
        "scenario_count": 2,
        "fixed_safe_runner": r"C:\python.exe -X utf8 C:\repo\tools\run_safe_goal_checks_20260620.py --s12-exit-code 2",
        "approval_bundles": [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "owner": "業務担当者",
                "scenarios": "44",
                "approval_scope": "spot check only",
                "still_forbidden": "rakuraku",
            },
            {
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "owner": "支払承認者",
                "scenarios": "70",
                "approval_scope": "confirm-preview only",
                "still_forbidden": "--execute",
            },
        ],
        "rows": [
            {
                "scenario": "44",
                "source": r"C:\evidence\s44.csv",
                "supplemental_evidence": r"C:\evidence\s44_shadow.md",
            },
            {"scenario": "70", "source": r"C:\evidence\s70.csv"},
        ],
    }


def test_build_packets_creates_one_csv_per_bundle(tmp_path: Path) -> None:
    module = load_module()

    packets = module.build_packets(sample_board_payload(), tmp_path)

    assert len(packets) == 2
    assert packets[0].bundle == "BUSINESS_REVIEW_BUNDLE"
    assert packets[0].csv_path.endswith("business_review_bundle.csv")
    assert "PDF processed" in packets[0].hard_stops
    assert "任意記録欄" in packets[0].cleanup_rule
    assert "必須条件にしない" in packets[0].cleanup_rule
    assert packets[0].supporting_input_paths.split(" / ")[0].endswith(
        "s44_business_review_single_entry_input.csv"
    )
    assert "s44_business_review_next_steps.md" in packets[0].supporting_input_paths
    assert "s44_business_review_bucket_decision_input.csv" in packets[0].supporting_input_paths
    assert "s44_business_review_priority_queue.csv" in packets[0].supporting_input_paths
    assert "s44_review_01_amount_zero_review.csv" in packets[0].supporting_input_paths


def test_write_packet_csvs_outputs_operator_fields(tmp_path: Path) -> None:
    module = load_module()
    packets = module.build_packets(sample_board_payload(), tmp_path)
    source_map = module.build_source_map(sample_board_payload())

    module.write_packet_csvs(packets, source_map)

    csv_path = tmp_path / "payment_approval_bundle.csv"
    assert csv_path.exists()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["scenario"] == "70"
    assert rows[0]["operator_result"] == ""
    assert rows[0]["source"] == r"C:\evidence\s70.csv"
    assert "s70_payment_confirmation_gate_checklist_prefill.csv" in rows[0]["supporting_input_paths"]
    assert rows[0]["current_safe_evidence"] == ""
    assert rows[0]["temporary_save_created"] == ""
    assert rows[0]["created_data_cleanup_evidence_path"] == ""


def test_supporting_input_paths_include_s71_environment_presence() -> None:
    module = load_module()

    paths = module.supporting_input_paths_for_bundle("PAID_AZURE_OCR_BUNDLE")

    assert "s71_azure_ocr_environment_presence.csv" in paths
    assert "s71_paid_azure_one_pdf_smoke_summary_template.json" in paths


def test_build_current_evidence_map_prefers_supplemental_evidence() -> None:
    module = load_module()

    current_evidence_map = module.build_current_evidence_map(sample_board_payload())

    assert current_evidence_map["44"] == r"C:\evidence\s44_shadow.md"
    assert current_evidence_map["70"] == r"C:\evidence\s70.csv"


def test_write_packet_csvs_preserves_existing_operator_fields(tmp_path: Path) -> None:
    module = load_module()
    packets = module.build_packets(sample_board_payload(), tmp_path)
    source_map = module.build_source_map(sample_board_payload())
    csv_path = tmp_path / "business_review_bundle.csv"
    csv_path.write_text(
        "\ufeffscenario,bundle,operator_result,evidence_path,reviewer,reviewed_at\n"
        "44,BUSINESS_REVIEW_BUNDLE,OK,C:\\evidence\\s44.log,reviewer,2026-06-20\n",
        encoding="utf-8",
    )

    module.write_packet_csvs(packets, source_map)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["operator_result"] == "OK"
    assert rows[0]["evidence_path"] == r"C:\evidence\s44.log"
    assert rows[0]["reviewer"] == "reviewer"
    assert rows[0]["reviewed_at"] == "2026-06-20"
    assert rows[0]["current_safe_evidence"] == ""
    assert "s44_business_review_single_entry_input.csv" in rows[0]["supporting_input_paths"]
    assert "s44_business_review_decision_input.csv" in rows[0]["supporting_input_paths"]
    assert "s44_business_review_bucket_decision_input.csv" in rows[0]["supporting_input_paths"]


def test_write_packet_csvs_preserves_cleanup_fields(tmp_path: Path) -> None:
    module = load_module()
    packets = module.build_packets(sample_board_payload(), tmp_path)
    source_map = module.build_source_map(sample_board_payload())
    csv_path = tmp_path / "business_review_bundle.csv"
    csv_path.write_text(
        "\ufeffscenario,bundle,operator_result,evidence_path,reviewer,reviewed_at,"
        "rakuraku_customer_login_used,temporary_save_created,created_data_cleanup_status,"
        "created_data_cleanup_evidence_path,cleanup_reviewer,cleanup_reviewed_at\n"
        "44,BUSINESS_REVIEW_BUNDLE,OK,C:\\evidence\\s44.log,reviewer,2026-06-20,"
        "YES,YES,削除済,C:\\evidence\\cleanup.log,reviewer,2026-06-20\n",
        encoding="utf-8",
    )

    module.write_packet_csvs(packets, source_map)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["rakuraku_customer_login_used"] == "YES"
    assert rows[0]["temporary_save_created"] == "YES"
    assert rows[0]["created_data_cleanup_status"] == "削除済"
    assert rows[0]["created_data_cleanup_evidence_path"] == r"C:\evidence\cleanup.log"
    assert "s44_review_02_amount_mismatch_review.csv" in rows[0]["supporting_input_paths"]


def test_build_markdown_lists_packet_csvs(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    monkeypatch.setattr(module, "build_board_payload", lambda _exit_code: sample_board_payload())
    payload = module.build_payload(2, tmp_path)

    markdown = module.build_markdown(payload)

    assert "# 目標実行パケット 2026-06-20" in markdown
    assert "BUSINESS_REVIEW_BUNDLE" in markdown
    assert "business_review_bundle.csv" in markdown
    assert "s44_business_review_priority_queue.csv" in markdown
    assert "削除証跡は承認ゲートの必須条件にしない" in markdown
