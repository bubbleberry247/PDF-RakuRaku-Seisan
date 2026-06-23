"""Sync completed remaining-operator stamps into repository evidence CSVs.

This tool reads the consolidated remaining-operator input CSV and copies only
complete `operator_result` / `reviewer` / `reviewed_at` stamps into blank
matching fields in the referenced repository-local CSVs. It does not create
approval values, run RK10, send mail, print, pay, submit, or write production
systems.
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
REPORTS = ROOT / "plans" / "reports"
DEFAULT_REMAINING_INPUT_CSV = (
    REPORTS / "remaining_operator_input_packet_20260623" / "remaining_operator_input.csv"
)
DEFAULT_OUT_DIR = REPORTS / "remaining_operator_input_packet_sync_20260623"
OPERATOR_FIELDS = ("operator_result", "reviewer", "reviewed_at")


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
class OperatorStamp:
    bundle: str
    scenario: str
    operator_result: str
    reviewer: str
    reviewed_at: str
    source_packet_csv: str
    source_unified_input_csv: str

    def key(self) -> tuple[str, str]:
        return self.bundle.strip(), self.scenario.strip()

    def is_complete(self) -> bool:
        return bool(self.operator_result and self.reviewer and self.reviewed_at)


@dataclass(frozen=True)
class TargetSyncResult:
    target_role: str
    target_csv: str
    bundle: str
    scenario: str
    updated: bool
    updated_fields: str
    skipped_reason: str


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {str(key): str(value).strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def read_fieldnames(path: Path) -> list[str]:
    if not path.exists():
        return []
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


def safe_report_csv(path_text: str) -> Path | None:
    if not path_text:
        return None
    try:
        path = Path(path_text).resolve()
        report_root = REPORTS.resolve()
    except OSError:
        return None
    if path.suffix.lower() != ".csv":
        return None
    try:
        path.relative_to(report_root)
    except ValueError:
        return None
    return path


def load_stamps(path: Path) -> tuple[list[OperatorStamp], list[OperatorStamp]]:
    complete: list[OperatorStamp] = []
    incomplete: list[OperatorStamp] = []
    for row in read_csv_rows(path):
        stamp = OperatorStamp(
            bundle=row.get("bundle", ""),
            scenario=row.get("scenario", ""),
            operator_result=row.get("operator_result", ""),
            reviewer=row.get("reviewer", ""),
            reviewed_at=row.get("reviewed_at", ""),
            source_packet_csv=row.get("source_packet_csv", ""),
            source_unified_input_csv=row.get("source_unified_input_csv", ""),
        )
        if not stamp.bundle or not stamp.scenario:
            continue
        if stamp.is_complete():
            complete.append(stamp)
        else:
            incomplete.append(stamp)
    return complete, incomplete


def ensure_operator_fieldnames(fieldnames: list[str]) -> list[str]:
    output = list(fieldnames)
    for field in OPERATOR_FIELDS:
        if field not in output:
            output.append(field)
    return output


def apply_stamp_to_row(
    row: dict[str, str],
    stamp: OperatorStamp,
) -> tuple[dict[str, str], list[str], str]:
    next_row = dict(row)
    updated_fields: list[str] = []
    for field in OPERATOR_FIELDS:
        current_value = next_row.get(field, "")
        next_value = getattr(stamp, field)
        if current_value and current_value != next_value:
            return row, [], f"CONFLICT_{field}"
        if not current_value and next_value:
            next_row[field] = next_value
            updated_fields.append(field)
    return next_row, updated_fields, ""


def sync_target_csv(
    target_csv: Path,
    target_role: str,
    stamps: list[OperatorStamp],
    apply_updates: bool,
) -> tuple[list[TargetSyncResult], bool]:
    rows = read_csv_rows(target_csv)
    fieldnames = ensure_operator_fieldnames(read_fieldnames(target_csv))
    if not rows:
        return [
            TargetSyncResult(
                target_role=target_role,
                target_csv=str(target_csv),
                bundle=stamp.bundle,
                scenario=stamp.scenario,
                updated=False,
                updated_fields="",
                skipped_reason="TARGET_CSV_EMPTY_OR_MISSING",
            )
            for stamp in stamps
        ], False
    stamps_by_key = {stamp.key(): stamp for stamp in stamps}
    matched_keys: set[tuple[str, str]] = set()
    changed = False
    updated_rows: list[dict[str, str]] = []
    results: list[TargetSyncResult] = []
    for row in rows:
        key = (row.get("bundle", ""), row.get("scenario", ""))
        stamp = stamps_by_key.get(key)
        if not stamp:
            updated_rows.append(row)
            continue
        matched_keys.add(key)
        next_row, updated_fields, skipped_reason = apply_stamp_to_row(row, stamp)
        if updated_fields:
            changed = True
            updated_rows.append(next_row)
            results.append(
                TargetSyncResult(
                    target_role=target_role,
                    target_csv=str(target_csv),
                    bundle=stamp.bundle,
                    scenario=stamp.scenario,
                    updated=True,
                    updated_fields=", ".join(updated_fields),
                    skipped_reason="",
                )
            )
            continue
        updated_rows.append(row)
        results.append(
            TargetSyncResult(
                target_role=target_role,
                target_csv=str(target_csv),
                bundle=stamp.bundle,
                scenario=stamp.scenario,
                updated=False,
                updated_fields="",
                skipped_reason=skipped_reason or "NO_BLANK_TARGET_FIELDS",
            )
        )
    for stamp in stamps:
        if stamp.key() not in matched_keys:
            results.append(
                TargetSyncResult(
                    target_role=target_role,
                    target_csv=str(target_csv),
                    bundle=stamp.bundle,
                    scenario=stamp.scenario,
                    updated=False,
                    updated_fields="",
                    skipped_reason="NO_MATCHING_TARGET_ROW",
                )
            )
    if changed and apply_updates:
        backup_path = target_csv.with_name(
            f"{target_csv.stem}.before_remaining_operator_sync_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}{target_csv.suffix}"
        )
        backup_path.write_bytes(target_csv.read_bytes())
        write_csv_rows(target_csv, fieldnames, updated_rows)
    return results, changed


def group_stamps_by_target(
    stamps: list[OperatorStamp],
    target_role: str,
) -> tuple[dict[Path, list[OperatorStamp]], list[TargetSyncResult]]:
    grouped: dict[Path, list[OperatorStamp]] = {}
    skipped: list[TargetSyncResult] = []
    for stamp in stamps:
        raw_path = (
            stamp.source_packet_csv
            if target_role == "source_packet_csv"
            else stamp.source_unified_input_csv
        )
        target_path = safe_report_csv(raw_path)
        if target_path is None:
            skipped.append(
                TargetSyncResult(
                    target_role=target_role,
                    target_csv=raw_path,
                    bundle=stamp.bundle,
                    scenario=stamp.scenario,
                    updated=False,
                    updated_fields="",
                    skipped_reason="UNSAFE_OR_NON_REPORT_CSV_PATH",
                )
            )
            continue
        grouped.setdefault(target_path, []).append(stamp)
    return grouped, skipped


def build_payload(
    remaining_input_csv: Path = DEFAULT_REMAINING_INPUT_CSV,
    apply_updates: bool = True,
) -> dict[str, Any]:
    complete_stamps, incomplete_stamps = load_stamps(remaining_input_csv)
    all_results: list[TargetSyncResult] = []
    changed_targets: set[str] = set()
    for target_role in ("source_packet_csv", "source_unified_input_csv"):
        grouped, skipped = group_stamps_by_target(complete_stamps, target_role)
        all_results.extend(skipped)
        for target_csv, stamps in grouped.items():
            results, changed = sync_target_csv(target_csv, target_role, stamps, apply_updates)
            all_results.extend(results)
            if changed:
                changed_targets.add(str(target_csv))
    conflict_count = sum(
        1 for result in all_results if result.skipped_reason.startswith("CONFLICT_")
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": (
            "repository-local CSV sync only; copies complete operator stamps; "
            "no approval creation, no RK10 ButtonRun, no production write, no mail, "
            "no print, no submit, no payment, no paid Azure OCR"
        ),
        "apply_updates": apply_updates,
        "remaining_input_csv": str(remaining_input_csv),
        "input_row_count": len(complete_stamps) + len(incomplete_stamps),
        "complete_input_row_count": len(complete_stamps),
        "skipped_incomplete_row_count": len(incomplete_stamps),
        "target_result_count": len(all_results),
        "updated_target_result_count": sum(1 for result in all_results if result.updated),
        "updated_cell_count": sum(
            len(result.updated_fields.split(", "))
            for result in all_results
            if result.updated_fields
        ),
        "changed_target_csv_count": len(changed_targets) if apply_updates else 0,
        "conflict_count": conflict_count,
        "unsafe_target_count": sum(
            1
            for result in all_results
            if result.skipped_reason == "UNSAFE_OR_NON_REPORT_CSV_PATH"
        ),
        "results": [asdict(result) for result in all_results],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Remaining Operator Input Packet Sync 2026-06-23",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- apply_updates: `{payload['apply_updates']}`",
        f"- input_row_count: `{payload['input_row_count']}`",
        f"- complete_input_row_count: `{payload['complete_input_row_count']}`",
        f"- skipped_incomplete_row_count: `{payload['skipped_incomplete_row_count']}`",
        f"- updated_target_result_count: `{payload['updated_target_result_count']}`",
        f"- updated_cell_count: `{payload['updated_cell_count']}`",
        f"- changed_target_csv_count: `{payload['changed_target_csv_count']}`",
        f"- conflict_count: `{payload['conflict_count']}`",
        f"- unsafe_target_count: `{payload['unsafe_target_count']}`",
        f"- safety: `{payload['safety']}`",
        "",
        "## Boundary",
        "",
        "- Only complete `operator_result` / `reviewer` / `reviewed_at` stamps are copied.",
        "- Existing conflicting nonblank values are not overwritten.",
        "- Target CSV paths must stay under `plans\\reports` and must already exist.",
        "",
        "## Sync Results",
        "",
        "| Target Role | Bundle | Scenario | Updated | Updated Fields | Skipped Reason | Target CSV |",
        "|---|---|---|---:|---|---|---|",
    ]
    for result in payload["results"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(result["target_role"]),
                    str(result["bundle"]),
                    str(result["scenario"]),
                    "YES" if result["updated"] else "NO",
                    str(result["updated_fields"]) if result["updated_fields"] else "-",
                    str(result["skipped_reason"]) if result["skipped_reason"] else "-",
                    f"`{result['target_csv']}`",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "remaining_operator_input_packet_sync.json"
    md_path = out_dir / "remaining_operator_input_packet_sync.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync complete remaining-operator stamps into local evidence CSVs."
    )
    parser.add_argument("--remaining-input-csv", type=Path, default=DEFAULT_REMAINING_INPUT_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        remaining_input_csv=args.remaining_input_csv,
        apply_updates=not args.dry_run,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps({key: value for key, value in payload.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
