"""Collect Scenario 70 payment-approval evidence into the bundle intake.

This tool never executes payment confirmation. It only packages existing
confirm-preview/checklist evidence after the business payment approval fields
have already been filled by a human.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_GATE_CHECKLIST = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\s70_payment_confirmation_gate_pack_20260619_1218"
    r"\s70_payment_confirmation_gate_checklist.csv"
)
DEFAULT_SAMPLE_PREVIEW_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "s70_sample_confirm_preview_20260620"
    / "s70_sample_confirm_preview.json"
)
DEFAULT_INTAKE_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "payment_approval_bundle"
    / "final_evidence_intake.csv"
)
DEFAULT_FINAL_EVIDENCE_DIR = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "payment_approval_bundle"
    / "final_evidence"
    / "scenario_70"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "s70_payment_approval_evidence_collect_20260620"
SYNC_NOTE = "s70_payment_approval_evidence_auto_collected_20260620"
TODO_PREFIX = "TODO"
TRUE_VALUES = {"1", "true", "yes", "y", "ok", "confirmed", "済", "確認済", "承認済", "はい"}


@dataclass(frozen=True)
class CollectionResult:
    generated_at: str
    status: str
    ready_for_intake: bool
    updated_intake: bool
    gate_checklist: str
    gate_checklist_exists: bool
    gate_checklist_sha256: str
    gate_checklist_prefill_csv: str
    sample_preview_json: str
    sample_preview_exists: bool
    sample_preview_status: str
    payment_date: str
    gate_payment_date: str
    sample_payment_date: str
    payment_date_match: bool
    expected_count: int | None
    expected_total_amount_yen: int | None
    prefill_suggested_expected_count: int | None
    prefill_suggested_expected_total_amount_yen: int | None
    sample_selected_count: int | None
    sample_selected_total_amount_yen: int | None
    count_difference: int | None
    amount_difference_yen: int | None
    bank_transfer_confirmed: bool
    approver: str
    execute_allowed_now: str
    confirmation_ok_pressed: bool
    payment_execute_performed: bool
    mail_sent: bool
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


def todo_or_value(value: object, placeholder: str) -> str:
    text = normalize(value)
    return text if text and text != "None" else placeholder


def parse_int(value: object) -> int | None:
    text = str(value or "").replace(",", "").strip()
    if not text or text.upper().startswith(TODO_PREFIX):
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def normalize(value: object) -> str:
    return str(value or "").strip()


def normalized_lower(value: object) -> str:
    return normalize(value).lower()


def date_key(value: object) -> str:
    text = normalize(value)
    if not text:
        return ""
    for date_format in ("%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, date_format).strftime("%Y%m%d")
        except ValueError:
            continue
    return text.replace("-", "/").replace(".", "/")


def is_truthy(value: object) -> bool:
    return normalized_lower(value) in TRUE_VALUES


def is_filled_approval(value: object) -> bool:
    text = normalize(value)
    return bool(text) and not text.upper().startswith(TODO_PREFIX)


def load_gate_row(path: Path) -> dict[str, str]:
    _fieldnames, rows = read_csv_rows(path)
    if not rows:
        return {}
    return rows[0]


def calculate_differences(
    expected_count: int | None,
    expected_total: int | None,
    sample_count: int | None,
    sample_total: int | None,
) -> tuple[int | None, int | None]:
    count_difference = None
    amount_difference = None
    if expected_count is not None and sample_count is not None:
        count_difference = sample_count - expected_count
    if expected_total is not None and sample_total is not None:
        amount_difference = sample_total - expected_total
    return count_difference, amount_difference


def build_blockers(
    gate_row: dict[str, str],
    sample_preview: dict[str, Any],
    expected_count: int | None,
    expected_total: int | None,
    count_difference: int | None,
    amount_difference: int | None,
    gate_payment_date: str,
    sample_payment_date: str,
    payment_date_match: bool,
) -> list[str]:
    blockers: list[str] = []
    if not gate_row:
        blockers.append("PAYMENT_GATE_CHECKLIST_MISSING_OR_EMPTY")
    if not sample_preview:
        blockers.append("S70_SAMPLE_PREVIEW_MISSING_OR_EMPTY")
    elif sample_preview.get("status") != "CONFIRM_PREVIEW_SAMPLE_OK":
        blockers.append("S70_SAMPLE_PREVIEW_NOT_OK")
    if not gate_payment_date:
        blockers.append("PAYMENT_DATE_NOT_FILLED")
    elif sample_preview and sample_payment_date and not payment_date_match:
        blockers.append("PAYMENT_DATE_MISMATCH")
    if expected_count is None:
        blockers.append("EXPECTED_COUNT_NOT_FILLED")
    if expected_total is None:
        blockers.append("EXPECTED_TOTAL_AMOUNT_NOT_FILLED")
    if not is_truthy(gate_row.get("required_bank_transfer_confirmed", "")):
        blockers.append("BANK_TRANSFER_CONFIRMATION_NOT_FILLED")
    if not is_filled_approval(gate_row.get("required_approver", "")):
        blockers.append("APPROVER_NOT_FILLED")
    if sample_preview.get("confirmation_ok_pressed") is not False:
        blockers.append("CONFIRMATION_OK_WAS_PRESSED")
    if sample_preview.get("payment_execute_performed") is not False:
        blockers.append("PAYMENT_EXECUTE_WAS_PERFORMED")
    if sample_preview.get("mail_sent") is not False:
        blockers.append("MAIL_WAS_SENT")
    if sample_preview.get("rk10_button_run") is not False:
        blockers.append("RK10_BUTTON_RUN_WAS_USED")
    if count_difference not in (None, 0):
        blockers.append("COUNT_DIFFERENCE_NOT_ZERO")
    if amount_difference not in (None, 0):
        blockers.append("AMOUNT_DIFFERENCE_NOT_ZERO")
    return blockers


def evidence_token() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_final_evidence(
    result_base: dict[str, Any],
    final_evidence_dir: Path,
    token: str,
) -> list[Path]:
    final_evidence_dir.mkdir(parents=True, exist_ok=True)
    log_path = final_evidence_dir / f"scenario_70_safe_run_log_{token}.txt"
    summary_path = final_evidence_dir / f"scenario_70_count_amount_summary_{token}.csv"
    log_lines = [
        "Scenario 70 payment-approval evidence collection",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        "scope=read-only evidence packaging; no --execute, no payment confirmation OK, no bank upload",
        f"gate_checklist={result_base['gate_checklist']}",
        f"gate_checklist_sha256={result_base['gate_checklist_sha256']}",
        f"sample_preview_json={result_base['sample_preview_json']}",
        f"sample_preview_status={result_base['sample_preview_status']}",
        f"payment_date={result_base['payment_date']}",
        f"gate_payment_date={result_base['gate_payment_date']}",
        f"sample_payment_date={result_base['sample_payment_date']}",
        f"payment_date_match={result_base['payment_date_match']}",
        f"expected_count={result_base['expected_count']}",
        f"expected_total_amount_yen={result_base['expected_total_amount_yen']}",
        f"sample_selected_count={result_base['sample_selected_count']}",
        f"sample_selected_total_amount_yen={result_base['sample_selected_total_amount_yen']}",
        f"count_difference={result_base['count_difference']}",
        f"amount_difference_yen={result_base['amount_difference_yen']}",
        f"bank_transfer_confirmed={result_base['bank_transfer_confirmed']}",
        f"approver={result_base['approver']}",
        f"execute_allowed_now={result_base['execute_allowed_now']}",
        f"confirmation_ok_pressed={result_base['confirmation_ok_pressed']}",
        f"payment_execute_performed={result_base['payment_execute_performed']}",
        f"mail_sent={result_base['mail_sent']}",
        f"rk10_button_run={result_base['rk10_button_run']}",
    ]
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    rows = [
        {"metric": key, "value": str(value)}
        for key, value in result_base.items()
        if key
        in {
            "payment_date",
            "gate_payment_date",
            "sample_payment_date",
            "payment_date_match",
            "expected_count",
            "expected_total_amount_yen",
            "sample_selected_count",
            "sample_selected_total_amount_yen",
            "count_difference",
            "amount_difference_yen",
            "bank_transfer_confirmed",
            "execute_allowed_now",
            "confirmation_ok_pressed",
            "payment_execute_performed",
        }
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
        if row.get("bundle") == "PAYMENT_APPROVAL_BUNDLE" and row.get("scenario") == "70":
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
    sample_preview_json: Path,
    intake_csv: Path,
    final_evidence_dir: Path,
    gate_checklist_prefill_csv: str = "",
) -> CollectionResult:
    gate_row = load_gate_row(gate_checklist)
    sample_preview = read_json(sample_preview_json)
    expected_count = parse_int(gate_row.get("required_expected_count"))
    expected_total = parse_int(gate_row.get("required_expected_total_amount_yen"))
    sample_count = parse_int(sample_preview.get("selected_records"))
    sample_total = parse_int(sample_preview.get("selected_total_amount_yen"))
    gate_payment_date = normalize(gate_row.get("payment_date"))
    sample_payment_date = normalize(sample_preview.get("payment_date"))
    payment_date_match = bool(
        gate_payment_date
        and sample_payment_date
        and date_key(gate_payment_date) == date_key(sample_payment_date)
    )
    prefill_count = sample_count if payment_date_match else None
    prefill_total = sample_total if payment_date_match else None
    if payment_date_match:
        count_difference, amount_difference = calculate_differences(
            expected_count,
            expected_total,
            sample_count,
            sample_total,
        )
    else:
        count_difference, amount_difference = None, None
    result_base = {
        "gate_checklist": str(gate_checklist),
        "gate_checklist_sha256": file_sha256(gate_checklist),
        "sample_preview_json": str(sample_preview_json),
        "sample_preview_status": normalize(sample_preview.get("status")),
        "payment_date": normalize(gate_row.get("payment_date") or sample_preview.get("payment_date")),
        "gate_payment_date": gate_payment_date,
        "sample_payment_date": sample_payment_date,
        "payment_date_match": payment_date_match,
        "expected_count": expected_count,
        "expected_total_amount_yen": expected_total,
        "sample_selected_count": sample_count,
        "sample_selected_total_amount_yen": sample_total,
        "count_difference": count_difference,
        "amount_difference_yen": amount_difference,
        "bank_transfer_confirmed": is_truthy(gate_row.get("required_bank_transfer_confirmed", "")),
        "approver": normalize(gate_row.get("required_approver")),
        "execute_allowed_now": normalize(gate_row.get("execute_allowed_now")),
        "confirmation_ok_pressed": sample_preview.get("confirmation_ok_pressed") is True,
        "payment_execute_performed": sample_preview.get("payment_execute_performed") is True,
        "mail_sent": sample_preview.get("mail_sent") is True,
        "rk10_button_run": sample_preview.get("rk10_button_run") is True,
    }
    blockers = build_blockers(
        gate_row,
        sample_preview,
        expected_count,
        expected_total,
        count_difference,
        amount_difference,
        gate_payment_date,
        sample_payment_date,
        payment_date_match,
    )
    evidence_files: list[Path] = []
    updated_intake = False
    if not blockers:
        evidence_files = write_final_evidence(result_base, final_evidence_dir, evidence_token())
        updated_intake = update_intake_csv(intake_csv, final_evidence_dir)
    if blockers:
        status = "WAITING_FOR_PAYMENT_APPROVAL"
    elif updated_intake:
        status = "READY_FOR_OPERATOR_FINAL_FIELDS"
    else:
        status = "BLOCKED_INTAKE_ROW_NOT_FOUND"
        blockers = ["PAYMENT_APPROVAL_INTAKE_ROW_NOT_FOUND"]
    return CollectionResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status=status,
        ready_for_intake=not blockers,
        updated_intake=updated_intake,
        gate_checklist=str(gate_checklist),
        gate_checklist_exists=gate_checklist.exists(),
        gate_checklist_sha256=file_sha256(gate_checklist),
        gate_checklist_prefill_csv=gate_checklist_prefill_csv,
        sample_preview_json=str(sample_preview_json),
        sample_preview_exists=sample_preview_json.exists(),
        sample_preview_status=result_base["sample_preview_status"],
        payment_date=result_base["payment_date"],
        gate_payment_date=gate_payment_date,
        sample_payment_date=sample_payment_date,
        payment_date_match=payment_date_match,
        expected_count=expected_count,
        expected_total_amount_yen=expected_total,
        prefill_suggested_expected_count=prefill_count,
        prefill_suggested_expected_total_amount_yen=prefill_total,
        sample_selected_count=sample_count,
        sample_selected_total_amount_yen=sample_total,
        count_difference=count_difference,
        amount_difference_yen=amount_difference,
        bank_transfer_confirmed=result_base["bank_transfer_confirmed"],
        approver=result_base["approver"],
        execute_allowed_now=result_base["execute_allowed_now"],
        confirmation_ok_pressed=result_base["confirmation_ok_pressed"],
        payment_execute_performed=result_base["payment_execute_performed"],
        mail_sent=result_base["mail_sent"],
        rk10_button_run=result_base["rk10_button_run"],
        final_evidence_dir=str(final_evidence_dir),
        final_evidence_files=[str(path) for path in evidence_files],
        intake_csv=str(intake_csv),
        blockers=", ".join(blockers),
    )


def build_markdown(result: CollectionResult) -> str:
    lines = [
        "# Scenario 70 payment-approval evidence collection 2026-06-20",
        "",
        f"- generated_at: `{result.generated_at}`",
        f"- status: `{result.status}`",
        f"- ready_for_intake: `{result.ready_for_intake}`",
        f"- updated_intake: `{result.updated_intake}`",
        f"- payment_date: `{result.payment_date}`",
        f"- gate_payment_date: `{result.gate_payment_date}`",
        f"- sample_payment_date: `{result.sample_payment_date}`",
        f"- payment_date_match: `{result.payment_date_match}`",
        f"- expected_count: `{result.expected_count}`",
        f"- expected_total_amount_yen: `{result.expected_total_amount_yen}`",
        f"- prefill_suggested_expected_count: `{result.prefill_suggested_expected_count}`",
        f"- prefill_suggested_expected_total_amount_yen: `{result.prefill_suggested_expected_total_amount_yen}`",
        f"- sample_selected_count: `{result.sample_selected_count}`",
        f"- sample_selected_total_amount_yen: `{result.sample_selected_total_amount_yen}`",
        f"- count_difference: `{result.count_difference}`",
        f"- amount_difference_yen: `{result.amount_difference_yen}`",
        f"- bank_transfer_confirmed: `{result.bank_transfer_confirmed}`",
        f"- approver: `{result.approver}`",
        f"- execute_allowed_now: `{result.execute_allowed_now}`",
        f"- confirmation_ok_pressed: `{result.confirmation_ok_pressed}`",
        f"- payment_execute_performed: `{result.payment_execute_performed}`",
        f"- mail_sent: `{result.mail_sent}`",
        f"- rk10_button_run: `{result.rk10_button_run}`",
        f"- blockers: `{result.blockers}`",
        f"- gate_checklist: `{result.gate_checklist}`",
        f"- gate_checklist_sha256: `{result.gate_checklist_sha256}`",
        f"- gate_checklist_prefill_csv: `{result.gate_checklist_prefill_csv}`",
        f"- sample_preview_json: `{result.sample_preview_json}`",
        f"- final_evidence_dir: `{result.final_evidence_dir}`",
        f"- intake_csv: `{result.intake_csv}`",
        "",
        "## Safety",
        "",
        "- This collector does not execute payment confirmation.",
        "- This collector does not press confirmation OK.",
        "- This collector does not open Rakuraku, upload to bank, send mail, run RK10, print, submit, or write production state.",
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


def build_gate_checklist_prefill_rows(result: CollectionResult) -> list[dict[str, str]]:
    return [
        {
            "scenario": "70",
            "gate": "payment_confirmation_execute_gate",
            "payment_date": result.payment_date,
            "current_safe_to_confirm_preview": "TODO_OPERATOR_VERIFY_PREVIEW_ONLY",
            "current_safe_to_execute_after_human_approval": "False",
            "last_known_run_status": result.sample_preview_status,
            "last_known_selected_records": todo_or_value(
                result.sample_selected_count,
                "TODO_EXPECTED_COUNT",
            ),
            "last_known_total_amount_yen": todo_or_value(
                result.sample_selected_total_amount_yen,
                "TODO_EXPECTED_TOTAL_AMOUNT_YEN",
            ),
            "required_expected_count": todo_or_value(
                result.prefill_suggested_expected_count,
                "TODO_BUSINESS_CONFIRM_COUNT",
            ),
            "required_expected_total_amount_yen": todo_or_value(
                result.prefill_suggested_expected_total_amount_yen,
                "TODO_BUSINESS_CONFIRM_AMOUNT",
            ),
            "required_bank_transfer_confirmed": "TODO_TRUE_AFTER_BANK_EVIDENCE",
            "required_approver": "TODO_NAME_OR_APPROVAL_RECORD",
            "execute_allowed_now": "NO",
            "reason": (
                "Draft prefill only. Business/payment approver must confirm count, amount, "
                "bank evidence, and approver before any irreversible operation."
            ),
            "primary_source": result.sample_preview_json,
        }
    ]


def write_gate_checklist_prefill(path: Path, result: CollectionResult) -> None:
    fieldnames = [
        "scenario",
        "gate",
        "payment_date",
        "current_safe_to_confirm_preview",
        "current_safe_to_execute_after_human_approval",
        "last_known_run_status",
        "last_known_selected_records",
        "last_known_total_amount_yen",
        "required_expected_count",
        "required_expected_total_amount_yen",
        "required_bank_transfer_confirmed",
        "required_approver",
        "execute_allowed_now",
        "reason",
        "primary_source",
    ]
    write_csv_rows(path, fieldnames, build_gate_checklist_prefill_rows(result))


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Scenario 70 payment-approval evidence.")
    parser.add_argument("--gate-checklist", type=Path, default=DEFAULT_GATE_CHECKLIST)
    parser.add_argument("--sample-preview-json", type=Path, default=DEFAULT_SAMPLE_PREVIEW_JSON)
    parser.add_argument("--intake-csv", type=Path, default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--final-evidence-dir", type=Path, default=DEFAULT_FINAL_EVIDENCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    prefill_path = args.out_dir / "s70_payment_confirmation_gate_checklist_prefill.csv"
    result = build_result(
        args.gate_checklist,
        args.sample_preview_json,
        args.intake_csv,
        args.final_evidence_dir,
        str(prefill_path),
    )
    json_path = args.out_dir / "s70_payment_approval_evidence_collect.json"
    md_path = args.out_dir / "s70_payment_approval_evidence_collect.md"
    write_gate_checklist_prefill(prefill_path, result)
    json_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(result), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
