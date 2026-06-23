"""Sync completed bundle evidence intake rows into the six-row operator sheet.

This tool only reads prepared evidence pack intake CSVs and writes repository
reports / the repository-local operator sheet. It never opens Outlook, RK10,
Rakuraku, Azure, printers, mail clients, payment systems, MainSV, or production
files. It also never creates approval evidence by itself; it only syncs a
bundle when every scenario intake row already has existing final evidence and
complete operator fields.
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

from validate_bundle_evidence_packs_20260620 import validate_final_evidence_filenames


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
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "bundle_evidence_intake_sync_20260620"
DEFAULT_SCOPE_EXCLUSIONS_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "objective_scope_exclusions_20260623"
    / "objective_scope_exclusions.json"
)
APPROVED_RESULTS = {
    "approved",
    "complete",
    "completed",
    "ok",
    "pass",
    "passed",
    "実施済",
    "完了",
    "承認",
    "承認済",
    "済",
}
YES_VALUES = {"1", "true", "yes", "y", "used", "created", "はい", "あり", "有", "作成", "作成済"}
CLEANUP_DONE_RESULTS = {
    "deleted",
    "delete_done",
    "removed",
    "cleanup_complete",
    "ok",
    "done",
    "削除",
    "削除済",
    "削除完了",
    "完了",
    "済",
}
SYNC_NOTE = "synced_from_final_evidence_intake_20260620"
STALE_CLEAR_NOTE = "cleared_stale_operator_sheet_fields_from_blocked_final_evidence_intake_20260620"
OPERATOR_SHEET_SYNC_FIELDS = (
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
class IntakeRowCheck:
    bundle: str
    scenario: str
    final_evidence_path: str
    final_evidence_exists: bool
    final_evidence_has_content: bool
    final_evidence_under_final_dir: bool
    final_evidence_filenames_match: bool
    final_evidence_filename_match_count: int
    final_evidence_filename_mismatch_count: int
    final_evidence_filename_issue: str
    final_evidence_filename_mismatches: str
    operator_result: str
    operator_result_approved: bool
    reviewer: str
    reviewed_at: str
    cleanup_required: bool
    cleanup_evidence_path: str
    cleanup_evidence_exists: bool
    cleanup_status_approved: bool
    status: str
    blockers: str

    @property
    def ready(self) -> bool:
        return self.status == "READY"


@dataclass(frozen=True)
class BundleSyncResult:
    bundle: str
    scenarios: str
    scenario_count: int
    intake_path: str
    final_evidence_dir: str
    intake_exists: bool
    intake_row_count: int
    ready_row_count: int
    ready_to_sync: bool
    operator_result: str
    evidence_path: str
    reviewer: str
    reviewed_at: str
    rakuraku_customer_login_used: str
    temporary_save_created: str
    created_data_cleanup_status: str
    created_data_cleanup_evidence_path: str
    cleanup_reviewer: str
    cleanup_reviewed_at: str
    blockers: str
    rows: list[IntakeRowCheck]


def normalize(value: str) -> str:
    return value.strip().lower()


def is_yes(value: str) -> bool:
    return normalize(value) in YES_VALUES


def evidence_item_count(value: str) -> int:
    if not value.strip():
        return 0
    path = Path(value)
    if path.is_file():
        return 1 if path.stat().st_size > 0 else 0
    if not path.is_dir():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file() and item.stat().st_size > 0)


def path_exists(value: str) -> bool:
    return bool(value.strip()) and Path(value).exists()


def path_has_content(value: str) -> bool:
    return evidence_item_count(value) > 0


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"bundle evidence pack json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def scenario_chunks(value: str) -> list[str]:
    chunks: list[str] = []
    for chunk in value.replace("、", ",").split(","):
        cleaned = chunk.strip()
        if cleaned:
            chunks.append(cleaned)
    return chunks


def scenario_tokens(value: str) -> set[str]:
    tokens = set(scenario_chunks(value))
    for chunk in list(tokens):
        if "/" in chunk and all(part.strip().isdigit() for part in chunk.split("/")):
            tokens.update(part.strip() for part in chunk.split("/") if part.strip())
    return tokens


def load_scope_exclusions(path: Path = DEFAULT_SCOPE_EXCLUSIONS_JSON) -> list[dict[str, str]]:
    payload = read_optional_json(path)
    raw_rows = payload.get("exclusions", [])
    if not isinstance(raw_rows, list):
        return []
    rows: list[dict[str, str]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        active = row.get("active", True)
        if active is False or str(active).strip().lower() in {"false", "0", "no"}:
            continue
        scenario = str(row.get("scenario", "")).strip()
        if scenario:
            rows.append({"scenario": scenario})
    return rows


def excluded_scenario_tokens(exclusions: list[dict[str, str]]) -> set[str]:
    tokens: set[str] = set()
    for exclusion in exclusions:
        tokens.update(scenario_tokens(exclusion.get("scenario", "")))
    return tokens


def scenario_is_excluded(scenario: str, excluded_tokens: set[str]) -> bool:
    return bool(scenario_tokens(scenario) & excluded_tokens)


def active_scenarios_text(scenarios: str, excluded_tokens: set[str]) -> str:
    active_chunks = [
        chunk
        for chunk in scenario_chunks(scenarios)
        if not scenario_is_excluded(chunk, excluded_tokens)
    ]
    return ",".join(active_chunks)


def active_scenario_count(
    scenarios: str,
    fallback_count: int,
    intake_rows: list[dict[str, str]],
    excluded_tokens: set[str],
) -> int:
    active_chunks = scenario_chunks(active_scenarios_text(scenarios, excluded_tokens))
    if active_chunks:
        return len(active_chunks)
    if intake_rows:
        return len(intake_rows)
    return fallback_count


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {str(key): str(value).strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def checked_status(blockers: list[str]) -> str:
    return "READY" if not blockers else "BLOCKED"


def build_intake_row_check(
    row: dict[str, str],
    final_evidence_dir: Path,
    filename_template_path: str,
) -> IntakeRowCheck:
    final_evidence_path = row.get("final_evidence_path", "")
    final_path = Path(final_evidence_path) if final_evidence_path else Path()
    final_exists = path_exists(final_evidence_path)
    final_has_content = path_has_content(final_evidence_path)
    under_final_dir = final_exists and is_relative_to(final_path, final_evidence_dir)
    (
        final_filenames_match,
        filename_match_count,
        filename_mismatch_count,
        filename_issue,
        filename_mismatches,
    ) = validate_final_evidence_filenames(final_evidence_path, filename_template_path)
    operator_result = row.get("operator_result", "")
    operator_approved = normalize(operator_result) in APPROVED_RESULTS
    reviewer = row.get("reviewer", "")
    reviewed_at = row.get("reviewed_at", "")
    rakuraku_used = row.get("rakuraku_customer_login_used", "")
    temp_created = row.get("temporary_save_created", "")
    cleanup_required = False
    cleanup_status = row.get("created_data_cleanup_status", "")
    cleanup_path = row.get("created_data_cleanup_evidence_path", "")
    cleanup_exists = path_exists(cleanup_path)
    cleanup_status_approved = normalize(cleanup_status) in CLEANUP_DONE_RESULTS
    blockers = []
    if not final_evidence_path:
        blockers.append("FINAL_EVIDENCE_PATH_BLANK")
    elif not final_exists:
        blockers.append("FINAL_EVIDENCE_NOT_FOUND")
    elif not final_has_content:
        blockers.append("FINAL_EVIDENCE_EMPTY")
    if final_exists and not under_final_dir:
        blockers.append("FINAL_EVIDENCE_OUTSIDE_FINAL_DIR")
    if final_exists and final_has_content and not final_filenames_match:
        blockers.append(filename_issue or "FINAL_EVIDENCE_FILENAME_NOT_VALID")
    if not operator_result:
        blockers.append("OPERATOR_RESULT_BLANK")
    elif not operator_approved:
        blockers.append("OPERATOR_RESULT_NOT_APPROVED")
    if not reviewer:
        blockers.append("REVIEWER_BLANK")
    if not reviewed_at:
        blockers.append("REVIEWED_AT_BLANK")
    return IntakeRowCheck(
        bundle=row.get("bundle", ""),
        scenario=row.get("scenario", ""),
        final_evidence_path=final_evidence_path,
        final_evidence_exists=final_exists,
        final_evidence_has_content=final_has_content,
        final_evidence_under_final_dir=under_final_dir,
        final_evidence_filenames_match=final_filenames_match,
        final_evidence_filename_match_count=filename_match_count,
        final_evidence_filename_mismatch_count=filename_mismatch_count,
        final_evidence_filename_issue=filename_issue,
        final_evidence_filename_mismatches=filename_mismatches,
        operator_result=operator_result,
        operator_result_approved=operator_approved,
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        cleanup_required=cleanup_required,
        cleanup_evidence_path=cleanup_path,
        cleanup_evidence_exists=cleanup_exists,
        cleanup_status_approved=cleanup_status_approved,
        status=checked_status(blockers),
        blockers=", ".join(blockers),
    )


def unique_join(values: list[str]) -> str:
    unique_values = []
    for value in values:
        if value and value not in unique_values:
            unique_values.append(value)
    return " / ".join(unique_values)


def filename_template_path_for_pack(pack: dict[str, Any]) -> str:
    explicit_path = str(pack.get("filename_template_path", ""))
    if explicit_path.strip():
        return explicit_path
    pack_dir = str(pack.get("pack_dir", ""))
    if not pack_dir.strip():
        return ""
    return str(Path(pack_dir) / "operator_evidence_filename_template.csv")


def synced_evidence_path(intake_rows: list[dict[str, str]], final_evidence_dir: str) -> str:
    evidence_paths = [
        row.get("final_evidence_path", "")
        for row in intake_rows
        if row.get("final_evidence_path", "")
    ]
    unique_paths = []
    for evidence_path in evidence_paths:
        if evidence_path not in unique_paths:
            unique_paths.append(evidence_path)
    if len(unique_paths) == 1:
        return unique_paths[0]
    return final_evidence_dir


def build_bundle_sync(
    pack: dict[str, Any],
    excluded_tokens: set[str] | None = None,
) -> BundleSyncResult:
    excluded = excluded_tokens or set()
    bundle = str(pack.get("bundle", ""))
    raw_scenarios = str(pack.get("scenarios", ""))
    intake_path = str(pack.get("intake_path", ""))
    final_evidence_dir = str(pack.get("final_evidence_dir", ""))
    filename_template_path = filename_template_path_for_pack(pack)
    raw_intake_rows = read_csv_rows(Path(intake_path))
    intake_rows = [
        row
        for row in raw_intake_rows
        if not scenario_is_excluded(row.get("scenario", ""), excluded)
    ]
    scenarios = active_scenarios_text(raw_scenarios, excluded)
    scenario_count = active_scenario_count(
        raw_scenarios,
        int(pack.get("scenario_count", 0)),
        intake_rows,
        excluded,
    )
    row_checks = [
        build_intake_row_check(row, Path(final_evidence_dir), filename_template_path)
        for row in intake_rows
    ]
    ready_count = sum(1 for row in row_checks if row.ready)
    required_ready_count = max(scenario_count, len(intake_rows))
    cleanup_tracking_rows = [
        row
        for row in intake_rows
        if is_yes(row.get("rakuraku_customer_login_used", ""))
        or is_yes(row.get("temporary_save_created", ""))
        or bool(row.get("created_data_cleanup_status", ""))
        or bool(row.get("created_data_cleanup_evidence_path", ""))
    ]
    cleanup_paths = [
        row.get("created_data_cleanup_evidence_path", "")
        for row in cleanup_tracking_rows
        if row.get("created_data_cleanup_evidence_path", "")
    ]
    cleanup_shared_path = unique_join(cleanup_paths)
    bundle_blockers = []
    if not Path(intake_path).exists():
        bundle_blockers.append("INTAKE_CSV_NOT_FOUND")
    if scenario_count == 0:
        bundle_blockers.append("SCENARIO_COUNT_ZERO")
    if len(intake_rows) < scenario_count:
        bundle_blockers.append("INTAKE_ROW_COUNT_MISMATCH")
    if ready_count != required_ready_count:
        bundle_blockers.append("NOT_ALL_ROWS_READY")
    row_blockers = []
    for row in row_checks:
        for blocker in row.blockers.split(", "):
            if blocker and blocker not in row_blockers:
                row_blockers.append(blocker)
    bundle_blockers.extend(row_blockers)
    ready_to_sync = not bundle_blockers
    return BundleSyncResult(
        bundle=bundle,
        scenarios=scenarios,
        scenario_count=scenario_count,
        intake_path=intake_path,
        final_evidence_dir=final_evidence_dir,
        intake_exists=Path(intake_path).exists(),
        intake_row_count=len(intake_rows),
        ready_row_count=ready_count,
        ready_to_sync=ready_to_sync,
        operator_result="OK" if ready_to_sync else "",
        evidence_path=synced_evidence_path(intake_rows, final_evidence_dir) if ready_to_sync else "",
        reviewer=unique_join([row.get("reviewer", "") for row in intake_rows]) if ready_to_sync else "",
        reviewed_at=unique_join([row.get("reviewed_at", "") for row in intake_rows]) if ready_to_sync else "",
        rakuraku_customer_login_used="YES" if ready_to_sync and any(is_yes(row.get("rakuraku_customer_login_used", "")) for row in intake_rows) else "",
        temporary_save_created="YES" if ready_to_sync and any(is_yes(row.get("temporary_save_created", "")) for row in intake_rows) else "",
        created_data_cleanup_status=unique_join([row.get("created_data_cleanup_status", "") for row in cleanup_tracking_rows]) if ready_to_sync and cleanup_tracking_rows else "",
        created_data_cleanup_evidence_path=cleanup_shared_path if ready_to_sync and cleanup_tracking_rows else "",
        cleanup_reviewer=unique_join([row.get("cleanup_reviewer", "") for row in cleanup_tracking_rows]) if ready_to_sync and cleanup_tracking_rows else "",
        cleanup_reviewed_at=unique_join([row.get("cleanup_reviewed_at", "") for row in cleanup_tracking_rows]) if ready_to_sync and cleanup_tracking_rows else "",
        blockers=", ".join(bundle_blockers),
        rows=row_checks,
    )


def read_operator_sheet(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [
            {str(key): str(value).strip() for key, value in row.items() if key is not None}
            for row in reader
        ]


def apply_sync_results(
    operator_sheet: Path,
    sync_results: list[BundleSyncResult],
) -> tuple[int, str, list[str]]:
    fieldnames, rows = read_operator_sheet(operator_sheet)
    if not rows:
        return 0, "", []
    results_by_bundle = {
        result.bundle: result
        for result in sync_results
    }
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = operator_sheet.with_name(f"{operator_sheet.stem}.before_intake_sync_{timestamp}{operator_sheet.suffix}")
    updated_count = 0
    updated_bundles = []
    updated_rows = []
    for row in rows:
        result = results_by_bundle.get(row.get("bundle", ""))
        if not result:
            updated_rows.append(row)
            continue
        if not result.ready_to_sync:
            stale_values_present = any(row.get(field, "") for field in OPERATOR_SHEET_SYNC_FIELDS)
            if not stale_values_present:
                updated_rows.append(row)
                continue
            updated = {
                **row,
                **{field: "" for field in OPERATOR_SHEET_SYNC_FIELDS},
                "notes": unique_join([row.get("notes", ""), STALE_CLEAR_NOTE]),
            }
            updated_count += 1
            updated_bundles.append(result.bundle)
            updated_rows.append(updated)
            continue
        updated = {
            **row,
            "operator_result": result.operator_result,
            "evidence_path": result.evidence_path,
            "reviewer": result.reviewer,
            "reviewed_at": result.reviewed_at,
            "rakuraku_customer_login_used": result.rakuraku_customer_login_used,
            "temporary_save_created": result.temporary_save_created,
            "created_data_cleanup_status": result.created_data_cleanup_status,
            "created_data_cleanup_evidence_path": result.created_data_cleanup_evidence_path,
            "cleanup_reviewer": result.cleanup_reviewer,
            "cleanup_reviewed_at": result.cleanup_reviewed_at,
            "notes": unique_join([row.get("notes", ""), SYNC_NOTE]),
        }
        if updated != row:
            updated_count += 1
            updated_bundles.append(result.bundle)
        updated_rows.append(updated)
    if updated_count == 0:
        return 0, "", []
    backup_path.write_bytes(operator_sheet.read_bytes())
    write_csv_rows(operator_sheet, fieldnames, updated_rows)
    return updated_count, str(backup_path), updated_bundles


def build_payload(
    pack_json: Path,
    operator_sheet: Path,
    apply_updates: bool,
    scope_exclusions_json: Path = DEFAULT_SCOPE_EXCLUSIONS_JSON,
) -> dict[str, Any]:
    pack_payload = read_json(pack_json)
    scope_exclusions = load_scope_exclusions(scope_exclusions_json)
    excluded_tokens = excluded_scenario_tokens(scope_exclusions)
    sync_results = [
        build_bundle_sync(pack, excluded_tokens)
        for pack in pack_payload.get("packs", [])
    ]
    ready_count = sum(1 for result in sync_results if result.ready_to_sync)
    updated_count = 0
    backup_path = ""
    updated_bundles: list[str] = []
    if apply_updates:
        updated_count, backup_path, updated_bundles = apply_sync_results(operator_sheet, sync_results)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": "repository-local intake sync only; no external operation and no evidence fabrication",
        "pack_json": str(pack_json),
        "operator_sheet": str(operator_sheet),
        "apply_updates": apply_updates,
        "scope_exclusion_count": len(scope_exclusions),
        "scope_exclusions_path": str(scope_exclusions_json),
        "scope_excluded_scenarios": [
            row.get("scenario", "")
            for row in scope_exclusions
            if row.get("scenario", "")
        ],
        "bundle_count": len(sync_results),
        "ready_to_sync_count": ready_count,
        "updated_bundle_count": updated_count,
        "updated_bundles": updated_bundles,
        "operator_sheet_backup_path": backup_path,
        "results": [
            {
                **asdict(result),
                "rows": [asdict(row) for row in result.rows],
            }
            for result in sync_results
        ],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    results = payload["results"]
    assert isinstance(results, list)
    lines = [
        "# 6束最終証跡取り込み同期 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- apply_updates: `{payload['apply_updates']}`",
        f"- scope_exclusion_count: `{payload.get('scope_exclusion_count', 0)}`",
        f"- scope_excluded_scenarios: `{', '.join(payload.get('scope_excluded_scenarios', []))}`",
        f"- bundle_count: `{payload['bundle_count']}`",
        f"- ready_to_sync_count: `{payload['ready_to_sync_count']}`",
        f"- updated_bundle_count: `{payload['updated_bundle_count']}`",
        f"- operator_sheet: `{payload['operator_sheet']}`",
        f"- operator_sheet_backup_path: `{payload['operator_sheet_backup_path']}`",
        "",
        "## Boundary",
        "",
        "- This syncs only when every scenario row in a bundle intake CSV already has existing evidence under `final_evidence` and approved operator fields.",
        "- It does not create evidence, approve missing rows, run Outlook/RK10/Rakuraku/Azure, send mail, print, submit, pay, or write production files.",
        "- Rakuraku customer-login / temporary-save / cleanup columns are optional tracking fields and do not block sync by themselves.",
        "",
        "## Bundle Sync Matrix",
        "",
        "| Bundle | Ready To Sync | Updated | Intake Rows | Ready Rows | Evidence Path | Reviewer | Reviewed At | Blockers |",
        "|---|---:|---:|---:|---:|---|---|---|---|",
    ]
    updated_bundles = set(payload.get("updated_bundles", []))
    for result in results:
        assert isinstance(result, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(result["bundle"]),
                    "YES" if result["ready_to_sync"] else "NO",
                    "YES" if result["bundle"] in updated_bundles else "NO",
                    str(result["intake_row_count"]),
                    str(result["ready_row_count"]),
                    f"`{result['evidence_path']}`" if result["evidence_path"] else "-",
                    str(result["reviewer"]) if result["reviewer"] else "-",
                    str(result["reviewed_at"]) if result["reviewed_at"] else "-",
                    str(result["blockers"]) if result["blockers"] else "-",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "bundle_evidence_intake_sync.json"
    md_path = out_dir / "bundle_evidence_intake_sync.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync bundle evidence intake into the operator sheet.")
    parser.add_argument("--pack-json", type=Path, default=DEFAULT_PACK_JSON)
    parser.add_argument("--operator-sheet", type=Path, default=DEFAULT_OPERATOR_SHEET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--scope-exclusions-json", type=Path, default=DEFAULT_SCOPE_EXCLUSIONS_JSON)
    parser.add_argument(
        "--no-apply",
        action="store_true",
        help="Only report ready bundles; do not update the operator sheet.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        args.pack_json,
        args.operator_sheet,
        apply_updates=not args.no_apply,
        scope_exclusions_json=args.scope_exclusions_json,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
