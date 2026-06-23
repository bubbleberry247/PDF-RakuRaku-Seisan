import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "collect_s44_business_review_evidence_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("collect_s44_business_review_evidence_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_intake(path: Path) -> None:
    fieldnames = [
        "bundle",
        "scenario",
        "required_final_evidence",
        "hard_stops",
        "current_reference_evidence",
        "suggested_final_evidence_folder",
        "final_evidence_path",
        "required_update_fields",
        "operator_result",
        "reviewer",
        "reviewed_at",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "required_final_evidence": "OK/NG入力済みCSV",
                "hard_stops": "review未了の登録",
                "current_reference_evidence": r"C:\sample.md",
                "suggested_final_evidence_folder": r"C:\final\scenario_44",
                "required_update_fields": "final_evidence_path, operator_result, reviewer, reviewed_at",
            }
        )


def read_intake_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.DictReader(handle))


def test_build_result_waits_when_business_review_has_no_ok_rows(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot_check.csv"
    source_csv.write_text("confirm_ok,amount_estimate\n,100\n", encoding="utf-8")
    source_json = tmp_path / "s44.json"
    source_json.write_text(
        json.dumps(
            {
                "source_csv": str(source_csv),
                "row_count": 1,
                "ok_count": 0,
                "ng_count": 0,
                "blank_count": 1,
                "ready_for_shadow_handoff": False,
                "status": "HOLD_NO_OK_ROWS",
                "shadow_handoff": {"generated": False},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    intake_csv = tmp_path / "final_evidence_intake.csv"
    write_intake(intake_csv)

    result = module.build_result(source_json, intake_csv, tmp_path / "final_evidence" / "scenario_44")

    assert result.status == "WAITING_FOR_BUSINESS_REVIEW"
    assert result.ready_for_intake is False
    assert result.updated_intake is False
    assert "HOLD_NO_OK_ROWS" in result.blockers
    assert read_intake_row(intake_csv)["final_evidence_path"] == ""


def test_build_result_collects_ready_business_review_evidence(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot_check.csv"
    source_csv.write_text("confirm_ok,amount_estimate\nOK,120\nNG,5\n", encoding="utf-8")
    decision_csv = tmp_path / "decision_input.csv"
    decision_csv.write_text(
        "operation_id,operator_entry_confirm_ok\noperation-1,OK\n",
        encoding="utf-8",
    )
    source_json = tmp_path / "s44.json"
    source_json.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-20T12:34:56",
                "source_csv": str(source_csv),
                "row_count": 2,
                "ok_count": 1,
                "ng_count": 1,
                "blank_count": 0,
                "invalid_ok_count": 0,
                "missing_pdf_count": 0,
                "decision_input_csv": str(decision_csv),
                "decision_input_sha256": "decision-sha",
                "decision_overlay_applied_count": 1,
                "decision_overlay_invalid_count": 0,
                "ready_for_shadow_handoff": True,
                "status": "READY_FOR_SHADOW_HANDOFF",
                "ok_rows": [{"confirm_ok": "OK", "amount_estimate": "120"}],
                "shadow_handoff": {
                    "generated": True,
                    "verified": True,
                    "data_file": str(tmp_path / "shadow" / "data.json"),
                    "latest_ready_file": str(tmp_path / "shadow" / "latest_ready.json"),
                    "checksum": "abc123",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    intake_csv = tmp_path / "final_evidence_intake.csv"
    write_intake(intake_csv)
    final_evidence_dir = tmp_path / "final_evidence" / "scenario_44"

    result = module.build_result(source_json, intake_csv, final_evidence_dir)

    assert result.status == "READY_FOR_OPERATOR_FINAL_FIELDS"
    assert result.ready_for_intake is True
    assert result.updated_intake is True
    assert len(result.final_evidence_files) == 2
    assert all(Path(path).exists() for path in result.final_evidence_files)
    assert "scenario_44_safe_run_log_20260620_123456.txt" in {
        Path(path).name for path in result.final_evidence_files
    }
    log_text = Path(result.final_evidence_files[0]).read_text(encoding="utf-8")
    assert f"decision_input_csv={decision_csv}" in log_text
    assert "decision_input_sha256=decision-sha" in log_text
    assert "decision_overlay_applied_count=1" in log_text
    row = read_intake_row(intake_csv)
    assert row["final_evidence_path"] == str(final_evidence_dir)
    assert row["operator_result"] == ""
    assert row["reviewer"] == ""
    assert module.SYNC_NOTE in row["notes"]


def test_update_intake_preserves_existing_reviewer_fields(tmp_path: Path) -> None:
    module = load_module()
    intake_csv = tmp_path / "final_evidence_intake.csv"
    write_intake(intake_csv)
    fieldnames, rows = module.read_csv_rows(intake_csv)
    rows[0]["operator_result"] = "承認済"
    rows[0]["reviewer"] = "APPROVER_KEIRI"
    rows[0]["reviewed_at"] = "2026-06-20T12:00:00"
    module.write_csv_rows(intake_csv, fieldnames, rows)

    updated = module.update_intake_csv(intake_csv, tmp_path / "final_evidence" / "scenario_44")

    row = read_intake_row(intake_csv)
    assert updated is True
    assert row["operator_result"] == "承認済"
    assert row["reviewer"] == "APPROVER_KEIRI"
    assert row["reviewed_at"] == "2026-06-20T12:00:00"
