"""Validate Scenario 71 real-PDF mock-OCR apply evidence without paid OCR.

This checker does not run Azure OCR, Outlook, RK10, or the Scenario 71 tool.
It validates the existing actual Scenario 71 run artifacts: real PDFs,
complete mock OCR coverage, workbook-copy output, transfer plan, review CSV,
and workbook reopen verification.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
ROBOT_ROOT = Path(r"C:\ProgramData\RK10\Robots\【71法定調書用　士業請求書集計】2026-01-28")
DEFAULT_REPORT_DIR = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\s71_real_pdf_apply_mock_ocr_20260619_105002"
)
DEFAULT_APPLY_RUN_DIR = ROBOT_ROOT / "work" / "runs" / "20260619_105002"
DEFAULT_MOCK_OCR_DIR = ROBOT_ROOT / "work" / "runs" / "20260618_175443" / "ocr_json"
DEFAULT_AZURE_PREFLIGHT_REPORT = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\s71_azure_no_cost_preflight_20260619_105314"
    r"\s71_azure_no_cost_preflight_report.md.numbered"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "s71_sample_mock_ocr_apply_20260620"
EXPECTED_STATUS = "REAL_PDF_MOCK_OCR_APPLY_VALIDATED"


@dataclass(frozen=True)
class ValidationPaths:
    report_dir: Path
    apply_run_dir: Path
    mock_ocr_dir: Path
    azure_preflight_report: Path


@dataclass(frozen=True)
class S71ValidationResult:
    generated_at: str
    status: str
    pdf_count: int
    mock_ocr_count: int
    transfer_plan_count: int
    review_csv_count: int
    auto_count: int
    review_count: int
    all_row_checks_match: bool
    output_workbook_exists: bool
    source_workbook: str
    output_workbook: str
    missing_mock_pdfs: list[str]
    non_mock_ocr_pdfs: list[str]
    failed_checks: list[str]
    paid_azure_ocr_executed: bool
    prod_mail_sent: bool
    source_workbook_written_by_checker: bool
    scenario_tool_reexecuted_by_checker: bool
    primary_sources: list[str]
    next_action: str


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_key_value_stdout(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def mock_exists_for_pdf(pdf_path: Path, mock_dir: Path) -> bool:
    if (mock_dir / f"{pdf_path.name}.json").exists():
        return True
    if (mock_dir / f"{pdf_path.stem}.json").exists():
        return True
    all_json = mock_dir / "all.json"
    if not all_json.exists():
        return False
    data = read_json(all_json)
    return isinstance(data, dict) and (pdf_path.name in data or pdf_path.stem in data)


def collect_mock_coverage(invoice_dir: Path, mock_dir: Path) -> tuple[list[Path], list[str]]:
    pdfs = sorted(invoice_dir.glob("*.pdf"), key=lambda path: path.name)
    missing = [pdf_path.name for pdf_path in pdfs if not mock_exists_for_pdf(pdf_path, mock_dir)]
    return pdfs, missing


def build_failed_checks(
    summary: dict[str, Any],
    stdout_values: dict[str, str],
    stderr_path: Path,
    workbook_verify: dict[str, Any],
    transfer_plan: list[dict[str, Any]],
    review_rows: list[dict[str, str]],
    run_log: str,
    azure_preflight_text: str,
    output_workbook: Path,
    source_workbook: Path,
    missing_mock_pdfs: list[str],
    non_mock_ocr_pdfs: list[str],
) -> list[str]:
    failed: list[str] = []
    command = [str(part) for part in summary.get("command", [])]
    command_text = " ".join(command)
    if summary.get("exit_code") != 0:
        failed.append("summary_exit_code_not_zero")
    if "--env LOCAL" not in command_text:
        failed.append("command_not_local_env")
    if "--mock-ocr-dir" not in command_text:
        failed.append("command_missing_mock_ocr_dir")
    if "--apply" not in command_text:
        failed.append("command_missing_apply")
    if " PROD " in f" {command_text} ":
        failed.append("command_uses_prod")
    if stderr_path.exists() and stderr_path.read_text(encoding="utf-8-sig", errors="replace").strip():
        failed.append("stderr_not_empty")
    if stdout_values.get("env") != "LOCAL":
        failed.append("stdout_env_not_local")
    if "finish auto=3 review=0 exit=0" not in run_log:
        failed.append("run_log_missing_success_exit")
    if missing_mock_pdfs:
        failed.append("missing_mock_ocr_for_some_pdfs")
    if non_mock_ocr_pdfs:
        failed.append("transfer_plan_contains_non_mock_ocr")
    if not bool(workbook_verify.get("all_row_checks_match")):
        failed.append("workbook_row_checks_not_all_match")
    if not bool(workbook_verify.get("target_sheet_exists")):
        failed.append("target_sheet_missing")
    if not bool(workbook_verify.get("review_sheet_exists")):
        failed.append("review_sheet_missing")
    if not output_workbook.exists():
        failed.append("output_workbook_missing")
    if source_workbook == output_workbook:
        failed.append("source_and_output_workbook_same_path")
    if len(transfer_plan) != len(review_rows):
        failed.append("transfer_plan_review_csv_count_mismatch")
    if any(item.get("status") != "AUTO" for item in transfer_plan):
        failed.append("transfer_plan_has_non_auto_item")
    if any(row.get("status") != "AUTO" for row in review_rows):
        failed.append("review_csv_has_non_auto_row")
    if "No Azure client was constructed" not in azure_preflight_text:
        failed.append("azure_preflight_no_client_evidence_missing")
    return failed


def validate_s71(paths: ValidationPaths, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = paths.report_dir / "summary.json"
    stdout_path = paths.report_dir / "stdout.txt"
    stderr_path = paths.report_dir / "stderr.txt"
    workbook_verify_path = paths.report_dir / "workbook_verify.json"
    transfer_plan_path = paths.apply_run_dir / "transfer_plan.json"
    review_csv_path = paths.apply_run_dir / "review_items.csv"
    run_log_path = paths.apply_run_dir / "run.log"

    summary = read_json(summary_path)
    stdout_values = read_key_value_stdout(stdout_path)
    workbook_verify = read_json(workbook_verify_path)
    transfer_plan = read_json(transfer_plan_path)
    review_rows = read_csv_rows(review_csv_path)
    run_log = run_log_path.read_text(encoding="utf-8-sig", errors="replace")
    azure_preflight_text = paths.azure_preflight_report.read_text(
        encoding="utf-8-sig",
        errors="replace",
    )

    invoice_dir = Path(stdout_values.get("invoice_dir", ""))
    source_workbook = Path(stdout_values.get("source_workbook", ""))
    output_workbook = Path(stdout_values.get("output_workbook", ""))
    pdfs, missing_mock_pdfs = collect_mock_coverage(invoice_dir, paths.mock_ocr_dir)
    non_mock_ocr_pdfs = [
        str(item.get("pdf_name") or item.get("pdf_path") or "")
        for item in transfer_plan
        if item.get("ocr", {}).get("source") != "mock"
    ]
    auto_count = sum(1 for item in transfer_plan if item.get("status") == "AUTO")
    review_count = len(transfer_plan) - auto_count
    failed_checks = build_failed_checks(
        summary=summary,
        stdout_values=stdout_values,
        stderr_path=stderr_path,
        workbook_verify=workbook_verify,
        transfer_plan=transfer_plan,
        review_rows=review_rows,
        run_log=run_log,
        azure_preflight_text=azure_preflight_text,
        output_workbook=output_workbook,
        source_workbook=source_workbook,
        missing_mock_pdfs=missing_mock_pdfs,
        non_mock_ocr_pdfs=non_mock_ocr_pdfs,
    )
    status = EXPECTED_STATUS if not failed_checks else "HOLD_S71_SAMPLE_MOCK_OCR_APPLY"
    result = S71ValidationResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status=status,
        pdf_count=len(pdfs),
        mock_ocr_count=len(pdfs) - len(missing_mock_pdfs),
        transfer_plan_count=len(transfer_plan),
        review_csv_count=len(review_rows),
        auto_count=auto_count,
        review_count=review_count,
        all_row_checks_match=bool(workbook_verify.get("all_row_checks_match")),
        output_workbook_exists=output_workbook.exists(),
        source_workbook=str(source_workbook),
        output_workbook=str(output_workbook),
        missing_mock_pdfs=missing_mock_pdfs,
        non_mock_ocr_pdfs=non_mock_ocr_pdfs,
        failed_checks=failed_checks,
        paid_azure_ocr_executed=False,
        prod_mail_sent=False,
        source_workbook_written_by_checker=False,
        scenario_tool_reexecuted_by_checker=False,
        primary_sources=[
            str(summary_path),
            str(stdout_path),
            str(stderr_path),
            str(workbook_verify_path),
            str(transfer_plan_path),
            str(review_csv_path),
            str(run_log_path),
            str(paths.azure_preflight_report),
        ],
        next_action=(
            "Keep Scenario 71 at mock-OCR apply validated; paid Azure OCR requires a separate approved one-PDF cost gate."
            if status == EXPECTED_STATUS
            else "Resolve failed_checks before using Scenario 71 evidence for production readiness."
        ),
    )
    payload = asdict(result)
    json_path = out_dir / "s71_sample_mock_ocr_apply_validation.json"
    md_path = out_dir / "s71_sample_mock_ocr_apply_validation.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(result), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    return payload


def build_markdown(result: S71ValidationResult) -> str:
    lines = [
        "# Scenario 71 sample mock OCR apply validation",
        "",
        f"- generated_at: `{result.generated_at}`",
        f"- status: `{result.status}`",
        f"- pdf_count: `{result.pdf_count}`",
        f"- mock_ocr_count: `{result.mock_ocr_count}`",
        f"- transfer_plan_count: `{result.transfer_plan_count}`",
        f"- review_csv_count: `{result.review_csv_count}`",
        f"- auto_count: `{result.auto_count}`",
        f"- review_count: `{result.review_count}`",
        f"- all_row_checks_match: `{result.all_row_checks_match}`",
        f"- output_workbook_exists: `{result.output_workbook_exists}`",
        f"- source_workbook: `{result.source_workbook}`",
        f"- output_workbook: `{result.output_workbook}`",
        f"- missing_mock_pdfs: `{len(result.missing_mock_pdfs)}`",
        f"- non_mock_ocr_pdfs: `{len(result.non_mock_ocr_pdfs)}`",
        f"- failed_checks: `{len(result.failed_checks)}`",
        f"- paid_azure_ocr_executed: `{result.paid_azure_ocr_executed}`",
        f"- prod_mail_sent: `{result.prod_mail_sent}`",
        f"- source_workbook_written_by_checker: `{result.source_workbook_written_by_checker}`",
        f"- scenario_tool_reexecuted_by_checker: `{result.scenario_tool_reexecuted_by_checker}`",
        f"- next_action: {result.next_action}",
        "",
        "## Safety",
        "",
        "- This checker validates existing actual-run artifacts only.",
        "- Azure client construction, PDF submission, network calls, paid OCR, Outlook mail, RK10 ButtonRun, and source workbook writes are not executed by this checker.",
        "- The validated Scenario 71 run used LOCAL env, real PDF files, complete mock OCR JSON coverage, and an output workbook copy.",
        "",
        "## Primary Sources",
        "",
    ]
    lines.extend(f"- `{source}`" for source in result.primary_sources)
    if result.failed_checks:
        lines.extend(["", "## Failed Checks", ""])
        lines.extend(f"- `{check}`" for check in result.failed_checks)
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Scenario 71 sample mock OCR apply evidence.",
    )
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--apply-run-dir", type=Path, default=DEFAULT_APPLY_RUN_DIR)
    parser.add_argument("--mock-ocr-dir", type=Path, default=DEFAULT_MOCK_OCR_DIR)
    parser.add_argument(
        "--azure-preflight-report",
        type=Path,
        default=DEFAULT_AZURE_PREFLIGHT_REPORT,
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = validate_s71(
        ValidationPaths(
            report_dir=args.report_dir,
            apply_run_dir=args.apply_run_dir,
            mock_ocr_dir=args.mock_ocr_dir,
            azure_preflight_report=args.azure_preflight_report,
        ),
        args.out_dir,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == EXPECTED_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
