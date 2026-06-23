"""Simulate completed remaining-operator input on isolated CSV copies.

This is a verification aid only. It copies repository-local evidence CSVs into
an isolated report work area, fills sample operator stamps in the copied
remaining-input CSV, runs the remaining-input sync against the copies, and then
validates the copied execution packet. It never edits the source execution
packet, unified intake CSV, RK10 files, or production systems.
"""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import sync_remaining_operator_input_packet_20260623 as sync_remaining
import validate_goal_execution_packet_scope_exclusions_20260623 as validate_packet


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_REMAINING_INPUT_CSV = (
    REPORTS / "remaining_operator_input_packet_20260623" / "remaining_operator_input.csv"
)
DEFAULT_PACKET_DIR = REPORTS / "goal_execution_packet_20260620"
DEFAULT_UNIFIED_INPUT_CSV = (
    REPORTS / "unified_final_evidence_intake_20260621" / "unified_final_evidence_input.csv"
)
DEFAULT_BUNDLE_SHEET = (
    REPORTS / "bundle_operator_sheet_20260620" / "bundle_operator_sheet.csv"
)
DEFAULT_OUT_DIR = REPORTS / "remaining_operator_input_completion_simulation_20260623"
SAMPLE_OPERATOR_RESULT = "OK"
SAMPLE_REVIEWER = "sample_operator_completion_simulation_20260623"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def csv_fieldnames(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or [])


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def copy_tree_contents(source_dir: Path, target_dir: Path) -> int:
    target_dir.mkdir(parents=True, exist_ok=True)
    copied_count = 0
    if not source_dir.exists():
        return copied_count
    for source_path in source_dir.iterdir():
        target_path = target_dir / source_path.name
        if source_path.is_dir():
            shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        else:
            shutil.copy2(source_path, target_path)
        copied_count += 1
    return copied_count


def copy_file_if_exists(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def remap_packet_csv_path(source_path_text: str, work_packet_dir: Path) -> str:
    source_path = Path(source_path_text)
    return str(work_packet_dir / source_path.name)


def build_simulated_remaining_input(
    source_remaining_csv: Path,
    work_remaining_csv: Path,
    work_packet_dir: Path,
    work_unified_csv: Path,
    reviewed_at: str,
) -> dict[str, Any]:
    rows = read_csv_rows(source_remaining_csv)
    fieldnames = csv_fieldnames(source_remaining_csv)
    simulated_rows: list[dict[str, str]] = []
    for row in rows:
        next_row = dict(row)
        next_row["operator_result"] = SAMPLE_OPERATOR_RESULT
        next_row["reviewer"] = SAMPLE_REVIEWER
        next_row["reviewed_at"] = reviewed_at
        next_row["source_packet_csv"] = remap_packet_csv_path(
            str(row.get("source_packet_csv", "")),
            work_packet_dir,
        )
        next_row["source_unified_input_csv"] = str(work_unified_csv)
        simulated_rows.append(next_row)
    write_csv_rows(work_remaining_csv, fieldnames, simulated_rows)
    write_numbered_copy(work_remaining_csv)
    return {
        "source_remaining_input_csv": str(source_remaining_csv),
        "work_remaining_input_csv": str(work_remaining_csv),
        "sample_completed_row_count": len(simulated_rows),
        "sample_operator_result": SAMPLE_OPERATOR_RESULT,
        "sample_reviewer": SAMPLE_REVIEWER,
        "sample_reviewed_at": reviewed_at,
    }


def write_validation_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    json_path = out_dir / "goal_execution_packet_validation.json"
    md_path = out_dir / "goal_execution_packet_validation.md"
    validate_packet.write_outputs(payload, out_dir)
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Remaining Operator Input Completion Simulation 2026-06-23",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- simulation_passed: `{payload['simulation_passed']}`",
        f"- safety: `{payload['safety']}`",
        f"- sample_completed_row_count: `{payload['sample_completed_row_count']}`",
        f"- sync_updated_cell_count: `{payload['sync_updated_cell_count']}`",
        f"- sync_conflict_count: `{payload['sync_conflict_count']}`",
        f"- sync_unsafe_target_count: `{payload['sync_unsafe_target_count']}`",
        f"- validation_all_packet_rows_approved: `{payload['validation_all_packet_rows_approved']}`",
        f"- validation_approved_row_count: `{payload['validation_approved_row_count']}`",
        f"- validation_row_count: `{payload['validation_row_count']}`",
        f"- validation_needs_attention_count: `{payload['validation_needs_attention_count']}`",
        f"- source_files_modified: `{payload['source_files_modified']}`",
        "",
        "## Boundary",
        "",
        "- This is a sample-input simulation on isolated copied CSVs.",
        "- The sample reviewer value is not an actual customer/operator approval.",
        "- Source execution packet CSVs and unified intake CSV are not modified.",
        "- No RK10 ButtonRun, production write, real mail, print, submit, payment, or paid Azure OCR is executed.",
        "",
        "## Key Paths",
        "",
        f"- work_reports_dir: `{payload['work_reports_dir']}`",
        f"- simulated_remaining_input_csv: `{payload['simulated_remaining_input_csv']}`",
        f"- sync_report: `{payload['sync_report_md']}`",
        f"- validation_report: `{payload['validation_report_md']}`",
    ]
    return "\n".join(lines) + "\n"


