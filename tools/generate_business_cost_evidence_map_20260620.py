"""Generate a read-only business-cost evidence map for the active RK10 goal.

The report recalculates count and amount evidence from existing sample, dry-run,
and mock-apply artifacts. It does not open RK10, Outlook, Rakuraku, Azure,
printers, mail, payment systems, MainSV, or production files.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "business_cost_evidence_map_20260620"
SAFE_EXECUTION_MAP = (
    ROOT
    / "plans"
    / "reports"
    / "safe_execution_evidence_map_20260620"
    / "safe_execution_evidence_map.md.numbered"
)
S12_OUTLOOK_FINAL_EVIDENCE_DIR = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "outlook_com_bundle"
    / "final_evidence"
    / "scenario_12_13"
)
S12_SUMMARY_PATTERN = "scenario_12_13_saved_pdf_count_summary_*.csv"
S44_HANDOFF_READY = (
    ROOT
    / "plans"
    / "reports"
    / "s44_sample_ok_shadow_20260620"
    / "shadow_handoff"
    / "latest_ready.json"
)
S55_STDOUT = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\other_scenarios_safe_sample_suite_clean_20260620_092405"
    r"\s55_matsujitsu_local_dryrun.stdout.txt"
)
S70_SELECTED_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s70_sample_confirm_preview_20260620"
    / "selected_candidates.csv"
)
S71_TRANSFER_PLAN = Path(
    r"C:\ProgramData\RK10\Robots\【71法定調書用　士業請求書集計】2026-01-28"
    r"\work\runs\20260620_092405\transfer_plan.json"
)
S58_TEST_STDOUT = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\other_scenarios_safe_sample_suite_clean_20260620_092405"
    r"\s58_test_suite.stdout.txt"
)
S58_WORK_DIR = Path(
    r"C:\ProgramData\RK10\Robots\【58基幹システムより査定支払い分はきだし（25日・末日】2026-01-27"
    r"\work"
)
S58_TEST_REPORT_PATTERN = "s58_test_report_*.json"
S47_STDOUT = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\other_scenarios_safe_sample_suite_clean_20260620_092405"
    r"\s47_existing_json_dryrun_no_upload.stdout.txt"
)
S51_52_RESULT_JSON = Path(
    r"C:\ProgramData\RK10\Robots\51&52ソフトバンク部門集計楽楽精算申請"
    r"\data\result\scenario52_result_2026-05.json"
)
S51_52_LOG = Path(
    r"C:\ProgramData\RK10\Robots\51&52ソフトバンク部門集計楽楽精算申請"
    r"\log\scenario_52_20260621.log"
)
S51_52_LOG_PATTERN = "scenario_52_*.log"
S63_ARTIFACT_JSON = Path(
    r"C:\ProgramData\RK10\Robots\【63楽楽精算申請（毎月同額支払い分】2026-02-02"
    r"\work\output\scenario63_run_20260620_093053_410979.json"
)
SCENARIOS = [
    "12/13",
    "37",
    "38",
    "42",
    "43",
    "44",
    "47",
    "51/52",
    "55",
    "56",
    "57",
    "58",
    "63",
    "70",
    "71",
]
AMOUNT_RE = re.compile(r"total_amount=([0-9,]+)")
COUNT_RE = re.compile(r"支払件数（転記分）:\s*([0-9,]+)件")
PROCESS_RE = re.compile(
    r"success=(?P<success>\d+)\s+"
    r"provisional=(?P<provisional>\d+)\s+"
    r"not_found=(?P<not_found>\d+)\s+"
    r"skipped=(?P<skipped>\d+)\s+"
    r"errors=(?P<errors>\d+)\s+"
    r"overflow=(?P<overflow>\d+)\s+"
    r"total_amount=(?P<total>[0-9,]+)"
)
S47_FLAGS_RE = re.compile(r"Found\s+(?P<flags>\d+)\s+flags")
S47_SEND_SKIP_RE = re.compile(
    r"Total:\s*(?P<total>\d+),\s*To send:\s*(?P<to_send>\d+),\s*To skip:\s*(?P<to_skip>\d+)"
)
S37_METHOD1_REPORT_JSON = Path(
    r"C:\ProgramData\RK10\Robots\37レコル公休・有休登録"
    r"\work\output\sample_test_data\reports\method1_report_20260620_092415.json"
)
S38_SAFE_GATE_JSON = Path(
    r"C:\ProgramData\RK10\Robots\38受注登録"
    r"\work\output\safe_gate_20260604\s38_safe_gate_review_20260620_092416.json"
)
S42_SAFE_GATE_JSON = Path(
    r"C:\ProgramData\RK10\Robots\42ドライブレポート抽出作業"
    r"\work\safe_gate_20260604\s42_safe_gate_review_20260620_092417_416300.json"
)
S43_LAST_COMPLETION_JSON = Path(
    r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成"
    r"\Temp\scenario43_external_pipeline_v92_last_completion.json"
)
S43_APPLICATION_AMOUNTS_RE = re.compile(
    r"rakuraku application amounts=\[(?P<items>.*?)\]\s+total=(?P<total>[0-9,]+)"
)
S43_APPLICATION_AMOUNT_ITEM_RE = re.compile(r",\s*([0-9,]+)\)")
S56_SAFE_GATE_JSON = Path(
    r"C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力"
    r"\work\safe_gate_20260604\s56_safe_gate_review_20260620_092917.json"
)
S57_RUN_PLAN_JSON = Path(
    r"C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】"
    r"\work\run_plan_20260620_092918_test.json"
)
S57_UI_RUN_JSON = Path(
    r"C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】"
    r"\work\ui_run_20260620_093003_test.json"
)
S57_POST_CHECK_JSON = Path(
    r"C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】"
    r"\work\post_check_20260620_093003_test.json"
)


@dataclass(frozen=True)
class BusinessCostEvidenceRow:
    scenario: str
    cost_evidence_status: str
    item_count: int | None
    total_amount_yen: int | None
    withholding_tax_yen: int | None
    validation_result: str
    safety_scope: str
    source: str
    source_exists: bool
    production_ready: bool
    remaining_gap: str


def parse_yen(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def newest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    matches = [path for path in directory.glob(pattern) if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: (path.stat().st_mtime, path.name))


def resolve_s51_52_log_path(log_path: Path) -> Path:
    if log_path != S51_52_LOG:
        return log_path
    latest_path = newest_file(log_path.parent, S51_52_LOG_PATTERN)
    return latest_path or log_path


def build_s12_13_row(
    final_evidence_dir: Path = S12_OUTLOOK_FINAL_EVIDENCE_DIR,
) -> BusinessCostEvidenceRow:
    summary_path = newest_file(final_evidence_dir, S12_SUMMARY_PATTERN)
    if summary_path is None:
        return missing_row(
            "12/13",
            "Outlook COM final evidence exists separately, but saved PDF count summary is missing",
            final_evidence_dir,
        )
    with summary_path.open("r", encoding="utf-8-sig", newline="") as input_file:
        rows = list(csv.DictReader(input_file))
    if len(rows) != 1:
        return invalid_row("12/13", "12/13 saved PDF count summary must contain exactly one row", summary_path)
    row = rows[0]
    check_exit = parse_yen(row.get("check_outlook_com_exit"))
    dryrun_exit = parse_yen(row.get("scan_only_dryrun_exit"))
    scanned_messages = parse_yen(row.get("scanned_messages"))
    saved_count = parse_yen(row.get("saved_attachment_count"))
    printed_count = parse_yen(row.get("printed_path_count"))
    unresolved_count = parse_yen(row.get("unresolved_count"))
    if None in {check_exit, dryrun_exit, scanned_messages, saved_count, printed_count, unresolved_count}:
        return invalid_row("12/13", "12/13 saved PDF count summary contains invalid counters", summary_path)
    validation = "PASS_COUNT_ONLY"
    if check_exit != 0 or dryrun_exit != 0 or printed_count != 0 or unresolved_count != 0:
        validation = "NEEDS_REVIEW"
    return BusinessCostEvidenceRow(
        scenario="12/13",
        cost_evidence_status="OUTLOOK_COM_DRYRUN_COUNT_PROOF_NO_PRINT_NO_MAIL",
        item_count=saved_count,
        total_amount_yen=None,
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="Outlook COM scan-only dry-run; no print, no mail send, no mail state change",
        source=str(summary_path),
        source_exists=True,
        production_ready=False,
        remaining_gap=(
            f"scan-only checked {scanned_messages} messages and saved {saved_count} attachments; "
            "invoice amount extraction and real print/save/send remain separate gates"
        ),
    )


def build_s44_row(ready_path: Path = S44_HANDOFF_READY) -> BusinessCostEvidenceRow:
    if not ready_path.exists():
        return missing_row("44", "S44 shadow handoff ready file is missing", ready_path)
    ready_payload = read_json(ready_path)
    data_file_abs = str(ready_payload.get("data_file_abs", ""))
    data_path = Path(data_file_abs) if data_file_abs else ready_path.parent / str(ready_payload.get("data_file", ""))
    if not data_path.exists():
        return missing_row("44", "S44 shadow handoff data file is missing", data_path)
    payload = read_json(data_path)
    rows = payload.get("data", [])
    if not isinstance(rows, list):
        return invalid_row("44", "S44 handoff data is not a list", data_path)
    amounts = [parse_yen(item.get("amount")) for item in rows if isinstance(item, dict)]
    if any(amount is None for amount in amounts):
        return invalid_row("44", "S44 amount field is missing or invalid", data_path)
    expected_count = parse_yen(payload.get("total_count"))
    actual_count = len(amounts)
    validation = "PASS" if expected_count in {None, actual_count} else "COUNT_MISMATCH"
    return BusinessCostEvidenceRow(
        scenario="44",
        cost_evidence_status="SAMPLE_SHADOW_HANDOFF_AMOUNT_RECALCULATED",
        item_count=actual_count,
        total_amount_yen=sum(amount for amount in amounts if amount is not None),
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="LOCAL shadow handoff only; no Rakuraku upload/post/approval",
        source=str(data_path),
        source_exists=True,
        production_ready=False,
        remaining_gap="live review queue approval, production handoff, upload/post, and RK10 runtime remain separate gates",
    )


def parse_s55_stdout(stdout_path: Path = S55_STDOUT) -> BusinessCostEvidenceRow:
    if not stdout_path.exists():
        return missing_row("55", "S55 dry-run stdout is missing", stdout_path)
    text = stdout_path.read_text(encoding="utf-8", errors="replace")
    process_matches = PROCESS_RE.findall(text)
    amount_matches = AMOUNT_RE.findall(text)
    count_match = COUNT_RE.search(text)
    if not process_matches or not amount_matches:
        return invalid_row("55", "S55 dry-run summary is missing amount/process counters", stdout_path)
    last_process = PROCESS_RE.finditer(text)
    process_match = list(last_process)[-1]
    total_amount = parse_yen(process_match.group("total"))
    transfer_count = parse_yen(count_match.group(1)) if count_match else None
    if transfer_count is None:
        success = parse_yen(process_match.group("success")) or 0
        provisional = parse_yen(process_match.group("provisional")) or 0
        not_found = parse_yen(process_match.group("not_found")) or 0
        transfer_count = success + provisional + not_found
    errors = parse_yen(process_match.group("errors"))
    overflow = parse_yen(process_match.group("overflow"))
    validation = "PASS" if errors == 0 and overflow == 0 and total_amount is not None else "NEEDS_REVIEW"
    return BusinessCostEvidenceRow(
        scenario="55",
        cost_evidence_status="DRYRUN_BUSINESS_AMOUNT_REPORTED",
        item_count=transfer_count,
        total_amount_yen=total_amount,
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="LOCAL dry-run/no-mail/no production write",
        source=str(stdout_path),
        source_exists=True,
        production_ready=False,
        remaining_gap="dry-run amount is proven, but production transfer/write/mail and RK10 runtime remain separate gates",
    )


def parse_s47_stdout(stdout_path: Path = S47_STDOUT) -> BusinessCostEvidenceRow:
    if not stdout_path.exists():
        return missing_row("47", "S47 dry-run stdout is missing", stdout_path)
    text = stdout_path.read_text(encoding="utf-8", errors="replace")
    flags_match = S47_FLAGS_RE.search(text)
    send_skip_match = S47_SEND_SKIP_RE.search(text)
    if flags_match is None or send_skip_match is None:
        return invalid_row("47", "S47 dry-run stdout is missing flag/send/skip counters", stdout_path)
    flags_count = parse_yen(flags_match.group("flags"))
    total_count = parse_yen(send_skip_match.group("total"))
    to_send_count = parse_yen(send_skip_match.group("to_send"))
    to_skip_count = parse_yen(send_skip_match.group("to_skip"))
    if None in {flags_count, total_count, to_send_count, to_skip_count}:
        return invalid_row("47", "S47 dry-run stdout contains invalid counters", stdout_path)
    validation = "PASS_COUNT_ONLY"
    if flags_count != total_count or total_count != to_send_count + to_skip_count:
        validation = "COUNT_MISMATCH"
    return BusinessCostEvidenceRow(
        scenario="47",
        cost_evidence_status="DRYRUN_FLAG_COUNT_PROOF_NO_AMOUNT_NO_UPLOAD",
        item_count=flags_count,
        total_amount_yen=None,
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="LOCAL dry-run from existing JSON; no Recoru upload and no mail",
        source=str(stdout_path),
        source_exists=True,
        production_ready=False,
        remaining_gap=(
            f"dry-run found {flags_count} flags, {to_send_count} to send, {to_skip_count} to skip; "
            "business amount, live Recoru upload/mail, approval, and RK10 runtime remain separate gates"
        ),
    )


def find_result_by_check_id(results: list[object], check_id: str) -> dict[str, Any] | None:
    for item in results:
        if isinstance(item, dict) and item.get("check_id") == check_id:
            return item
    return None


def build_s37_row(report_path: Path = S37_METHOD1_REPORT_JSON) -> BusinessCostEvidenceRow:
    if not report_path.exists():
        return missing_row("37", "S37 method1 sample validation report is missing", report_path)
    payload = read_json(report_path)
    if not isinstance(payload, dict):
        return invalid_row("37", "S37 method1 report is not a JSON object", report_path)
    results = payload.get("results", [])
    if not isinstance(results, list):
        return invalid_row("37", "S37 method1 report results are not a list", report_path)
    zero_target = find_result_by_check_id(results, "M1-01")
    unknown_mapping = find_result_by_check_id(results, "M1-02")
    conversion_rules = find_result_by_check_id(results, "M1-03")
    if zero_target is None or unknown_mapping is None or conversion_rules is None:
        return invalid_row("37", "S37 method1 report is missing required check rows", report_path)
    item_count = parse_yen((zero_target.get("details") or {}).get("stdout"))
    checked_items = parse_yen((conversion_rules.get("details") or {}).get("checked_items"))
    all_passed = all(
        isinstance(item, dict) and item.get("passed") is True
        for item in [zero_target, unknown_mapping, conversion_rules]
    )
    validation = "PASS_COUNT_ONLY"
    if not all_passed or item_count != 0 or checked_items != 5:
        validation = "NEEDS_REVIEW"
    return BusinessCostEvidenceRow(
        scenario="37",
        cost_evidence_status="RECORU_SAMPLE_ZERO_TARGET_AND_GUARD_COUNT_PROOF_NO_AMOUNT",
        item_count=item_count,
        total_amount_yen=None,
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="method1 sample validation only; no live Recoru registration or mail",
        source=str(report_path),
        source_exists=True,
        production_ready=False,
        remaining_gap=(
            f"sample get-count={item_count}, unmapped-employee guard passed, "
            f"conversion rules checked {checked_items}; live Recoru registration/mail, "
            "approval, and RK10 runtime remain separate gates"
        ),
    )


def check_result(payload: dict[str, Any], check_id: str) -> str:
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return ""
    for item in checks:
        if isinstance(item, dict) and item.get("id") == check_id:
            return str(item.get("result", ""))
    return ""


def build_s38_row(review_path: Path = S38_SAFE_GATE_JSON) -> BusinessCostEvidenceRow:
    if not review_path.exists():
        return missing_row("38", "S38 safe gate review JSON is missing", review_path)
    payload = read_json(review_path)
    if not isinstance(payload, dict):
        return invalid_row("38", "S38 safe gate review is not a JSON object", review_path)
    data_count = parse_yen(payload.get("data_count"))
    validation = "PASS_COUNT_ONLY"
    if (
        data_count != 1
        or payload.get("safe_candidate_passed") is not True
        or payload.get("safe_to_prod_register") is not False
        or check_result(payload, "karuwaza_not_executed") != "PASS"
        or check_result(payload, "production_excel_not_written") != "PASS"
    ):
        validation = "NEEDS_REVIEW"
    return BusinessCostEvidenceRow(
        scenario="38",
        cost_evidence_status="ORDER_REGISTRATION_ONE_CASE_PROOF_NO_PROD_REGISTER_NO_AMOUNT",
        item_count=data_count,
        total_amount_yen=None,
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="one LOCAL safe candidate only; no Karuwaza registration and no production Excel write",
        source=str(review_path),
        source_exists=True,
        production_ready=False,
        remaining_gap=(
            f"safe candidate data_count={data_count}; Karuwaza registration and production Excel write "
            "were not executed; operator approval, site run, and RKS regeneration/runtime remain separate gates"
        ),
    )


def build_s42_row(review_path: Path = S42_SAFE_GATE_JSON) -> BusinessCostEvidenceRow:
    if not review_path.exists():
        return missing_row("42", "S42 safe gate review JSON is missing", review_path)
    payload = read_json(review_path)
    if not isinstance(payload, dict):
        return invalid_row("42", "S42 safe gate review is not a JSON object", review_path)
    latest = payload.get("latest", {})
    csv_info = latest.get("csv", {}) if isinstance(latest, dict) else {}
    excel_info = latest.get("excel", {}) if isinstance(latest, dict) else {}
    csv_rows = parse_yen(csv_info.get("row_count_without_header")) if isinstance(csv_info, dict) else None
    excel_rows = parse_yen(excel_info.get("max_row")) if isinstance(excel_info, dict) else None
    csv_dry_run = payload.get("csv_dry_run_result", {})
    static_safety = payload.get("static_safety", {})
    validation = "PASS_COUNT_ONLY"
    if (
        payload.get("local_candidate_passed") is not True
        or csv_rows is None
        or csv_rows <= 0
        or excel_rows is None
        or not isinstance(csv_dry_run, dict)
        or parse_yen(csv_dry_run.get("exit_code")) != 0
        or not isinstance(static_safety, dict)
        or static_safety.get("csv_to_excel_dry_run_no_save") is not True
        or static_safety.get("no_mainsv_write_in_python_tools") is not True
    ):
        validation = "NEEDS_REVIEW"
    return BusinessCostEvidenceRow(
        scenario="42",
        cost_evidence_status="DRIVE_REPORT_ROW_COUNT_PROOF_NO_MAINSV_WRITE",
        item_count=csv_rows,
        total_amount_yen=None,
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="CSV to Excel dry-run only; no MainSV write and no mail confirmation",
        source=str(review_path),
        source_exists=True,
        production_ready=False,
        remaining_gap=(
            f"latest CSV rows={csv_rows}, Excel rows={excel_rows}; dry-run did not save Excel or write MainSV; "
            "site save/reopen proof, mail confirmation, and RKS entry/runtime remain separate gates"
        ),
    )


def parse_s43_application_amounts(log_text: str) -> tuple[list[int], int | None]:
    match = S43_APPLICATION_AMOUNTS_RE.search(log_text)
    if match is None:
        return [], None
    amounts = [amount for amount in (parse_yen(value) for value in S43_APPLICATION_AMOUNT_ITEM_RE.findall(match.group("items"))) if amount is not None]
    return amounts, parse_yen(match.group("total"))


def build_s43_row(completion_path: Path = S43_LAST_COMPLETION_JSON) -> BusinessCostEvidenceRow:
    if not completion_path.exists():
        return missing_row("43", "S43 latest completion JSON is missing", completion_path)
    payload = read_json(completion_path)
    if not isinstance(payload, dict):
        return invalid_row("43", "S43 latest completion JSON is not an object", completion_path)
    log_path_text = str(payload.get("log", ""))
    log_path = Path(log_path_text) if log_path_text else completion_path
    if not log_path.exists():
        return missing_row("43", "S43 latest completion log is missing", log_path)
    outputs = payload.get("outputs", {})
    if not isinstance(outputs, dict):
        return invalid_row("43", "S43 latest completion outputs are not an object", completion_path)
    total_amount = parse_yen(outputs.get("total_amount"))
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    line_amounts, line_total = parse_s43_application_amounts(log_text)
    step_rows = payload.get("steps", [])
    steps_exit_zero = isinstance(step_rows, list) and all(
        isinstance(item, dict) and parse_yen(item.get("return_code")) == 0
        for item in step_rows
    )
    validation = "PASS"
    if (
        payload.get("status") != "COMPLETED_TEMPORARY_SAVE"
        or payload.get("safe_boundary") != "temporary_save_only_final_application_not_clicked"
        or payload.get("final_application_clicked") is not False
        or not steps_exit_zero
        or total_amount is None
        or not line_amounts
        or sum(line_amounts) != total_amount
        or line_total != total_amount
        or "temporary save completed" not in log_text
    ):
        validation = "NEEDS_REVIEW"
    return BusinessCostEvidenceRow(
        scenario="43",
        cost_evidence_status="RAKURAKU_TEMP_SAVE_AMOUNT_REPORTED_FINAL_NOT_CLICKED",
        item_count=len(line_amounts) if line_amounts else None,
        total_amount_yen=total_amount,
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="existing S43 temporary-save completion evidence; final application was not clicked",
        source=str(completion_path),
        source_exists=True,
        production_ready=False,
        remaining_gap=(
            f"temporary-save evidence reports {total_amount:,} yen across {len(line_amounts)} lines; "
            f"env={payload.get('env')} operator={payload.get('operator_name')}; "
            "operator final review/approval and any production rerun remain separate gates; "
            f"log={log_path}"
        ),
    )


def build_s56_row(review_path: Path = S56_SAFE_GATE_JSON) -> BusinessCostEvidenceRow:
    if not review_path.exists():
        return missing_row("56", "S56 safe gate review JSON is missing", review_path)
    payload = read_json(review_path)
    if not isinstance(payload, dict):
        return invalid_row("56", "S56 safe gate review is not a JSON object", review_path)
    latest_log = payload.get("latest_verified_log", {})
    if not isinstance(latest_log, dict):
        return invalid_row("56", "S56 latest_verified_log is not an object", review_path)
    target_count = parse_yen(latest_log.get("target_count"))
    write_count = parse_yen(latest_log.get("write_count"))
    validation = "PASS_COUNT_ONLY"
    if (
        payload.get("local_candidate_passed") is not True
        or payload.get("safe_to_prod_execute") is not False
        or target_count is None
        or write_count is None
        or target_count != write_count
        or latest_log.get("no_traceback") is not True
    ):
        validation = "NEEDS_REVIEW"
    return BusinessCostEvidenceRow(
        scenario="56",
        cost_evidence_status="S56_LOCAL_COPY_WRITE_COUNT_PROOF_NO_PRODUCTION_MAIL",
        item_count=target_count,
        total_amount_yen=None,
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="LOCAL copy/write-count evidence plus no-mail dry-run gate; no production workbook/mail execution",
        source=str(review_path),
        source_exists=True,
        production_ready=False,
        remaining_gap=(
            f"local verified log reports target_count={target_count}, write_count={write_count}, no_traceback=True; "
            "PROD preflight/dry-run, separate-name output reopen, completion mail, and RKS runtime remain separate gates"
        ),
    )


def build_s57_row(
    run_plan_path: Path = S57_RUN_PLAN_JSON,
    ui_run_path: Path = S57_UI_RUN_JSON,
    post_check_path: Path = S57_POST_CHECK_JSON,
) -> BusinessCostEvidenceRow:
    if not run_plan_path.exists():
        return missing_row("57", "S57 run plan JSON is missing", run_plan_path)
    if not ui_run_path.exists():
        return missing_row("57", "S57 UI dry-run JSON is missing", ui_run_path)
    if not post_check_path.exists():
        return missing_row("57", "S57 post-check JSON is missing", post_check_path)
    run_plan = read_json(run_plan_path)
    ui_run = read_json(ui_run_path)
    post_check = read_json(post_check_path)
    if not isinstance(run_plan, dict) or not isinstance(ui_run, dict) or not isinstance(post_check, dict):
        return invalid_row("57", "S57 dry-run artifacts must be JSON objects", run_plan_path)
    steps = ui_run.get("steps", [])
    dry_run_steps_ok = isinstance(steps, list) and all(
        isinstance(item, dict) and item.get("status") == "dry-run"
        for item in steps
    )
    validation = "PASS_COUNT_ONLY"
    if (
        run_plan.get("dry_run") is not True
        or ui_run.get("dry_run") is not True
        or ui_run.get("result_status") != "completed"
        or not dry_run_steps_ok
        or post_check.get("status") != "missing_allowed"
        or post_check.get("output_exists") is not False
    ):
        validation = "NEEDS_REVIEW"
    return BusinessCostEvidenceRow(
        scenario="57",
        cost_evidence_status="S57_DRYRUN_OUTPUT_PLAN_PROOF_NO_FINAL_COPY",
        item_count=1,
        total_amount_yen=None,
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="test dry-run plan/UI/post-check only; no MainSV final copy and no mail",
        source=str(run_plan_path),
        source_exists=True,
        production_ready=False,
        remaining_gap=(
            f"dry-run planned one output file for period {run_plan.get('period_yyyymm')} and validated "
            f"{len(steps) if isinstance(steps, list) else 0} UI steps; final output remained missing_allowed; "
            "MainSV final copy, production UI run, latest clean runtime log, and RKS runtime remain separate gates"
        ),
    )


def build_s51_52_row(
    result_path: Path = S51_52_RESULT_JSON,
    log_path: Path = S51_52_LOG,
) -> BusinessCostEvidenceRow:
    log_path = resolve_s51_52_log_path(log_path)
    if not result_path.exists():
        return missing_row("51/52", "S51/52 scenario52 result JSON is missing", result_path)
    if not log_path.exists():
        return missing_row("51/52", "S51/52 scenario52 latest log is missing", log_path)
    payload = read_json(result_path)
    if not isinstance(payload, dict):
        return invalid_row("51/52", "S51/52 result JSON is not an object", result_path)
    amounts = payload.get("rakuraku_application_amounts")
    if not isinstance(amounts, dict):
        amounts = payload.get("rakuraku_application_amounts_candidate")
    if not isinstance(amounts, dict):
        amounts = payload.get("application_amounts_candidate")
    if not isinstance(amounts, dict):
        amounts = payload.get("application_amounts", {})
    if not isinstance(amounts, dict):
        return invalid_row("51/52", "S51/52 application amount fields are not an object", result_path)
    amount_values = [parse_yen(value) for value in amounts.values()]
    saved_total = parse_yen(payload.get("saved_invoice_total"))
    if saved_total is None:
        saved_total = parse_yen(payload.get("total_amount"))
    application_total = parse_yen(payload.get("rakuraku_application_total"))
    if application_total is None:
        application_total = parse_yen(payload.get("rakuraku_application_total_candidate"))
    if application_total is None:
        application_total = parse_yen(payload.get("total_amount"))
    if None in {*amount_values, saved_total, application_total}:
        return invalid_row("51/52", "S51/52 result JSON contains invalid amount fields", result_path)
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    validation = "PASS"
    if saved_total != application_total or sum(amount for amount in amount_values if amount is not None) != application_total:
        validation = "COUNT_MISMATCH"
    formatted_total = f"{application_total:,}" if application_total is not None else ""
    excel_only_safe_stop = (
        payload.get("rakuraku_application_skipped") is True
        and payload.get("receipt_registered") is False
        and payload.get("payment_draft_saved") is False
        and payload.get("payment_submitted") is False
    )
    manual_submission_safe_stop = (
        excel_only_safe_stop
        and payload.get("manual_submission_required") is True
        and payload.get("policy") == "manual_rakuraku_submission_by_customer_staff"
        and payload.get("manual_submission_basis")
        == "scenario51_created_documents_plus_postal_invoice"
    )
    if manual_submission_safe_stop:
        if payload.get("status") != "success" or payload.get("env") not in {"LOCAL", "PROD"}:
            validation = "NEEDS_REVIEW"
        required_manual_markers = [
            f"合計金額: {formatted_total}円",
            "【正常停止】SoftBank 51/52は楽楽精算へ自動申請しません。",
            "シナリオ作成資料と郵送請求を合算し、客先担当者が手動で楽楽精算へ申請します。",
            "完了通知メール: スキップ（--no-mail）",
        ]
        if any(marker not in log_text for marker in required_manual_markers):
            validation = "NEEDS_REVIEW"
        return BusinessCostEvidenceRow(
            scenario="51/52",
            cost_evidence_status="SOFTBANK_MANUAL_SUBMISSION_AMOUNT_REPORTED_RAKURAKU_SKIPPED",
            item_count=len(amount_values),
            total_amount_yen=application_total,
            withholding_tax_yen=None,
            validation_result=validation,
            safety_scope=(
                "manual-submission record only; no Rakuraku login, no draft save, "
                "no final submit, no mail"
            ),
            source=str(result_path),
            source_exists=True,
            production_ready=False,
            remaining_gap=(
                f"scenario-created document amount is {formatted_total} yen; "
                f"department amount count is {len(amount_values)} and amount difference is 0; "
                "postal invoice combination and Rakuraku application are manual customer-staff work; "
                f"log={log_path}"
            ),
        )
    if excel_only_safe_stop:
        if payload.get("status") != "success" or payload.get("env") != "PROD":
            validation = "NEEDS_REVIEW"
        required_safe_stop_markers = [
            "【安全停止】",
            "楽楽精算登録と一時保存は行いません",
            f"楽楽申請用合計: {formatted_total}円",
        ]
        if any(marker not in log_text for marker in required_safe_stop_markers):
            validation = "NEEDS_REVIEW"
        return BusinessCostEvidenceRow(
            scenario="51/52",
            cost_evidence_status="SOFTBANK_EXCEL_ONLY_AMOUNT_REPORTED_RAKURAKU_SKIPPED",
            item_count=len(amount_values),
            total_amount_yen=application_total,
            withholding_tax_yen=None,
            validation_result=validation,
            safety_scope=(
                "PROD Excel-only safe-stop; no Rakuraku registration, no draft save, "
                "no final submit"
            ),
            source=str(result_path),
            source_exists=True,
            production_ready=False,
            remaining_gap=(
                f"Excel-only safe-stop amount is {formatted_total} yen; "
                "Rakuraku registration and draft save were skipped until paper invoice, "
                "phone-number integration, and management-table updates are ready; "
                f"log={log_path}"
            ),
        )

    if (
        payload.get("status") != "success"
        or payload.get("env") != "PROD"
        or payload.get("receipt_registered") is not True
        or payload.get("payment_draft_saved") is not True
        or payload.get("payment_submitted") is not False
    ):
        validation = "NEEDS_REVIEW"
    required_log_markers = [
        "支払依頼一時保存: 完了",
        "支払依頼申請: スキップ",
        "完了通知メール: スキップ（--no-mail）",
        f"楽楽申請用合計: {formatted_total}円",
    ]
    if any(marker not in log_text for marker in required_log_markers):
        validation = "NEEDS_REVIEW"
    return BusinessCostEvidenceRow(
        scenario="51/52",
        cost_evidence_status="RAKURAKU_DRAFT_SAVE_AMOUNT_REPORTED_NO_FINAL_SUBMIT_NO_MAIL",
        item_count=len(amount_values),
        total_amount_yen=application_total,
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="existing Rakuraku draft-save evidence; no final submit and no mail per latest log",
        source=str(result_path),
        source_exists=True,
        production_ready=False,
        remaining_gap=(
            f"receipt registered and payment draft saved for {formatted_total} yen; "
            "final submit, completion mail, RKS runtime, and operator final evidence remain separate gates; "
            f"log={log_path}"
        ),
    )


def build_s70_row(selected_csv_path: Path = S70_SELECTED_CSV) -> BusinessCostEvidenceRow:
    if not selected_csv_path.exists():
        return missing_row("70", "S70 selected candidates CSV is missing", selected_csv_path)
    with selected_csv_path.open("r", encoding="utf-8-sig", newline="") as input_file:
        rows = list(csv.DictReader(input_file))
    amounts = [parse_yen(row.get("amount_yen")) for row in rows]
    if any(amount is None for amount in amounts):
        return invalid_row("70", "S70 selected candidate amount is missing or invalid", selected_csv_path)
    return BusinessCostEvidenceRow(
        scenario="70",
        cost_evidence_status="SAMPLE_CONFIRM_PREVIEW_AMOUNT_RECALCULATED",
        item_count=len(rows),
        total_amount_yen=sum(amount for amount in amounts if amount is not None),
        withholding_tax_yen=None,
        validation_result="PASS",
        safety_scope="LOCAL confirm-preview sample only; no OK press, payment, bank upload, mail, or RK10 run",
        source=str(selected_csv_path),
        source_exists=True,
        production_ready=False,
        remaining_gap="expected count/amount, bank evidence, approver, and irreversible execute approval remain separate gates",
    )


def build_s71_row(transfer_plan_path: Path = S71_TRANSFER_PLAN) -> BusinessCostEvidenceRow:
    if not transfer_plan_path.exists():
        return missing_row("71", "S71 transfer plan is missing", transfer_plan_path)
    rows = read_json(transfer_plan_path)
    if not isinstance(rows, list):
        return invalid_row("71", "S71 transfer plan is not a list", transfer_plan_path)
    amounts = [parse_yen(row.get("amount")) for row in rows if isinstance(row, dict)]
    withholdings = [parse_yen(row.get("withholding_tax")) for row in rows if isinstance(row, dict)]
    if any(amount is None for amount in amounts) or any(tax is None for tax in withholdings):
        return invalid_row("71", "S71 amount or withholding field is missing or invalid", transfer_plan_path)
    return BusinessCostEvidenceRow(
        scenario="71",
        cost_evidence_status="REAL_PDF_MOCK_OCR_APPLY_AMOUNT_RECALCULATED",
        item_count=len(amounts),
        total_amount_yen=sum(amount for amount in amounts if amount is not None),
        withholding_tax_yen=sum(tax for tax in withholdings if tax is not None),
        validation_result="PASS",
        safety_scope="real PDFs with mock OCR and apply-copy validation only; no paid Azure OCR or source workbook write",
        source=str(transfer_plan_path),
        source_exists=True,
        production_ready=False,
        remaining_gap="paid OCR, operator review, production workbook write, mail, and RK10 runtime remain separate gates",
    )


def build_s58_row(
    report_dir: Path = S58_WORK_DIR,
    fallback_stdout_path: Path = S58_TEST_STDOUT,
) -> BusinessCostEvidenceRow:
    latest_report = newest_file(report_dir, S58_TEST_REPORT_PATTERN)
    if latest_report is None:
        if not fallback_stdout_path.exists():
            return missing_row(
                "58",
                "S58 test-suite JSON report and legacy stdout are missing",
                fallback_stdout_path,
            )
        return BusinessCostEvidenceRow(
            scenario="58",
            cost_evidence_status="AMOUNT_PARSER_TEST_CASES_PRESENT",
            item_count=None,
            total_amount_yen=None,
            withholding_tax_yen=None,
            validation_result="PASS_PARSER_TEST_ONLY",
            safety_scope="legacy text parser test-suite stdout only; no one current business-cost total",
            source=str(fallback_stdout_path),
            source_exists=True,
            production_ready=False,
            remaining_gap="current target payment file total and production write evidence remain separate gates",
        )

    payload = read_json(latest_report)
    if not isinstance(payload, dict):
        return invalid_row("58", "S58 latest test-suite report is not a JSON object", latest_report)
    results = payload.get("results", [])
    if not isinstance(results, list):
        return invalid_row("58", "S58 latest test-suite results field is not a list", latest_report)
    record_counts: list[int] = []
    total_amounts: list[int] = []
    for result in results:
        if not isinstance(result, dict):
            return invalid_row("58", "S58 latest test-suite result row is not an object", latest_report)
        actual = result.get("actual", {})
        if not isinstance(actual, dict):
            return invalid_row("58", "S58 latest test-suite actual field is not an object", latest_report)
        record_count = parse_yen(actual.get("record_count"))
        total_amount = parse_yen(actual.get("total_amount"))
        if record_count is None or total_amount is None:
            return invalid_row(
                "58",
                "S58 latest test-suite record_count or total_amount is missing or invalid",
                latest_report,
            )
        record_counts.append(record_count)
        total_amounts.append(total_amount)
    case_count = parse_yen(payload.get("case_count"))
    passed_count = parse_yen(payload.get("passed_count"))
    failed_count = parse_yen(payload.get("failed_count"))
    status = str(payload.get("status", ""))
    validation = "PASS"
    if (
        status != "completed"
        or case_count != len(results)
        or passed_count != len(results)
        or failed_count != 0
        or any(str(result.get("outcome", "")).upper() != "PASS" for result in results if isinstance(result, dict))
    ):
        validation = "NEEDS_REVIEW"
    return BusinessCostEvidenceRow(
        scenario="58",
        cost_evidence_status="LOCAL_SAMPLE_TEST_SUITE_AMOUNT_RECALCULATED",
        item_count=sum(record_counts),
        total_amount_yen=sum(total_amounts),
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="LOCAL sample test-suite with dry-run/no-mail confirmation outputs only; no MainSV write and no production mail",
        source=str(latest_report),
        source_exists=True,
        production_ready=False,
        remaining_gap="operator-selected real payment date/category, MainSV production write, mail, and RK10 runtime remain separate gates",
    )


def build_s63_row(artifact_path: Path = S63_ARTIFACT_JSON) -> BusinessCostEvidenceRow:
    if not artifact_path.exists():
        return missing_row("63", "S63 dry-run artifact JSON is missing", artifact_path)
    payload = read_json(artifact_path)
    if not isinstance(payload, dict):
        return invalid_row("63", "S63 artifact is not a JSON object", artifact_path)
    items = payload.get("items", [])
    if not isinstance(items, list):
        return invalid_row("63", "S63 items field is not a list", artifact_path)
    amounts = [parse_yen(item.get("amount")) for item in items if isinstance(item, dict)]
    if len(amounts) != len(items) or any(amount is None for amount in amounts):
        return invalid_row("63", "S63 item amount is missing or invalid", artifact_path)
    selected_items = parse_yen(payload.get("selected_items"))
    submitted = payload.get("submitted")
    mode = str(payload.get("mode", ""))
    status = str(payload.get("status", ""))
    validation = "PASS"
    if selected_items not in {None, len(amounts)}:
        validation = "COUNT_MISMATCH"
    if mode != "dry_run" or submitted is not False or status != "completed":
        validation = "NEEDS_REVIEW"
    return BusinessCostEvidenceRow(
        scenario="63",
        cost_evidence_status="LOCAL_DRYRUN_PAYMENT_ITEMS_AMOUNT_RECALCULATED",
        item_count=len(amounts),
        total_amount_yen=sum(amount for amount in amounts if amount is not None),
        withholding_tax_yen=None,
        validation_result=validation,
        safety_scope="LOCAL dry-run payment request preparation only; no final submit or production write",
        source=str(artifact_path),
        source_exists=True,
        production_ready=False,
        remaining_gap="operator review, user/applicant decision, Rakuraku final submit, mail, and RK10 runtime remain separate gates",
    )


def missing_row(scenario: str, reason: str, source: Path) -> BusinessCostEvidenceRow:
    return BusinessCostEvidenceRow(
        scenario=scenario,
        cost_evidence_status="MISSING_COST_EVIDENCE",
        item_count=None,
        total_amount_yen=None,
        withholding_tax_yen=None,
        validation_result="MISSING",
        safety_scope="read-only evidence lookup only",
        source=str(source),
        source_exists=False,
        production_ready=False,
        remaining_gap=reason,
    )


def invalid_row(scenario: str, reason: str, source: Path) -> BusinessCostEvidenceRow:
    return BusinessCostEvidenceRow(
        scenario=scenario,
        cost_evidence_status="INVALID_COST_EVIDENCE",
        item_count=None,
        total_amount_yen=None,
        withholding_tax_yen=None,
        validation_result="NEEDS_REVIEW",
        safety_scope="read-only evidence lookup only",
        source=str(source),
        source_exists=source.exists(),
        production_ready=False,
        remaining_gap=reason,
    )


def default_row(scenario: str) -> BusinessCostEvidenceRow:
    status = "NOT_SUMMARIZED_IN_THIS_COST_MAP"
    gap = "safe execution evidence exists separately; current count/amount total is not summarized in this cost map"
    return BusinessCostEvidenceRow(
        scenario=scenario,
        cost_evidence_status=status,
        item_count=None,
        total_amount_yen=None,
        withholding_tax_yen=None,
        validation_result="NOT_PROVEN_IN_COST_MAP",
        safety_scope="no external operation",
        source=str(SAFE_EXECUTION_MAP),
        source_exists=SAFE_EXECUTION_MAP.exists(),
        production_ready=False,
        remaining_gap=gap,
    )


def build_rows() -> list[BusinessCostEvidenceRow]:
    keyed_rows = {
        "12/13": build_s12_13_row(),
        "37": build_s37_row(),
        "38": build_s38_row(),
        "42": build_s42_row(),
        "43": build_s43_row(),
        "44": build_s44_row(),
        "47": parse_s47_stdout(),
        "51/52": build_s51_52_row(),
        "55": parse_s55_stdout(),
        "56": build_s56_row(),
        "57": build_s57_row(),
        "58": build_s58_row(),
        "63": build_s63_row(),
        "70": build_s70_row(),
        "71": build_s71_row(),
    }
    return [keyed_rows.get(scenario, default_row(scenario)) for scenario in SCENARIOS]


def build_payload() -> dict[str, object]:
    rows = build_rows()
    verified_rows = [
        row
        for row in rows
        if row.validation_result == "PASS" and row.total_amount_yen is not None
    ]
    missing_rows = [
        row
        for row in rows
        if row.cost_evidence_status in {"MISSING_COST_EVIDENCE", "INVALID_COST_EVIDENCE"}
    ]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": "read-only recalculation from existing local evidence; no external operation",
        "scenario_count": len(rows),
        "amount_verified_scenario_count": len(verified_rows),
        "missing_or_invalid_cost_evidence_count": len(missing_rows),
        "production_ready_count": 0,
        "safe_execution_map": str(SAFE_EXECUTION_MAP),
        "rows": [asdict(row) for row in rows],
    }


def csv_fields() -> list[str]:
    return [
        "scenario",
        "cost_evidence_status",
        "item_count",
        "total_amount_yen",
        "withholding_tax_yen",
        "validation_result",
        "safety_scope",
        "source",
        "source_exists",
        "production_ready",
        "remaining_gap",
    ]


def format_optional_int(value: object) -> str:
    amount = parse_yen(value)
    return "-" if amount is None else f"{amount:,}"


def build_markdown(payload: dict[str, object]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# Business Cost Evidence Map 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- safety: `{payload['safety']}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- amount_verified_scenario_count: `{payload['amount_verified_scenario_count']}`",
        f"- missing_or_invalid_cost_evidence_count: `{payload['missing_or_invalid_cost_evidence_count']}`",
        f"- production_ready_count: `{payload['production_ready_count']}`",
        f"- safe_execution_map: `{payload['safe_execution_map']}`",
        "",
        "## Meaning",
        "",
        "- Amount totals here prove only the stated sample/dry-run/mock-apply/draft-save scope.",
        "- They do not prove production payment, final submit, mail, print, bank upload, MainSV write, paid OCR, or RK10 runtime.",
        "",
        "## Scenario Cost Map",
        "",
        "| Scenario | Cost Evidence Status | Count | Amount Yen | Withholding Yen | Validation | Source Exists | Remaining Gap |",
        "|---|---|---:|---:|---:|---|---:|---|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    str(row["cost_evidence_status"]).replace("|", "/"),
                    format_optional_int(row["item_count"]),
                    format_optional_int(row["total_amount_yen"]),
                    format_optional_int(row["withholding_tax_yen"]),
                    str(row["validation_result"]).replace("|", "/"),
                    "YES" if row["source_exists"] else "NO",
                    str(row["remaining_gap"]).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Sources", ""])
    for row in rows:
        assert isinstance(row, dict)
        lines.append(f"- {row['scenario']}: `{row['source']}`")
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, object], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "business_cost_evidence_map.json"
    md_path = out_dir / "business_cost_evidence_map.md"
    csv_path = out_dir / "business_cost_evidence_map.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=csv_fields())
        writer.writeheader()
        rows = payload["rows"]
        assert isinstance(rows, list)
        writer.writerows(rows)
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    return {"json": str(json_path), "markdown": str(md_path), "csv": str(csv_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate business-cost evidence map.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
