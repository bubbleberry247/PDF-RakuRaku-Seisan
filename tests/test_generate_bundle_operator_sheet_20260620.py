import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_bundle_operator_sheet_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_bundle_operator_sheet_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_packet(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "packets": [
                    {
                        "bundle": "BUSINESS_REVIEW_BUNDLE",
                        "owner": "業務担当者",
                        "scenarios": "44",
                        "approval_scope": "spot check",
                        "allowed_operations": "shadow only",
                        "evidence_to_capture": "csv",
                        "hard_stops": "Rakuraku",
                        "csv_path": r"C:\packet\business_review_bundle.csv",
                    },
                    {
                        "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                        "owner": "RK10操作担当者",
                        "scenarios": "37, 38",
                        "approval_scope": "open/build",
                        "allowed_operations": "safe runtime",
                        "evidence_to_capture": "logs",
                        "hard_stops": "ButtonRun",
                        "csv_path": r"C:\packet\rk10_editor_runtime_bundle.csv",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_build_payload_creates_one_row_per_bundle(tmp_path: Path) -> None:
    module = load_module()
    packet_path = tmp_path / "packet.json"
    write_packet(packet_path)

    evidence_pack_dir = tmp_path / "packs"
    payload = module.build_payload(packet_path, tmp_path, evidence_pack_dir)

    assert payload["bundle_count"] == 2
    assert payload["needs_attention_bundle_count"] == 2
    assert payload["evidence_pack_dir"] == str(evidence_pack_dir)
    assert payload["rows"][0]["bundle"] == "BUSINESS_REVIEW_BUNDLE"
    assert payload["rows"][0]["prepared_evidence_pack_path"].endswith("business_review_bundle")
    assert payload["rows"][0]["temporary_save_created"] == ""
    assert payload["rows"][0]["created_data_cleanup_evidence_path"] == ""
    assert payload["rows"][1]["scenario_count"] == 2


def test_build_rows_preserves_existing_operator_fields(tmp_path: Path) -> None:
    module = load_module()
    packet_path = tmp_path / "packet.json"
    write_packet(packet_path)
    sheet_path = tmp_path / "bundle_operator_sheet.csv"
    sheet_path.write_text(
        "\ufeffbundle,operator_result,evidence_path,reviewer,reviewed_at,"
        "rakuraku_customer_login_used,temporary_save_created,created_data_cleanup_status,"
        "created_data_cleanup_evidence_path,cleanup_reviewer,cleanup_reviewed_at,notes\n"
        "BUSINESS_REVIEW_BUNDLE,OK,C:\\evidence\\bundle,reviewer,2026-06-20,"
        "YES,YES,削除済,C:\\evidence\\cleanup.log,reviewer,2026-06-20,done\n",
        encoding="utf-8",
    )

    payload = module.build_payload(packet_path, tmp_path)

    row = payload["rows"][0]
    assert row["operator_result"] == "OK"
    assert row["evidence_path"] == r"C:\evidence\bundle"
    assert row["reviewer"] == "reviewer"
    assert row["reviewed_at"] == "2026-06-20"
    assert row["temporary_save_created"] == "YES"
    assert row["created_data_cleanup_status"] == "削除済"
    assert row["created_data_cleanup_evidence_path"] == r"C:\evidence\cleanup.log"
    assert row["notes"] == "done"


def test_count_complete_bundle_rows_does_not_require_cleanup_when_temporary_save_created(tmp_path: Path) -> None:
    module = load_module()
    packet_path = tmp_path / "packet.json"
    write_packet(packet_path)
    sheet_path = tmp_path / "bundle_operator_sheet.csv"
    sheet_path.write_text(
        "\ufeffbundle,operator_result,evidence_path,reviewer,reviewed_at,"
        "rakuraku_customer_login_used,temporary_save_created,notes\n"
        "BUSINESS_REVIEW_BUNDLE,OK,C:\\evidence\\bundle,reviewer,2026-06-20,YES,YES,done\n",
        encoding="utf-8",
    )

    payload = module.build_payload(packet_path, tmp_path)

    assert payload["complete_bundle_count"] == 1
    assert payload["needs_attention_bundle_count"] == 1


def test_write_csv_outputs_bundle_sheet(tmp_path: Path) -> None:
    module = load_module()
    packet_path = tmp_path / "packet.json"
    write_packet(packet_path)
    payload = module.build_payload(packet_path, tmp_path)
    rows = [module.BundleSheetRow(**row) for row in payload["rows"]]
    csv_path = tmp_path / "bundle_operator_sheet.csv"

    module.write_csv(rows, csv_path)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[0]["bundle"] == "BUSINESS_REVIEW_BUNDLE"
    assert csv_rows[0]["prepared_evidence_pack_path"].endswith("business_review_bundle")
    assert "created_data_cleanup_evidence_path" in csv_rows[0]
    assert csv_rows[1]["scenarios"] == "37, 38"


def test_build_markdown_explains_six_row_input(tmp_path: Path) -> None:
    module = load_module()
    packet_path = tmp_path / "packet.json"
    write_packet(packet_path)
    payload = module.build_payload(packet_path, tmp_path)

    markdown = module.build_markdown(payload)

    assert "# 6束オペレーター入力シート 2026-06-20" in markdown
    assert "15シナリオ個別ではなく、この6行だけ" in markdown
    assert "prepared_evidence_pack_path" in markdown
    assert "削除証跡は承認ゲートの必須条件にしない" in markdown
