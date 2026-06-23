import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "sync_execution_packet_candidate_evidence_paths_20260621.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "sync_execution_packet_candidate_evidence_paths_20260621",
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


def unified_fieldnames() -> list[str]:
    return [
        "entry_key",
        "bundle",
        "scenario",
        "final_evidence_path",
        "operator_result",
        "reviewer",
        "reviewed_at",
    ]


def packet_fieldnames() -> list[str]:
    return [
        "scenario",
        "bundle",
        "operator_result",
        "evidence_path",
        "reviewer",
        "reviewed_at",
    ]


def test_sync_prefills_blank_packet_evidence_path_only(tmp_path: Path) -> None:
    module = load_module()
    candidate_dir = tmp_path / "final_evidence" / "scenario_44"
    candidate_dir.mkdir(parents=True)
    unified_csv = tmp_path / "unified.csv"
    packet_dir = tmp_path / "packets"
    packet_csv = packet_dir / "business_review_bundle.csv"
    write_csv(
        unified_csv,
        unified_fieldnames(),
        [
            {
                "entry_key": "BUSINESS_REVIEW_BUNDLE::44",
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "final_evidence_path": str(candidate_dir),
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )
    write_csv(
        packet_csv,
        packet_fieldnames(),
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

    payload = module.build_payload(unified_csv, packet_dir, apply_updates=True)

    rows = read_csv(packet_csv)
    assert payload["updated_row_count"] == 1
    assert payload["changed_csv_count"] == 1
    assert rows[0]["evidence_path"] == str(candidate_dir)
    assert rows[0]["operator_result"] == ""
    assert rows[0]["reviewer"] == ""
    assert rows[0]["reviewed_at"] == ""


def test_sync_does_not_override_existing_packet_evidence_path(tmp_path: Path) -> None:
    module = load_module()
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    manual_dir = tmp_path / "manual"
    manual_dir.mkdir()
    unified_csv = tmp_path / "unified.csv"
    packet_dir = tmp_path / "packets"
    packet_csv = packet_dir / "payment_approval_bundle.csv"
    write_csv(
        unified_csv,
        unified_fieldnames(),
        [
            {
                "entry_key": "PAYMENT_APPROVAL_BUNDLE::70",
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenario": "70",
                "final_evidence_path": str(candidate_dir),
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )
    write_csv(
        packet_csv,
        packet_fieldnames(),
        [
            {
                "scenario": "70",
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "operator_result": "",
                "evidence_path": str(manual_dir),
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )

    payload = module.build_payload(unified_csv, packet_dir, apply_updates=True)

    rows = read_csv(packet_csv)
    assert payload["updated_row_count"] == 0
    assert rows[0]["evidence_path"] == str(manual_dir)


def test_sync_reports_missing_packet_csv_without_creating_approval(
    tmp_path: Path,
) -> None:
    module = load_module()
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    unified_csv = tmp_path / "unified.csv"
    packet_dir = tmp_path / "packets"
    write_csv(
        unified_csv,
        unified_fieldnames(),
        [
            {
                "entry_key": "PAID_AZURE_OCR_BUNDLE::71",
                "bundle": "PAID_AZURE_OCR_BUNDLE",
                "scenario": "71",
                "final_evidence_path": str(candidate_dir),
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )

    payload = module.build_payload(unified_csv, packet_dir, apply_updates=True)

    assert payload["updated_row_count"] == 0
    assert payload["missing_packet_csv_count"] == 1
    assert "paid_azure_ocr_bundle.csv" in payload["missing_packet_csvs"][0]
