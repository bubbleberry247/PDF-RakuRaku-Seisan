import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "simulate_remaining_operator_input_completion_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "simulate_remaining_operator_input_completion_20260623",
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


def test_simulation_completes_isolated_copies_without_touching_sources(
    tmp_path: Path,
) -> None:
    module = load_module()
    source_reports = tmp_path / "source_reports"
    evidence_dir = source_reports / "bundle_evidence_packs_20260620" / "business_review" / "scenario_44"
    evidence_dir.mkdir(parents=True)
    packet_dir = source_reports / "goal_execution_packet_20260620"
    packet_csv = packet_dir / "business_review_bundle.csv"
    unified_csv = (
        source_reports
        / "unified_final_evidence_intake_20260621"
        / "unified_final_evidence_input.csv"
    )
    remaining_csv = (
        source_reports
        / "remaining_operator_input_packet_20260623"
        / "remaining_operator_input.csv"
    )
    bundle_sheet = source_reports / "bundle_operator_sheet_20260620" / "bundle_operator_sheet.csv"
    write_csv(
        packet_csv,
        packet_fieldnames(),
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "operator_result": "",
                "evidence_path": str(evidence_dir),
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
                "final_evidence_path": str(evidence_dir),
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
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "source_packet_csv": str(packet_csv),
                "source_unified_input_csv": str(unified_csv),
            }
        ],
    )
    write_csv(
        bundle_sheet,
        [
            "bundle",
            "operator_result",
            "evidence_path",
            "reviewer",
            "reviewed_at",
        ],
        [],
    )

    payload = module.build_payload(
        remaining_input_csv=remaining_csv,
        packet_dir=packet_dir,
        unified_input_csv=unified_csv,
        bundle_sheet=bundle_sheet,
        out_dir=tmp_path / "simulation",
        reviewed_at="2026-06-23T05:20:00",
    )

    assert payload["simulation_passed"] is True
    assert payload["sample_completed_row_count"] == 1
    assert payload["sync_updated_cell_count"] == 6
    assert payload["validation_all_packet_rows_approved"] is True
    assert payload["validation_approved_row_count"] == 1
    assert payload["validation_needs_attention_count"] == 0
    assert payload["source_files_modified"] is False
    assert read_csv(packet_csv)[0]["operator_result"] == ""
    work_packet_csv = (
        tmp_path
        / "simulation"
        / "work"
        / "reports"
        / "goal_execution_packet_20260620"
        / "business_review_bundle.csv"
    )
    assert read_csv(work_packet_csv)[0]["operator_result"] == "OK"


def test_simulation_writes_summary_outputs(tmp_path: Path) -> None:
    module = load_module()
    source_reports = tmp_path / "source_reports"
    evidence_dir = source_reports / "evidence" / "scenario_70"
    evidence_dir.mkdir(parents=True)
    packet_dir = source_reports / "goal_execution_packet_20260620"
    packet_csv = packet_dir / "payment_approval_bundle.csv"
    unified_csv = (
        source_reports
        / "unified_final_evidence_intake_20260621"
        / "unified_final_evidence_input.csv"
    )
    remaining_csv = (
        source_reports
        / "remaining_operator_input_packet_20260623"
        / "remaining_operator_input.csv"
    )
    bundle_sheet = source_reports / "bundle_operator_sheet_20260620" / "bundle_operator_sheet.csv"
    write_csv(
        packet_csv,
        packet_fieldnames(),
        [
            {
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenario": "70",
                "operator_result": "",
                "evidence_path": str(evidence_dir),
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
                "final_evidence_path": str(evidence_dir),
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
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "source_packet_csv": str(packet_csv),
                "source_unified_input_csv": str(unified_csv),
            }
        ],
    )
    write_csv(
        bundle_sheet,
        [
            "bundle",
            "operator_result",
            "evidence_path",
            "reviewer",
            "reviewed_at",
        ],
        [],
    )
    out_dir = tmp_path / "simulation"
    payload = module.build_payload(
        remaining_csv,
        packet_dir,
        unified_csv,
        bundle_sheet,
        out_dir,
        reviewed_at="2026-06-23T05:20:00",
    )

    module.write_outputs(payload, out_dir)

    assert (out_dir / "remaining_operator_input_completion_simulation.json").exists()
    assert (out_dir / "remaining_operator_input_completion_simulation.md").exists()
    assert (out_dir / "remaining_operator_input_completion_simulation.md.numbered").exists()
    assert (out_dir / "sync" / "remaining_operator_input_packet_sync.md.numbered").exists()
    assert (out_dir / "validation" / "goal_execution_packet_validation.md.numbered").exists()
