"""Collect approved RK10 runtime evidence into the RK10 bundle intake.

This tool never opens RK10, builds RKS files, runs ButtonRun, edits RKS
packages, or performs production writes. It only packages rows already approved
by the RK10 runtime operator-intake validator.
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
DEFAULT_VALIDATION_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "rks_runtime_operator_intake_validation_20260620"
    / "rks_runtime_operator_intake_validation.json"
)
DEFAULT_INTAKE_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "rk10_editor_runtime_bundle"
    / "final_evidence_intake.csv"
)
DEFAULT_FINAL_EVIDENCE_ROOT = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "rk10_editor_runtime_bundle"
    / "final_evidence"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "rk10_runtime_bundle_evidence_collect_20260620"
SYNC_NOTE = "rk10_runtime_bundle_evidence_auto_collected_20260620"
AUTO_APPEND_NOTE = "rk10_runtime_bundle_intake_row_auto_appended_from_validator_20260621"
VALIDATOR_IDENTITY_SYNC_NOTE = "reviewer_checked_at_synced_from_rks_runtime_validator_20260621"
RK10_BUNDLE = "RK10_EDITOR_RUNTIME_BUNDLE"
DEFAULT_REQUIRED_FINAL_EVIDENCE = "metadata guard、open/build結果、safe-stopログ、latest clean log、別名保存パス"
DEFAULT_HARD_STOPS = "ButtonRun、本番書込、実メール、実印刷、最終申請、ZIP直接RKS改変"
DEFAULT_REQUIRED_UPDATE_FIELDS = "final_evidence_path, operator_result, reviewer, reviewed_at"
INTAKE_FIELDNAMES = [
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
TEMPLATE_FIELDNAMES = [
    "bundle",
    "scenario",
    "template_only_not_final_evidence",
    "save_under_folder",
    "evidence_kind",
    "example_filename",
    "purpose",
    "notes",
]
TEMPLATE_FILENAME = "operator_evidence_filename_template.csv"
TEMPLATE_MARKDOWN_FILENAME = "operator_evidence_filename_template.md"


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
class ScenarioCollection:
    scenario: str
    status: str
    approved_by_validator: bool
    intake_row_exists: bool
    updated_intake: bool
    latest_log_path: str
    latest_log_path_exists: bool
    latest_log_sha256: str
    final_evidence_dir: str
    final_evidence_files: list[str]
    issue_codes: str
    blockers: str


@dataclass(frozen=True)
class CollectionResult:
    generated_at: str
    status: str
    validation_json: str
    validation_json_exists: bool
    intake_csv: str
    approved_validator_count: int
    appended_intake_row_count: int
    template_appended_row_count: int
    collected_count: int
    skipped_count: int
    scenarios: list[ScenarioCollection]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def complete_fieldnames(fieldnames: list[str]) -> list[str]:
    completed = list(fieldnames)
    for fieldname in INTAKE_FIELDNAMES:
        if fieldname not in completed:
            completed.append(fieldname)
    return completed


def file_sha256(path_text: str) -> str:
    path = Path(path_text)
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evidence_token() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def scenario_slug(scenario: str) -> str:
    return scenario.replace("/", "_")


def intake_scenarios(rows: list[dict[str, str]]) -> set[str]:
    return {
        row.get("scenario", "")
        for row in rows
        if row.get("bundle") == RK10_BUNDLE and row.get("scenario")
    }


def append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing}; {note}"


def append_missing_intake_rows(
    intake_csv: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    approved_rows: list[dict[str, Any]],
    final_evidence_root: Path,
) -> tuple[list[str], list[dict[str, str]], int]:
    completed_fieldnames = complete_fieldnames(fieldnames)
    existing_scenarios = intake_scenarios(rows)
    new_rows = [{fieldname: row.get(fieldname, "") for fieldname in completed_fieldnames} for row in rows]
    appended_count = 0
    for row in approved_rows:
        scenario = str(row.get("scenario", "")).strip()
        if not scenario or scenario in existing_scenarios:
            continue
        final_evidence_dir = final_evidence_root / f"scenario_{scenario_slug(scenario)}"
        new_rows.append(
            {
                fieldname: ""
                for fieldname in completed_fieldnames
            }
            | {
                "bundle": RK10_BUNDLE,
                "scenario": scenario,
                "required_final_evidence": DEFAULT_REQUIRED_FINAL_EVIDENCE,
                "hard_stops": DEFAULT_HARD_STOPS,
                "current_reference_evidence": str(row.get("latest_log_path", "")).strip(),
                "suggested_final_evidence_folder": str(final_evidence_dir),
                "required_update_fields": DEFAULT_REQUIRED_UPDATE_FIELDS,
                "notes": AUTO_APPEND_NOTE,
            }
        )
        existing_scenarios.add(scenario)
        appended_count += 1
    if appended_count or completed_fieldnames != fieldnames:
        write_csv_rows(intake_csv, completed_fieldnames, new_rows)
    return completed_fieldnames, new_rows, appended_count


def template_rows_for_scenario(final_evidence_root: Path, scenario: str) -> list[dict[str, str]]:
    slug = scenario_slug(scenario)
    scenario_folder = final_evidence_root / f"scenario_{slug}"
    templates = [
        ("log", f"scenario_{slug}_rk10_metadata_guard_YYYYMMDD_HHMMSS.txt", "RKS metadata guard output"),
        ("screenshot", f"scenario_{slug}_rk10_editor_open_build_YYYYMMDD_HHMMSS.png", "RK10 editor open/build proof"),
        ("log", f"scenario_{slug}_safe_stop_latest_clean_log_YYYYMMDD_HHMMSS.txt", "Safe-stop runtime latest clean log"),
        ("log", f"scenario_{slug}_rks_status_gate_YYYYMMDD_HHMMSS.txt", "RKS status gate output"),
    ]
    return [
        {
            "bundle": RK10_BUNDLE,
            "scenario": scenario,
            "template_only_not_final_evidence": "YES",
            "save_under_folder": str(scenario_folder),
            "evidence_kind": evidence_kind,
            "example_filename": example_filename,
            "purpose": purpose,
            "notes": "Create the actual file only after the allowed safe run/review. Do not treat this template row as evidence.",
        }
        for evidence_kind, example_filename, purpose in templates
    ]


def template_row_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("scenario", ""), row.get("example_filename", "")


def write_template_markdown(template_path: Path, rows: list[dict[str, str]]) -> None:
    markdown_path = template_path.with_name(TEMPLATE_MARKDOWN_FILENAME)
    lines = [
        f"# {RK10_BUNDLE} 証跡ファイル名テンプレート",
        "",
        "- scope: `TEMPLATE_ONLY_NOT_FINAL_EVIDENCE`",
        "- このファイルは命名ガイドであり、完了証跡ではない。",
        "- 実行後に作成した実ファイルだけを `final_evidence` 配下へ置く。",
        "",
        "| Scenario | Kind | Save Under Folder | Example Filename | Purpose |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.get("scenario", ""),
                    row.get("evidence_kind", ""),
                    f"`{row.get('save_under_folder', '')}`",
                    f"`{row.get('example_filename', '')}`",
                    row.get("purpose", ""),
                ]
            )
            + " |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_numbered_copy(markdown_path)


def ensure_filename_templates_for_scenarios(
    final_evidence_root: Path,
    scenarios: set[str],
) -> int:
    template_path = final_evidence_root.parent / TEMPLATE_FILENAME
    fieldnames, rows = read_csv_rows(template_path)
    fieldnames = fieldnames or TEMPLATE_FIELDNAMES
    completed_fieldnames = [*fieldnames, *[field for field in TEMPLATE_FIELDNAMES if field not in fieldnames]]
    existing_keys = {template_row_key(row) for row in rows}
    next_rows = [{field: row.get(field, "") for field in completed_fieldnames} for row in rows]
    appended_count = 0
    for scenario in sorted(scenario for scenario in scenarios if scenario):
        for row in template_rows_for_scenario(final_evidence_root, scenario):
            key = template_row_key(row)
            if key in existing_keys:
                continue
            next_rows.append({field: row.get(field, "") for field in completed_fieldnames})
            existing_keys.add(key)
            appended_count += 1
    if appended_count or completed_fieldnames != fieldnames:
        write_csv_rows(template_path, completed_fieldnames, next_rows)
        write_template_markdown(template_path, next_rows)
    return appended_count


def write_evidence_files(row: dict[str, Any], final_evidence_dir: Path, token: str) -> list[Path]:
    final_evidence_dir.mkdir(parents=True, exist_ok=True)
    slug = scenario_slug(str(row["scenario"]))
    status_gate_path = final_evidence_dir / f"scenario_{slug}_rks_status_gate_{token}.txt"
    latest_log_path = final_evidence_dir / f"scenario_{slug}_safe_stop_latest_clean_log_{token}.txt"
    lines = [
        f"Scenario {row['scenario']} RK10 runtime evidence collection",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        "scope=approved validator evidence packaging only; no RK10 open/build/runtime execution",
        f"rks_path={row.get('rks_path', '')}",
        f"operator_decision={row.get('operator_decision', '')}",
        f"rk10_editor_open={row.get('rk10_editor_open', '')}",
        f"rk10_build={row.get('rk10_build', '')}",
        f"runtime_or_safe_stop={row.get('runtime_or_safe_stop', '')}",
        f"latest_log_clean={row.get('latest_log_clean', '')}",
        f"latest_log_path={row.get('latest_log_path', '')}",
        f"latest_log_sha256={file_sha256(str(row.get('latest_log_path', '')))}",
        f"operator_name={row.get('operator_name', '')}",
        f"checked_at={row.get('checked_at', '')}",
        f"approved={row.get('approved')}",
        f"issue_codes={row.get('issue_codes', '')}",
    ]
    status_gate_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    latest_log_path.write_text(
        "\n".join(
            [
                f"latest_log_path={row.get('latest_log_path', '')}",
                f"latest_log_clean={row.get('latest_log_clean', '')}",
                f"latest_log_path_exists={row.get('latest_log_path_exists')}",
                f"latest_log_has_hard_errors={row.get('latest_log_has_hard_errors')}",
                f"latest_log_sha256={file_sha256(str(row.get('latest_log_path', '')))}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return [status_gate_path, latest_log_path]


def validator_identity(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("operator_name", "")).strip(), str(row.get("checked_at", "")).strip()


def update_intake_csv(
    intake_csv: Path,
    validator_row: dict[str, Any],
    final_evidence_dir: Path,
) -> bool:
    fieldnames, rows = read_csv_rows(intake_csv)
    if not rows:
        return False
    scenario = str(validator_row.get("scenario", "")).strip()
    validator_reviewer, validator_reviewed_at = validator_identity(validator_row)
    completed_fieldnames = complete_fieldnames(fieldnames)
    updated = False
    new_rows = []
    for row in rows:
        if row.get("bundle") == "RK10_EDITOR_RUNTIME_BUNDLE" and row.get("scenario") == scenario:
            notes = append_note(row.get("notes", ""), SYNC_NOTE)
            reviewer = row.get("reviewer", "") or validator_reviewer
            reviewed_at = row.get("reviewed_at", "") or validator_reviewed_at
            if (not row.get("reviewer", "") and validator_reviewer) or (
                not row.get("reviewed_at", "") and validator_reviewed_at
            ):
                notes = append_note(notes, VALIDATOR_IDENTITY_SYNC_NOTE)
            row = {
                **row,
                "final_evidence_path": str(final_evidence_dir),
                "operator_result": row.get("operator_result") or "OK",
                "reviewer": reviewer,
                "reviewed_at": reviewed_at,
                "notes": notes,
            }
            updated = True
        new_rows.append({fieldname: row.get(fieldname, "") for fieldname in completed_fieldnames})
    if updated:
        write_csv_rows(intake_csv, completed_fieldnames, new_rows)
    return updated


def build_scenario_collection(
    row: dict[str, Any],
    intake_csv: Path,
    intake_scenario_set: set[str],
    final_evidence_root: Path,
) -> ScenarioCollection:
    scenario = str(row.get("scenario", ""))
    approved = row.get("approved") is True
    latest_log_path = str(row.get("latest_log_path", ""))
    latest_log_exists = Path(latest_log_path).exists() if latest_log_path else False
    final_evidence_dir = final_evidence_root / f"scenario_{scenario_slug(scenario)}"
    blockers: list[str] = []
    if not approved:
        blockers.append("NOT_APPROVED_BY_RKS_RUNTIME_VALIDATOR")
    if scenario not in intake_scenario_set:
        blockers.append("SCENARIO_NOT_IN_RK10_BUNDLE_FINAL_INTAKE")
    if not latest_log_exists:
        blockers.append("LATEST_LOG_PATH_MISSING_OR_NOT_FOUND")
    operator_name, checked_at = validator_identity(row)
    if not operator_name:
        blockers.append("VALIDATOR_OPERATOR_NAME_MISSING")
    if not checked_at:
        blockers.append("VALIDATOR_CHECKED_AT_MISSING")
    evidence_files: list[Path] = []
    updated = False
    if not blockers:
        evidence_files = write_evidence_files(row, final_evidence_dir, evidence_token())
        updated = update_intake_csv(intake_csv, row, final_evidence_dir)
        if not updated:
            blockers.append("RK10_BUNDLE_INTAKE_ROW_NOT_FOUND")
    status = "READY_FOR_REVIEWER_TIMESTAMP" if updated and not blockers else "SKIPPED_OR_WAITING"
    return ScenarioCollection(
        scenario=scenario,
        status=status,
        approved_by_validator=approved,
        intake_row_exists=scenario in intake_scenario_set,
        updated_intake=updated,
        latest_log_path=latest_log_path,
        latest_log_path_exists=latest_log_exists,
        latest_log_sha256=file_sha256(latest_log_path),
        final_evidence_dir=str(final_evidence_dir),
        final_evidence_files=[str(path) for path in evidence_files],
        issue_codes=str(row.get("issue_codes", "")),
        blockers=", ".join(blockers),
    )


def build_result(
    validation_json: Path,
    intake_csv: Path,
    final_evidence_root: Path,
) -> CollectionResult:
    validation = read_json(validation_json)
    rows = validation.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    _fieldnames, intake_rows = read_csv_rows(intake_csv)
    approved_rows = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("requires_rk10_evidence") is True
        and row.get("approved") is True
    ]
    fieldnames, intake_rows, appended_count = append_missing_intake_rows(
        intake_csv,
        _fieldnames,
        intake_rows,
        approved_rows,
        final_evidence_root,
    )
    intake_set = intake_scenarios(intake_rows)
    template_appended_count = ensure_filename_templates_for_scenarios(
        final_evidence_root,
        intake_set,
    )
    scenario_results = [
        build_scenario_collection(row, intake_csv, intake_set, final_evidence_root)
        for row in approved_rows
    ]
    collected_count = sum(1 for row in scenario_results if row.updated_intake)
    skipped_count = len(scenario_results) - collected_count
    status = "READY_FOR_REVIEWER_TIMESTAMP" if collected_count else "WAITING_FOR_RK10_RUNTIME_EVIDENCE"
    if skipped_count:
        status = "PARTIAL_READY_FOR_REVIEWER_TIMESTAMP" if collected_count else status
    return CollectionResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status=status,
        validation_json=str(validation_json),
        validation_json_exists=validation_json.exists(),
        intake_csv=str(intake_csv),
        approved_validator_count=len(approved_rows),
        appended_intake_row_count=appended_count,
        template_appended_row_count=template_appended_count,
        collected_count=collected_count,
        skipped_count=skipped_count,
        scenarios=scenario_results,
    )


def build_markdown(result: CollectionResult) -> str:
    lines = [
        "# RK10 runtime bundle evidence collection 2026-06-20",
        "",
        f"- generated_at: `{result.generated_at}`",
        f"- status: `{result.status}`",
        f"- approved_validator_count: `{result.approved_validator_count}`",
        f"- appended_intake_row_count: `{result.appended_intake_row_count}`",
        f"- template_appended_row_count: `{result.template_appended_row_count}`",
        f"- collected_count: `{result.collected_count}`",
        f"- skipped_count: `{result.skipped_count}`",
        f"- validation_json: `{result.validation_json}`",
        f"- validation_json_exists: `{result.validation_json_exists}`",
        f"- intake_csv: `{result.intake_csv}`",
        "",
        "## Safety",
        "",
        "- This collector does not open RK10, build RKS, run RKS, press ButtonRun, edit RKS packages, send mail, print, submit, pay, or write production files.",
        "- It only packages rows already approved by `rks_runtime_operator_intake_validation`.",
        "- It does not convert `OK_CANDIDATE` static status into runtime approval.",
        "- For approved validator rows only, reviewer and reviewed_at are copied from validator operator_name and checked_at.",
        "- Non-approved or missing runtime scenarios still require operator evidence before bundle sync.",
        "",
        "## Scenario Matrix",
        "",
        "| Scenario | Status | Approved | Intake Row | Updated | Latest Log Exists | Blockers |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in result.scenarios:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.scenario,
                    row.status,
                    "YES" if row.approved_by_validator else "NO",
                    "YES" if row.intake_row_exists else "NO",
                    "YES" if row.updated_intake else "NO",
                    "YES" if row.latest_log_path_exists else "NO",
                    f"`{row.blockers}`" if row.blockers else "-",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Final Evidence Files", ""])
    files = [path for row in result.scenarios for path in row.final_evidence_files]
    if files:
        lines.extend(f"- `{path}`" for path in files)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect approved RK10 runtime bundle evidence.")
    parser.add_argument("--validation-json", type=Path, default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--intake-csv", type=Path, default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--final-evidence-root", type=Path, default=DEFAULT_FINAL_EVIDENCE_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    result = build_result(args.validation_json, args.intake_csv, args.final_evidence_root)
    json_path = args.out_dir / "rk10_runtime_bundle_evidence_collect.json"
    md_path = args.out_dir / "rk10_runtime_bundle_evidence_collect.md"
    json_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(result), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
