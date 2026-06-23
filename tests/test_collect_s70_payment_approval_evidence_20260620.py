import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "collect_s70_payment_approval_evidence_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("collect_s70_payment_approval_evidence_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_gate(path: Path, **overrides: str) -> None:
    fieldnames = [
        "scenario",
        "gate",
        "payment_date",
        "required_expected_count",
        "required_expected_total_amount_yen",
        "required_bank_transfer_confirmed",
        "required_approver",
        "execute_allowed_now",
    ]
    row = {
        "scenario": "70",
        "gate": "payment_confirmation_execute_gate",
        "payment_date": "2026/02/27",
        "required_expected_count": "TODO_business_confirm",
        "required_expected_total_amount_yen": "TODO_business_confirm",
        "required_bank_transfer_confirmed": "TODO_true_after_bank_evidence",
        "required_approver": "TODO_name_or_approval_record",
        "execute_allowed_now": "NO",
        **overrides,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def write_sample_preview(path: Path, **overrides: object) -> None:
    payload = {
        "status": "CONFIRM_PREVIEW_SAMPLE_OK",
        "payment_date": "2026/02/27",
        "selected_records": 2,
        "selected_total_amount_yen": 80235,
        "confirmation_ok_pressed": False,
        "payment_execute_performed": False,
        "mail_sent": False,
        "rk10_button_run": False,
        **overrides,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


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
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenario": "70",
                "required_final_evidence": "入力済み承認表",
                "hard_stops": "--execute",
                "current_reference_evidence": r"C:\sample.md",
                "suggested_final_evidence_folder": r"C:\final\scenario_70",
                "required_update_fields": "final_evidence_path, operator_result, reviewer, reviewed_at",
            }
        )


def read_intake_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.DictReader(handle))


def test_build_result_waits_when_payment_approval_fields_are_todo(tmp_path: Path) -> None:
    module = load_module()
    gate_path = tmp_path / "gate.csv"
    sample_path = tmp_path / "sample.json"
    intake_path = tmp_path / "intake.csv"
    write_gate(gate_path)
    write_sample_preview(sample_path)
    write_intake(intake_path)

    result = module.build_result(gate_path, sample_path, intake_path, tmp_path / "final" / "scenario_70")

    assert result.status == "WAITING_FOR_PAYMENT_APPROVAL"
    assert result.ready_for_intake is False
    assert result.updated_intake is False
    assert result.prefill_suggested_expected_count == 2
    assert result.prefill_suggested_expected_total_amount_yen == 80235
    assert "EXPECTED_COUNT_NOT_FILLED" in result.blockers
    assert "BANK_TRANSFER_CONFIRMATION_NOT_FILLED" in result.blockers
    assert read_intake_row(intake_path)["final_evidence_path"] == ""


def test_write_gate_checklist_prefill_suggests_sample_values_without_unlocking(
    tmp_path: Path,
) -> None:
    module = load_module()
    gate_path = tmp_path / "gate.csv"
    sample_path = tmp_path / "sample.json"
    intake_path = tmp_path / "intake.csv"
    prefill_path = tmp_path / "s70_prefill.csv"
    write_gate(gate_path)
    write_sample_preview(sample_path)
    write_intake(intake_path)

    result = module.build_result(
        gate_path,
        sample_path,
        intake_path,
        tmp_path / "final" / "scenario_70",
        str(prefill_path),
    )
    module.write_gate_checklist_prefill(prefill_path, result)

    with prefill_path.open("r", encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))

    assert result.status == "WAITING_FOR_PAYMENT_APPROVAL"
    assert result.ready_for_intake is False
    assert result.prefill_suggested_expected_count == 2
    assert result.prefill_suggested_expected_total_amount_yen == 80235
    assert row["required_expected_count"] == "2"
    assert row["required_expected_total_amount_yen"] == "80235"
    assert row["required_bank_transfer_confirmed"] == "TODO_TRUE_AFTER_BANK_EVIDENCE"
    assert row["required_approver"] == "TODO_NAME_OR_APPROVAL_RECORD"
    assert row["execute_allowed_now"] == "NO"


