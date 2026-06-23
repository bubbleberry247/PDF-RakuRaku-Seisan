"""Collect successful OUTLOOK_COM_BUNDLE logs into the final evidence intake.

This tool never opens Outlook and never scans mail. It only reads logs produced
by the operator-run `outlook_com_bundle_dryrun.ps1`. If both the COM preflight
and scan-only dry-run exited 0, and the logs do not contain irreversible action
markers, it writes one repository-local evidence summary and updates the
OUTLOOK_COM_BUNDLE final evidence intake CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_LOG_DIR = (
    ROOT
    / "plans"
    / "reports"
    / "external_approval_runbook_20260620"
    / "outlook_com_bundle_logs"
)
DEFAULT_INTAKE = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "outlook_com_bundle"
    / "final_evidence_intake.csv"
)
DEFAULT_FINAL_EVIDENCE_DIR = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "outlook_com_bundle"
    / "final_evidence"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "outlook_bundle_evidence_collect_20260620"
SCENARIO_EVIDENCE_DIR_NAME = "scenario_12_13"
LEGACY_AUTO_REVIEWER = "OUTLOOK_COM_BUNDLE_AUTO_COLLECTOR"
SYNC_NOTE = "auto_collected_from_outlook_com_bundle_logs_20260620"
LEGACY_CLEAR_NOTE = "legacy_outlook_auto_approval_fields_cleared_20260622"
FORBIDDEN_KEYWORDS = (
    "--execute",
    "--print",
    "mail_sent=1",
    "printed=1",
    "state_changed=1",
    "mark_as_read",
    "既読",
    "印刷しました",
    "送信しました",
)
IGNORED_FORBIDDEN_LINE_PREFIXES = (
    "outlook_com_bundle safety:",
)


def configure_csv_field_size_limit() -> int:
    limit = sys.maxsize
    while limit > 0:
        try:
            csv.field_size_limit(limit)
            return limit
        except OverflowError:
            limit //= 10
    return csv.field_size_limit()


CSV_FIELD_SIZE_LIMIT = configure_csv_field_size_limit()


@dataclass(frozen=True)
class OutlookLogStatus:
    summary_path: str
    check_log_path: str
    scan_log_path: str
    check_exit: str
    scan_exit: str
    summary_exists: bool
    check_log_exists: bool
    scan_log_exists: bool
    forbidden_keywords: list[str]

    @property
    def successful(self) -> bool:
        return (
            self.check_exit == "0"
            and self.scan_exit == "0"
            and self.summary_exists
            and self.check_log_exists
            and self.scan_log_exists
            and not self.forbidden_keywords
        )


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    if raw.count(b"\x00") > max(0, len(raw) // 10):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")


def parse_summary_value(summary_text: str, key: str) -> str:
    for line in summary_text.splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def find_forbidden_keywords(*texts: str) -> list[str]:
    found = []
    for line in "\n".join(texts).splitlines():
        normalized_line = line.strip().lstrip("\ufeff").lower()
        if normalized_line.startswith(IGNORED_FORBIDDEN_LINE_PREFIXES):
            continue
        for keyword in FORBIDDEN_KEYWORDS:
            normalized_keyword = keyword.lower()
            if normalized_keyword in normalized_line and keyword not in found:
                found.append(keyword)
    return found


def inspect_logs(log_dir: Path) -> OutlookLogStatus:
    summary_path = log_dir / "summary.txt"
    check_log_path = log_dir / "01_check_outlook_com.log"
    scan_log_path = log_dir / "02_scan_only_dryrun.log"
    summary_text = read_text(summary_path)
    check_text = read_text(check_log_path)
    scan_text = read_text(scan_log_path)
    return OutlookLogStatus(
        summary_path=str(summary_path),
        check_log_path=str(check_log_path),
        scan_log_path=str(scan_log_path),
        check_exit=parse_summary_value(summary_text, "check_outlook_com_exit"),
        scan_exit=parse_summary_value(summary_text, "scan_only_dryrun_exit"),
        summary_exists=summary_path.exists(),
        check_log_exists=check_log_path.exists(),
        scan_log_exists=scan_log_path.exists(),
        forbidden_keywords=find_forbidden_keywords(summary_text, check_text, scan_text),
    )


def status_text(log_status: OutlookLogStatus) -> str:
    if log_status.successful:
        return "READY_FOR_FINAL_EVIDENCE_INTAKE"
    blockers = []
    if not log_status.summary_exists:
        blockers.append("SUMMARY_NOT_FOUND")
    if not log_status.check_log_exists:
        blockers.append("CHECK_LOG_NOT_FOUND")
    if not log_status.scan_log_exists:
        blockers.append("SCAN_LOG_NOT_FOUND")
    if log_status.check_exit != "0":
        blockers.append(f"CHECK_EXIT_{log_status.check_exit or 'BLANK'}")
    if log_status.scan_exit != "0":
        blockers.append(f"SCAN_EXIT_{log_status.scan_exit or 'BLANK'}")
    if log_status.forbidden_keywords:
        blockers.append("FORBIDDEN_KEYWORDS_FOUND")
    return "OUTLOOK_BUNDLE_NOT_SUCCESSFUL" if not blockers else ", ".join(blockers)


def build_evidence_text(log_status: OutlookLogStatus) -> str:
    return "\n".join(
        [
            "# OUTLOOK_COM_BUNDLE Final Evidence Summary",
            "",
            f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
            "- scope: `12/13 Outlook COM preflight and scan-only dry-run/no-mail/no-print`",
            f"- check_outlook_com_exit: `{log_status.check_exit}`",
            f"- scan_only_dryrun_exit: `{log_status.scan_exit}`",
            f"- summary_path: `{log_status.summary_path}`",
            f"- check_log_path: `{log_status.check_log_path}`",
            f"- scan_log_path: `{log_status.scan_log_path}`",
            "- forbidden_operations_checked: `--execute`, `--print`, mail send markers, print markers, state change markers",
            "- production_effect: `none asserted by this collector; it only imports successful dry-run logs`",
            "",
        ]
    )


def timestamp_token(generated_at: str) -> str:
    return generated_at.replace("-", "").replace(":", "").replace("T", "_")


def evidence_token(generated_at: str, scan_text: str) -> str:
    _, report = read_run_report(scan_text)
    run_id = str(report.get("run_id", ""))
    if re.fullmatch(r"\d{8}_\d{6}", run_id):
        return run_id
    run_dir = parse_run_dir(scan_text)
    if run_dir and re.fullmatch(r"\d{8}_\d{6}", run_dir.name):
        return run_dir.name
    return timestamp_token(generated_at)


def parse_run_dir(scan_text: str) -> Path | None:
    for line in scan_text.splitlines():
        match = re.search(r"run_dir=(.+)$", line.strip())
        if match:
            return Path(match.group(1).strip())
    return None


def read_run_report(scan_text: str) -> tuple[str, dict[str, Any]]:
    run_dir = parse_run_dir(scan_text)
    if run_dir is None:
        return "", {}
    report_path = run_dir / "report.json"
    if not report_path.exists():
        return str(report_path), {}
    try:
        return str(report_path), json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return str(report_path), {}


def count_list(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def build_count_summary_rows(
    generated_at: str,
    log_status: OutlookLogStatus,
    scan_text: str,
) -> list[dict[str, str]]:
    report_path, report = read_run_report(scan_text)
    return [
        {
            "generated_at": generated_at,
            "check_outlook_com_exit": log_status.check_exit,
            "scan_only_dryrun_exit": log_status.scan_exit,
            "dry_run": str(report.get("dry_run", "")),
            "scanned_messages": str(report.get("scanned_messages", "")),
            "saved_attachment_count": str(count_list(report.get("saved_attachments"))),
            "printed_path_count": str(count_list(report.get("printed_paths"))),
            "url_only_task_count": str(count_list(report.get("url_only_tasks"))),
            "unresolved_count": str(count_list(report.get("unresolved"))),
            "report_json_path": report_path,
        }
    ]


def write_count_summary_csv(
    path: Path,
    generated_at: str,
    log_status: OutlookLogStatus,
    scan_text: str,
) -> None:
    fieldnames = [
        "generated_at",
        "check_outlook_com_exit",
        "scan_only_dryrun_exit",
        "dry_run",
        "scanned_messages",
        "saved_attachment_count",
        "printed_path_count",
        "url_only_task_count",
        "unresolved_count",
        "report_json_path",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(build_count_summary_rows(generated_at, log_status, scan_text))


def write_evidence_files(final_evidence_dir: Path, log_status: OutlookLogStatus, generated_at: str) -> Path:
    scenario_dir = final_evidence_dir / SCENARIO_EVIDENCE_DIR_NAME
    scenario_dir.mkdir(parents=True, exist_ok=True)
    check_text = read_text(Path(log_status.check_log_path))
    scan_text = read_text(Path(log_status.scan_log_path))
    token = evidence_token(generated_at, scan_text)
    preflight_path = scenario_dir / f"scenario_12_13_outlook_com_preflight_exit0_{token}.txt"
    dryrun_path = scenario_dir / f"scenario_12_13_dryrun_no_print_no_mail_{token}.log"
    count_path = scenario_dir / f"scenario_12_13_saved_pdf_count_summary_{token}.csv"
    preflight_path.write_text(
        "\n".join(
            [
                "OUTLOOK_COM_BUNDLE preflight evidence",
                f"generated_at={generated_at}",
                f"check_outlook_com_exit={log_status.check_exit}",
                f"source_log={log_status.check_log_path}",
                "",
                check_text,
            ]
        ),
        encoding="utf-8",
    )
    dryrun_path.write_text(
        "\n".join(
            [
                "OUTLOOK_COM_BUNDLE scan-only dry-run evidence",
                f"generated_at={generated_at}",
                f"scan_only_dryrun_exit={log_status.scan_exit}",
                f"source_log={log_status.scan_log_path}",
                "forbidden_operations=not_executed_by_bundle_script",
                "",
                scan_text,
            ]
        ),
        encoding="utf-8",
    )
    write_count_summary_csv(count_path, generated_at, log_status, scan_text)
    return scenario_dir


def read_intake(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [
            {str(key): str(value).strip() for key, value in row.items() if key is not None}
            for row in reader
        ]


def write_intake(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    parts = [part.strip() for part in existing.split(" / ") if part.strip()]
    if note in parts:
        return existing
    return " / ".join([*parts, note])


def is_legacy_auto_approval(row: dict[str, str]) -> bool:
    return (
        row.get("operator_result", "").strip().upper() == "OK"
        and row.get("reviewer", "").strip() == LEGACY_AUTO_REVIEWER
        and SYNC_NOTE in row.get("notes", "")
    )


def update_intake(intake_path: Path, evidence_path: Path) -> bool:
    fieldnames, rows = read_intake(intake_path)
    if not rows:
        return False
    updated = False
    updated_rows = []
    for row in rows:
        if row.get("bundle") == "OUTLOOK_COM_BUNDLE" and row.get("scenario") == "12/13":
            notes = append_note(row.get("notes", ""), SYNC_NOTE)
            row = {
                **row,
                "final_evidence_path": str(evidence_path),
                "rakuraku_customer_login_used": "NO",
                "temporary_save_created": "NO",
                "created_data_cleanup_status": "",
                "created_data_cleanup_evidence_path": "",
                "cleanup_reviewer": "",
                "cleanup_reviewed_at": "",
                "notes": notes,
            }
            if is_legacy_auto_approval(row):
                row = {
                    **row,
                    "operator_result": "",
                    "reviewer": "",
                    "reviewed_at": "",
                    "notes": append_note(row.get("notes", ""), LEGACY_CLEAR_NOTE),
                }
            updated = True
        updated_rows.append(row)
    if updated:
        write_intake(intake_path, fieldnames, updated_rows)
    return updated


def build_payload(
    log_dir: Path,
    intake_path: Path,
    final_evidence_dir: Path,
    apply_updates: bool,
) -> dict[str, Any]:
    log_status = inspect_logs(log_dir)
    status = status_text(log_status)
    final_evidence_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().isoformat(timespec="seconds")
    evidence_path = final_evidence_dir / SCENARIO_EVIDENCE_DIR_NAME
    updated_intake = False
    if log_status.successful and apply_updates:
        evidence_path = write_evidence_files(final_evidence_dir, log_status, generated_at)
        updated_intake = update_intake(intake_path, evidence_path)
    return {
        "generated_at": generated_at,
        "overall_goal_complete": False,
        "safety": "read existing Outlook dry-run logs only; no Outlook launch, mail send, print, state change, or production write",
        "status": status,
        "ready_for_intake": log_status.successful,
        "updated_intake": updated_intake,
        "apply_updates": apply_updates,
        "log_dir": str(log_dir),
        "intake_path": str(intake_path),
        "final_evidence_dir": str(final_evidence_dir),
        "evidence_path": str(evidence_path),
        "evidence_file": str(evidence_path),
        "log_status": {
            "summary_path": log_status.summary_path,
            "check_log_path": log_status.check_log_path,
            "scan_log_path": log_status.scan_log_path,
            "check_exit": log_status.check_exit,
            "scan_exit": log_status.scan_exit,
            "summary_exists": log_status.summary_exists,
            "check_log_exists": log_status.check_log_exists,
            "scan_log_exists": log_status.scan_log_exists,
            "forbidden_keywords": log_status.forbidden_keywords,
        },
    }


def build_markdown(payload: dict[str, Any]) -> str:
    log_status = payload["log_status"]
    assert isinstance(log_status, dict)
    return "\n".join(
        [
            "# OUTLOOK_COM_BUNDLE 証跡取込 2026-06-20",
            "",
            f"- generated_at: `{payload['generated_at']}`",
            f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
            f"- safety: `{payload['safety']}`",
            f"- status: `{payload['status']}`",
            f"- ready_for_intake: `{payload['ready_for_intake']}`",
            f"- updated_intake: `{payload['updated_intake']}`",
            f"- apply_updates: `{payload['apply_updates']}`",
            f"- check_exit: `{log_status['check_exit']}`",
            f"- scan_exit: `{log_status['scan_exit']}`",
            f"- forbidden_keywords: `{', '.join(log_status['forbidden_keywords'])}`",
            f"- evidence_file: `{payload['evidence_file']}`",
            f"- intake_path: `{payload['intake_path']}`",
            "",
            "## Boundary",
            "",
            "- This collector only reads already-produced OUTLOOK_COM_BUNDLE logs.",
            "- It does not open Outlook, scan mail, save attachments, print, send mail, or change mail state.",
            "- Intake is updated only when COM check and scan-only dry-run both exited 0 and no forbidden markers are present.",
            "- Operator result, reviewer identity, and reviewed_at still must be supplied before the bundle can sync as final evidence.",
            "",
        ]
    )


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "outlook_bundle_evidence_collect.json"
    md_path = out_dir / "outlook_bundle_evidence_collect.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect successful Outlook bundle dry-run logs into final evidence intake.")
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--intake-path", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--final-evidence-dir", type=Path, default=DEFAULT_FINAL_EVIDENCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--no-apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        args.log_dir,
        args.intake_path,
        args.final_evidence_dir,
        apply_updates=not args.no_apply,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
