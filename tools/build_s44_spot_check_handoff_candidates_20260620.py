"""Build read-only Scenario 44 handoff candidates from business spot checks.

This tool reads the business spot-check CSV and writes report artifacts only.
It never writes the live review database, the live handoff directory, Rakuraku,
PDF processed folders, mail, RK10, or production shared folders.

When one or more rows are marked confirm_ok=OK, it uses the existing
HandoffService contract to generate a shadow handoff under the report
directory. The shadow output proves the handoff data shape and checksum without
changing live state.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
ROBOT44_ROOT = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請")
ROBOT44_TOOLS = ROBOT44_ROOT / "tools"
SPOT_CHECK_CSV = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\s44_business_spot_check_sheet_20260619_1240\s44_business_spot_check_26.csv"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "s44_spot_check_handoff_candidates_20260620"
DECISION_VALUES = {"OK", "NG"}
REVIEW_BUCKET_FILENAMES = {
    "AMOUNT_ZERO_REVIEW": "s44_review_01_amount_zero_review.csv",
    "AMOUNT_MISMATCH_REVIEW": "s44_review_02_amount_mismatch_review.csv",
    "AMOUNT_MATCH_QUICK_REVIEW": "s44_review_03_amount_match_quick_review.csv",
    "REQUIRED_FIELD_REVIEW": "s44_review_04_required_field_review.csv",
    "PDF_MISSING_REVIEW": "s44_review_05_pdf_missing_review.csv",
}
BUCKET_DECISION_INPUT_FIELDS = [
    "review_bucket",
    "bucket_decision",
    "bucket_reject_reason",
    "reviewer",
    "reviewed_at",
    "eligible_row_count",
    "can_apply_ok",
    "can_apply_ng",
    "operator_next_action",
    "allowed_scope",
    "still_forbidden",
]
BUCKET_OK_ALLOWED = {"AMOUNT_MATCH_QUICK_REVIEW"}
DECISION_INPUT_FIELDS = [
    "operation_id",
    "operator_entry_confirm_ok",
    "operator_entry_reject_reason",
    "reviewer",
    "reviewed_at",
    "review_bucket",
    "review_sort_key",
    "operator_next_action",
    "attention_reasons",
    "vendor_name",
    "amount_estimate",
    "filename_amount",
    "amount_difference_yen",
    "receiving_date",
    "invoice_number",
    "filename",
    "pdf_path",
    "pdf_exists",
]
SINGLE_ENTRY_INPUT_FIELDS = [
    "entry_type",
    "review_bucket",
    "operation_id",
    "decision",
    "reject_reason",
    "reviewer",
    "reviewed_at",
    "eligible_row_count",
    "can_apply_ok",
    "can_apply_ng",
    "operator_next_action",
    "vendor_name",
    "amount_estimate",
    "filename_amount",
    "amount_difference_yen",
    "receiving_date",
    "invoice_number",
    "filename",
    "pdf_path",
    "pdf_exists",
    "allowed_scope",
    "still_forbidden",
]


@dataclass(frozen=True)
class SpotCheckSummary:
    generated_at: str
    source_csv: str
    source_exists: bool
    row_count: int
    ok_count: int
    ng_count: int
    blank_count: int
    invalid_ok_count: int
    missing_pdf_count: int
    decision_input_csv: str
    decision_input_exists: bool
    decision_input_row_count: int
    decision_input_sha256: str
    decision_overlay_applied_count: int
    decision_overlay_invalid_count: int
    bucket_decision_input_csv: str
    bucket_decision_input_exists: bool
    bucket_decision_input_row_count: int
    bucket_decision_input_sha256: str
    bucket_decision_overlay_applied_count: int
    bucket_decision_overlay_invalid_count: int
    ready_for_shadow_handoff: bool
    status: str
    next_action: str
    ok_rows: list[dict[str, str]]
    pending_rows: list[dict[str, str]]
    invalid_ok_rows: list[dict[str, str]]
    missing_pdf_rows: list[dict[str, str]]


def normalize(value: str | None) -> str:
    return (value or "").strip()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "cp932", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        except UnicodeDecodeError:
            continue
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def parse_amount(value: str | None) -> int | None:
    text = normalize(value).replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_filename_amount(filename: str | None) -> int | None:
    text = normalize(filename)
    name = text.replace("\\", "/").rsplit("/", 1)[-1]
    if not name.lower().endswith(".pdf"):
        return None
    stem = name[:-4]
    numeric_tokens = [token for token in stem.split("_") if token.isdecimal()]
    if not numeric_tokens:
        return None
    amount_token = numeric_tokens[-1]
    if len(numeric_tokens) >= 3 and len(amount_token) == 3:
        amount_token = numeric_tokens[-2]
    return parse_amount(amount_token)


def row_key(row: dict[str, str]) -> str:
    return normalize(row.get("operation_id")) or normalize(row.get("filename"))


def normalize_decision(value: str | None) -> str:
    decision = normalize(value).upper()
    if decision in DECISION_VALUES:
        return decision
    return ""


def classify_review_bucket(attention_reasons: list[str]) -> tuple[str, str, str]:
    reason_set = set(attention_reasons)
    if "PDF_MISSING" in reason_set:
        return (
            "PDF_MISSING_REVIEW",
            "Restore or re-point the PDF before entering OK.",
            "10",
        )
    if {
        "VENDOR_MISSING",
        "RECEIVING_DATE_MISSING",
        "AMOUNT_ESTIMATE_MISSING",
    } & reason_set:
        return (
            "REQUIRED_FIELD_REVIEW",
            "Fix missing vendor/date/amount fields before entering OK.",
            "20",
        )
    if "AMOUNT_ESTIMATE_ZERO" in reason_set:
        return (
            "AMOUNT_ZERO_REVIEW",
            "Do not enter OK until the PDF amount is verified and the amount source is corrected or explicitly approved.",
            "30",
        )
    if "AMOUNT_DIFFERS_FROM_FILENAME" in reason_set:
        return (
            "AMOUNT_MISMATCH_REVIEW",
            "Compare amount_estimate with the PDF/filename; enter OK only after business confirmation, otherwise enter NG with a reason.",
            "40",
        )
    return (
        "AMOUNT_MATCH_QUICK_REVIEW",
        "Open PDF briefly; enter OK only if the business owner approves this row, otherwise enter NG with a reason.",
        "50",
    )


def build_review_metadata(row: dict[str, str]) -> dict[str, str]:
    amount_estimate = parse_amount(row.get("amount_estimate"))
    filename_amount = parse_filename_amount(row.get("filename"))
    pdf_path = normalize(row.get("pdf_path"))
    pdf_exists = bool(pdf_path) and Path(pdf_path).exists()
    attention_reasons = ["NEEDS_BUSINESS_CONFIRM_OK_OR_NG"]
    if not pdf_exists:
        attention_reasons.append("PDF_MISSING")
    if not normalize(row.get("vendor_name")):
        attention_reasons.append("VENDOR_MISSING")
    if not normalize(row.get("receiving_date")):
        attention_reasons.append("RECEIVING_DATE_MISSING")
    if amount_estimate is None:
        attention_reasons.append("AMOUNT_ESTIMATE_MISSING")
    elif amount_estimate == 0:
        attention_reasons.append("AMOUNT_ESTIMATE_ZERO")
    if amount_estimate is not None and filename_amount is not None:
        if amount_estimate != filename_amount:
            attention_reasons.append("AMOUNT_DIFFERS_FROM_FILENAME")
    review_bucket, operator_next_action, review_sort_key = classify_review_bucket(
        attention_reasons
    )
    amount_difference = (
        str(amount_estimate - filename_amount)
        if amount_estimate is not None and filename_amount is not None
        else ""
    )
    return {
        "review_bucket": review_bucket,
        "review_sort_key": review_sort_key,
        "operator_next_action": operator_next_action,
        "attention_reasons": "; ".join(attention_reasons),
        "amount_estimate": str(amount_estimate) if amount_estimate is not None else "",
        "filename_amount": str(filename_amount) if filename_amount is not None else "",
        "amount_difference_yen": amount_difference,
        "pdf_exists": "YES" if pdf_exists else "NO",
    }


def build_decision_input_rows(
    source_rows: list[dict[str, str]],
    existing_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    existing_by_key = {row_key(row): row for row in existing_rows if row_key(row)}
    decision_rows: list[dict[str, str]] = []
    for row in source_rows:
        key = row_key(row)
        existing = existing_by_key.get(key, {})
        pdf_path = normalize(row.get("pdf_path"))
        review_metadata = build_review_metadata(row)
        decision_rows.append(
            {
                "operation_id": normalize(row.get("operation_id")),
                "operator_entry_confirm_ok": normalize(
                    existing.get("operator_entry_confirm_ok")
                ),
                "operator_entry_reject_reason": normalize(
                    existing.get("operator_entry_reject_reason")
                ),
                "reviewer": normalize(existing.get("reviewer")),
                "reviewed_at": normalize(existing.get("reviewed_at")),
                "review_bucket": review_metadata["review_bucket"],
                "review_sort_key": review_metadata["review_sort_key"],
                "operator_next_action": review_metadata["operator_next_action"],
                "attention_reasons": review_metadata["attention_reasons"],
                "vendor_name": normalize(row.get("vendor_name")),
                "amount_estimate": review_metadata["amount_estimate"],
                "filename_amount": review_metadata["filename_amount"],
                "amount_difference_yen": review_metadata["amount_difference_yen"],
                "receiving_date": normalize(row.get("receiving_date")),
                "invoice_number": normalize(row.get("invoice_number")),
                "filename": normalize(row.get("filename")),
                "pdf_path": pdf_path,
                "pdf_exists": review_metadata["pdf_exists"],
            }
        )
    return decision_rows


def ensure_decision_input_template(source_csv: Path, decision_input_csv: Path) -> int:
    if not source_csv.exists():
        return 0
    source_rows = read_csv_rows(source_csv)
    existing_rows = read_csv_rows(decision_input_csv) if decision_input_csv.exists() else []
    decision_rows = build_decision_input_rows(source_rows, existing_rows)
    if existing_rows == decision_rows:
        return len(decision_rows)
    try:
        write_csv(decision_input_csv, decision_rows)
    except PermissionError:
        return len(existing_rows)
    return len(decision_rows)


def row_has_decision(row: dict[str, str]) -> bool:
    return bool(
        normalize(row.get("confirm_ok"))
        or normalize(row.get("operator_entry_confirm_ok"))
    )


def bucket_operator_action(bucket: str) -> str:
    if bucket in BUCKET_OK_ALLOWED:
        return (
            "If all rows in this bucket are business-approved, enter OK once; "
            "otherwise enter NG with a shared reason or leave blank."
        )
    return (
        "Bucket OK is not allowed for this risk bucket. Enter NG with a shared "
        "reason only when all rows should be rejected, or review rows individually."
    )


def build_bucket_decision_input_rows(
    review_rows: list[dict[str, str]],
    existing_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    existing_by_bucket = {
        normalize(row.get("review_bucket")): row
        for row in existing_rows
        if normalize(row.get("review_bucket"))
    }
    eligible_counts = Counter(
        normalize(row.get("review_bucket"))
        for row in review_rows
        if normalize(row.get("review_bucket")) and not row_has_decision(row)
    )
    rows: list[dict[str, str]] = []
    for bucket in REVIEW_BUCKET_FILENAMES:
        eligible_count = eligible_counts.get(bucket, 0)
        if eligible_count == 0:
            continue
        existing = existing_by_bucket.get(bucket, {})
        rows.append(
            {
                "review_bucket": bucket,
                "bucket_decision": normalize(existing.get("bucket_decision")),
                "bucket_reject_reason": normalize(
                    existing.get("bucket_reject_reason")
                ),
                "reviewer": normalize(existing.get("reviewer")),
                "reviewed_at": normalize(existing.get("reviewed_at")),
                "eligible_row_count": str(eligible_count),
                "can_apply_ok": "YES" if bucket in BUCKET_OK_ALLOWED else "NO",
                "can_apply_ng": "YES",
                "operator_next_action": bucket_operator_action(bucket),
                "allowed_scope": (
                    "Applies only to rows in this bucket with blank row-level "
                    "operator_entry_confirm_ok."
                ),
                "still_forbidden": (
                    "No source CSV write, live review.db update, live handoff, "
                    "Rakuraku operation, PDF processed move, mail, print, RK10 "
                    "ButtonRun, or production write."
                ),
            }
        )
    return rows


def ensure_bucket_decision_input_template(
    source_csv: Path,
    decision_input_csv: Path,
    bucket_decision_input_csv: Path,
) -> int:
    if not source_csv.exists():
        return 0
    source_rows = read_csv_rows(source_csv)
    existing_decision_rows = (
        read_csv_rows(decision_input_csv) if decision_input_csv.exists() else []
    )
    review_rows = build_decision_input_rows(source_rows, existing_decision_rows)
    existing_bucket_rows = (
        read_csv_rows(bucket_decision_input_csv)
        if bucket_decision_input_csv.exists()
        else []
    )
    bucket_rows = build_bucket_decision_input_rows(review_rows, existing_bucket_rows)
    if existing_bucket_rows == bucket_rows:
        return len(bucket_rows)
    try:
        write_csv(
            bucket_decision_input_csv,
            bucket_rows,
            fieldnames=BUCKET_DECISION_INPUT_FIELDS,
        )
    except PermissionError:
        return len(existing_bucket_rows)
    return len(bucket_rows)


def single_entry_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        normalize(row.get("entry_type")).upper(),
        normalize(row.get("review_bucket")),
        normalize(row.get("operation_id")),
    )


def build_single_entry_input_rows(
    review_rows: list[dict[str, str]],
    bucket_rows: list[dict[str, str]],
    existing_single_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    existing_by_key = {
        single_entry_key(row): row
        for row in existing_single_rows
        if normalize(row.get("entry_type"))
    }
    rows: list[dict[str, str]] = []
    for bucket_row in bucket_rows:
        key = ("BUCKET", normalize(bucket_row.get("review_bucket")), "")
        existing = existing_by_key.get(key, {})
        rows.append(
            {
                "entry_type": "BUCKET",
                "review_bucket": normalize(bucket_row.get("review_bucket")),
                "operation_id": "",
                "decision": normalize(existing.get("decision"))
                or normalize(bucket_row.get("bucket_decision")),
                "reject_reason": normalize(existing.get("reject_reason"))
                or normalize(bucket_row.get("bucket_reject_reason")),
                "reviewer": normalize(existing.get("reviewer"))
                or normalize(bucket_row.get("reviewer")),
                "reviewed_at": normalize(existing.get("reviewed_at"))
                or normalize(bucket_row.get("reviewed_at")),
                "eligible_row_count": normalize(bucket_row.get("eligible_row_count")),
                "can_apply_ok": normalize(bucket_row.get("can_apply_ok")),
                "can_apply_ng": normalize(bucket_row.get("can_apply_ng")),
                "operator_next_action": normalize(
                    bucket_row.get("operator_next_action")
                ),
                "vendor_name": "",
                "amount_estimate": "",
                "filename_amount": "",
                "amount_difference_yen": "",
                "receiving_date": "",
                "invoice_number": "",
                "filename": "",
                "pdf_path": "",
                "pdf_exists": "",
                "allowed_scope": normalize(bucket_row.get("allowed_scope")),
                "still_forbidden": normalize(bucket_row.get("still_forbidden")),
            }
        )
    for review_row in sorted(review_rows, key=review_sort_value):
        key = (
            "ROW",
            normalize(review_row.get("review_bucket")),
            normalize(review_row.get("operation_id")),
        )
        existing = existing_by_key.get(key, {})
        rows.append(
            {
                "entry_type": "ROW",
                "review_bucket": normalize(review_row.get("review_bucket")),
                "operation_id": normalize(review_row.get("operation_id")),
                "decision": normalize(existing.get("decision"))
                or normalize(review_row.get("operator_entry_confirm_ok")),
                "reject_reason": normalize(existing.get("reject_reason"))
                or normalize(review_row.get("operator_entry_reject_reason")),
                "reviewer": normalize(existing.get("reviewer"))
                or normalize(review_row.get("reviewer")),
                "reviewed_at": normalize(existing.get("reviewed_at"))
                or normalize(review_row.get("reviewed_at")),
                "eligible_row_count": "",
                "can_apply_ok": "YES",
                "can_apply_ng": "YES",
                "operator_next_action": normalize(
                    review_row.get("operator_next_action")
                ),
                "vendor_name": normalize(review_row.get("vendor_name")),
                "amount_estimate": normalize(review_row.get("amount_estimate")),
                "filename_amount": normalize(review_row.get("filename_amount")),
                "amount_difference_yen": normalize(
                    review_row.get("amount_difference_yen")
                ),
                "receiving_date": normalize(review_row.get("receiving_date")),
                "invoice_number": normalize(review_row.get("invoice_number")),
                "filename": normalize(review_row.get("filename")),
                "pdf_path": normalize(review_row.get("pdf_path")),
                "pdf_exists": normalize(review_row.get("pdf_exists")),
                "allowed_scope": (
                    "Applies only to this operation_id. Blank decision keeps the row on hold."
                ),
                "still_forbidden": (
                    "No source CSV write, live review.db update, live handoff, "
                    "Rakuraku operation, PDF processed move, mail, print, RK10 "
                    "ButtonRun, or production write."
                ),
            }
        )
    return rows


def ensure_single_entry_input_template(
    source_csv: Path,
    decision_input_csv: Path,
    bucket_decision_input_csv: Path,
    single_entry_input_csv: Path,
) -> int:
    if not source_csv.exists():
        return 0
    source_rows = read_csv_rows(source_csv)
    decision_rows = (
        read_csv_rows(decision_input_csv) if decision_input_csv.exists() else []
    )
    review_rows = build_decision_input_rows(source_rows, decision_rows)
    bucket_rows = (
        read_csv_rows(bucket_decision_input_csv)
        if bucket_decision_input_csv.exists()
        else []
    )
    existing_single_rows = (
        read_csv_rows(single_entry_input_csv)
        if single_entry_input_csv.exists()
        else []
    )
    single_rows = build_single_entry_input_rows(
        review_rows,
        bucket_rows,
        existing_single_rows,
    )
    if existing_single_rows == single_rows:
        return len(single_rows)
    try:
        write_csv(
            single_entry_input_csv,
            single_rows,
            fieldnames=SINGLE_ENTRY_INPUT_FIELDS,
        )
    except PermissionError:
        return len(existing_single_rows)
    return len(single_rows)


def single_entry_has_operator_input(row: dict[str, str]) -> bool:
    return any(
        normalize(row.get(field))
        for field in ("decision", "reject_reason", "reviewer", "reviewed_at")
    )


def sync_single_entry_input_to_decision_inputs(
    single_entry_input_csv: Path,
    decision_input_csv: Path,
    bucket_decision_input_csv: Path,
) -> tuple[int, int]:
    if not single_entry_input_csv.exists():
        return 0, 0
    single_rows = read_csv_rows(single_entry_input_csv)
    row_entries = {
        normalize(row.get("operation_id")): row
        for row in single_rows
        if normalize(row.get("entry_type")).upper() == "ROW"
        and normalize(row.get("operation_id"))
        and single_entry_has_operator_input(row)
    }
    bucket_entries = {
        normalize(row.get("review_bucket")): row
        for row in single_rows
        if normalize(row.get("entry_type")).upper() == "BUCKET"
        and normalize(row.get("review_bucket"))
        and single_entry_has_operator_input(row)
    }
    row_sync_count = 0
    bucket_sync_count = 0
    if decision_input_csv.exists() and row_entries:
        decision_rows = read_csv_rows(decision_input_csv)
        synced_decision_rows: list[dict[str, str]] = []
        for row in decision_rows:
            entry = row_entries.get(normalize(row.get("operation_id")))
            if not entry:
                synced_decision_rows.append(dict(row))
                continue
            synced_decision_rows.append(
                {
                    **row,
                    "operator_entry_confirm_ok": normalize(entry.get("decision")),
                    "operator_entry_reject_reason": normalize(
                        entry.get("reject_reason")
                    ),
                    "reviewer": normalize(entry.get("reviewer")),
                    "reviewed_at": normalize(entry.get("reviewed_at")),
                }
            )
            row_sync_count += 1
        try:
            write_csv(
                decision_input_csv,
                synced_decision_rows,
                fieldnames=DECISION_INPUT_FIELDS,
            )
        except PermissionError:
            row_sync_count = 0
    if bucket_decision_input_csv.exists() and bucket_entries:
        bucket_rows = read_csv_rows(bucket_decision_input_csv)
        synced_bucket_rows: list[dict[str, str]] = []
        for row in bucket_rows:
            entry = bucket_entries.get(normalize(row.get("review_bucket")))
            if not entry:
                synced_bucket_rows.append(dict(row))
                continue
            synced_bucket_rows.append(
                {
                    **row,
                    "bucket_decision": normalize(entry.get("decision")),
                    "bucket_reject_reason": normalize(entry.get("reject_reason")),
                    "reviewer": normalize(entry.get("reviewer")),
                    "reviewed_at": normalize(entry.get("reviewed_at")),
                }
            )
            bucket_sync_count += 1
        try:
            write_csv(
                bucket_decision_input_csv,
                synced_bucket_rows,
                fieldnames=BUCKET_DECISION_INPUT_FIELDS,
            )
        except PermissionError:
            bucket_sync_count = 0
    return row_sync_count, bucket_sync_count


def apply_decision_input_rows(
    source_rows: list[dict[str, str]],
    decision_input_csv: Path | None,
) -> tuple[list[dict[str, str]], int, int, int, str, bool]:
    if decision_input_csv is None:
        return source_rows, 0, 0, 0, "", False
    if not decision_input_csv.exists():
        return source_rows, 0, 0, 0, "", False
    decision_rows = read_csv_rows(decision_input_csv)
    decision_by_key = {row_key(row): row for row in decision_rows if row_key(row)}
    applied_count = 0
    invalid_count = 0
    merged_rows: list[dict[str, str]] = []
    for row in source_rows:
        key = row_key(row)
        decision_row = decision_by_key.get(key, {})
        raw_decision = normalize(decision_row.get("operator_entry_confirm_ok"))
        decision = normalize_decision(raw_decision)
        reviewer = normalize(decision_row.get("reviewer"))
        reviewed_at = normalize(decision_row.get("reviewed_at"))
        reject_reason = normalize(decision_row.get("operator_entry_reject_reason"))
        missing_required_review_fields = bool(decision) and (
            not reviewer or not reviewed_at or (decision == "NG" and not reject_reason)
        )
        if raw_decision and (not decision or missing_required_review_fields):
            invalid_count += 1
            merged_rows.append(dict(row))
            continue
        if not decision:
            merged_rows.append(dict(row))
            continue
        merged_rows.append(
            {
                **row,
                "confirm_ok": decision,
                "reject_reason": reject_reason or normalize(row.get("reject_reason")),
            }
        )
        applied_count += 1
    return (
        merged_rows,
        applied_count,
        invalid_count,
        len(decision_rows),
        file_sha256(decision_input_csv),
        True,
    )


def validate_bucket_decision(row: dict[str, str]) -> str:
    bucket = normalize(row.get("review_bucket"))
    raw_decision = normalize(row.get("bucket_decision"))
    decision = normalize_decision(raw_decision)
    if not bucket or bucket not in REVIEW_BUCKET_FILENAMES:
        return ""
    if raw_decision and not decision:
        return ""
    if not decision:
        return ""
    reviewer = normalize(row.get("reviewer"))
    reviewed_at = normalize(row.get("reviewed_at"))
    if not reviewer or not reviewed_at:
        return ""
    if decision == "OK" and bucket not in BUCKET_OK_ALLOWED:
        return ""
    if decision == "NG" and not normalize(row.get("bucket_reject_reason")):
        return ""
    return decision


def is_invalid_bucket_decision(row: dict[str, str]) -> bool:
    bucket = normalize(row.get("review_bucket"))
    raw_decision = normalize(row.get("bucket_decision"))
    if not raw_decision:
        return False
    if not bucket or bucket not in REVIEW_BUCKET_FILENAMES:
        return True
    decision = normalize_decision(raw_decision)
    if not decision:
        return True
    reviewer = normalize(row.get("reviewer"))
    reviewed_at = normalize(row.get("reviewed_at"))
    if not reviewer or not reviewed_at:
        return True
    if decision == "OK" and bucket not in BUCKET_OK_ALLOWED:
        return True
    if decision == "NG" and not normalize(row.get("bucket_reject_reason")):
        return True
    return False


def apply_bucket_decision_input_rows(
    source_rows: list[dict[str, str]],
    bucket_decision_input_csv: Path | None,
) -> tuple[list[dict[str, str]], int, int, int, str, bool]:
    if bucket_decision_input_csv is None:
        return source_rows, 0, 0, 0, "", False
    if not bucket_decision_input_csv.exists():
        return source_rows, 0, 0, 0, "", False
    bucket_rows = read_csv_rows(bucket_decision_input_csv)
    invalid_count = sum(1 for row in bucket_rows if is_invalid_bucket_decision(row))
    decisions_by_bucket = {
        normalize(row.get("review_bucket")): row
        for row in bucket_rows
        if validate_bucket_decision(row)
    }
    applied_count = 0
    merged_rows: list[dict[str, str]] = []
    for row in source_rows:
        if normalize(row.get("confirm_ok")):
            merged_rows.append(dict(row))
            continue
        review_bucket = build_review_metadata(row)["review_bucket"]
        bucket_row = decisions_by_bucket.get(review_bucket)
        if not bucket_row:
            merged_rows.append(dict(row))
            continue
        decision = validate_bucket_decision(bucket_row)
        merged_rows.append(
            {
                **row,
                "confirm_ok": decision,
                "reject_reason": normalize(bucket_row.get("bucket_reject_reason"))
                or normalize(row.get("reject_reason")),
            }
        )
        applied_count += 1
    return (
        merged_rows,
        applied_count,
        invalid_count,
        len(bucket_rows),
        file_sha256(bucket_decision_input_csv),
        True,
    )


def is_ok(row: dict[str, str]) -> bool:
    return normalize(row.get("confirm_ok")).upper() == "OK"


def is_ng(row: dict[str, str]) -> bool:
    return normalize(row.get("confirm_ok")).upper() == "NG"


def has_required_ok_fields(row: dict[str, str]) -> bool:
    amount = parse_amount(row.get("amount_estimate"))
    required = [
        normalize(row.get("vendor_name")),
        normalize(row.get("receiving_date")),
        normalize(row.get("pdf_path")),
    ]
    return all(required) and amount is not None


def analyze_spot_check(
    path: Path,
    decision_input_csv: Path | None = None,
    bucket_decision_input_csv: Path | None = None,
) -> SpotCheckSummary:
    generated_at = datetime.now().isoformat(timespec="seconds")
    if not path.exists():
        return SpotCheckSummary(
            generated_at=generated_at,
            source_csv=str(path),
            source_exists=False,
            row_count=0,
            ok_count=0,
            ng_count=0,
            blank_count=0,
            invalid_ok_count=0,
            missing_pdf_count=0,
            decision_input_csv=str(decision_input_csv or ""),
            decision_input_exists=bool(decision_input_csv and decision_input_csv.exists()),
            decision_input_row_count=0,
            decision_input_sha256="",
            decision_overlay_applied_count=0,
            decision_overlay_invalid_count=0,
            bucket_decision_input_csv=str(bucket_decision_input_csv or ""),
            bucket_decision_input_exists=bool(
                bucket_decision_input_csv and bucket_decision_input_csv.exists()
            ),
            bucket_decision_input_row_count=0,
            bucket_decision_input_sha256="",
            bucket_decision_overlay_applied_count=0,
            bucket_decision_overlay_invalid_count=0,
            ready_for_shadow_handoff=False,
            status="HOLD_MISSING_SPOT_CHECK",
            next_action="Restore or recreate the Scenario 44 business spot-check CSV.",
            ok_rows=[],
            pending_rows=[],
            invalid_ok_rows=[],
            missing_pdf_rows=[],
        )

    rows = read_csv_rows(path)
    (
        rows,
        decision_overlay_applied_count,
        decision_overlay_invalid_count,
        decision_input_row_count,
        decision_input_sha256,
        decision_input_exists,
    ) = apply_decision_input_rows(rows, decision_input_csv)
    (
        rows,
        bucket_decision_overlay_applied_count,
        bucket_decision_overlay_invalid_count,
        bucket_decision_input_row_count,
        bucket_decision_input_sha256,
        bucket_decision_input_exists,
    ) = apply_bucket_decision_input_rows(rows, bucket_decision_input_csv)
    ok_rows = [row for row in rows if is_ok(row)]
    ng_rows = [row for row in rows if is_ng(row)]
    blank_rows = [row for row in rows if not normalize(row.get("confirm_ok"))]
    pending_rows = [row for row in rows if not is_ok(row)]
    invalid_ok_rows = [row for row in ok_rows if not has_required_ok_fields(row)]
    missing_pdf_rows = [
        row
        for row in ok_rows
        if normalize(row.get("pdf_path")) and not Path(normalize(row.get("pdf_path"))).exists()
    ]

    if decision_overlay_invalid_count or bucket_decision_overlay_invalid_count:
        status = "HOLD_DECISION_INPUT_INVALID"
        next_action = (
            "Fix row/bucket decision input values. Row decisions accept OK, NG, "
            "or blank; OK/NG rows require reviewer and reviewed_at, and NG rows "
            "also require a reject reason. Bucket OK is allowed only for "
            "AMOUNT_MATCH_QUICK_REVIEW; bucket NG requires reviewer, reviewed_at, "
            "and a shared reject reason."
        )
    elif not ok_rows:
        status = "HOLD_NO_OK_ROWS"
        next_action = (
            "Business owner must mark operator_entry_confirm_ok=OK/NG "
            "in the repo-local decision input CSV for rows allowed to advance."
        )
    elif invalid_ok_rows:
        status = "HOLD_OK_ROWS_INVALID"
        next_action = "Fix missing vendor/date/pdf/amount fields before shadow handoff generation."
    elif missing_pdf_rows:
        status = "HOLD_OK_ROWS_PDF_MISSING"
        next_action = "Restore or re-point missing PDFs before shadow handoff generation."
    else:
        status = "READY_FOR_SHADOW_HANDOFF"
        next_action = "Generate shadow handoff now; live handoff still needs a separate approval."

    return SpotCheckSummary(
        generated_at=generated_at,
        source_csv=str(path),
        source_exists=True,
        row_count=len(rows),
        ok_count=len(ok_rows),
        ng_count=len(ng_rows),
        blank_count=len(blank_rows),
        invalid_ok_count=len(invalid_ok_rows),
        missing_pdf_count=len(missing_pdf_rows),
        decision_input_csv=str(decision_input_csv or ""),
        decision_input_exists=decision_input_exists,
        decision_input_row_count=decision_input_row_count,
        decision_input_sha256=decision_input_sha256,
        decision_overlay_applied_count=decision_overlay_applied_count,
        decision_overlay_invalid_count=decision_overlay_invalid_count,
        bucket_decision_input_csv=str(bucket_decision_input_csv or ""),
        bucket_decision_input_exists=bucket_decision_input_exists,
        bucket_decision_input_row_count=bucket_decision_input_row_count,
        bucket_decision_input_sha256=bucket_decision_input_sha256,
        bucket_decision_overlay_applied_count=bucket_decision_overlay_applied_count,
        bucket_decision_overlay_invalid_count=bucket_decision_overlay_invalid_count,
        ready_for_shadow_handoff=status == "READY_FOR_SHADOW_HANDOFF",
        status=status,
        next_action=next_action,
        ok_rows=ok_rows,
        pending_rows=pending_rows,
        invalid_ok_rows=invalid_ok_rows,
        missing_pdf_rows=missing_pdf_rows,
    )


def build_handoff_items(ok_rows: Iterable[dict[str, str]]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for index, row in enumerate(ok_rows):
        amount = parse_amount(row.get("amount_estimate"))
        if amount is None:
            amount = 0
        pdf_path = normalize(row.get("pdf_path"))
        filename = normalize(row.get("filename")) or Path(pdf_path).name
        operation_id = normalize(row.get("operation_id"))
        items.append(
            {
                "_index": index,
                "_pdf_path": pdf_path,
                "_pdf_name": filename,
                "_item_id": operation_id or filename,
                "_current_state": "business_spot_check_ok",
                "idempotency_key": operation_id or filename,
                "vendor_name": normalize(row.get("vendor_name")),
                "issue_date": normalize(row.get("receiving_date")),
                "receiving_date": normalize(row.get("receiving_date")),
                "invoice_number": normalize(row.get("invoice_number")),
                "amount": amount,
                "remarks": "business spot check OK; shadow handoff only",
                "amounts": [{"amount": amount}],
            }
        )
    return items


def build_review_aid_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    review_rows: list[dict[str, str]] = []
    for row in rows:
        pdf_path = normalize(row.get("pdf_path"))
        review_metadata = build_review_metadata(row)
        review_rows.append(
            {
                "confirm_ok": normalize(row.get("confirm_ok")),
                "reject_reason": normalize(row.get("reject_reason")),
                "operator_entry_confirm_ok": "",
                "operator_entry_reject_reason": "",
                "review_bucket": review_metadata["review_bucket"],
                "review_sort_key": review_metadata["review_sort_key"],
                "operator_next_action": review_metadata["operator_next_action"],
                "attention_reasons": review_metadata["attention_reasons"],
                "vendor_name": normalize(row.get("vendor_name")),
                "amount_estimate": review_metadata["amount_estimate"],
                "filename_amount": review_metadata["filename_amount"],
                "amount_difference_yen": review_metadata["amount_difference_yen"],
                "receiving_date": normalize(row.get("receiving_date")),
                "invoice_number": normalize(row.get("invoice_number")),
                "filename": normalize(row.get("filename")),
                "operation_id": normalize(row.get("operation_id")),
                "pdf_exists": review_metadata["pdf_exists"],
                "pdf_path": pdf_path,
            }
        )
    return review_rows


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_csv(
    path: Path,
    rows: list[dict[str, str]],
    fieldnames: list[str] | None = None,
) -> None:
    output_fieldnames = fieldnames or (list(rows[0].keys()) if rows else [
        "confirm_ok",
        "reject_reason",
        "vendor_name",
        "amount_estimate",
        "receiving_date",
        "invoice_number",
        "filename",
        "operation_id",
        "pdf_path",
    ])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def review_sort_value(row: dict[str, str]) -> tuple[int, str, str, str]:
    try:
        sort_key = int(normalize(row.get("review_sort_key")))
    except ValueError:
        sort_key = 999
    return (
        sort_key,
        normalize(row.get("vendor_name")),
        normalize(row.get("receiving_date")),
        normalize(row.get("operation_id")),
    )


def write_review_priority_files(
    out_dir: Path,
    review_aid_rows: list[dict[str, str]],
) -> tuple[Path, dict[str, str]]:
    sorted_rows = sorted(review_aid_rows, key=review_sort_value)
    priority_csv = out_dir / "s44_business_review_priority_queue.csv"
    write_csv(priority_csv, sorted_rows)

    bucket_csvs: dict[str, str] = {}
    for bucket, filename in REVIEW_BUCKET_FILENAMES.items():
        bucket_rows = [row for row in sorted_rows if row.get("review_bucket") == bucket]
        if not bucket_rows:
            continue
        bucket_csv = out_dir / filename
        write_csv(bucket_csv, bucket_rows)
        bucket_csvs[bucket] = str(bucket_csv)
    return priority_csv, bucket_csvs


def build_minimum_input_plan(
    summary: SpotCheckSummary,
    review_bucket_counts: dict[str, int],
) -> list[dict[str, str]]:
    quick_count = review_bucket_counts.get("AMOUNT_MATCH_QUICK_REVIEW", 0)
    mismatch_count = review_bucket_counts.get("AMOUNT_MISMATCH_REVIEW", 0)
    zero_count = review_bucket_counts.get("AMOUNT_ZERO_REVIEW", 0)
    risk_count = mismatch_count + zero_count
    total_review_count = sum(review_bucket_counts.values())
    plan: list[dict[str, str]] = []
    if quick_count:
        plan.append(
            {
                "priority": "1",
                "target": "AMOUNT_MATCH_QUICK_REVIEW bucket row",
                "allowed_input": "OK or NG in bucket_decision",
                "ok_effect": (
                    f"Up to {quick_count} row(s) can become OK candidates; "
                    f"{max(total_review_count - quick_count, 0)} risk row(s) remain held."
                ),
                "safety_condition": (
                    "Use bucket OK only when every quick-review row is business-approved."
                ),
            }
        )
    if risk_count:
        plan.append(
            {
                "priority": "2",
                "target": "AMOUNT_ZERO_REVIEW and AMOUNT_MISMATCH_REVIEW rows",
                "allowed_input": "row-level OK/NG, or bucket-level NG only",
                "ok_effect": (
                    "Risk buckets cannot be bulk-approved; accepted rows require "
                    "row-level business review."
                ),
                "safety_condition": (
                    f"Review {zero_count} zero-amount row(s) and "
                    f"{mismatch_count} mismatch row(s) before production migration."
                ),
            }
        )
    if summary.blank_count:
        plan.append(
            {
                "priority": "3",
                "target": "blank decisions",
                "allowed_input": "leave blank to keep rows on hold",
                "ok_effect": f"{summary.blank_count} row(s) remain blocked until reviewed.",
                "safety_condition": (
                    "Blank means hold; it never updates live review.db or live handoff."
                ),
            }
        )
    return plan


def build_operator_next_steps_markdown(
    summary: SpotCheckSummary,
    bucket_decision_input_csv: Path,
    priority_csv: Path,
    bucket_csvs: dict[str, str],
    review_bucket_counts: dict[str, int],
    single_entry_input_csv: Path | None = None,
) -> str:
    quick_count = review_bucket_counts.get("AMOUNT_MATCH_QUICK_REVIEW", 0)
    mismatch_count = review_bucket_counts.get("AMOUNT_MISMATCH_REVIEW", 0)
    zero_count = review_bucket_counts.get("AMOUNT_ZERO_REVIEW", 0)
    total_review_count = sum(review_bucket_counts.values())
    risk_count = mismatch_count + zero_count
    lines = [
        "# Scenario 44 business review next steps",
        "",
        f"- generated_at: `{summary.generated_at}`",
        f"- status: `{summary.status}`",
        f"- source_csv: `{summary.source_csv}`",
        f"- single_entry_input_csv: `{single_entry_input_csv or ''}`",
        f"- decision_input_csv: `{summary.decision_input_csv}`",
        f"- bucket_decision_input_csv: `{bucket_decision_input_csv}`",
        f"- priority_queue_csv: `{priority_csv}`",
        f"- total_review_rows: `{total_review_count}`",
        f"- quick_review_rows: `{quick_count}`",
        f"- mismatch_review_rows: `{mismatch_count}`",
        f"- zero_amount_review_rows: `{zero_count}`",
        "",
        "## Fastest Safe Input Path",
        "",
        "- First open the single-entry CSV and review the `BUCKET` rows.",
        "- `AMOUNT_MATCH_QUICK_REVIEW` can be marked `OK` only if every row in that bucket is business-approved.",
        "- `AMOUNT_MISMATCH_REVIEW` and `AMOUNT_ZERO_REVIEW` cannot be bulk-marked `OK`; they can only be bulk-marked `NG` with reviewer, reviewed_at, and a shared reject reason.",
        "- If a risk-bucket row should be accepted, leave the bucket blank and use the `ROW` entry for that operation_id.",
        "",
        "## Minimum Inputs To Unblock",
        "",
        f"- Current decisions: OK `{summary.ok_count}`, NG `{summary.ng_count}`, blank `{summary.blank_count}`.",
        f"- Fastest shadow-handoff unlock: if all quick-review rows are business-approved, enter `OK` only on the `AMOUNT_MATCH_QUICK_REVIEW` bucket row; this can create `{quick_count}` OK candidate(s) and leaves `{risk_count}` risk row(s) held.",
        "- Every `OK/NG` entry must include `reviewer` and `reviewed_at`; every `NG` entry must also include a reject reason.",
        "- If even one quick-review row is not approved, do not use bucket `OK`; review rows individually in the row-level decision CSV.",
        "- Full Scenario 44 completion still requires each zero-amount and amount-mismatch row to be reviewed as row-level `OK/NG`, or bucket-level `NG` only when every row in that risk bucket should be rejected.",
        "",
        "## Review Order (fastest-to-unblock)",
        "",
        f"- 1. Quick amount-match rows: `{bucket_csvs.get('AMOUNT_MATCH_QUICK_REVIEW', '')}`",
        f"- 2. Amount mismatch rows: `{bucket_csvs.get('AMOUNT_MISMATCH_REVIEW', '')}`",
        f"- 3. High-risk zero amount rows: `{bucket_csvs.get('AMOUNT_ZERO_REVIEW', '')}`",
        "- This order only reduces the first HOLD. Full Scenario 44 completion still requires all risk rows to be reviewed safely.",
        "",
        "## After Editing",
        "",
        "- Re-run the fixed safe runner to regenerate the Scenario 44 report and decide whether shadow handoff can be generated.",
        "- Do not edit the source spot-check CSV directly.",
        "- Do not update live review.db, create live handoff, move PDFs to processed, operate Rakuraku, send mail, print, press RK10 ButtonRun, or write production files.",
    ]
    return "\n".join(lines) + "\n"


def write_operator_next_steps_file(
    out_dir: Path,
    summary: SpotCheckSummary,
    bucket_decision_input_csv: Path,
    priority_csv: Path,
    bucket_csvs: dict[str, str],
    review_bucket_counts: dict[str, int],
    single_entry_input_csv: Path | None = None,
) -> Path:
    next_steps_md = out_dir / "s44_business_review_next_steps.md"
    next_steps_text = build_operator_next_steps_markdown(
        summary,
        bucket_decision_input_csv,
        priority_csv,
        bucket_csvs,
        review_bucket_counts,
        single_entry_input_csv,
    )
    try:
        next_steps_md.write_text(next_steps_text, encoding="utf-8")
    except PermissionError:
        locked_copy = Path(str(next_steps_md) + ".locked_copy")
        locked_copy.write_text(next_steps_text, encoding="utf-8")
        write_numbered_copy(locked_copy)
        return locked_copy
    try:
        write_numbered_copy(next_steps_md)
    except PermissionError:
        Path(str(next_steps_md) + ".numbered.locked_copy").write_text(
            "\n".join(
                f"{index:5}: {line}"
                for index, line in enumerate(next_steps_text.splitlines(), 1)
            )
            + "\n",
            encoding="utf-8",
        )
    return next_steps_md


def generate_shadow_handoff(summary: SpotCheckSummary, out_dir: Path) -> dict[str, object] | None:
    if not summary.ready_for_shadow_handoff:
        return None
    sys.path.insert(0, str(ROBOT44_TOOLS))
    from review_helper.services.handoff_service import HandoffService

    handoff_dir = out_dir / "shadow_handoff"
    service = HandoffService(handoff_dir=handoff_dir)
    result = service.generate_handoff(
        data_items=build_handoff_items(summary.ok_rows),
        manual_queue=[],
        ready_by="codex:s44_spot_check_shadow",
        env="LOCAL",
    )
    verified, message = service.verify_handoff()
    return {
        "generated": True,
        "verified": verified,
        "verify_message": message,
        **result,
    }


def build_markdown(
    summary: SpotCheckSummary,
    shadow_result: dict[str, object] | None,
    review_aid_csv: Path,
    bucket_decision_input_csv: Path,
    review_attention_count: int,
    review_bucket_counts: dict[str, int],
    priority_csv: Path,
    bucket_csvs: dict[str, str],
    next_steps_md: Path,
    single_entry_input_csv: Path,
    single_entry_input_row_count: int,
) -> str:
    minimum_input_plan = build_minimum_input_plan(summary, review_bucket_counts)
    lines = [
        "# Scenario 44 business spot-check handoff candidates",
        "",
        f"- generated_at: `{summary.generated_at}`",
        f"- status: `{summary.status}`",
        f"- source_csv: `{summary.source_csv}`",
        f"- row_count: `{summary.row_count}`",
        f"- ok_count: `{summary.ok_count}`",
        f"- ng_count: `{summary.ng_count}`",
        f"- blank_count: `{summary.blank_count}`",
        f"- invalid_ok_count: `{summary.invalid_ok_count}`",
        f"- missing_pdf_count: `{summary.missing_pdf_count}`",
        f"- decision_input_csv: `{summary.decision_input_csv}`",
        f"- decision_input_exists: `{summary.decision_input_exists}`",
        f"- decision_input_row_count: `{summary.decision_input_row_count}`",
        f"- decision_overlay_applied_count: `{summary.decision_overlay_applied_count}`",
        f"- decision_overlay_invalid_count: `{summary.decision_overlay_invalid_count}`",
        f"- bucket_decision_input_csv: `{summary.bucket_decision_input_csv}`",
        f"- bucket_decision_input_exists: `{summary.bucket_decision_input_exists}`",
        f"- bucket_decision_input_row_count: `{summary.bucket_decision_input_row_count}`",
        f"- bucket_decision_overlay_applied_count: `{summary.bucket_decision_overlay_applied_count}`",
        f"- bucket_decision_overlay_invalid_count: `{summary.bucket_decision_overlay_invalid_count}`",
        f"- ready_for_shadow_handoff: `{summary.ready_for_shadow_handoff}`",
        f"- next_action: {summary.next_action}",
        "",
        "## Safety",
        "",
        "- Live review.db is not updated.",
        "- Live handoff/latest_ready.json is not updated.",
        "- Rakuraku registration, final submit, PDF processed move, mail, RK10 ButtonRun, and production writes are not executed.",
        "",
        "## Business Review Aid",
        "",
        f"- review_aid_csv: `{review_aid_csv}`",
        f"- review_attention_count: `{review_attention_count}`",
        f"- decision_input_csv: `{summary.decision_input_csv}`",
        "- Fill `operator_entry_confirm_ok` with `OK` or `NG`, plus `reviewer` and `reviewed_at`; `NG` also requires `operator_entry_reject_reason`. Leave blank to keep the row on hold.",
        f"- bucket_decision_input_csv: `{bucket_decision_input_csv}`",
        f"- single_entry_input_csv: `{single_entry_input_csv}`",
        f"- single_entry_input_row_count: `{single_entry_input_row_count}`",
        "- The single-entry CSV is the preferred operator file; `BUCKET` and `ROW` entries are synced back into the split decision CSVs before analysis.",
        "- For `AMOUNT_MATCH_QUICK_REVIEW`, fill one bucket row with `OK` only when every eligible row in that bucket is business-approved.",
        "- Riskier buckets reject bucket-level `OK`; they can only be bulk-marked `NG` with reviewer, reviewed_at, and a shared reject reason.",
        "- This CSV is a draft aid only. It does not decide OK/NG and does not update the source spot-check CSV.",
        f"- priority_queue_csv: `{priority_csv}`",
        f"- next_steps_md: `{next_steps_md}`",
        "- Review buckets:",
        *[
            f"  - `{bucket}`: `{count}`"
            for bucket, count in sorted(review_bucket_counts.items())
        ],
        "- Bucket CSVs:",
        *[
            f"  - `{bucket}`: `{path}`"
            for bucket, path in sorted(bucket_csvs.items())
        ],
        "",
        "## Minimum Input Plan",
        "",
        *[
            (
                f"- P{row['priority']} `{row['target']}`: {row['allowed_input']}; "
                f"{row['ok_effect']} Safety: {row['safety_condition']}"
            )
            for row in minimum_input_plan
        ],
        "",
        "## Shadow Handoff",
        "",
    ]
    if shadow_result is None:
        lines.append("- generated: `False`")
    else:
        lines.extend(
            [
                "- generated: `True`",
                f"- verified: `{shadow_result.get('verified')}`",
                f"- verify_message: `{shadow_result.get('verify_message')}`",
                f"- data_file: `{shadow_result.get('data_file')}`",
                f"- latest_ready_file: `{shadow_result.get('latest_ready_file')}`",
                f"- item_count: `{shadow_result.get('item_count')}`",
                f"- checksum: `{shadow_result.get('checksum')}`",
            ]
        )
    return "\n".join(lines) + "\n"


def write_reports(
    summary: SpotCheckSummary,
    out_dir: Path,
    single_entry_input_csv: Path | None = None,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ok_csv = out_dir / "s44_spot_check_ok_candidates.csv"
    pending_csv = out_dir / "s44_spot_check_pending_or_ng.csv"
    review_aid_csv = out_dir / "s44_business_review_aid.csv"
    write_csv(ok_csv, summary.ok_rows)
    write_csv(pending_csv, summary.pending_rows)
    review_aid_rows = build_review_aid_rows(summary.ok_rows + summary.pending_rows)
    write_csv(review_aid_csv, review_aid_rows)
    bucket_decision_input_csv = (
        Path(summary.bucket_decision_input_csv)
        if summary.bucket_decision_input_csv
        else out_dir / "s44_business_review_bucket_decision_input.csv"
    )
    existing_bucket_rows = (
        read_csv_rows(bucket_decision_input_csv)
        if bucket_decision_input_csv.exists()
        else []
    )
    bucket_decision_rows = build_bucket_decision_input_rows(
        review_aid_rows,
        existing_bucket_rows,
    )
    try:
        write_csv(
            bucket_decision_input_csv,
            bucket_decision_rows,
            fieldnames=BUCKET_DECISION_INPUT_FIELDS,
        )
    except PermissionError:
        bucket_decision_rows = existing_bucket_rows
    single_entry_path = single_entry_input_csv or (
        out_dir / "s44_business_review_single_entry_input.csv"
    )
    priority_csv, bucket_csvs = write_review_priority_files(out_dir, review_aid_rows)
    review_bucket_counts = dict(
        sorted(Counter(row.get("review_bucket", "") for row in review_aid_rows).items())
    )
    existing_single_rows = (
        read_csv_rows(single_entry_path) if single_entry_path.exists() else []
    )
    single_entry_rows = build_single_entry_input_rows(
        review_aid_rows,
        bucket_decision_rows,
        existing_single_rows,
    )
    try:
        write_csv(
            single_entry_path,
            single_entry_rows,
            fieldnames=SINGLE_ENTRY_INPUT_FIELDS,
        )
    except PermissionError:
        single_entry_rows = existing_single_rows
    next_steps_md = write_operator_next_steps_file(
        out_dir,
        summary,
        bucket_decision_input_csv,
        priority_csv,
        bucket_csvs,
        review_bucket_counts,
        single_entry_path,
    )

    shadow_result = generate_shadow_handoff(summary, out_dir)
    payload = {
        **asdict(summary),
        "ok_candidates_csv": str(ok_csv),
        "pending_or_ng_csv": str(pending_csv),
        "business_review_aid_csv": str(review_aid_csv),
        "business_review_bucket_decision_input_csv": str(bucket_decision_input_csv),
        "business_review_bucket_decision_input_row_count": len(bucket_decision_rows),
        "business_review_single_entry_input_csv": str(single_entry_path),
        "business_review_single_entry_input_row_count": len(single_entry_rows),
        "business_review_priority_csv": str(priority_csv),
        "business_review_next_steps_md": str(next_steps_md),
        "business_review_bucket_csvs": bucket_csvs,
        "business_review_aid_row_count": len(review_aid_rows),
        "business_review_attention_count": sum(
            1
            for row in review_aid_rows
            if row.get("attention_reasons") != "NEEDS_BUSINESS_CONFIRM_OK_OR_NG"
        ),
        "business_review_bucket_counts": review_bucket_counts,
        "business_review_minimum_input_plan": build_minimum_input_plan(
            summary,
            review_bucket_counts,
        ),
        "shadow_handoff": shadow_result or {"generated": False},
    }
    json_path = out_dir / "s44_spot_check_handoff_candidates.json"
    md_path = out_dir / "s44_spot_check_handoff_candidates.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        build_markdown(
            summary,
            shadow_result,
            review_aid_csv,
            bucket_decision_input_csv,
            payload["business_review_attention_count"],
            review_bucket_counts,
            priority_csv,
            bucket_csvs,
            next_steps_md,
            single_entry_path,
            len(single_entry_rows),
        ),
        encoding="utf-8",
    )
    write_numbered_copy(md_path)
    write_numbered_copy(json_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Scenario 44 spot-check handoff candidates.")
    parser.add_argument("--spot-check-csv", type=Path, default=SPOT_CHECK_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--decision-input-csv",
        type=Path,
        default=None,
        help="Repo-local business decision input CSV. Defaults under --out-dir.",
    )
    parser.add_argument(
        "--bucket-decision-input-csv",
        type=Path,
        default=None,
        help="Repo-local bucket decision input CSV. Defaults under --out-dir.",
    )
    parser.add_argument(
        "--single-entry-input-csv",
        type=Path,
        default=None,
        help="Preferred repo-local single-entry business review CSV. Defaults under --out-dir.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    decision_input_csv = args.decision_input_csv or (
        args.out_dir / "s44_business_review_decision_input.csv"
    )
    bucket_decision_input_csv = args.bucket_decision_input_csv or (
        args.out_dir / "s44_business_review_bucket_decision_input.csv"
    )
    single_entry_input_csv = args.single_entry_input_csv or (
        args.out_dir / "s44_business_review_single_entry_input.csv"
    )
    ensure_decision_input_template(args.spot_check_csv, decision_input_csv)
    ensure_bucket_decision_input_template(
        args.spot_check_csv,
        decision_input_csv,
        bucket_decision_input_csv,
    )
    ensure_single_entry_input_template(
        args.spot_check_csv,
        decision_input_csv,
        bucket_decision_input_csv,
        single_entry_input_csv,
    )
    sync_single_entry_input_to_decision_inputs(
        single_entry_input_csv,
        decision_input_csv,
        bucket_decision_input_csv,
    )
    summary = analyze_spot_check(
        args.spot_check_csv,
        decision_input_csv,
        bucket_decision_input_csv,
    )
    write_reports(summary, args.out_dir, single_entry_input_csv)
    allowed_hold_statuses = {"HOLD_NO_OK_ROWS", "READY_FOR_SHADOW_HANDOFF"}
    return 0 if summary.status in allowed_hold_statuses else 1


if __name__ == "__main__":
    raise SystemExit(main())
