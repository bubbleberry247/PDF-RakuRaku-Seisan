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


def test_completion_simulation_filters_scope_excluded_packet_rows(tmp_path: Path) -> None:
    module = load_module()
    source_reports = tmp_path / "source_reports"
    evidence_dir = source_reports / "evidence" / "scenario_47"
    excluded_evidence_dir = source_reports / "evidence" / "scenario_43"
    evidence_dir.mkdir(parents=True)
    excluded_evidence_dir.mkdir(parents=True)
    packet_dir = source_reports / "goal_execution_packet_20260620"
    packet_csv = packet_dir / "business_data_approval_bundle.csv"
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
    scope_exclusions_json = tmp_path / "scope_exclusions.json"
    scope_exclusions_json.write_text(
        '{"exclusions":[{"scenario":"43","active":true}]}',
        encoding="utf-8",
    )
    packet_fields = [
        "bundle",
        "scenario",
        "operator_result",
        "evidence_path",
        "reviewer",
        "reviewed_at",
    ]
    write_csv(
        packet_csv,
        packet_fields,
        [
            {
                "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                "scenario": "43",
                "operator_result": "",
                "evidence_path": str(excluded_evidence_dir),
                "reviewer": "",
                "reviewed_at": "",
            },
            {
                "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                "scenario": "47",
                "operator_result": "",
                "evidence_path": str(evidence_dir),
                "reviewer": "",
                "reviewed_at": "",
            },
        ],
    )
    write_csv(
        unified_csv,
        [
            "bundle",
            "scenario",
            "final_evidence_path",
            "operator_result",
            "reviewer",
            "reviewed_at",
        ],
        [
            {
                "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                "scenario": "47",
                "final_evidence_path": str(evidence_dir),
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
    )
    write_csv(
        remaining_csv,
        [
            "bundle",
            "scenario",
            "operator_result",
            "reviewer",
            "reviewed_at",
            "source_packet_csv",
            "source_unified_input_csv",
        ],
        [
            {
                "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                "scenario": "47",
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
        ["bundle", "operator_result", "evidence_path", "reviewer", "reviewed_at"],
        [],
    )

    payload = module.build_payload(
        remaining_input_csv=remaining_csv,
        packet_dir=packet_dir,
        unified_input_csv=unified_csv,
        bundle_sheet=bundle_sheet,
        out_dir=tmp_path / "simulation",
        reviewed_at="2026-06-23T05:20:00",
        scope_exclusions_json=scope_exclusions_json,
    )

    assert payload["simulation_passed"] is True
    assert payload["validation_row_count"] == 1
    assert payload["validation_payload"]["raw_row_count"] == 2
    assert payload["validation_payload"]["excluded_row_count"] == 1
    assert payload["validation_payload"]["excluded_rows"][0]["scenario"] == "43"
