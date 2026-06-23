"""Stage current reference evidence into template-matching final folders.

This tool copies already-existing reference logs/reports into repository-local
final evidence folders using the approved filename templates. It does not
create approvals, fabricate missing evidence, open external applications,
submit, print, pay, run RK10, call Azure, or write production data.

Only evidence paths and notes are prefilled. Operator result, reviewer, and
reviewed_at remain human/operator fields unless an upstream collector already
provided them.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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
DEFAULT_OPERATOR_SHEET = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_operator_sheet_20260620"
    / "bundle_operator_sheet.csv"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "final_evidence_candidate_stage_20260621"
SYNC_NOTE = "staged_reference_evidence_candidate_20260621_not_approval"
PATH_SEPARATOR = " / "
RK10_BUNDLE = "RK10_EDITOR_RUNTIME_BUNDLE"
OPERATOR_SHEET_FIELDS = [
    "bundle",
    "owner",
    "scenarios",
    "scenario_count",
    "approval_scope",
    "allowed_operations",
    "evidence_to_capture",
    "hard_stops",
    "packet_csv_path",
    "prepared_evidence_pack_path",
    "operator_result",
    "evidence_path",
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
class StageResult:
    bundle: str
    scenario: str
    source_path: str
    source_exists: bool
    source_sha256: str
    staged_path: str
    staged: bool
    changed: bool
    intake_path: str
    intake_updated: bool
    skipped_reason: str


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


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y%m%d_%H%M%S")


def merge_notes(existing: str, note: str) -> str:
    if not note:
        return existing
    parts = [part.strip() for part in existing.split(PATH_SEPARATOR) if part.strip()]
    if note in parts:
        return existing
    return PATH_SEPARATOR.join([*parts, note])


def read_template_rows(path: Path) -> list[dict[str, str]]:
    return read_csv_rows(path)


def scenario_key(value: str) -> str:
    return value.replace("/", "_").replace("&", "_").replace(" ", "")


def template_matches_scenario(row: dict[str, str], scenario: str) -> bool:
    row_scenario = row.get("scenario", "")
    return row_scenario == scenario or scenario_key(row_scenario) == scenario_key(scenario)


def choose_template_row(
    template_rows: list[dict[str, str]],
    bundle: str,
    scenario: str,
    source_path: Path,
) -> dict[str, str] | None:
    candidates = [row for row in template_rows if template_matches_scenario(row, scenario)]
    if not candidates:
        return None
    source_name = source_path.name.lower()
    if bundle == "RK10_EDITOR_RUNTIME_BUNDLE":
        if "status_gate" in source_name:
            for row in candidates:
                if "rks_status_gate" in row.get("example_filename", ""):
                    return row
        if "safe" in source_name or "recheck" in source_name:
            for row in candidates:
                if "safe_stop_latest_clean_log" in row.get("example_filename", ""):
                    return row
    for row in candidates:
        if "safe_run_log" in row.get("example_filename", ""):
            return row
    return candidates[0]


def render_filename(template: str, timestamp: str) -> str:
    return template.replace("YYYYMMDD", timestamp[:8]).replace("HHMMSS", timestamp[-6:])


def staged_content(
    source_path: Path,
    source_sha256: str,
    staged_timestamp: str,
    bundle: str,
    scenario: str,
) -> bytes:
    header = "\n".join(
        [
            "# Staged reference evidence candidate",
            f"staged_candidate_timestamp: {staged_timestamp}",
            f"bundle: {bundle}",
            f"scenario: {scenario}",
            f"source_path: {source_path}",
            f"source_sha256: {source_sha256}",
            "safety: repository-local copy only; not approval; no external operation",
            "operator_action_required: review and fill operator_result/reviewer/reviewed_at separately",
            "",
            "--- source content begins ---",
            "",
        ]
    )
    return header.encode("utf-8") + source_path.read_bytes()


def write_staged_file(
    destination: Path,
    content: bytes,
) -> tuple[bool, bool]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.read_bytes() == content:
        return True, False
    destination.write_bytes(content)
    return True, True


def update_intake_path(intake_path: Path, bundle: str, scenario: str, final_path: Path) -> bool:
    if not intake_path.exists():
        return False
    rows = read_csv_rows(intake_path)
    fieldnames = csv_fieldnames(intake_path, [])
    changed = False
    updated_rows = []
    for row in rows:
        if row.get("bundle", "") == bundle and scenario_key(row.get("scenario", "")) == scenario_key(scenario):
            next_row = {
                **row,
                "final_evidence_path": row.get("final_evidence_path", "") or str(final_path),
                "notes": merge_notes(row.get("notes", ""), SYNC_NOTE),
            }
            if next_row != row:
                changed = True
            updated_rows.append(next_row)
            continue
        updated_rows.append(row)
    if changed:
        write_csv_rows(intake_path, fieldnames, updated_rows)
    return changed


def intake_rows_by_key(path: Path) -> dict[str, dict[str, str]]:
    return {
        f"{row.get('bundle', '')}::{scenario_key(row.get('scenario', ''))}": row
        for row in read_csv_rows(path)
    }


def build_stage_results(pack_payload: dict[str, Any], generated_at: str) -> list[StageResult]:
    results: list[StageResult] = []
    packs = pack_payload.get("packs", [])
    if not isinstance(packs, list):
        return results
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        bundle = str(pack.get("bundle", "")).strip()
        intake_path = Path(str(pack.get("intake_path", "")))
        template_rows = read_template_rows(Path(str(pack.get("filename_template_path", ""))))
        intake_lookup = intake_rows_by_key(intake_path)
        scenario_evidence = pack.get("scenario_evidence", [])
        if not isinstance(scenario_evidence, list):
            continue
        for evidence in scenario_evidence:
            if not isinstance(evidence, dict):
                continue
            scenario = str(evidence.get("scenario", "")).strip()
            source_text = str(evidence.get("current_reference_evidence", "")).strip()
            source_path = Path(source_text) if source_text else Path()
            if not source_text or not source_path.exists() or not source_path.is_file():
                results.append(
                    StageResult(
                        bundle=bundle,
                        scenario=scenario,
                        source_path=source_text,
                        source_exists=False,
                        source_sha256="",
                        staged_path="",
                        staged=False,
                        changed=False,
                        intake_path=str(intake_path),
                        intake_updated=False,
                        skipped_reason="SOURCE_NOT_FOUND",
                    )
                )
                continue
            template_row = choose_template_row(template_rows, bundle, scenario, source_path)
            if not template_row:
                results.append(
                    StageResult(
                        bundle=bundle,
                        scenario=scenario,
                        source_path=str(source_path),
                        source_exists=True,
                        source_sha256=sha256_file(source_path),
                        staged_path="",
                        staged=False,
                        changed=False,
                        intake_path=str(intake_path),
                        intake_updated=False,
                        skipped_reason="TEMPLATE_ROW_NOT_FOUND",
                    )
                )
                continue
            intake_row = intake_lookup.get(f"{bundle}::{scenario_key(scenario)}", {})
            final_folder_text = (
                intake_row.get("suggested_final_evidence_folder", "")
                or template_row.get("save_under_folder", "")
            )
            if not final_folder_text:
                results.append(
                    StageResult(
                        bundle=bundle,
                        scenario=scenario,
                        source_path=str(source_path),
                        source_exists=True,
                        source_sha256=sha256_file(source_path),
                        staged_path="",
                        staged=False,
                        changed=False,
                        intake_path=str(intake_path),
                        intake_updated=False,
                        skipped_reason="FINAL_FOLDER_NOT_FOUND",
                    )
                )
                continue
            source_hash = sha256_file(source_path)
            timestamp = source_timestamp(source_path)
            filename = render_filename(template_row.get("example_filename", ""), timestamp)
            destination = Path(final_folder_text) / filename
            content = staged_content(source_path, source_hash, timestamp, bundle, scenario)
            staged, changed = write_staged_file(destination, content)
            intake_updated = update_intake_path(intake_path, bundle, scenario, Path(final_folder_text))
            results.append(
                StageResult(
                    bundle=bundle,
                    scenario=scenario,
                    source_path=str(source_path),
                    source_exists=True,
                    source_sha256=source_hash,
                    staged_path=str(destination),
                    staged=staged,
                    changed=changed,
                    intake_path=str(intake_path),
                    intake_updated=intake_updated,
                    skipped_reason="",
                )
            )
    return results


def update_operator_sheet(
    operator_sheet: Path,
    pack_payload: dict[str, Any],
    results: list[StageResult],
) -> tuple[int, str]:
    if not operator_sheet.exists():
        return 0, ""
    rows = read_csv_rows(operator_sheet)
    fieldnames = csv_fieldnames(operator_sheet, OPERATOR_SHEET_FIELDS)
    staged_bundles = {result.bundle for result in results if result.staged}
    final_dir_by_bundle = {
        str(pack.get("bundle", "")): str(pack.get("final_evidence_dir", ""))
        for pack in pack_payload.get("packs", [])
        if isinstance(pack, dict)
    }
    changed_count = 0
    updated_rows = []
    for row in rows:
        bundle = row.get("bundle", "")
        final_dir = final_dir_by_bundle.get(bundle, "")
        if bundle == RK10_BUNDLE:
            auto_filled_by_this_tool = (
                row.get("evidence_path", "") == final_dir
                and SYNC_NOTE in row.get("notes", "")
                and not row.get("operator_result", "")
                and not row.get("reviewer", "")
                and not row.get("reviewed_at", "")
            )
            if auto_filled_by_this_tool:
                next_row = {
                    **row,
                    "evidence_path": "",
                    "notes": merge_notes(row.get("notes", ""), "rk10_bundle_path_left_blank_due_template_scope"),
                }
                if next_row != row:
                    changed_count += 1
                updated_rows.append(next_row)
                continue
            updated_rows.append(row)
            continue
        if bundle in staged_bundles and final_dir and not row.get("evidence_path", ""):
            next_row = {
                **row,
                "evidence_path": final_dir,
                "notes": merge_notes(row.get("notes", ""), SYNC_NOTE),
            }
            if next_row != row:
                changed_count += 1
            updated_rows.append(next_row)
            continue
        updated_rows.append(row)
    if changed_count == 0:
        return 0, ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = operator_sheet.with_name(
        f"{operator_sheet.stem}.before_candidate_stage_{timestamp}{operator_sheet.suffix}"
    )
    backup_path.write_bytes(operator_sheet.read_bytes())
    write_csv_rows(operator_sheet, fieldnames, updated_rows)
    return changed_count, str(backup_path)


def build_payload(pack_json: Path, operator_sheet: Path, apply_updates: bool) -> dict[str, Any]:
    generated_at = datetime.now().isoformat(timespec="seconds")
    pack_payload = read_json(pack_json)
    results = build_stage_results(pack_payload, generated_at) if apply_updates else []
    operator_sheet_updated_count = 0
    operator_sheet_backup_path = ""
    if apply_updates:
        operator_sheet_updated_count, operator_sheet_backup_path = update_operator_sheet(
            operator_sheet,
            pack_payload,
            results,
        )
    return {
        "generated_at": generated_at,
        "overall_goal_complete": False,
        "safety": "repository-local candidate staging only; no approval, no external operation",
        "pack_json": str(pack_json),
        "operator_sheet": str(operator_sheet),
        "apply_updates": apply_updates,
        "stage_result_count": len(results),
        "staged_count": sum(1 for result in results if result.staged),
        "changed_file_count": sum(1 for result in results if result.changed),
        "intake_updated_count": sum(1 for result in results if result.intake_updated),
        "skipped_count": sum(1 for result in results if result.skipped_reason),
        "operator_sheet_updated_count": operator_sheet_updated_count,
        "operator_sheet_backup_path": operator_sheet_backup_path,
        "results": [asdict(result) for result in results],
    }


def format_path(value: str) -> str:
    return f"`{value}`" if value else "-"


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Final evidence candidate staging 2026-06-21",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- apply_updates: `{payload['apply_updates']}`",
        f"- stage_result_count: `{payload['stage_result_count']}`",
        f"- staged_count: `{payload['staged_count']}`",
        f"- changed_file_count: `{payload['changed_file_count']}`",
        f"- intake_updated_count: `{payload['intake_updated_count']}`",
        f"- skipped_count: `{payload['skipped_count']}`",
        f"- operator_sheet_updated_count: `{payload['operator_sheet_updated_count']}`",
        f"- operator_sheet_backup_path: `{payload['operator_sheet_backup_path']}`",
        "",
        "## Boundary",
        "",
        "- Staged files are copies of existing reference evidence with template-matching filenames.",
        "- This does not mark operator_result, reviewer, or reviewed_at.",
        "- Existing validation gates still decide whether evidence is complete.",
        "",
        "## Staged Evidence",
        "",
        "| Bundle | Scenario | Staged | Changed | Intake Updated | Source | Staged Path | Skipped Reason |",
        "|---|---|---:|---:|---:|---|---|---|",
    ]
    for result in payload["results"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(result["bundle"]),
                    str(result["scenario"]),
                    "YES" if result["staged"] else "NO",
                    "YES" if result["changed"] else "NO",
                    "YES" if result["intake_updated"] else "NO",
                    format_path(str(result["source_path"])),
                    format_path(str(result["staged_path"])),
                    str(result["skipped_reason"]) or "-",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "final_evidence_candidate_stage.json"
    csv_path = out_dir / "final_evidence_candidate_stage.csv"
    md_path = out_dir / "final_evidence_candidate_stage.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = payload["results"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = list(asdict(StageResult("", "", "", False, "", "", False, False, "", False, "")).keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)
    write_numbered_copy(csv_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage final evidence candidates from current references.")
    parser.add_argument("--pack-json", type=Path, default=DEFAULT_PACK_JSON)
    parser.add_argument("--operator-sheet", type=Path, default=DEFAULT_OPERATOR_SHEET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--no-apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.pack_json, args.operator_sheet, apply_updates=not args.no_apply)
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
