import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "sync_remaining_operator_input_packet_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "sync_remaining_operator_input_packet_20260623",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def packet_fieldnames() -> list[str]:
    return [
        "bundle",
        "scenario",
        "operator_result",
        "evidence_path",
        "reviewer",
        "reviewed_at",
    ]


def unified_fieldnames() -> list[str]:
    return [
        "bundle",
        "scenario",
        "final_evidence_path",
        "operator_result",
        "reviewer",
        "reviewed_at",
    ]


def remaining_fieldnames() -> list[str]:
    return [
        "bundle",
        "scenario",
        "operator_result",
        "reviewer",
        "reviewed_at",
        "source_packet_csv",
        "source_unified_input_csv",
    ]


def test_sync_complete_stamp_updates_packet_and_unified_csvs(tmp_path: Path) -> None:
    module = load_module()
    module.REPORTS = tmp_path
    packet_csv = tmp_path / "goal_execution_packet_20260620" / "business_review_bundle.csv"
    unified_csv = tmp_path / "unified_final_evidence_intake_20260621" / "unified.csv"
    remaining_csv = tmp_path / "remaining_operator_input.csv"
    write_csv(
        packet_csv,
        packet_fieldnames(),
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "operator_result": "",
                "evidence_path": str(tmp_path / "evidence"),
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )
    write_csv(
        unified_csv,
        unified_fieldnames(),
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "final_evidence_path": str(tmp_path / "evidence"),
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )
    write_csv(
        remaining_csv,
        remaining_fieldnames(),
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "operator_result": "OK",
                "reviewer": "operator_a",
                "reviewed_at": "2026-06-23T05:20:00",
                "source_packet_csv": str(packet_csv),
                "source_unified_input_csv": str(unified_csv),
            }
        ],
    )

    payload = module.build_payload(remaining_csv, apply_updates=True)

    packet_row = read_csv(packet_csv)[0]
    unified_row = read_csv(unified_csv)[0]
    assert payload["complete_input_row_count"] == 1
    assert payload["skipped_incomplete_row_count"] == 0
    assert payload["changed_target_csv_count"] == 2
    assert payload["updated_cell_count"] == 6
    assert packet_row["operator_result"] == "OK"
    assert packet_row["reviewer"] == "operator_a"
    assert packet_row["reviewed_at"] == "2026-06-23T05:20:00"
    assert unified_row["operator_result"] == "OK"
    assert unified_row["reviewer"] == "operator_a"
    assert unified_row["reviewed_at"] == "2026-06-23T05:20:00"


def test_sync_skips_incomplete_stamp(tmp_path: Path) -> None:
    module = load_module()
    module.REPORTS = tmp_path
    packet_csv = tmp_path / "goal_execution_packet_20260620" / "payment_approval_bundle.csv"
    unified_csv = tmp_path / "unified_final_evidence_intake_20260621" / "unified.csv"
    remaining_csv = tmp_path / "remaining_operator_input.csv"
    write_csv(
        packet_csv,
        packet_fieldnames(),
        [
            {
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenario": "70",
                "operator_result": "",
                "evidence_path": str(tmp_path / "evidence"),
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )
    write_csv(
        unified_csv,
        unified_fieldnames(),
        [
            {
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenario": "70",
                "final_evidence_path": str(tmp_path / "evidence"),
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )
    write_csv(
        remaining_csv,
        remaining_fieldnames(),
        [
            {
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenario": "70",
                "operator_result": "OK",
                "reviewer": "",
                "reviewed_at": "2026-06-23T05:20:00",
                "source_packet_csv": str(packet_csv),
                "source_unified_input_csv": str(unified_csv),
            }
        ],
    )

    payload = module.build_payload(remaining_csv, apply_updates=True)

    assert payload["complete_input_row_count"] == 0
    assert payload["skipped_incomplete_row_count"] == 1
    assert payload["changed_target_csv_count"] == 0
    assert read_csv(packet_csv)[0]["operator_result"] == ""
    assert read_csv(unified_csv)[0]["operator_result"] == ""


def test_sync_does_not_overwrite_conflicting_value(tmp_path: Path) -> None:
    module = load_module()
    module.REPORTS = tmp_path
    packet_csv = tmp_path / "goal_execution_packet_20260620" / "paid_azure_ocr_bundle.csv"
    unified_csv = tmp_path / "unified_final_evidence_intake_20260621" / "unified.csv"
    remaining_csv = tmp_path / "remaining_operator_input.csv"
    write_csv(
        packet_csv,
        packet_fieldnames(),
        [
            {
                "bundle": "PAID_AZURE_OCR_BUNDLE",
                "scenario": "71",
                "operator_result": "HOLD",
                "evidence_path": str(tmp_path / "evidence"),
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )
    write_csv(
        unified_csv,
        unified_fieldnames(),
        [
            {
                "bundle": "PAID_AZURE_OCR_BUNDLE",
                "scenario": "71",
                "final_evidence_path": str(tmp_path / "evidence"),
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )
    write_csv(
        remaining_csv,
        remaining_fieldnames(),
        [
            {
                "bundle": "PAID_AZURE_OCR_BUNDLE",
                "scenario": "71",
                "operator_result": "OK",
                "reviewer": "operator_a",
                "reviewed_at": "2026-06-23T05:20:00",
                "source_packet_csv": str(packet_csv),
                "source_unified_input_csv": str(unified_csv),
            }
        ],
    )

    payload = module.build_payload(remaining_csv, apply_updates=True)

    assert payload["conflict_count"] == 1
    assert read_csv(packet_csv)[0]["operator_result"] == "HOLD"
    assert read_csv(packet_csv)[0]["reviewer"] == ""
    assert read_csv(unified_csv)[0]["operator_result"] == "OK"
