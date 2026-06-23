"""Run Scenario 44 sample OK shadow handoff without touching live state.

This tool copies the business spot-check CSV into a repository report folder,
marks a small sample of rows as OK, marks the rest as NG, then reuses the
existing Scenario 44 handoff candidate builder. It never writes live review.db,
live handoff/latest_ready.json, Rakuraku, PDF processed folders, mail, RK10, or
production shared folders.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from build_s44_spot_check_handoff_candidates_20260620 import (
    DEFAULT_OUT_DIR as LIVE_CANDIDATE_OUT_DIR,
)
from build_s44_spot_check_handoff_candidates_20260620 import (
    SPOT_CHECK_CSV,
    analyze_spot_check,
    read_csv_rows,
    write_reports,
)


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "s44_sample_ok_shadow_20260620"
DEFAULT_OK_LIMIT = 3


@dataclass(frozen=True)
class SampleBuildResult:
    generated_at: str
    source_csv: str
    sample_csv: str
    source_exists: bool
    source_row_count: int
    requested_ok_limit: int
    sample_ok_count: int
    sample_ng_count: int
    skipped_missing_pdf_count: int
    status: str
    next_action: str


def normalize(value: str | None) -> str:
    return (value or "").strip()


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(rows[0].keys()) if rows else [
        "confirm_ok",
        "reject_reason",
        "vendor_name",
        "amount_estimate",
        "receiving_date",
        "invoice_number",
        "filename",
        "operation_id",
        "pdf_path",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_sample_rows(rows: list[dict[str, str]], ok_limit: int) -> tuple[list[dict[str, str]], int]:
    sample_rows: list[dict[str, str]] = []
    ok_count = 0
    skipped_missing_pdf_count = 0
    for row in rows:
        pdf_path = normalize(row.get("pdf_path"))
        next_row = {**row}
        if ok_count < ok_limit and pdf_path and Path(pdf_path).exists():
            next_row["confirm_ok"] = "OK"
            next_row["reject_reason"] = "sample shadow handoff only; not business approval"
            ok_count += 1
        else:
            next_row["confirm_ok"] = "NG"
            next_row["reject_reason"] = "sample shadow handoff excluded"
            if ok_count < ok_limit and pdf_path and not Path(pdf_path).exists():
                skipped_missing_pdf_count += 1
        sample_rows.append(next_row)
    return sample_rows, skipped_missing_pdf_count


def build_sample_csv(source_csv: Path, out_dir: Path, ok_limit: int) -> SampleBuildResult:
    generated_at = datetime.now().isoformat(timespec="seconds")
    sample_csv = out_dir / f"s44_spot_check_sample_{ok_limit}ok.csv"
    if not source_csv.exists():
        return SampleBuildResult(
            generated_at=generated_at,
            source_csv=str(source_csv),
            sample_csv=str(sample_csv),
            source_exists=False,
            source_row_count=0,
            requested_ok_limit=ok_limit,
            sample_ok_count=0,
            sample_ng_count=0,
            skipped_missing_pdf_count=0,
            status="HOLD_MISSING_SOURCE_CSV",
            next_action="Restore the Scenario 44 spot-check CSV before sample shadow execution.",
        )

    rows = read_csv_rows(source_csv)
    sample_rows, skipped_missing_pdf_count = build_sample_rows(rows, ok_limit)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(sample_csv, sample_rows)
    sample_ok_count = sum(1 for row in sample_rows if normalize(row.get("confirm_ok")).upper() == "OK")
    sample_ng_count = sum(1 for row in sample_rows if normalize(row.get("confirm_ok")).upper() == "NG")
    status = "READY_FOR_SHADOW_HANDOFF" if sample_ok_count > 0 else "HOLD_NO_SAMPLE_OK_ROWS"
    next_action = (
        "Run existing Scenario 44 shadow handoff builder against the sample CSV."
        if sample_ok_count > 0
        else "Provide at least one sample row with an existing PDF path."
    )
    return SampleBuildResult(
        generated_at=generated_at,
        source_csv=str(source_csv),
        sample_csv=str(sample_csv),
        source_exists=True,
        source_row_count=len(rows),
        requested_ok_limit=ok_limit,
        sample_ok_count=sample_ok_count,
        sample_ng_count=sample_ng_count,
        skipped_missing_pdf_count=skipped_missing_pdf_count,
        status=status,
        next_action=next_action,
    )


def build_markdown(result: SampleBuildResult, handoff_payload: dict[str, object] | None) -> str:
    lines = [
        "# Scenario 44 sample OK shadow handoff",
        "",
        f"- generated_at: `{result.generated_at}`",
        f"- status: `{result.status}`",
        f"- source_csv: `{result.source_csv}`",
        f"- sample_csv: `{result.sample_csv}`",
        f"- source_row_count: `{result.source_row_count}`",
        f"- requested_ok_limit: `{result.requested_ok_limit}`",
        f"- sample_ok_count: `{result.sample_ok_count}`",
        f"- sample_ng_count: `{result.sample_ng_count}`",
        f"- skipped_missing_pdf_count: `{result.skipped_missing_pdf_count}`",
        f"- next_action: {result.next_action}",
        "",
        "## Safety",
        "",
        "- The original business spot-check CSV is not modified.",
        "- Live review.db and live handoff/latest_ready.json are not updated.",
        "- Rakuraku registration, final submit, PDF processed move, mail, RK10 ButtonRun, and production writes are not executed.",
        "- OK marks in the sample CSV are test input only and are not business approval.",
        "",
        "## Shadow Result",
        "",
    ]
    shadow = (handoff_payload or {}).get("shadow_handoff", {})
    if not isinstance(shadow, dict) or not shadow.get("generated"):
        lines.append("- generated: `False`")
    else:
        lines.extend(
            [
                "- generated: `True`",
                f"- verified: `{shadow.get('verified')}`",
                f"- verify_message: `{shadow.get('verify_message')}`",
                f"- data_file: `{shadow.get('data_file')}`",
                f"- latest_ready_file: `{shadow.get('latest_ready_file')}`",
                f"- item_count: `{shadow.get('item_count')}`",
                f"- checksum: `{shadow.get('checksum')}`",
            ]
        )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_report(result: SampleBuildResult, handoff_payload: dict[str, object] | None, out_dir: Path) -> dict[str, object]:
    payload = {
        **result.__dict__,
        "live_candidate_out_dir": str(LIVE_CANDIDATE_OUT_DIR),
        "shadow_handoff_payload": handoff_payload or {"shadow_handoff": {"generated": False}},
    }
    json_path = out_dir / "s44_sample_ok_shadow.json"
    md_path = out_dir / "s44_sample_ok_shadow.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(result, handoff_payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Scenario 44 sample OK shadow handoff.")
    parser.add_argument("--source-csv", type=Path, default=SPOT_CHECK_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--ok-limit", type=int, default=DEFAULT_OK_LIMIT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_sample_csv(args.source_csv, args.out_dir, args.ok_limit)
    handoff_payload = None
    if result.status == "READY_FOR_SHADOW_HANDOFF":
        summary = analyze_spot_check(Path(result.sample_csv))
        handoff_payload = write_reports(summary, args.out_dir)
    payload = write_report(result, handoff_payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.status == "READY_FOR_SHADOW_HANDOFF" else 1


if __name__ == "__main__":
    raise SystemExit(main())
