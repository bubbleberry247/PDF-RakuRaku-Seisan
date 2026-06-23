import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "validate_goal_execution_packet_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("validate_goal_execution_packet_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_bundle_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "scenario",
        "bundle",
        "operator_result",
        "evidence_path",
        "reviewer",
        "reviewed_at",
        "rakuraku_customer_login_used",
        "temporary_save_created",
        "created_data_cleanup_status",
        "created_data_cleanup_evidence_path",
        "cleanup_reviewer",
        "cleanup_reviewed_at",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_payload_marks_blank_rows_as_needing_attention(tmp_path: Path) -> None:
    module = load_module()
    write_bundle_csv(
        tmp_path / "business_review_bundle.csv",
        [
            {
                "scenario": "44",
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "operator_result": "",
                "evidence_path": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )

    payload = module.build_payload(tmp_path, tmp_path / "missing_bundle_sheet.csv")

    assert payload["all_packet_rows_approved"] is False
    assert payload["packet_csv_count"] == 1
    assert payload["row_count"] == 1
    assert payload["needs_attention_count"] == 1
    assert payload["rows"][0]["status"] == "MISSING_OPERATOR_FIELDS"
    assert payload["rows"][0]["missing_fields"] == (
        "operator_result, evidence_path, reviewer, reviewed_at"
    )


def test_build_payload_accepts_ok_row_with_existing_evidence(tmp_path: Path) -> None:
    module = load_module()
    evidence_path = tmp_path / "evidence.log"
    evidence_path.write_text("ok", encoding="utf-8")
    write_bundle_csv(
        tmp_path / "payment_approval_bundle.csv",
        [
            {
                "scenario": "70",
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "operator_result": "OK",
                "evidence_path": str(evidence_path),
                "reviewer": "reviewer",
                "reviewed_at": "2026-06-20",
            }
        ],
    )

    payload = module.build_payload(tmp_path, tmp_path / "missing_bundle_sheet.csv")

    assert payload["all_packet_rows_approved"] is True
    assert payload["approved_row_count"] == 1
    assert payload["rows"][0]["status"] == "APPROVED_WITH_EVIDENCE"
    assert payload["rows"][0]["evidence_exists"] is True


def test_build_payload_approves_temp_save_row_without_cleanup_evidence(tmp_path: Path) -> None:
    module = load_module()
    evidence_path = tmp_path / "evidence.log"
    evidence_path.write_text("ok", encoding="utf-8")
    write_bundle_csv(
        tmp_path / "business_review_bundle.csv",
        [
            {
                "scenario": "44",
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "operator_result": "OK",
                "evidence_path": str(evidence_path),
                "reviewer": "reviewer",
                "reviewed_at": "2026-06-20",
                "rakuraku_customer_login_used": "YES",
                "temporary_save_created": "YES",
            }
        ],
    )

    payload = module.build_payload(tmp_path, tmp_path / "missing_bundle_sheet.csv")

    assert payload["all_packet_rows_approved"] is True
    assert payload["approved_row_count"] == 1
    assert payload["needs_attention_count"] == 0
    assert payload["rows"][0]["status"] == "APPROVED_WITH_EVIDENCE"
    assert payload["rows"][0]["missing_fields"] == ""


def test_build_payload_accepts_temp_save_when_cleanup_evidence_exists(tmp_path: Path) -> None:
    module = load_module()
    evidence_path = tmp_path / "evidence.log"
    evidence_path.write_text("ok", encoding="utf-8")
    cleanup_path = tmp_path / "cleanup.log"
    cleanup_path.write_text("deleted", encoding="utf-8")
    write_bundle_csv(
        tmp_path / "business_review_bundle.csv",
        [
            {
                "scenario": "44",
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "operator_result": "OK",
                "evidence_path": str(evidence_path),
                "reviewer": "reviewer",
                "reviewed_at": "2026-06-20",
                "rakuraku_customer_login_used": "YES",
                "temporary_save_created": "YES",
                "created_data_cleanup_status": "削除済",
                "created_data_cleanup_evidence_path": str(cleanup_path),
                "cleanup_reviewer": "reviewer",
                "cleanup_reviewed_at": "2026-06-20",
            }
        ],
    )

    payload = module.build_payload(tmp_path, tmp_path / "missing_bundle_sheet.csv")

    assert payload["all_packet_rows_approved"] is True
    assert payload["approved_row_count"] == 1
    assert payload["rows"][0]["status"] == "APPROVED_WITH_EVIDENCE"
    assert payload["rows"][0]["cleanup_evidence_exists"] is True


def test_build_payload_accepts_bundle_sheet_approval(tmp_path: Path) -> None:
    module = load_module()
    evidence_dir = tmp_path / "bundle_evidence"
    evidence_dir.mkdir()
    write_bundle_csv(
        tmp_path / "payment_approval_bundle.csv",
        [
            {
                "scenario": "70",
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "operator_result": "",
                "evidence_path": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )
    bundle_sheet = tmp_path / "bundle_operator_sheet.csv"
    bundle_sheet.write_text(
        "\ufeffbundle,operator_result,evidence_path,reviewer,reviewed_at\n"
        f"PAYMENT_APPROVAL_BUNDLE,OK,{evidence_dir},reviewer,2026-06-20\n",
        encoding="utf-8",
    )

    payload = module.build_payload(tmp_path, bundle_sheet)

    assert payload["all_packet_rows_approved"] is True
    assert payload["approved_bundle_count"] == 1
    assert payload["approved_row_count"] == 1
    assert payload["rows"][0]["status"] == "APPROVED_BY_BUNDLE_WITH_EVIDENCE"
    assert payload["rows"][0]["evidence_path"] == str(evidence_dir)


def test_build_attention_rows_lists_bundle_and_scenario_gaps(tmp_path: Path) -> None:
    module = load_module()
    write_bundle_csv(
        tmp_path / "payment_approval_bundle.csv",
        [
            {
                "scenario": "70",
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "operator_result": "",
                "evidence_path": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )
    bundle_sheet = tmp_path / "bundle_operator_sheet.csv"
    bundle_sheet.write_text(
        "\ufeffbundle,operator_result,evidence_path,reviewer,reviewed_at\n"
        "PAYMENT_APPROVAL_BUNDLE,,,,\n",
        encoding="utf-8",
    )
    payload = module.build_payload(tmp_path, bundle_sheet)

    rows = module.build_attention_rows(payload)

    assert len(rows) == 2
    assert rows[0].level == "bundle"
    assert rows[0].target_csv == str(bundle_sheet)
    assert rows[1].level == "scenario"
    assert rows[1].scenario == "70"
    assert "operator_result" in rows[1].missing_fields


def test_write_attention_csv_creates_operator_next_action_file(tmp_path: Path) -> None:
    module = load_module()
    attention_path = tmp_path / "attention.csv"
    rows = [
        module.AttentionRow(
            level="scenario",
            bundle="PAYMENT_APPROVAL_BUNDLE",
            scenario="70",
            status="MISSING_OPERATOR_FIELDS",
            missing_fields="operator_result, evidence_path",
            target_csv=str(tmp_path / "payment.csv"),
            bundle_sheet_path=str(tmp_path / "bundle.csv"),
            evidence_path="",
            cleanup_evidence_path="",
            next_action=module.next_attention_action("MISSING_OPERATOR_FIELDS"),
        )
    ]

    module.write_attention_csv(attention_path, rows)

    with attention_path.open("r", encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[0]["scenario"] == "70"
    assert "evidence_path" in csv_rows[0]["next_action"]


def test_build_markdown_lists_validation_rules(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "all_packet_rows_approved": False,
        "safety": "read-only",
        "packet_dir": str(tmp_path),
        "packet_csv_count": 0,
        "row_count": 0,
        "approved_row_count": 0,
        "needs_attention_count": 0,
        "missing_packet_dir": False,
        "bundle_sheet_path": str(tmp_path / "bundle_operator_sheet.csv"),
        "bundle_sheet_exists": False,
        "bundle_approval_count": 0,
        "approved_bundle_count": 0,
        "bundle_approvals": [],
        "rows": [],
    }

    markdown = module.build_markdown(payload)

    assert "# 目標実行パケット証跡検証 2026-06-20" in markdown
    assert "operator_result" in markdown
    assert "削除証跡は承認ゲートの必須条件にしない" in markdown
    assert "実メール・実印刷・支払実行・本番申請は行わない" in markdown
