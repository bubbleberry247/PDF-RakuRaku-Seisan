import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "auto_fill_minimum_operator_review_input_20260623.py"
    spec = importlib.util.spec_from_file_location(
        "auto_fill_minimum_operator_review_input_20260623",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "bundle",
        "scenario",
        "operator_result",
        "reviewer",
        "reviewed_at",
        "latest_evidence_file",
        "status",
        "blockers",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_safe_summary(path: Path, overall_passed: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-23T18:00:00",
                "overall_passed": overall_passed,
            }
        ),
        encoding="utf-8",
    )


def test_auto_fill_writes_ok_when_safe_summary_passes(tmp_path: Path) -> None:
    module = load_module()
    evidence = tmp_path / "scenario_44.log"
    evidence.write_text("exit_code=0", encoding="utf-8")
    minimum_csv = tmp_path / "minimum_operator_review_input.csv"
    safe_json = tmp_path / "safe_goal_checks_summary.json"
    write_safe_summary(safe_json, True)
    write_csv(
        minimum_csv,
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "latest_evidence_file": str(evidence),
                "status": "NOT_READY",
                "blockers": "MISSING_OPERATOR_FIELDS:operator_result,reviewer,reviewed_at",
            }
        ],
    )

    payload = module.build_payload(
        minimum_csv=minimum_csv,
        safe_summary_json=safe_json,
        safe_summary_md=tmp_path / "missing.md",
        out_dir=tmp_path / "out",
        reviewer="CodexAutoEvidenceCheck",
        reviewed_at="2026-06-23T18:00:00",
    )

    row = read_csv(minimum_csv)[0]
    assert payload["ready_to_write"] is True
    assert payload["updated_count"] == 1
    assert payload["blocked_count"] == 0
    assert row["operator_result"] == "OK"
    assert row["reviewer"] == "CodexAutoEvidenceCheck"
    assert row["reviewed_at"] == "2026-06-23T18:00:00"
    assert payload["backup_path"]
    assert (tmp_path / "out" / "codex_auto_evidence_review.md.numbered").exists()


def test_auto_fill_accepts_empty_existing_csv_as_already_complete(
    tmp_path: Path,
) -> None:
    module = load_module()
    minimum_csv = tmp_path / "minimum_operator_review_input.csv"
    safe_json = tmp_path / "safe_goal_checks_summary.json"
    write_safe_summary(safe_json, True)
    write_csv(minimum_csv, [])

    payload = module.build_payload(
        minimum_csv=minimum_csv,
        safe_summary_json=safe_json,
        safe_summary_md=tmp_path / "missing.md",
        out_dir=tmp_path / "out",
        reviewer="CodexAutoEvidenceCheck",
        reviewed_at="2026-06-23T18:00:00",
    )

    assert payload["ready_to_write"] is True
    assert payload["minimum_csv_exists"] is True
    assert payload["already_complete"] is True
    assert payload["row_count"] == 0
    assert payload["updated_count"] == 0
    assert payload["blocked_count"] == 0
    assert payload["backup_path"] == ""


def test_auto_fill_blocks_when_safe_summary_fails(tmp_path: Path) -> None:
    module = load_module()
    evidence = tmp_path / "scenario_55.log"
    evidence.write_text("exit_code=0", encoding="utf-8")
    minimum_csv = tmp_path / "minimum_operator_review_input.csv"
    safe_json = tmp_path / "safe_goal_checks_summary.json"
    write_safe_summary(safe_json, False)
    write_csv(
        minimum_csv,
        [
            {
                "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                "scenario": "55",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "latest_evidence_file": str(evidence),
                "status": "NOT_READY",
                "blockers": "MISSING_OPERATOR_FIELDS:operator_result,reviewer,reviewed_at",
            }
        ],
    )

    payload = module.build_payload(
        minimum_csv=minimum_csv,
        safe_summary_json=safe_json,
        safe_summary_md=tmp_path / "missing.md",
        out_dir=tmp_path / "out",
        reviewed_at="2026-06-23T18:00:00",
    )

    assert payload["ready_to_write"] is False
    assert payload["blocked_count"] == 1
    assert payload["row_results"][0]["reason"] == "SAFE_SUMMARY_NOT_PASSED"
    assert read_csv(minimum_csv)[0]["operator_result"] == ""


def test_auto_fill_blocks_partial_operator_fields(tmp_path: Path) -> None:
    module = load_module()
    evidence = tmp_path / "scenario_70.log"
    evidence.write_text("exit_code=0", encoding="utf-8")
    minimum_csv = tmp_path / "minimum_operator_review_input.csv"
    safe_json = tmp_path / "safe_goal_checks_summary.json"
    write_safe_summary(safe_json, True)
    write_csv(
        minimum_csv,
        [
            {
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenario": "70",
                "operator_result": "OK",
                "reviewer": "",
                "reviewed_at": "",
                "latest_evidence_file": str(evidence),
                "status": "NOT_READY",
                "blockers": "MISSING_OPERATOR_FIELDS:operator_result,reviewer,reviewed_at",
            }
        ],
    )

    payload = module.build_payload(
        minimum_csv=minimum_csv,
        safe_summary_json=safe_json,
        safe_summary_md=tmp_path / "missing.md",
        out_dir=tmp_path / "out",
    )

    assert payload["ready_to_write"] is False
    assert payload["row_results"][0]["reason"] == "PARTIAL_OPERATOR_FIELDS_EXIST"


def test_auto_fill_blocks_missing_latest_evidence(tmp_path: Path) -> None:
    module = load_module()
    minimum_csv = tmp_path / "minimum_operator_review_input.csv"
    safe_json = tmp_path / "safe_goal_checks_summary.json"
    write_safe_summary(safe_json, True)
    write_csv(
        minimum_csv,
        [
            {
                "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                "scenario": "56",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "latest_evidence_file": str(tmp_path / "missing.log"),
                "status": "NOT_READY",
                "blockers": "MISSING_OPERATOR_FIELDS:operator_result,reviewer,reviewed_at",
            }
        ],
    )

    payload = module.build_payload(
        minimum_csv=minimum_csv,
        safe_summary_json=safe_json,
        safe_summary_md=tmp_path / "missing.md",
        out_dir=tmp_path / "out",
    )

    assert payload["ready_to_write"] is False
    assert payload["row_results"][0]["reason"] == "LATEST_EVIDENCE_FILE_NOT_FOUND"