def hash_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_existing_files(paths: list[Path]) -> dict[str, str]:
    return {str(path): hash_file(path) for path in paths if path.exists()}


def build_payload(
    remaining_input_csv: Path = DEFAULT_REMAINING_INPUT_CSV,
    packet_dir: Path = DEFAULT_PACKET_DIR,
    unified_input_csv: Path = DEFAULT_UNIFIED_INPUT_CSV,
    bundle_sheet: Path = DEFAULT_BUNDLE_SHEET,
    out_dir: Path = DEFAULT_OUT_DIR,
    reviewed_at: str | None = None,
    scope_exclusions_json: Path = validate_packet.SCOPE_EXCLUSIONS_JSON,
) -> dict[str, Any]:
    reviewed_at = reviewed_at or datetime.now().isoformat(timespec="seconds")
    work_reports = out_dir / "work" / "reports"
    work_packet_dir = work_reports / "goal_execution_packet_20260620"
    work_unified_csv = (
        work_reports
        / "unified_final_evidence_intake_20260621"
        / "unified_final_evidence_input.csv"
    )
    work_bundle_sheet = work_reports / "bundle_operator_sheet_20260620" / "bundle_operator_sheet.csv"
    work_remaining_csv = (
        work_reports / "remaining_operator_input_packet_20260623" / "remaining_operator_input.csv"
    )
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source_hashes_before = hash_existing_files(
        [remaining_input_csv, unified_input_csv, bundle_sheet, *sorted(packet_dir.glob("*_bundle.csv"))]
    )
    copied_packet_item_count = copy_tree_contents(packet_dir, work_packet_dir)
    unified_copied = copy_file_if_exists(unified_input_csv, work_unified_csv)
    bundle_sheet_copied = copy_file_if_exists(bundle_sheet, work_bundle_sheet)
    remaining_input = build_simulated_remaining_input(
        remaining_input_csv,
        work_remaining_csv,
        work_packet_dir,
        work_unified_csv,
        reviewed_at,
    )
    original_reports_root = sync_remaining.REPORTS
    try:
        sync_remaining.REPORTS = work_reports
        sync_payload = sync_remaining.build_payload(work_remaining_csv, apply_updates=True)
    finally:
        sync_remaining.REPORTS = original_reports_root
    sync_out_dir = out_dir / "sync"
    sync_remaining.write_outputs(sync_payload, sync_out_dir)
    validation_payload = validate_packet.build_payload(
        work_packet_dir,
        work_bundle_sheet,
        scope_exclusions_json,
    )
    validation_out_dir = out_dir / "validation"
    write_validation_outputs(validation_payload, validation_out_dir)
    source_hashes_after = hash_existing_files(
        [remaining_input_csv, unified_input_csv, bundle_sheet, *sorted(packet_dir.glob("*_bundle.csv"))]
    )
    source_files_modified = source_hashes_before != source_hashes_after
    simulation_passed = (
        bool(remaining_input["sample_completed_row_count"])
        and sync_payload["complete_input_row_count"] == remaining_input["sample_completed_row_count"]
        and sync_payload["conflict_count"] == 0
        and sync_payload["unsafe_target_count"] == 0
        and validation_payload["all_packet_rows_approved"] is True
        and int(validation_payload["needs_attention_count"]) == 0
        and not source_files_modified
    )
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "simulation_passed": simulation_passed,
        "safety": (
            "isolated copied CSV simulation only; no approval creation in source files; "
            "no RK10 ButtonRun; no production write; no mail; no print; no submit; "
            "no payment; no paid Azure OCR"
        ),
        "work_reports_dir": str(work_reports),
        "copied_packet_item_count": copied_packet_item_count,
        "unified_copied": unified_copied,
        "bundle_sheet_copied": bundle_sheet_copied,
        "source_files_modified": source_files_modified,
        **remaining_input,
        "simulated_remaining_input_csv": str(work_remaining_csv),
        "sync_report_md": str(sync_out_dir / "remaining_operator_input_packet_sync.md.numbered"),
        "sync_updated_cell_count": sync_payload["updated_cell_count"],
        "sync_conflict_count": sync_payload["conflict_count"],
        "sync_unsafe_target_count": sync_payload["unsafe_target_count"],
        "sync_payload": sync_payload,
        "validation_report_md": str(validation_out_dir / "goal_execution_packet_validation.md.numbered"),
        "validation_all_packet_rows_approved": validation_payload["all_packet_rows_approved"],
        "validation_approved_row_count": validation_payload["approved_row_count"],
        "validation_row_count": validation_payload["row_count"],
        "validation_needs_attention_count": validation_payload["needs_attention_count"],
        "validation_payload": validation_payload,
    }
    return payload


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "remaining_operator_input_completion_simulation.json"
    md_path = out_dir / "remaining_operator_input_completion_simulation.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)


def main() -> int:
    payload = build_payload()
    write_outputs(payload)
    print(json.dumps({key: value for key, value in payload.items() if not key.endswith("_payload")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
