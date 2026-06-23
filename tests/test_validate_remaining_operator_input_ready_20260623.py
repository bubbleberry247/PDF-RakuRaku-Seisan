import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "validate_remaining_operator_input_ready_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "validate_remaining_operator_input_ready_20260623",
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


def write_empty_remaining_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "bundle",
        "scenario",
        "operator_result",
        "reviewer",
        "reviewed_at",
        "evidence_path",
        "latest_evidence_file",
        "source_packet_csv",
        "source_unified_input_csv",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()


def create_ready_support_files(tmp_path: Path) -> dict[str, Path]:
    report_root = tmp_path / "reports"
    evidence_path = report_root / "evidence" / "scenario_44"
    latest_evidence_file = evidence_path / "latest_evidence.txt"
    source_packet_csv = report_root / "packet" / "business_review_bundle.csv"
    source_unified_input_csv = report_root / "unified" / "unified_final_evidence_input.csv"
    evidence_path.mkdir(parents=True)
    latest_evidence_file.write_text("safe evidence", encoding="utf-8")
    target_row = {
        "bundle": "BUSINESS_REVIEW_BUNDLE",
        "scenario": "44",
        "operator_result": "",
        "reviewer": "",
        "reviewed_at": "",
    }
    write_csv(source_packet_csv, [target_row])
    write_csv(source_unified_input_csv, [target_row])
    return {
        "report_root": report_root,
        "evidence_path": evidence_path,
        "latest_evidence_file": latest_evidence_file,
        "source_packet_csv": source_packet_csv,
        "source_unified_input_csv": source_unified_input_csv,
    }


def base_remaining_row(paths: dict[str, Path]) -> dict[str, str]:
    return {
        "bundle": "BUSINESS_REVIEW_BUNDLE",
        "scenario": "44",
        "operator_result": "",
        "reviewer": "",
        "reviewed_at": "",
        "evidence_path": str(paths["evidence_path"]),
        "latest_evidence_file": str(paths["latest_evidence_file"]),
        "source_packet_csv": str(paths["source_packet_csv"]),
        "source_unified_input_csv": str(paths["source_unified_input_csv"]),
    }


def test_incomplete_operator_fields_are_not_ready(tmp_path: Path) -> None:
    module = load_module()
    paths = create_ready_support_files(tmp_path)
    remaining_input_csv = paths["report_root"] / "remaining_operator_input.csv"
    write_csv(remaining_input_csv, [base_remaining_row(paths)])

    payload = module.build_payload(
        remaining_input_csv,
        report_root=paths["report_root"],
    )

    assert payload["ready_to_run_after_fill"] is False
    assert payload["row_count"] == 1
    assert payload["not_ready_row_count"] == 1
    assert payload["missing_operator_field_row_count"] == 1
    assert "MISSING_OPERATOR_FIELDS" in payload["rows"][0]["blockers"]


def test_complete_approved_operator_fields_are_ready(tmp_path: Path) -> None:
    module = load_module()
    paths = create_ready_support_files(tmp_path)
    remaining_input_csv = paths["report_root"] / "remaining_operator_input.csv"
    row = base_remaining_row(paths)
    row.update(
        {
            "operator_result": "OK",
            "reviewer": "operator_a",
            "reviewed_at": "2026-06-23T09:30:00",
        }
    )
    write_csv(remaining_input_csv, [row])

    payload = module.build_payload(
        remaining_input_csv,
        report_root=paths["report_root"],
    )

    assert payload["ready_to_run_after_fill"] is True
    assert payload["complete_operator_row_count"] == 1
    assert payload["approved_operator_result_row_count"] == 1
    assert payload["not_ready_row_count"] == 0
    assert payload["rows"][0]["status"] == "READY_FOR_SYNC"


