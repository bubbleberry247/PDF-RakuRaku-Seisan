import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "collect_s71_paid_azure_ocr_evidence_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("collect_s71_paid_azure_ocr_evidence_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_gate(path: Path, status: str = "READY", secret_value_printed: str = "NO") -> None:
    fieldnames = [
        "scope",
        "required_var",
        "current_present",
        "secret_value_printed",
        "required_before_paid_test",
        "status",
    ]
    rows = [
        ("LOCAL_or_TEST", "RK10_AzureDI_Endpoint", "True", secret_value_printed, "set endpoint", status),
        ("LOCAL_or_TEST", "RK10_AzureDI_Key", "True", secret_value_printed, "set key", status),
        ("PROD", "Azure_OCR_Endpoint", "True", secret_value_printed, "set endpoint", status),
        ("PROD", "Azure_OCR_Key", "True", secret_value_printed, "set key", status),
        ("PAID_TEST", "budget_approval", "True", "NO", "record approver and max pages", status),
        ("PAID_TEST", "sample_pdf_selection", "True", "NO", "choose exactly one PDF", status),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)


def write_mock_validation(path: Path, **overrides: object) -> None:
    payload = {
        "status": "REAL_PDF_MOCK_OCR_APPLY_VALIDATED",
        "paid_azure_ocr_executed": False,
        "source_workbook_written_by_checker": False,
        **overrides,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_paid_smoke(path: Path, **overrides: object) -> None:
    payload = {
        "status": "PAID_AZURE_ONE_PDF_SMOKE_OK",
        "sample_pdf_name": "approved_sample_invoice.pdf",
        "approver": "APPROVER_AZURE_COST",
        "approved_max_documents": 1,
        "approved_max_pages": 2,
        "approved_budget_yen": 500,
        "document_count": 1,
        "page_count": 1,
        "actual_cost_yen": 25,
        "paid_azure_ocr_executed": True,
        "multiple_pdf_submission": False,
        "secret_value_printed": False,
        "excel_copy_verified": True,
        "output_workbook_exists": True,
        "prod_mail_sent": False,
        "source_workbook_written": False,
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
                "bundle": "PAID_AZURE_OCR_BUNDLE",
                "scenario": "71",
                "required_final_evidence": "環境変数存在確認、サンプルPDF名、費用上限、OCR結果、コピーExcel照合",
                "hard_stops": "複数PDF送信、秘密値出力、原本Excel直書き、上限超過",
                "current_reference_evidence": r"C:\sample.md",
                "suggested_final_evidence_folder": r"C:\final\scenario_71",
                "required_update_fields": "final_evidence_path, operator_result, reviewer, reviewed_at",
            }
        )


def read_intake_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.DictReader(handle))


def test_build_result_waits_when_paid_gate_and_smoke_are_missing(tmp_path: Path) -> None:
    module = load_module()
    gate_path = tmp_path / "gate.csv"
    mock_path = tmp_path / "mock.json"
    smoke_path = tmp_path / "smoke.json"
    intake_path = tmp_path / "intake.csv"
    write_gate(gate_path, status="MISSING")
    write_mock_validation(mock_path)
    write_intake(intake_path)

    result = module.build_result(
        gate_path,
        mock_path,
        smoke_path,
        intake_path,
        tmp_path / "final" / "scenario_71",
    )

    assert result.status == "WAITING_FOR_PAID_AZURE_OCR_APPROVAL"
    assert result.ready_for_intake is False
    assert result.updated_intake is False
    assert "CHECKLIST_RK10_AzureDI_Endpoint_NOT_READY" in result.blockers
    assert "PAID_SMOKE_SUMMARY_MISSING" in result.blockers
    assert read_intake_row(intake_path)["final_evidence_path"] == ""


def test_write_paid_smoke_template_does_not_unlock_or_print_secrets(
    tmp_path: Path,
) -> None:
    module = load_module()
    gate_path = tmp_path / "gate.csv"
    mock_path = tmp_path / "mock.json"
    smoke_path = tmp_path / "missing_smoke.json"
    intake_path = tmp_path / "intake.csv"
    template_path = tmp_path / "smoke_template.json"
    write_gate(gate_path, status="MISSING")
    write_mock_validation(mock_path)
    write_intake(intake_path)

    result = module.build_result(
        gate_path,
        mock_path,
        smoke_path,
        intake_path,
        tmp_path / "final" / "scenario_71",
        str(template_path),
    )
    module.write_paid_smoke_template(template_path, result)
    template = json.loads(template_path.read_text(encoding="utf-8"))

    assert result.status == "WAITING_FOR_PAID_AZURE_OCR_APPROVAL"
    assert result.ready_for_intake is False
    assert template["template_only_not_evidence"] is True
    assert template["approved_max_documents"] == 1
    assert template["document_count"] == 1
    assert template["secret_value_printed"] is False
    assert template["multiple_pdf_submission"] is False
    assert "TODO_TRUE_AFTER_SINGLE_PAID_SMOKE" == template["paid_azure_ocr_executed"]
    serialized = json.dumps(template, ensure_ascii=False).lower()
    assert "dummy_secret" not in serialized
    assert "api_key_value" not in serialized


