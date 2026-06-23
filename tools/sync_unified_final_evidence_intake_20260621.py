"""Generate and sync one operator input CSV for all final evidence intakes.

This tool is repository-local only. It does not create approval evidence,
copy files into final evidence folders, open external applications, submit,
print, pay, run RK10, call Azure, or write production data.

The single CSV is an operator convenience layer above the existing per-bundle
``final_evidence_intake.csv`` files. Nonblank operator fields are synced back
to the matching per-bundle intake rows. Blank values never clear existing data.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_PACK_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "bundle_evidence_packs.json"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "unified_final_evidence_intake_20260621"
DEFAULT_INPUT_CSV = DEFAULT_OUT_DIR / "unified_final_evidence_input.csv"
SYNC_NOTE = "synced_from_unified_final_evidence_input_20260621"
LEGACY_OUTLOOK_AUTO_REVIEWER = "OUTLOOK_COM_BUNDLE_AUTO_COLLECTOR"
LEGACY_OUTLOOK_AUTO_NOTE = "auto_collected_from_outlook_com_bundle_logs_20260620"
LEGACY_OUTLOOK_CLEAR_NOTE = "legacy_outlook_auto_approval_fields_cleared_20260622"
PATH_SEPARATOR = " / "
BASE_INTAKE_FIELDS = [
    "bundle",
    "scenario",
    "required_final_evidence",
    "hard_stops",
    "current_reference_evidence",
    "suggested_final_evidence_folder",
    "final_evidence_path",
    "required_update_fields",
    "operator_result",
    "reviewer",
    "reviewed_at",
    "rakuraku_customer_login_used",
    "temporary_save_created",
    "created_data_cleanup_status",
    "created_data_cleanup_evidence_path",
    "cleanup_reviewer",
    "cleanup_reviewed_at",
    "notes",
]
EDITABLE_FIELDS = [
    "final_evidence_path",
    "operator_result",
    "reviewer",
    "reviewed_at",
    "rakuraku_customer_login_used",
    "temporary_save_created",
    "created_data_cleanup_status",
    "created_data_cleanup_evidence_path",
    "cleanup_reviewer",
    "cleanup_reviewed_at",
    "notes",
]
UNIFIED_FIELDS = [
    "entry_key",
    *BASE_INTAKE_FIELDS,
    "source_intake_path",
    "allowed_scope",
    "still_forbidden",
]


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
class IntakeWriteResult:
    intake_path: str
    changed: bool
    updated_row_count: int
    updated_field_count: int
    backup_path: str
    skipped_reason: str


def entry_key(bundle: str, scenario: str) -> str:
    return f"{bundle.strip()}::{scenario.strip()}"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"bundle evidence pack json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {str(key): str(value).strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def csv_fieldnames(path: Path, fallback: list[str]) -> list[str]:
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or fallback)


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_csv_rows_with_fallback(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> Path:
    try:
        write_csv_rows(path, fieldnames, rows)
        return path
    except PermissionError:
        fallback = path.with_name(f"{path.name}.locked_copy")
        write_csv_rows(fallback, fieldnames, rows)
        return fallback


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def merge_notes(existing: str, incoming: str) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in (existing, incoming):
        for part in str(value or "").split(PATH_SEPARATOR):
            normalized = part.strip()
            if not normalized or normalized in seen:
                continue
            parts.append(normalized)
            seen.add(normalized)
    return PATH_SEPARATOR.join(parts)


def has_operator_input(row: dict[str, str]) -> bool:
    return any(str(row.get(field, "")).strip() for field in EDITABLE_FIELDS)


def is_legacy_outlook_auto_approval(row: dict[str, str]) -> bool:
    return (
        row.get("bundle", "").strip() == "OUTLOOK_COM_BUNDLE"
        and row.get("scenario", "").strip() == "12/13"
        and row.get("operator_result", "").strip().upper() == "OK"
        and row.get("reviewer", "").strip() == LEGACY_OUTLOOK_AUTO_REVIEWER
        and LEGACY_OUTLOOK_AUTO_NOTE in row.get("notes", "")
    )


def clear_legacy_outlook_auto_approval(row: dict[str, str]) -> tuple[dict[str, str], int]:
    if not is_legacy_outlook_auto_approval(row):
        return row, 0
    cleared = {
        **row,
        "operator_result": "",
        "reviewer": "",
        "reviewed_at": "",
        "notes": merge_notes(row.get("notes", ""), LEGACY_OUTLOOK_CLEAR_NOTE),
    }
    return cleared, 3


def build_source_rows(pack_payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    packs = pack_payload.get("packs", [])
    if not isinstance(packs, list):
        return rows
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        intake_path = str(pack.get("intake_path", "")).strip()
        if not intake_path:
            continue
        for intake_row in read_csv_rows(Path(intake_path)):
            bundle = intake_row.get("bundle", str(pack.get("bundle", "")))
            scenario = intake_row.get("scenario", "")
            row = {
                "entry_key": entry_key(bundle, scenario),
                "source_intake_path": intake_path,
                "allowed_scope": "Copies nonblank operator fields into the matching repository-local final_evidence_intake.csv row only.",
                "still_forbidden": str(pack.get("hard_stops", "")).strip()
                or "No production registration, mail, print, payment, RK10 ButtonRun, Azure paid OCR, or production write.",
            }
            for field in BASE_INTAKE_FIELDS:
                row[field] = intake_row.get(field, "")
            row["bundle"] = bundle
            row["scenario"] = scenario
            rows.append(row)
    return rows


def merge_existing_input_rows(
    source_rows: list[dict[str, str]],
    existing_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    existing_by_key = {
        row.get("entry_key", entry_key(row.get("bundle", ""), row.get("scenario", ""))): row
        for row in existing_rows
    }
    merged_rows = []
    for source_row in source_rows:
        source_row, _source_clear_count = clear_legacy_outlook_auto_approval(source_row)
        existing = existing_by_key.get(source_row["entry_key"], {})
        existing, _existing_clear_count = clear_legacy_outlook_auto_approval(existing)
        merged = {**source_row}
        for field in EDITABLE_FIELDS:
            source_value = str(source_row.get(field, "")).strip()
            existing_value = str(existing.get(field, "")).strip()
            if field == "notes":
                merged[field] = merge_notes(source_value, existing_value)
                continue
            if not source_value and existing_value:
                merged[field] = existing_value
        merged_rows.append(merged)
    return merged_rows


def group_rows_by_intake_path(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if not has_operator_input(row):
            continue
        intake_path = row.get("source_intake_path", "")
        if not intake_path:
            continue
        grouped.setdefault(intake_path, []).append(row)
    return grouped


def fieldnames_for_intake(path: Path) -> list[str]:
    existing = csv_fieldnames(path, BASE_INTAKE_FIELDS)
    return [*existing, *[field for field in BASE_INTAKE_FIELDS if field not in existing]]


def apply_rows_to_intake(intake_path: Path, unified_rows: list[dict[str, str]]) -> IntakeWriteResult:
    if not intake_path.exists():
        return IntakeWriteResult(
            intake_path=str(intake_path),
            changed=False,
            updated_row_count=0,
            updated_field_count=0,
            backup_path="",
            skipped_reason="INTAKE_CSV_NOT_FOUND",
        )
    fieldnames = fieldnames_for_intake(intake_path)
    target_rows = read_csv_rows(intake_path)
    input_by_key = {
        entry_key(row.get("bundle", ""), row.get("scenario", "")): row
        for row in unified_rows
    }
    updated_rows = []
    updated_row_count = 0
    updated_field_count = 0
    for target_row in target_rows:
        key = entry_key(target_row.get("bundle", ""), target_row.get("scenario", ""))
        input_row = input_by_key.get(key)
        if not input_row:
            updated_rows.append(target_row)
            continue
        updated, cleared_field_count = clear_legacy_outlook_auto_approval(target_row)
        row_changed = cleared_field_count > 0
        updated_field_count += cleared_field_count
        for field in EDITABLE_FIELDS:
            incoming = str(input_row.get(field, "")).strip()
            if not incoming:
                continue
            current = str(updated.get(field, "")).strip()
            next_value = merge_notes(current, incoming) if field == "notes" else incoming
            if next_value != current:
                updated[field] = next_value
                row_changed = True
                updated_field_count += 1
        if row_changed:
            updated["notes"] = merge_notes(updated.get("notes", ""), SYNC_NOTE)
            updated_row_count += 1
        updated_rows.append(updated)
    if updated_row_count == 0:
        return IntakeWriteResult(
            intake_path=str(intake_path),
            changed=False,
            updated_row_count=0,
            updated_field_count=0,
            backup_path="",
            skipped_reason="",
        )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = intake_path.with_name(
        f"{intake_path.stem}.before_unified_sync_{timestamp}{intake_path.suffix}"
    )
    try:
        backup_path.write_bytes(intake_path.read_bytes())
        write_csv_rows(intake_path, fieldnames, updated_rows)
    except PermissionError:
        return IntakeWriteResult(
            intake_path=str(intake_path),
            changed=False,
            updated_row_count=0,
            updated_field_count=0,
            backup_path="",
            skipped_reason="INTAKE_CSV_LOCKED",
        )
    return IntakeWriteResult(
        intake_path=str(intake_path),
        changed=True,
        updated_row_count=updated_row_count,
        updated_field_count=updated_field_count,
        backup_path=str(backup_path),
        skipped_reason="",
    )


def apply_unified_rows(rows: list[dict[str, str]], apply_updates: bool) -> list[IntakeWriteResult]:
    if not apply_updates:
        return []
    return [
        apply_rows_to_intake(Path(intake_path), intake_rows)
        for intake_path, intake_rows in group_rows_by_intake_path(rows).items()
    ]


def build_payload(
    pack_json: Path,
    input_csv: Path,
    apply_updates: bool,
) -> dict[str, Any]:
    pack_payload = read_json(pack_json)
    source_rows = build_source_rows(pack_payload)
    existing_rows = read_csv_rows(input_csv)
    unified_rows = merge_existing_input_rows(source_rows, existing_rows)
    sync_results = apply_unified_rows(unified_rows, apply_updates)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": "repository-local single CSV sync only; no approval, no evidence copy, no external operation",
        "pack_json": str(pack_json),
        "unified_input_csv": str(input_csv),
        "unified_input_csv_written": "",
        "apply_updates": apply_updates,
        "source_intake_count": len(
            {
                row.get("source_intake_path", "")
                for row in unified_rows
                if row.get("source_intake_path", "")
            }
        ),
        "unified_row_count": len(unified_rows),
        "rows_with_operator_input_count": sum(1 for row in unified_rows if has_operator_input(row)),
        "updated_intake_count": sum(1 for result in sync_results if result.changed),
        "skipped_intake_count": sum(1 for result in sync_results if result.skipped_reason),
        "updated_field_count": sum(result.updated_field_count for result in sync_results),
        "sync_results": [asdict(result) for result in sync_results],
        "rows": unified_rows,
    }


def format_path(value: str) -> str:
    return f"`{value}`" if value else "-"


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Unified final evidence input 2026-06-21",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- apply_updates: `{payload['apply_updates']}`",
        f"- source_intake_count: `{payload['source_intake_count']}`",
        f"- unified_row_count: `{payload['unified_row_count']}`",
        f"- rows_with_operator_input_count: `{payload['rows_with_operator_input_count']}`",
        f"- updated_intake_count: `{payload['updated_intake_count']}`",
        f"- skipped_intake_count: `{payload['skipped_intake_count']}`",
        f"- updated_field_count: `{payload['updated_field_count']}`",
        f"- unified_input_csv: `{payload['unified_input_csv_written'] or payload['unified_input_csv']}`",
        "",
        "## Boundary",
        "",
        "- Fill this one CSV instead of hunting through each bundle's `final_evidence_intake.csv`.",
        "- Blank cells never clear existing bundle intake values.",
        "- Nonblank operator fields are copied only into repository-local final evidence intake CSVs.",
        "- This does not approve a scenario by itself; the existing validation gates still require existing evidence paths and approved reviewer fields.",
        "",
        "## Sync Results",
        "",
        "| Intake | Changed | Rows | Fields | Backup | Skipped Reason |",
        "|---|---:|---:|---:|---|---|",
    ]
    for result in payload["sync_results"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    format_path(str(result["intake_path"])),
                    "YES" if result["changed"] else "NO",
                    str(result["updated_row_count"]),
                    str(result["updated_field_count"]),
                    format_path(str(result["backup_path"])),
                    str(result["skipped_reason"]) or "-",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    input_path = Path(payload["unified_input_csv"])
    written_input_path = write_csv_rows_with_fallback(input_path, UNIFIED_FIELDS, payload["rows"])
    payload["unified_input_csv_written"] = str(written_input_path)
    json_path = out_dir / "unified_final_evidence_intake_sync.json"
    md_path = out_dir / "unified_final_evidence_intake_sync.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(written_input_path)
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync one final evidence input CSV into bundle intakes.")
    parser.add_argument("--pack-json", type=Path, default=DEFAULT_PACK_JSON)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--no-apply",
        action="store_true",
        help="Only generate the unified input CSV and report; do not sync back to bundle intakes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.pack_json, args.input_csv, apply_updates=not args.no_apply)
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
