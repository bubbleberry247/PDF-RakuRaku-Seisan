"""Read-only RK10 HOLD release gate checker.

This tool does not run Outlook, RK10, Rakuraku, Azure, printing, mail, or
payment actions. It only reads gate CSV/report artifacts and produces a
machine-readable summary plus a small Markdown report.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "outlook_bundle_evidence_collect_20260620"
    / "outlook_bundle_evidence_collect.json"
)

S44_SPOT_CHECK = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\s44_business_spot_check_sheet_20260619_1240\s44_business_spot_check_26.csv"
)
S70_CHECKLIST = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\s70_payment_confirmation_gate_pack_20260619_1218"
    r"\s70_payment_confirmation_gate_checklist.csv"
)
S71_CHECKLIST = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\s71_azure_ocr_gate_pack_20260619_1220"
    r"\s71_azure_ocr_paid_test_gate_checklist.csv"
)


@dataclass(frozen=True)
class GateResult:
    scenario: str
    status: str
    ready: bool
    reason: str
    next_action: str
    source: str


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def outlook_safe_dryrun_evidence_ready(path: Path | None = None) -> bool:
    payload = load_json(path or OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON)
    log_status = payload.get("log_status", {})
    if not isinstance(log_status, dict):
        return False
    return (
        payload.get("status") == "READY_FOR_FINAL_EVIDENCE_INTAKE"
        and payload.get("ready_for_intake") is True
        and str(log_status.get("check_exit")) == "0"
        and str(log_status.get("scan_exit")) == "0"
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "cp932", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        except UnicodeDecodeError:
            continue
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def normalize(value: str | None) -> str:
    return (value or "").strip()


def is_todo(value: str | None) -> bool:
    text = normalize(value).lower()
    return not text or text.startswith("todo") or text in {"false", "no", "missing"}


def check_s44(path: Path) -> GateResult:
    if not path.exists():
        return GateResult(
            "44",
            "HOLD_MISSING_SPOT_CHECK",
            False,
            "spot check CSV is missing",
            "Create or restore the 26-row spot check CSV before live handoff.",
            str(path),
        )
    rows = read_csv_rows(path)
    ok_rows = [row for row in rows if normalize(row.get("confirm_ok")).upper() == "OK"]
    pending_rows = [row for row in rows if normalize(row.get("confirm_ok")).upper() != "OK"]
    if not ok_rows:
        return GateResult(
            "44",
            "HOLD_NO_CONFIRMED_ROWS",
            False,
            f"0 OK rows / {len(pending_rows)} not confirmed rows",
            "Business owner must write OK/NG; only OK rows may advance.",
            str(path),
        )
    return GateResult(
        "44",
        "READY_FOR_LIVE_HANDOFF_CANDIDATE_FILTER",
        True,
        f"{len(ok_rows)} OK rows / {len(pending_rows)} not confirmed rows",
        "Generate live handoff only for OK rows; do not move PDFs or submit.",
        str(path),
    )


def check_s70(path: Path) -> GateResult:
    if not path.exists():
        return GateResult(
            "70",
            "HOLD_MISSING_CHECKLIST",
            False,
            "payment confirmation checklist is missing",
            "Restore the checklist before confirm-preview or execute.",
            str(path),
        )
    rows = read_csv_rows(path)
    row = rows[0] if rows else {}
    required_fields = [
        "required_expected_count",
        "required_expected_total_amount_yen",
        "required_bank_transfer_confirmed",
        "required_approver",
    ]
    missing = [field for field in required_fields if is_todo(row.get(field))]
    execute_allowed = normalize(row.get("execute_allowed_now")).upper() == "YES"
    if missing or not execute_allowed:
        return GateResult(
            "70",
            "HOLD_PAYMENT_EXECUTE_NOT_ALLOWED",
            False,
            f"missing={','.join(missing) or 'none'}; execute_allowed_now={row.get('execute_allowed_now', '')}",
            "Fill expected count, amount, bank evidence, approver; run confirm-preview only before execute.",
            str(path),
        )
    return GateResult(
        "70",
        "READY_FOR_CONFIRM_PREVIEW_ONLY",
        True,
        "required fields are present and execute_allowed_now=YES",
        "Run confirm-preview; execute still needs separate explicit approval.",
        str(path),
    )


def check_s71(path: Path) -> GateResult:
    if not path.exists():
        return GateResult(
            "71",
            "HOLD_MISSING_CHECKLIST",
            False,
            "Azure OCR gate checklist is missing",
            "Restore the checklist before paid OCR smoke test.",
            str(path),
        )
    rows = read_csv_rows(path)
    missing = [
        row.get("required_var", "")
        for row in rows
        if normalize(row.get("status")).upper() != "READY"
    ]
    if missing:
        return GateResult(
            "71",
            "HOLD_AZURE_OCR_GATE_MISSING",
            False,
            f"missing={','.join(missing)}",
            "Set endpoint/key in environment and record budget approval plus exactly one sample PDF.",
            str(path),
        )
    return GateResult(
        "71",
        "READY_FOR_ONE_FILE_PAID_OCR_SMOKE",
        True,
        "all paid OCR gate rows are READY",
        "Run one approved PDF only; do not write original workbook.",
        str(path),
    )


def check_s12_13(exit_code: int | None) -> GateResult:
    if outlook_safe_dryrun_evidence_ready():
        observed = "unknown" if exit_code is None else str(exit_code)
        return GateResult(
            "12/13",
            "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
            True,
            "collected Outlook COM check + scan-only dry-run/no-print/no-mail evidence is ready; "
            f"s12_exit_code_input={observed}",
            "Fill operator_result/reviewer/reviewed_at in OUTLOOK_COM_BUNDLE final intake; real print/send remains a separate gate.",
            str(OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON),
        )
    if exit_code != 0:
        observed = "unknown" if exit_code is None else str(exit_code)
        return GateResult(
            "12/13",
            "HOLD_OUTLOOK_COM_NOT_READY",
            False,
            f"latest --check-outlook-com exit_code={observed}",
            "Recover Classic Outlook COM, then re-run --check-outlook-com before dry-run/no-print/no-mail.",
            r"C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py",
        )
    return GateResult(
        "12/13",
        "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
        True,
        "latest --check-outlook-com exit_code=0",
        "Run dry-run/no-print/no-mail; real print/send remains a separate gate.",
        r"C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools\outlook_save_pdf_and_batch_print.py",
    )


def build_markdown(results: Iterable[GateResult], generated_at: str) -> str:
    rows = list(results)
    lines = [
        "# HOLD解除ゲート 自動判定",
        "",
        f"- generated_at: `{generated_at}`",
        f"- overall_ready: `{all(row.ready for row in rows)}`",
        "- safety: read-only CSV/report check only",
        "",
        "| Scenario | Status | Ready | Reason | Next Action |",
        "|---|---|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.scenario,
                    row.status,
                    "YES" if row.ready else "NO",
                    row.reason.replace("|", "/"),
                    row.next_action.replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Sources",
            "",
            *[f"- {row.scenario}: `{row.source}`" for row in rows],
        ]
    )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    numbered_path = Path(str(path) + ".numbered")
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    numbered_path.write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check RK10 HOLD release gates.")
    parser.add_argument(
        "--s12-exit-code",
        type=int,
        default=None,
        help="Latest outlook COM check exit code. Use 0 only when just verified.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "plans" / "reports" / "hold_gate_checker_20260620",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now().isoformat(timespec="seconds")
    results = [
        check_s44(S44_SPOT_CHECK),
        check_s70(S70_CHECKLIST),
        check_s71(S71_CHECKLIST),
        check_s12_13(args.s12_exit_code),
    ]
    payload = {
        "generated_at": generated_at,
        "overall_ready": all(result.ready for result in results),
        "safety": "read-only CSV/report check only",
        "results": [asdict(result) for result in results],
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "hold_gate_summary.json"
    md_path = args.out_dir / "hold_gate_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(results, generated_at), encoding="utf-8")
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