def test_environment_presence_reports_only_presence_without_values(tmp_path: Path) -> None:
    module = load_module()
    gate_path = tmp_path / "gate.csv"
    mock_path = tmp_path / "mock.json"
    smoke_path = tmp_path / "missing_smoke.json"
    intake_path = tmp_path / "intake.csv"
    env_csv_path = tmp_path / "environment_presence.csv"
    write_gate(gate_path, status="MISSING")
    write_mock_validation(mock_path)
    write_intake(intake_path)

    environment = {
        "RK10_AzureDI_Endpoint": "https://example.cognitiveservices.azure.com/",
        "RK10_AzureDI_Key": "dummy_secret_should_not_be_written",
    }
    result = module.build_result(
        gate_path,
        mock_path,
        smoke_path,
        intake_path,
        tmp_path / "final" / "scenario_71",
        environment_presence_csv=str(env_csv_path),
        environment=environment,
    )
    _fieldnames, checklist_rows = module.read_csv_rows(gate_path)
    env_rows = module.environment_presence_rows(checklist_rows, environment)
    module.write_environment_presence_csv(env_csv_path, env_rows)

    serialized_result = json.dumps(result.__dict__, ensure_ascii=False)
    serialized_csv = env_csv_path.read_text(encoding="utf-8-sig")

    assert result.environment_required_var_count == 4
    assert result.environment_present_var_count == 2
    assert result.environment_secret_value_printed is False
    assert "Azure_OCR_Endpoint" in result.environment_missing_required_vars
    assert "dummy_secret_should_not_be_written" not in serialized_result
    assert "dummy_secret_should_not_be_written" not in serialized_csv
    assert "https://example.cognitiveservices.azure.com/" not in serialized_csv
    assert "NOT_PRINTED" in serialized_csv


def test_build_result_collects_ready_paid_azure_evidence(tmp_path: Path) -> None:
    module = load_module()
    gate_path = tmp_path / "gate.csv"
    mock_path = tmp_path / "mock.json"
    smoke_path = tmp_path / "smoke.json"
    intake_path = tmp_path / "intake.csv"
    final_dir = tmp_path / "final" / "scenario_71"
    write_gate(gate_path)
    write_mock_validation(mock_path)
    write_paid_smoke(smoke_path)
    write_intake(intake_path)

    result = module.build_result(gate_path, mock_path, smoke_path, intake_path, final_dir)

    assert result.status == "READY_FOR_OPERATOR_FINAL_FIELDS"
    assert result.ready_for_intake is True
    assert result.updated_intake is True
    assert result.smoke_document_count == 1
    assert result.smoke_cost_yen == 25
    assert len(result.final_evidence_files) == 2
    assert all(Path(path).exists() for path in result.final_evidence_files)
    assert {Path(path).name for path in result.final_evidence_files} == {
        Path(path).name for path in final_dir.glob("scenario_71_*")
    }
    row = read_intake_row(intake_path)
    assert row["final_evidence_path"] == str(final_dir)
    assert row["operator_result"] == ""
    assert row["reviewer"] == ""
    assert module.SYNC_NOTE in row["notes"]


def test_build_result_blocks_secret_printing_and_multiple_pdf_submission(tmp_path: Path) -> None:
    module = load_module()
    gate_path = tmp_path / "gate.csv"
    mock_path = tmp_path / "mock.json"
    smoke_path = tmp_path / "smoke.json"
    intake_path = tmp_path / "intake.csv"
    write_gate(gate_path, secret_value_printed="YES")
    write_mock_validation(mock_path)
    write_paid_smoke(smoke_path, multiple_pdf_submission=True, document_count=2, secret_value_printed=True)
    write_intake(intake_path)

    result = module.build_result(
        gate_path,
        mock_path,
        smoke_path,
        intake_path,
        tmp_path / "final" / "scenario_71",
    )

    assert result.status == "WAITING_FOR_PAID_AZURE_OCR_APPROVAL"
    assert "CHECKLIST_SECRET_VALUE_PRINTED" in result.blockers
    assert "MULTIPLE_PDF_SUBMISSION_DETECTED" in result.blockers
    assert "PAID_SMOKE_SECRET_VALUE_PRINTED" in result.blockers
    assert result.updated_intake is False
