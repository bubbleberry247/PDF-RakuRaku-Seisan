import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "validate_s71_sample_mock_ocr_apply_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "validate_s71_sample_mock_ocr_apply_20260620",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_review_csv(path: Path, pdf_names: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "status",
                "pdf_name",
                "vendor_name",
                "target_rows",
                "payment_date",
                "amount",
                "withholding_tax",
                "review_reasons",
            ],
        )
        writer.writeheader()
        for index, pdf_name in enumerate(pdf_names, 1):
            writer.writerow(
                {
                    "status": "AUTO",
                    "pdf_name": pdf_name,
                    "vendor_name": f"vendor-{index}",
                    "target_rows": str(index),
                    "payment_date": "2025/12/30",
                    "amount": str(index * 1000),
                    "withholding_tax": "0",
                    "review_reasons": "",
                }
            )


def build_fixture(tmp_path: Path, mock_all_pdfs: bool = True) -> tuple[object, Path]:
    module = load_module()
    report_dir = tmp_path / "report"
    run_dir = tmp_path / "run"
    mock_dir = tmp_path / "mock_ocr"
    invoice_dir = tmp_path / "invoices"
    source_workbook = tmp_path / "source.xlsx"
    output_workbook = report_dir / "output.xlsx"
    azure_preflight_report = tmp_path / "azure_preflight.md.numbered"
    pdf_names = ["sample-a.pdf", "sample-b.pdf", "sample-c.pdf"]
    invoice_dir.mkdir(parents=True)
    mock_dir.mkdir(parents=True)
    for index, pdf_name in enumerate(pdf_names, 1):
        (invoice_dir / pdf_name).write_bytes(b"%PDF-1.4 sample")
        if mock_all_pdfs or index < len(pdf_names):
            write_json(mock_dir / f"{Path(pdf_name).stem}.json", {"pdf_name": pdf_name})
    source_workbook.write_bytes(b"source")
    output_workbook.parent.mkdir(parents=True, exist_ok=True)
    output_workbook.write_bytes(b"output")
    write_json(
        report_dir / "summary.json",
        {
            "command": [
                "python",
                "main_71_v2.py",
                "--env",
                "LOCAL",
                "--era",
                "R7",
                "--month",
                "12",
                "--mock-ocr-dir",
                str(mock_dir),
                "--apply",
            ],
            "exit_code": 0,
        },
    )
    (report_dir / "stdout.txt").write_text(
        "\n".join(
            [
                "env=LOCAL",
                f"source_workbook={source_workbook}",
                f"invoice_dir={invoice_dir}",
                "pdf_count=3 auto=3 review=0",
                f"output_workbook={output_workbook}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (report_dir / "stderr.txt").write_text("", encoding="utf-8")
    write_json(
        report_dir / "workbook_verify.json",
        {
            "target_sheet_exists": True,
            "review_sheet_exists": True,
            "review_csv_count": 3,
            "transfer_plan_count": 3,
            "auto_count": 3,
            "review_count": 0,
            "all_row_checks_match": True,
        },
    )
    write_json(
        run_dir / "transfer_plan.json",
        [
            {
                "pdf_name": pdf_name,
                "status": "AUTO",
                "review_reasons": [],
                "ocr": {"source": "mock"},
            }
            for pdf_name in pdf_names
        ],
    )
    write_review_csv(run_dir / "review_items.csv", pdf_names)
    (run_dir / "run.log").write_text(
        "env=LOCAL\nfinish auto=3 review=0 exit=0\n",
        encoding="utf-8",
    )
    azure_preflight_report.write_text(
        "No Azure client was constructed, no PDF was submitted, no network call was made.",
        encoding="utf-8",
    )
    paths = module.ValidationPaths(
        report_dir=report_dir,
        apply_run_dir=run_dir,
        mock_ocr_dir=mock_dir,
        azure_preflight_report=azure_preflight_report,
    )
    return paths, tmp_path / "out"


def test_validate_s71_accepts_real_pdf_mock_ocr_apply_evidence(tmp_path: Path) -> None:
    module = load_module()
    paths, out_dir = build_fixture(tmp_path)

    payload = module.validate_s71(paths, out_dir)

    assert payload["status"] == module.EXPECTED_STATUS
    assert payload["pdf_count"] == 3
    assert payload["mock_ocr_count"] == 3
    assert payload["auto_count"] == 3
    assert payload["review_count"] == 0
    assert payload["all_row_checks_match"] is True
    assert payload["paid_azure_ocr_executed"] is False
    assert payload["scenario_tool_reexecuted_by_checker"] is False
    assert (out_dir / "s71_sample_mock_ocr_apply_validation.md.numbered").exists()


def test_validate_s71_holds_when_mock_ocr_missing(tmp_path: Path) -> None:
    module = load_module()
    paths, out_dir = build_fixture(tmp_path, mock_all_pdfs=False)

    payload = module.validate_s71(paths, out_dir)

    assert payload["status"] == "HOLD_S71_SAMPLE_MOCK_OCR_APPLY"
    assert payload["mock_ocr_count"] == 2
    assert "missing_mock_ocr_for_some_pdfs" in payload["failed_checks"]


def test_build_markdown_states_paid_ocr_is_not_executed(tmp_path: Path) -> None:
    module = load_module()
    paths, out_dir = build_fixture(tmp_path)
    payload = module.validate_s71(paths, out_dir)
    result = module.S71ValidationResult(**payload)

    markdown = module.build_markdown(result)

    assert "paid OCR" in markdown
    assert "Outlook mail" in markdown
    assert "source workbook writes are not executed" in markdown
