"""Collect Scenario 44 business-review evidence into the bundle intake.

This tool does not decide OK/NG and does not touch live RK10/Rakuraku state.
It only packages existing Scenario 44 spot-check/shadow-handoff evidence after
the business spot-check CSV already contains approved OK rows.
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
DEFAULT_S44_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_spot_check_handoff_candidates.json"
)
DEFAULT_INTAKE_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "business_review_bundle"
    / "final_evidence_intake.csv"
)
DEFAULT_FINAL_EVIDENCE_DIR = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "business_review_bundle"
    / "final_evidence"
    / "scenario_44"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "s44_business_review_evidence_collect_20260620"
SYNC_NOTE = "s44_business_review_evidence_auto_collected_20260620"


@dataclass(frozen=True)
class CollectionResult:
    generated_at: str
    status: str
    ready_for_intake: bool
    updated_intake: bool
    source_json: str
    source_csv: str
    source_csv_exists: bool
    source_csv_sha256: str
    row_count: int
    ok_count: int
    ng_count: int
    blank_count: int
    invalid_ok_count: int
    missing_pdf_count: int
    shadow_handoff_generated: bool
    shadow_handoff_verified: bool
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
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {str(key): str(value).strip() for key, value in row.items() if key is not None}
            for row in reader
        ]
    return fieldnames, rows


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_amount(value: object) -> int:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def build_blockers(payload: dict[str, Any], source_csv: Path) -> list[str]:
    blockers: list[str] = []
    if not payload:
        blockers.append("S44_HANDOFF_CANDIDATES_JSON_MISSING_OR_EMPTY")
        return blockers
    if not source_csv.exists():
        blockers.append("S44_SOURCE_CSV_NOT_FOUND")
    if payload.get("ready_for_shadow_handoff") is not True:
        blockers.append(str(payload.get("status") or "S44_NOT_READY_FOR_SHADOW_HANDOFF"))
    shadow_handoff = payload.get("shadow_handoff", {})
    if not isinstance(shadow_handoff, dict) or shadow_handoff.get("generated") is not True:
        blockers.append("SHADOW_HANDOFF_NOT_GENERATED")
    elif shadow_handoff.get("verified") is not True:
        blockers.append("SHADOW_HANDOFF_NOT_VERIFIED")
    return blockers


def evidence_token(payload: dict[str, Any]) -> str:
    generated_at = str(payload.get("generated_at", "")).replace("-", "").replace(":", "")
    token = generated_at.replace("T", "_")[:15]
    if len(token) == 15 and token[8] == "_":
        return token
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_final_evidence(
    payload: dict[str, Any],
    final_evidence_dir: Path,
    token: str,
) -> list[Path]:
    final_evidence_dir.mkdir(parents=True, exist_ok=True)
    source_csv = Path(str(payload.get("source_csv", "")))
    decision_input_text = str(payload.get("decision_input_csv", ""))
    decision_input_csv = Path(decision_input_text) if decision_input_text else Path()
    decision_input_exists = bool(decision_input_text) and decision_input_csv.exists()
    decision_input_sha256 = str(payload.get("decision_input_sha256", "")) or (
        file_sha256(decision_input_csv) if decision_input_exists else ""
    )
    ok_rows = [row for row in payload.get("ok_rows", []) if isinstance(row, dict)]
    total_ok_amount = sum(parse_amount(row.get("amount_estimate")) for row in ok_rows)
    shadow_handoff = payload.get("shadow_handoff", {})
    if not isinstance(shadow_handoff, dict):
        shadow_handoff = {}

    log_path = final_evidence_dir / f"scenario_44_safe_run_log_{token}.txt"
    summary_path = final_evidence_dir / f"scenario_44_count_amount_summary_{token}.csv"

    log_lines = [
        "Scenario 44 business-review evidence collection",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        "scope=read-only evidence packaging; no live handoff, no Rakuraku, no PDF move, no mail",
        f"source_csv={source_csv}",
        f"source_csv_exists={source_csv.exists()}",
        f"source_csv_sha256={file_sha256(source_csv)}",
        f"decision_input_csv={decision_input_text}",
        f"decision_input_exists={decision_input_exists}",
        f"decision_input_sha256={decision_input_sha256}",
        f"decision_overlay_applied_count={payload.get('decision_overlay_applied_count', 0)}",
        f"decision_overlay_invalid_count={payload.get('decision_overlay_invalid_count', 0)}",
        f"row_count={payload.get('row_count', 0)}",
        f"ok_count={payload.get('ok_count', 0)}",
        f"ng_count={payload.get('ng_count', 0)}",
        f"blank_count={payload.get('blank_count', 0)}",
        f"invalid_ok_count={payload.get('invalid_ok_count', 0)}",
        f"missing_pdf_count={payload.get('missing_pdf_count', 0)}",
        f"shadow_handoff_generated={shadow_handoff.get('generated') is True}",
        f"shadow_handoff_verified={shadow_handoff.get('verified') is True}",
        f"shadow_handoff_data_file={shadow_handoff.get('data_file', '')}",
        f"shadow_handoff_latest_ready_file={shadow_handoff.get('latest_ready_file', '')}",
        f"shadow_handoff_checksum={shadow_handoff.get('checksum', '')}",
    ]
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    summary_rows = [
        {"metric": "row_count", "value": str(payload.get("row_count", 0))},
        {"metric": "ok_count", "value": str(payload.get("ok_count", 0))},
        {"metric": "ng_count", "value": str(payload.get("ng_count", 0))},
        {"metric": "blank_count", "value": str(payload.get("blank_count", 0))},
        {"metric": "invalid_ok_count", "value": str(payload.get("invalid_ok_count", 0))},
        {"metric": "missing_pdf_count", "value": str(payload.get("missing_pdf_count", 0))},
        {"metric": "total_ok_amount_estimate", "value": str(total_ok_amount)},
        {"metric": "source_csv_sha256", "value": file_sha256(source_csv)},
        {"metric": "decision_input_sha256", "value": decision_input_sha256},
        {
            "metric": "decision_overlay_applied_count",
            "value": str(payload.get("decision_overlay_applied_count", 0)),
        },
        {
            "metric": "decision_overlay_invalid_count",
            "value": str(payload.get("decision_overlay_invalid_count", 0)),
        },
        {"metric": "shadow_handoff_verified", "value": str(shadow_handoff.get("verified") is True)},
    ]
    write_csv_rows(summary_path, ["metric", "value"], summary_rows)
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
        if row.get("bundle") == "BUSINESS_REVIEW_BUNDLE" and row.get("scenario") == "44":
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
    source_json: Path,
    intake_csv: Path,
    final_evidence_dir: Path,
) -> CollectionResult:
    payload = read_json(source_json)
    source_csv = Path(str(payload.get("source_csv", ""))) if payload else Path()
    shadow_handoff = payload.get("shadow_handoff", {}) if payload else {}
    if not isinstance(shadow_handoff, dict):
        shadow_handoff = {}
    blockers = build_blockers(payload, source_csv)
    evidence_files: list[Path] = []
    updated_intake = False
    if not blockers:
        evidence_files = write_final_evidence(payload, final_evidence_dir, evidence_token(payload))
        updated_intake = update_intake_csv(intake_csv, final_evidence_dir)
    status = (
        "READY_FOR_OPERATOR_FINAL_FIELDS"
        if not blockers and updated_intake
        else "WAITING_FOR_BUSINESS_REVIEW"
    )
    if not blockers and not updated_intake:
        status = "BLOCKED_INTAKE_ROW_NOT_FOUND"
        blockers = ["BUSINESS_REVIEW_INTAKE_ROW_NOT_FOUND"]
    return CollectionResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status=status,
        ready_for_intake=not blockers,
        updated_intake=updated_intake,
        source_json=str(source_json),
        source_csv=str(source_csv) if str(source_csv) != "." else "",
        source_csv_exists=source_csv.exists(),
        source_csv_sha256=file_sha256(source_csv),
        row_count=int(payload.get("row_count", 0) or 0) if payload else 0,
        ok_count=int(payload.get("ok_count", 0) or 0) if payload else 0,
        ng_count=int(payload.get("ng_count", 0) or 0) if payload else 0,
        blank_count=int(payload.get("blank_count", 0) or 0) if payload else 0,
        invalid_ok_count=int(payload.get("invalid_ok_count", 0) or 0) if payload else 0,
        missing_pdf_count=int(payload.get("missing_pdf_count", 0) or 0) if payload else 0,
        shadow_handoff_generated=shadow_handoff.get("generated") is True,
        shadow_handoff_verified=shadow_handoff.get("verified") is True,
        final_evidence_dir=str(final_evidence_dir),
        final_evidence_files=[str(path) for path in evidence_files],
        intake_csv=str(intake_csv),
        blockers=", ".join(blockers),
    )


def build_markdown(result: CollectionResult) -> str:
    lines = [
        "# Scenario 44 business-review evidence collection 2026-06-20",
        "",
        f"- generated_at: `{result.generated_at}`",
        f"- status: `{result.status}`",
        f"- ready_for_intake: `{result.ready_for_intake}`",
        f"- updated_intake: `{result.updated_intake}`",
        f"- row_count: `{result.row_count}`",
        f"- ok_count: `{result.ok_count}`",
        f"- ng_count: `{result.ng_count}`",
        f"- blank_count: `{result.blank_count}`",
        f"- invalid_ok_count: `{result.invalid_ok_count}`",
        f"- missing_pdf_count: `{result.missing_pdf_count}`",
        f"- shadow_handoff_generated: `{result.shadow_handoff_generated}`",
        f"- shadow_handoff_verified: `{result.shadow_handoff_verified}`",
        f"- blockers: `{result.blockers}`",
        f"- source_csv: `{result.source_csv}`",
        f"- source_csv_sha256: `{result.source_csv_sha256}`",
        f"- final_evidence_dir: `{result.final_evidence_dir}`",
        f"- intake_csv: `{result.intake_csv}`",
        "",
        "## Safety",
        "",
        "- This collector does not decide OK/NG.",
        "- This collector does not write live handoff/latest_ready.json.",
        "- This collector does not operate Rakuraku, move PDFs, send mail, run RK10, print, pay, submit, or write production state.",
        "- Operator result, reviewer identity, and reviewed_at still must be supplied by the business reviewer before the bundle can sync as final evidence.",
        "",
        "## Final Evidence Files",
        "",
    ]
    if result.final_evidence_files:
        lines.extend(f"- `{path}`" for path in result.final_evidence_files)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Scenario 44 business-review evidence.")
    parser.add_argument("--source-json", type=Path, default=DEFAULT_S44_JSON)
    parser.add_argument("--intake-csv", type=Path, default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--final-evidence-dir", type=Path, default=DEFAULT_FINAL_EVIDENCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    result = build_result(args.source_json, args.intake_csv, args.final_evidence_dir)
    json_path = args.out_dir / "s44_business_review_evidence_collect.json"
    md_path = args.out_dir / "s44_business_review_evidence_collect.md"
    json_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(result), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