def test_hold_is_not_final_approved_result(tmp_path: Path) -> None:
    module = load_module()
    paths = create_ready_support_files(tmp_path)
    remaining_input_csv = paths["report_root"] / "remaining_operator_input.csv"
    row = base_remaining_row(paths)
    row.update(
        {
            "operator_result": "HOLD",
            "reviewer": "operator_a",
            "reviewed_at": "2026-06-23T09:30:00",
        }
    )
    write_csv(remaining_input_csv, [row])

    payload = module.build_payload(
        remaining_input_csv,
        report_root=paths["report_root"],
    )

    assert payload["ready_to_run_after_fill"] is False
    assert payload["non_approved_result_row_count"] == 1
    assert payload["not_ready_row_count"] == 1
    assert "NON_APPROVED_OPERATOR_RESULT" in payload["rows"][0]["blockers"]


def test_scope_exclusion_removes_scenario_from_active_counts(tmp_path: Path) -> None:
    module = load_module()
    paths = create_ready_support_files(tmp_path)
    remaining_input_csv = paths["report_root"] / "remaining_operator_input.csv"
    active_row = base_remaining_row(paths)
    active_row.update(
        {
            "operator_result": "OK",
            "reviewer": "operator_a",
            "reviewed_at": "2026-06-23T09:30:00",
        }
    )
    excluded_row = {
        **base_remaining_row(paths),
        "scenario": "43",
        "operator_result": "",
        "reviewer": "",
        "reviewed_at": "",
    }
    scope_exclusions_json = tmp_path / "scope_exclusions.json"
    scope_exclusions_json.write_text(
        json.dumps(
            {
                "exclusions": [
                    {
                        "scenario": "43",
                        "active": True,
                        "reason": "external fix",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    write_csv(remaining_input_csv, [excluded_row, active_row])

    payload = module.build_payload(
        remaining_input_csv,
        report_root=paths["report_root"],
        scope_exclusions_json=scope_exclusions_json,
    )

    assert payload["ready_to_run_after_fill"] is True
    assert payload["raw_row_count"] == 2
    assert payload["row_count"] == 1
    assert payload["excluded_row_count"] == 1
    assert payload["raw_not_ready_row_count"] == 1
    assert payload["not_ready_row_count"] == 0
    assert payload["rows"][0]["scenario"] == "44"
    assert payload["excluded_rows"][0]["scenario"] == "43"


def test_empty_existing_remaining_csv_means_no_remaining_rows(tmp_path: Path) -> None:
    module = load_module()
    remaining_input_csv = tmp_path / "reports" / "remaining_operator_input.csv"
    write_empty_remaining_csv(remaining_input_csv)

    payload = module.build_payload(
        remaining_input_csv,
        report_root=tmp_path / "reports",
    )

    assert payload["remaining_input_csv_exists"] is True
    assert payload["ready_to_run_after_fill"] is True
    assert payload["row_count"] == 0
    assert payload["not_ready_row_count"] == 0


def test_write_outputs_creates_json_markdown_and_numbered(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-23T09:30:00",
        "ready_to_run_after_fill": False,
        "overall_goal_complete": False,
        "safety": "read-only preflight",
        "remaining_input_csv": str(tmp_path / "remaining_operator_input.csv"),
        "row_count": 1,
        "raw_row_count": 1,
        "raw_not_ready_row_count": 1,
        "scope_exclusion_count": 0,
        "scope_exclusions_path": "",
        "scope_exclusions": [],
        "excluded_row_count": 0,
        "complete_operator_row_count": 0,
        "approved_operator_result_row_count": 0,
        "not_ready_row_count": 1,
        "missing_operator_field_row_count": 1,
        "non_approved_result_row_count": 0,
        "missing_evidence_row_count": 0,
        "unsafe_or_missing_target_row_count": 0,
        "rows": [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "status": "NOT_READY",
                "blockers": "MISSING_OPERATOR_FIELDS:operator_result,reviewer,reviewed_at",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        ],
        "excluded_rows": [],
    }

    module.write_outputs(payload, tmp_path / "out")

    json_path = tmp_path / "out" / "remaining_operator_input_ready_validation.json"
    md_path = tmp_path / "out" / "remaining_operator_input_ready_validation.md"
    assert json_path.exists()
    assert Path(str(json_path) + ".numbered").exists()
    assert md_path.exists()
    assert Path(str(md_path) + ".numbered").exists()
    written_payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")
    assert written_payload["ready_to_run_after_fill"] is False
    assert "HOLD" in markdown
    assert "MISSING_OPERATOR_FIELDS" in markdown