def test_build_result_blocks_when_gate_date_differs_from_sample_preview(
    tmp_path: Path,
) -> None:
    module = load_module()
    gate_path = tmp_path / "gate.csv"
    sample_path = tmp_path / "sample.json"
    intake_path = tmp_path / "intake.csv"
    prefill_path = tmp_path / "s70_prefill.csv"
    write_gate(
        gate_path,
        payment_date="2026/04/30",
        required_expected_count="2",
        required_expected_total_amount_yen="80235",
        required_bank_transfer_confirmed="確認済",
        required_approver="APPROVER_KEIRI",
    )
    write_sample_preview(sample_path, payment_date="2026/02/27")
    write_intake(intake_path)

    result = module.build_result(
        gate_path,
        sample_path,
        intake_path,
        tmp_path / "final" / "scenario_70",
        str(prefill_path),
    )
    module.write_gate_checklist_prefill(prefill_path, result)

    with prefill_path.open("r", encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))

    assert result.status == "WAITING_FOR_PAYMENT_APPROVAL"
    assert result.ready_for_intake is False
    assert result.payment_date_match is False
    assert "PAYMENT_DATE_MISMATCH" in result.blockers
    assert result.prefill_suggested_expected_count is None
    assert result.prefill_suggested_expected_total_amount_yen is None
    assert row["last_known_selected_records"] == "2"
    assert row["last_known_total_amount_yen"] == "80235"
    assert row["required_expected_count"] == "TODO_BUSINESS_CONFIRM_COUNT"
    assert row["required_expected_total_amount_yen"] == "TODO_BUSINESS_CONFIRM_AMOUNT"
    assert read_intake_row(intake_path)["final_evidence_path"] == ""


def test_build_result_collects_ready_payment_approval_evidence(tmp_path: Path) -> None:
    module = load_module()
    gate_path = tmp_path / "gate.csv"
    sample_path = tmp_path / "sample.json"
    intake_path = tmp_path / "intake.csv"
    final_dir = tmp_path / "final" / "scenario_70"
    write_gate(
        gate_path,
        required_expected_count="2",
        required_expected_total_amount_yen="80235",
        required_bank_transfer_confirmed="確認済",
        required_approver="APPROVER_KEIRI",
    )
    write_sample_preview(sample_path)
    write_intake(intake_path)

    result = module.build_result(gate_path, sample_path, intake_path, final_dir)

    assert result.status == "READY_FOR_OPERATOR_FINAL_FIELDS"
    assert result.ready_for_intake is True
    assert result.updated_intake is True
    assert result.count_difference == 0
    assert result.amount_difference_yen == 0
    assert len(result.final_evidence_files) == 2
    assert all(Path(path).exists() for path in result.final_evidence_files)
    assert {Path(path).name for path in result.final_evidence_files} == {
        Path(path).name for path in final_dir.glob("scenario_70_*")
    }
    row = read_intake_row(intake_path)
    assert row["final_evidence_path"] == str(final_dir)
    assert row["operator_result"] == ""
    assert row["reviewer"] == ""
    assert module.SYNC_NOTE in row["notes"]


def test_build_result_blocks_when_confirmation_ok_was_pressed(tmp_path: Path) -> None:
    module = load_module()
    gate_path = tmp_path / "gate.csv"
    sample_path = tmp_path / "sample.json"
    intake_path = tmp_path / "intake.csv"
    write_gate(
        gate_path,
        required_expected_count="2",
        required_expected_total_amount_yen="80235",
        required_bank_transfer_confirmed="true",
        required_approver="APPROVER_KEIRI",
    )
    write_sample_preview(sample_path, confirmation_ok_pressed=True)
    write_intake(intake_path)

    result = module.build_result(gate_path, sample_path, intake_path, tmp_path / "final" / "scenario_70")

    assert result.status == "WAITING_FOR_PAYMENT_APPROVAL"
    assert "CONFIRMATION_OK_WAS_PRESSED" in result.blockers
    assert result.updated_intake is False
