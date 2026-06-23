"""Collect Scenario 71 paid Azure OCR evidence into the bundle intake.

This tool never calls Azure OCR. It only packages existing one-PDF paid-smoke
evidence after the cost, sample, and secret-handling gates have already been
approved and recorded by a human/operator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_GATE_CHECKLIST = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\s71_azure_ocr_gate_pack_20260619_1220"
    r"\s71_azure_ocr_paid_test_gate_checklist.csv"
)
DEFAULT_MOCK_VALIDATION_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "s71_sample_mock_ocr_apply_20260620"
    / "s71_sample_mock_ocr_apply_validation.json"
)
DEFAULT_PAID_SMOKE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "s71_paid_azure_one_pdf_smoke_20260620"
    / "s71_paid_azure_one_pdf_smoke_summary.json"
)
DEFAULT_INTAKE_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "paid_azure_ocr_bundle"
    / "final_evidence_intake.csv"
)
DEFAULT_FINAL_EVIDENCE_DIR = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "paid_azure_ocr_bundle"
    / "final_evidence"
    / "scenario_71"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "s71_paid_azure_ocr_evidence_collect_20260620"
SYNC_NOTE = "s71_paid_azure_ocr_evidence_auto_collected_20260620"
TODO_PREFIX = "TODO"
READY_STATUSES = {"READY", "OK", "PASSED", "COMPLETE", "COMPLETED", "承認済", "確認済"}
TRUE_VALUES = {"1", "true", "yes", "y", "ok", "confirmed", "済", "確認済", "承認済", "はい"}
FALSE_VALUES = {"", "0", "false", "no", "n", "ng", "none", "未", "未実施"}
PAID_SMOKE_OK_STATUSES = {
    "PAID_AZURE_ONE_PDF_SMOKE_OK",
    "PAID_AZURE_ONE_PDF_SMOKE_VALIDATED",
}
MOCK_VALIDATION_OK_STATUS = "REAL_PDF_MOCK_OCR_APPLY_VALIDATED"
ENVIRONMENT_REQUIRED_SUFFIXES = ("_Endpoint", "_Key")


@dataclass(frozen=True)
class CollectionResult:
    generated_at: str
    status: str
    ready_for_intake: bool
    updated_intake: bool
    gate_checklist: str
    gate_checklist_exists: bool
    gate_checklist_sha256: str
    environment_presence_csv: str
    environment_required_var_count: int
    environment_present_var_count: int
    environment_missing_required_vars: str
    environment_secret_value_printed: bool
    required_row_count: int
    ready_required_row_count: int
    secret_value_printed_in_checklist: bool
    mock_validation_json: str
    mock_validation_exists: bool
    mock_validation_status: str
    paid_smoke_json: str
    paid_smoke_template_json: str
    paid_smoke_exists: bool
    paid_smoke_status: str
    sample_pdf_name: str
    approver: str
    approved_max_documents: int | None
    approved_max_pages: int | None
    approved_budget_yen: int | None
    smoke_document_count: int | None
    smoke_page_count: int | None
    smoke_cost_yen: int | None
    paid_azure_ocr_executed: bool
    multiple_pdf_submission: bool
    secret_value_printed_in_smoke: bool
    excel_copy_verified: bool
    output_workbook_exists: bool
    prod_mail_sent: bool
    source_workbook_written: bool
    rk10_button_run: bool
    final_evidence_dir: str
    final_evidence_files: list[str]
    intake_csv: str
    blockers: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    for encoding in ("utf-8-sig", "cp932", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = list(reader.fieldnames or [])
                rows = [
                    {str(key): str(value).strip() for key, value in row.items() if key is not None}
                    for row in reader
                ]
            return fieldnames, rows
        except UnicodeDecodeError:
            continue
    return [], []


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize(value: object) -> str:
    return str(value or "").strip()


def normalized_lower(value: object) -> str:
    return normalize(value).lower()


def parse_int(value: object) -> int | None:
    text = normalize(value).replace(",", "")
    if not text or text.upper().startswith(TODO_PREFIX):
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def is_truthy(value: object) -> bool:
    return normalized_lower(value) in TRUE_VALUES


def is_falsey(value: object) -> bool:
    return normalized_lower(value) in FALSE_VALUES


def is_filled(value: object) -> bool:
    text = normalize(value)
    return bool(text) and not text.upper().startswith(TODO_PREFIX)


def is_ready_status(value: object) -> bool:
    return normalize(value).upper() in READY_STATUSES


def checklist_secret_printed(rows: list[dict[str, str]]) -> bool:
    return any(not is_falsey(row.get("secret_value_printed")) for row in rows)


def required_row_statuses(rows: list[dict[str, str]]) -> dict[str, str]:
    return {row.get("required_var", ""): row.get("status", "") for row in rows}


def is_environment_required_var(required_var: str) -> bool:
    return required_var.endswith(ENVIRONMENT_REQUIRED_SUFFIXES)


def environment_presence_rows(
    checklist_rows: list[dict[str, str]],
    environment: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    env = environment if environment is not None else os.environ
    rows: list[dict[str, str]] = []
    for row in checklist_rows:
        required_var = row.get("required_var", "")
        if not is_environment_required_var(required_var):
            continue
        rows.append(
            {
                "scope": row.get("scope", ""),
                "required_var": required_var,
                "present_in_current_process_environment": str(bool(normalize(env.get(required_var)))),
                "secret_value_printed": "NO",
                "value": "NOT_PRINTED",
                "source": "current_process_environment_presence_only",
            }
        )
    return rows


def environment_presence_summary(rows: list[dict[str, str]]) -> tuple[int, int, str]:
    required_count = len(rows)
    present_count = sum(1 for row in rows if is_truthy(row.get("present_in_current_process_environment")))
    missing_vars = [
        row.get("required_var", "")
        for row in rows
        if not is_truthy(row.get("present_in_current_process_environment"))
    ]
    return required_count, present_count, ", ".join(missing_vars)


def first_present_value(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def build_blockers(
    checklist_rows: list[dict[str, str]],
    mock_validation: dict[str, Any],
    paid_smoke: dict[str, Any],
    result_base: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not checklist_rows:
        blockers.append("AZURE_OCR_GATE_CHECKLIST_MISSING_OR_EMPTY")
    for required_var, status in required_row_statuses(checklist_rows).items():
        if not is_ready_status(status):
            blockers.append(f"CHECKLIST_{required_var}_NOT_READY")
    if result_base["secret_value_printed_in_checklist"]:
        blockers.append("CHECKLIST_SECRET_VALUE_PRINTED")
    if not mock_validation:
        blockers.append("S71_MOCK_VALIDATION_MISSING_OR_EMPTY")
    elif mock_validation.get("status") != MOCK_VALIDATION_OK_STATUS:
        blockers.append("S71_MOCK_VALIDATION_NOT_OK")
    if mock_validation.get("paid_azure_ocr_executed") is not False:
        blockers.append("MOCK_VALIDATION_PAID_AZURE_WAS_EXECUTED")
    if mock_validation.get("source_workbook_written_by_checker") is not False:
        blockers.append("MOCK_VALIDATION_SOURCE_WORKBOOK_WAS_WRITTEN")
    if not paid_smoke:
        blockers.append("PAID_SMOKE_SUMMARY_MISSING")
    elif paid_smoke.get("status") not in PAID_SMOKE_OK_STATUSES:
        blockers.append("PAID_SMOKE_STATUS_NOT_OK")
    if not is_filled(result_base["sample_pdf_name"]):
        blockers.append("SAMPLE_PDF_NAME_NOT_FILLED")
    if not is_filled(result_base["approver"]):
        blockers.append("APPROVER_NOT_FILLED")
    if result_base["approved_max_documents"] is None:
        blockers.append("APPROVED_MAX_DOCUMENTS_NOT_FILLED")
    if result_base["approved_max_pages"] is None:
        blockers.append("APPROVED_MAX_PAGES_NOT_FILLED")
    if result_base["approved_budget_yen"] is None:
        blockers.append("APPROVED_BUDGET_YEN_NOT_FILLED")
    if result_base["paid_azure_ocr_executed"] is not True:
        blockers.append("PAID_AZURE_OCR_NOT_EXECUTED_IN_SMOKE")
    if result_base["smoke_document_count"] != 1:
        blockers.append("PAID_SMOKE_DOCUMENT_COUNT_NOT_ONE")
    if result_base["multiple_pdf_submission"]:
        blockers.append("MULTIPLE_PDF_SUBMISSION_DETECTED")
    if result_base["secret_value_printed_in_smoke"]:
        blockers.append("PAID_SMOKE_SECRET_VALUE_PRINTED")
    if result_base["excel_copy_verified"] is not True:
        blockers.append("EXCEL_COPY_NOT_VERIFIED")
    if result_base["output_workbook_exists"] is not True:
        blockers.append("OUTPUT_WORKBOOK_NOT_CONFIRMED")
    if result_base["prod_mail_sent"]:
        blockers.append("PROD_MAIL_WAS_SENT")
    if result_base["source_workbook_written"]:
        blockers.append("SOURCE_WORKBOOK_WAS_WRITTEN")
    if result_base["rk10_button_run"]:
        blockers.append("RK10_BUTTON_RUN_WAS_USED")
    approved_max_documents = result_base["approved_max_documents"]
    approved_max_pages = result_base["approved_max_pages"]
    approved_budget_yen = result_base["approved_budget_yen"]
    smoke_document_count = result_base["smoke_document_count"]
    smoke_page_count = result_base["smoke_page_count"]
    smoke_cost_yen = result_base["smoke_cost_yen"]
    if approved_max_documents is not None and smoke_document_count is not None:
        if smoke_document_count > approved_max_documents:
            blockers.append("APPROVED_DOCUMENT_LIMIT_EXCEEDED")
    if approved_max_pages is not None and smoke_page_count is not None:
        if smoke_page_count > approved_max_pages:
            blockers.append("APPROVED_PAGE_LIMIT_EXCEEDED")
    if approved_budget_yen is not None and smoke_cost_yen is not None:
        if smoke_cost_yen > approved_budget_yen:
            blockers.append("APPROVED_BUDGET_EXCEEDED")
    return blockers


def evidence_token() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_final_evidence(
    result_base: dict[str, Any],
    final_evidence_dir: Path,
    token: str,
) -> list[Path]:
    final_evidence_dir.mkdir(parents=True, exist_ok=True)
    log_path = final_evidence_dir / f"scenario_71_safe_run_log_{token}.txt"
    summary_path = final_evidence_dir / f"scenario_71_count_amount_summary_{token}.csv"
    log_lines = [
        "Scenario 71 paid Azure OCR evidence collection",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        "scope=read-only evidence packaging; no Azure client, no PDF submission, no network call",
        f"gate_checklist={result_base['gate_checklist']}",
        f"gate_checklist_sha256={result_base['gate_checklist_sha256']}",
        f"mock_validation_json={result_base['mock_validation_json']}",
        f"mock_validation_status={result_base['mock_validation_status']}",
        f"paid_smoke_json={result_base['paid_smoke_json']}",
        f"paid_smoke_status={result_base['paid_smoke_status']}",
        f"sample_pdf_name={result_base['sample_pdf_name']}",
        f"approver={result_base['approver']}",
        f"approved_max_documents={result_base['approved_max_documents']}",
        f"approved_max_pages={result_base['approved_max_pages']}",
        f"approved_budget_yen={result_base['approved_budget_yen']}",
        f"smoke_document_count={result_base['smoke_document_count']}",
        f"smoke_page_count={result_base['smoke_page_count']}",
        f"smoke_cost_yen={result_base['smoke_cost_yen']}",
        f"paid_azure_ocr_executed={result_base['paid_azure_ocr_executed']}",
        f"multiple_pdf_submission={result_base['multiple_pdf_submission']}",
        f"secret_value_printed_in_checklist={result_base['secret_value_printed_in_checklist']}",
        f"secret_value_printed_in_smoke={result_base['secret_value_printed_in_smoke']}",
        f"excel_copy_verified={result_base['excel_copy_verified']}",
        f"output_workbook_exists={result_base['output_workbook_exists']}",
        f"prod_mail_sent={result_base['prod_mail_sent']}",
        f"source_workbook_written={result_base['source_workbook_written']}",
        f"rk10_button_run={result_base['rk10_button_run']}",
    ]
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    summary_keys = {
        "sample_pdf_name",
        "approver",
        "approved_max_documents",
        "approved_max_pages",
        "approved_budget_yen",
        "smoke_document_count",
        "smoke_page_count",
        "smoke_cost_yen",
        "paid_azure_ocr_executed",
        "excel_copy_verified",
        "output_workbook_exists",
    }
    rows = [
        {"metric": key, "value": str(value)}
        for key, value in result_base.items()
        if key in summary_keys
    ]
    write_csv_rows(summary_path, ["metric", "value"], rows)
    return [log_path, summary_path]


def append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing}; {note}"


def update_intake_csv(intake_csv: Path, final_evidence_dir: Path) -> bool:
    fieldnames, rows = read_csv_rows(intake_csv)
    if not rows:
        return False
    updated = False
    new_rows = []
    for row in rows:
        if row.get("bundle") == "PAID_AZURE_OCR_BUNDLE" and row.get("scenario") == "71":
            row = {
                **row,
                "final_evidence_path": str(final_evidence_dir),
                "notes": append_note(row.get("notes", ""), SYNC_NOTE),
            }
            updated = True
        new_rows.append(row)
    if updated:
        write_csv_rows(intake_csv, fieldnames, new_rows)
    return updated


def build_result(
    gate_checklist: Path,
    mock_validation_json: Path,
    paid_smoke_json: Path,
    intake_csv: Path,
    final_evidence_dir: Path,
    paid_smoke_template_json: str = "",
    environment_presence_csv: str = "",
    environment: Mapping[str, str] | None = None,
) -> CollectionResult:
    _fieldnames, checklist_rows = read_csv_rows(gate_checklist)
    mock_validation = read_json(mock_validation_json)
    paid_smoke = read_json(paid_smoke_json)
    ready_count = sum(1 for row in checklist_rows if is_ready_status(row.get("status")))
    env_rows = environment_presence_rows(checklist_rows, environment)
    env_required_count, env_present_count, env_missing_vars = environment_presence_summary(env_rows)
    result_base = {
        "gate_checklist": str(gate_checklist),
        "gate_checklist_sha256": file_sha256(gate_checklist),
        "environment_presence_csv": environment_presence_csv,
        "environment_required_var_count": env_required_count,
        "environment_present_var_count": env_present_count,
        "environment_missing_required_vars": env_missing_vars,
        "environment_secret_value_printed": False,
        "required_row_count": len(checklist_rows),
        "ready_required_row_count": ready_count,
        "secret_value_printed_in_checklist": checklist_secret_printed(checklist_rows),
        "mock_validation_json": str(mock_validation_json),
        "mock_validation_status": normalize(mock_validation.get("status")),
        "paid_smoke_json": str(paid_smoke_json),
        "paid_smoke_status": normalize(paid_smoke.get("status")),
        "sample_pdf_name": normalize(first_present_value(paid_smoke, ("sample_pdf_name", "sample_pdf", "pdf_name"))),
        "approver": normalize(first_present_value(paid_smoke, ("approver", "cost_approver", "approved_by"))),
        "approved_max_documents": parse_int(
            first_present_value(paid_smoke, ("approved_max_documents", "max_documents", "approved_document_limit"))
        ),
        "approved_max_pages": parse_int(
            first_present_value(paid_smoke, ("approved_max_pages", "max_pages", "approved_page_limit"))
        ),
        "approved_budget_yen": parse_int(
            first_present_value(paid_smoke, ("approved_budget_yen", "budget_yen", "max_cost_yen"))
        ),
        "smoke_document_count": parse_int(
            first_present_value(paid_smoke, ("document_count", "pdf_count", "submitted_pdf_count"))
        ),
        "smoke_page_count": parse_int(first_present_value(paid_smoke, ("page_count", "submitted_page_count"))),
        "smoke_cost_yen": parse_int(
            first_present_value(paid_smoke, ("actual_cost_yen", "estimated_cost_yen", "cost_yen"))
        ),
        "paid_azure_ocr_executed": is_truthy(paid_smoke.get("paid_azure_ocr_executed")),
        "multiple_pdf_submission": is_truthy(paid_smoke.get("multiple_pdf_submission")),
        "secret_value_printed_in_smoke": is_truthy(paid_smoke.get("secret_value_printed")),
        "excel_copy_verified": is_truthy(paid_smoke.get("excel_copy_verified")),
        "output_workbook_exists": is_truthy(paid_smoke.get("output_workbook_exists")),
        "prod_mail_sent": is_truthy(paid_smoke.get("prod_mail_sent")),
        "source_workbook_written": is_truthy(
            first_present_value(paid_smoke, ("source_workbook_written", "source_workbook_written_by_checker"))
        ),
        "rk10_button_run": is_truthy(paid_smoke.get("rk10_button_run")),
    }
    blockers = build_blockers(checklist_rows, mock_validation, paid_smoke, result_base)
    evidence_files: list[Path] = []
    updated_intake = False
    if not blockers:
        evidence_files = write_final_evidence(result_base, final_evidence_dir, evidence_token())
        updated_intake = update_intake_csv(intake_csv, final_evidence_dir)
    if blockers:
        status = "WAITING_FOR_PAID_AZURE_OCR_APPROVAL"
    elif updated_intake:
        status = "READY_FOR_OPERATOR_FINAL_FIELDS"
    else:
        status = "BLOCKED_INTAKE_ROW_NOT_FOUND"
        blockers = ["PAID_AZURE_OCR_INTAKE_ROW_NOT_FOUND"]
    return CollectionResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status=status,
        ready_for_intake=not blockers,
        updated_intake=updated_intake,
        gate_checklist=str(gate_checklist),
        gate_checklist_exists=gate_checklist.exists(),
        gate_checklist_sha256=file_sha256(gate_checklist),
        environment_presence_csv=environment_presence_csv,
        environment_required_var_count=env_required_count,
        environment_present_var_count=env_present_count,
        environment_missing_required_vars=env_missing_vars,
        environment_secret_value_printed=False,
        required_row_count=len(checklist_rows),
        ready_required_row_count=ready_count,
        secret_value_printed_in_checklist=result_base["secret_value_printed_in_checklist"],
        mock_validation_json=str(mock_validation_json),
        mock_validation_exists=mock_validation_json.exists(),
        mock_validation_status=result_base["mock_validation_status"],
        paid_smoke_json=str(paid_smoke_json),
        paid_smoke_template_json=paid_smoke_template_json,
        paid_smoke_exists=paid_smoke_json.exists(),
        paid_smoke_status=result_base["paid_smoke_status"],
        sample_pdf_name=result_base["sample_pdf_name"],
        approver=result_base["approver"],
        approved_max_documents=result_base["approved_max_documents"],
        approved_max_pages=result_base["approved_max_pages"],
        approved_budget_yen=result_base["approved_budget_yen"],
        smoke_document_count=result_base["smoke_document_count"],
        smoke_page_count=result_base["smoke_page_count"],
        smoke_cost_yen=result_base["smoke_cost_yen"],
        paid_azure_ocr_executed=result_base["paid_azure_ocr_executed"],
        multiple_pdf_submission=result_base["multiple_pdf_submission"],
        secret_value_printed_in_smoke=result_base["secret_value_printed_in_smoke"],
        excel_copy_verified=result_base["excel_copy_verified"],
        output_workbook_exists=result_base["output_workbook_exists"],
        prod_mail_sent=result_base["prod_mail_sent"],
        source_workbook_written=result_base["source_workbook_written"],
        rk10_button_run=result_base["rk10_button_run"],
        final_evidence_dir=str(final_evidence_dir),
        final_evidence_files=[str(path) for path in evidence_files],
        intake_csv=str(intake_csv),
        blockers=", ".join(blockers),
    )


def build_markdown(result: CollectionResult) -> str:
    lines = [
        "# Scenario 71 paid Azure OCR evidence collection 2026-06-20",
        "",
        f"- generated_at: `{result.generated_at}`",
        f"- status: `{result.status}`",
        f"- ready_for_intake: `{result.ready_for_intake}`",
        f"- updated_intake: `{result.updated_intake}`",
        f"- required_row_count: `{result.required_row_count}`",
        f"- ready_required_row_count: `{result.ready_required_row_count}`",
        f"- secret_value_printed_in_checklist: `{result.secret_value_printed_in_checklist}`",
        f"- mock_validation_status: `{result.mock_validation_status}`",
        f"- paid_smoke_status: `{result.paid_smoke_status}`",
        f"- sample_pdf_name: `{result.sample_pdf_name}`",
        f"- approver: `{result.approver}`",
        f"- approved_max_documents: `{result.approved_max_documents}`",
        f"- approved_max_pages: `{result.approved_max_pages}`",
        f"- approved_budget_yen: `{result.approved_budget_yen}`",
        f"- smoke_document_count: `{result.smoke_document_count}`",
        f"- smoke_page_count: `{result.smoke_page_count}`",
        f"- smoke_cost_yen: `{result.smoke_cost_yen}`",
        f"- paid_azure_ocr_executed: `{result.paid_azure_ocr_executed}`",
        f"- multiple_pdf_submission: `{result.multiple_pdf_submission}`",
        f"- secret_value_printed_in_smoke: `{result.secret_value_printed_in_smoke}`",
        f"- excel_copy_verified: `{result.excel_copy_verified}`",
        f"- output_workbook_exists: `{result.output_workbook_exists}`",
        f"- prod_mail_sent: `{result.prod_mail_sent}`",
        f"- source_workbook_written: `{result.source_workbook_written}`",
        f"- rk10_button_run: `{result.rk10_button_run}`",
        f"- blockers: `{result.blockers}`",
        f"- gate_checklist: `{result.gate_checklist}`",
        f"- gate_checklist_sha256: `{result.gate_checklist_sha256}`",
        f"- environment_presence_csv: `{result.environment_presence_csv}`",
        f"- environment_required_var_count: `{result.environment_required_var_count}`",
        f"- environment_present_var_count: `{result.environment_present_var_count}`",
        f"- environment_missing_required_vars: `{result.environment_missing_required_vars}`",
        f"- environment_secret_value_printed: `{result.environment_secret_value_printed}`",
        f"- mock_validation_json: `{result.mock_validation_json}`",
        f"- paid_smoke_json: `{result.paid_smoke_json}`",
        f"- paid_smoke_template_json: `{result.paid_smoke_template_json}`",
        f"- final_evidence_dir: `{result.final_evidence_dir}`",
        f"- intake_csv: `{result.intake_csv}`",
        "",
        "## Safety",
        "",
        "- This collector does not call Azure OCR.",
        "- This collector does not construct an Azure client, submit a PDF, make network calls, print secrets, or write source workbooks.",
        "- This collector rejects multiple-PDF evidence and over-budget evidence.",
        "- Operator result, reviewer identity, and reviewed_at still must be supplied before the bundle can sync as final evidence.",
        "",
        "## Final Evidence Files",
        "",
    ]
    if result.final_evidence_files:
        lines.extend(f"- `{path}`" for path in result.final_evidence_files)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def build_paid_smoke_template(result: CollectionResult) -> dict[str, Any]:
    return {
        "status": "TODO_PAID_AZURE_ONE_PDF_SMOKE_OK_AFTER_APPROVAL",
        "template_only_not_evidence": True,
        "safety": (
            "Do not paste endpoint/key/secret values here. Record only host presence, "
            "approved limits, one-PDF smoke counts, and copy-workbook verification."
        ),
        "sample_pdf_name": result.sample_pdf_name or "TODO_APPROVED_SINGLE_PDF_NAME",
        "approver": result.approver or "TODO_COST_APPROVER",
        "approved_max_documents": result.approved_max_documents or 1,
        "approved_max_pages": result.approved_max_pages or "TODO_APPROVED_MAX_PAGES",
        "approved_budget_yen": result.approved_budget_yen or "TODO_APPROVED_BUDGET_YEN",
        "document_count": result.smoke_document_count or 1,
        "page_count": result.smoke_page_count or "TODO_ACTUAL_PAGE_COUNT",
        "actual_cost_yen": result.smoke_cost_yen or "TODO_ACTUAL_COST_YEN",
        "paid_azure_ocr_executed": "TODO_TRUE_AFTER_SINGLE_PAID_SMOKE",
        "multiple_pdf_submission": False,
        "secret_value_printed": False,
        "excel_copy_verified": "TODO_TRUE_AFTER_COPY_WORKBOOK_CHECK",
        "output_workbook_exists": "TODO_TRUE_AFTER_OUTPUT_WORKBOOK_CHECK",
        "prod_mail_sent": False,
        "source_workbook_written": False,
        "rk10_button_run": False,
        "environment_presence_csv": result.environment_presence_csv,
        "mock_validation_json": result.mock_validation_json,
        "gate_checklist": result.gate_checklist,
    }


def write_environment_presence_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    fieldnames = [
        "scope",
        "required_var",
        "present_in_current_process_environment",
        "secret_value_printed",
        "value",
        "source",
    ]
    try:
        write_csv_rows(path, fieldnames, rows)
        return path
    except PermissionError:
        locked_copy_path = Path(str(path) + ".locked_copy")
        write_csv_rows(locked_copy_path, fieldnames, rows)
        return locked_copy_path


def write_paid_smoke_template(path: Path, result: CollectionResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_paid_smoke_template(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Scenario 71 paid Azure OCR evidence.")
    parser.add_argument("--gate-checklist", type=Path, default=DEFAULT_GATE_CHECKLIST)
    parser.add_argument("--mock-validation-json", type=Path, default=DEFAULT_MOCK_VALIDATION_JSON)
    parser.add_argument("--paid-smoke-json", type=Path, default=DEFAULT_PAID_SMOKE_JSON)
    parser.add_argument("--intake-csv", type=Path, default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--final-evidence-dir", type=Path, default=DEFAULT_FINAL_EVIDENCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    paid_smoke_template_path = args.out_dir / "s71_paid_azure_one_pdf_smoke_summary_template.json"
    environment_presence_path = args.out_dir / "s71_azure_ocr_environment_presence.csv"
    _fieldnames, checklist_rows = read_csv_rows(args.gate_checklist)
    actual_environment_presence_path = write_environment_presence_csv(
        environment_presence_path,
        environment_presence_rows(checklist_rows),
    )
    result = build_result(
        args.gate_checklist,
        args.mock_validation_json,
        args.paid_smoke_json,
        args.intake_csv,
        args.final_evidence_dir,
        str(paid_smoke_template_path),
        str(actual_environment_presence_path),
    )
    json_path = args.out_dir / "s71_paid_azure_ocr_evidence_collect.json"
    md_path = args.out_dir / "s71_paid_azure_ocr_evidence_collect.md"
    write_paid_smoke_template(paid_smoke_template_path, result)
    json_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(result), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
