"""Validate the six bundle evidence pack folders.

This checker verifies that prepared evidence containers exist and that the
operator sheet points to real final evidence only when all required operator
fields are filled. It never treats prepared folders as production completion.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
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
DEFAULT_INTAKE_SYNC_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_intake_sync_20260620"
    / "bundle_evidence_intake_sync.json"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "bundle_evidence_pack_validation_20260620"
OPERATOR_FIELDS = ("operator_result", "evidence_path", "reviewer", "reviewed_at")


@dataclass(frozen=True)
class ScenarioReferenceCheck:
    scenario: str
    source: str
    source_exists: bool
    source_exists_now: bool
    source_size_bytes: int
    source_sha256: str
    current_reference_evidence: str
    current_reference_exists: bool
    current_reference_exists_now: bool
    current_reference_size_bytes: int
    current_reference_sha256: str


@dataclass(frozen=True)
class BundlePackCheck:
    bundle: str
    scenarios: str
    scenario_count: int
    pack_dir: str
    pack_dir_exists: bool
    manifest_path: str
    manifest_exists: bool
    checklist_path: str
    checklist_exists: bool
    numbered_checklist_exists: bool
    intake_path: str
    intake_exists: bool
    filename_template_path: str
    filename_template_exists: bool
    filename_template_markdown_path: str
    filename_template_markdown_exists: bool
    numbered_filename_template_markdown_exists: bool
    final_evidence_dir: str
    final_evidence_dir_exists: bool
    manifest_bundle_matches: bool
    checklist_mentions_boundary: bool
    final_evidence_path: str
    final_evidence_path_source: str
    final_evidence_path_exists: bool
    final_evidence_path_allowed: bool
    final_evidence_path_issue: str
    final_evidence_has_content: bool
    final_evidence_item_count: int
    final_evidence_filenames_match: bool
    final_evidence_filename_match_count: int
    final_evidence_filename_mismatch_count: int
    final_evidence_filename_issue: str
    final_evidence_filename_mismatches: str
    operator_fields_complete: bool
    operator_field_issue: str
    final_evidence_ready: bool
    scenario_references: list[ScenarioReferenceCheck]

    @property
    def prepared_pack_ready(self) -> bool:
        return (
            self.pack_dir_exists
            and self.manifest_exists
            and self.checklist_exists
            and self.numbered_checklist_exists
            and self.intake_exists
            and self.filename_template_exists
            and self.filename_template_markdown_exists
            and self.numbered_filename_template_markdown_exists
            and self.final_evidence_dir_exists
            and self.manifest_bundle_matches
            and self.checklist_mentions_boundary
        )


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"bundle evidence pack json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_operator_sheet(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            str(row.get("bundle", "")).strip(): {
                str(key): str(value).strip()
                for key, value in row.items()
                if key is not None
            }
            for row in csv.DictReader(handle)
            if str(row.get("bundle", "")).strip()
        }


def read_intake_sync(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    if not isinstance(results, list):
        return {}
    return {
        str(row.get("bundle", "")).strip(): row
        for row in results
        if isinstance(row, dict) and str(row.get("bundle", "")).strip()
    }


def path_exists(value: str) -> bool:
    return bool(value.strip()) and Path(value).exists()


def evidence_item_count(value: str) -> int:
    return len(non_empty_evidence_files(value))


def non_empty_evidence_files(value: str) -> list[Path]:
    if not value.strip():
        return []
    path = Path(value)
    if path.is_file():
        return [path] if path.stat().st_size > 0 else []
    if not path.is_dir():
        return []
    return sorted(
        item
        for item in path.rglob("*")
        if item.is_file() and item.stat().st_size > 0
    )


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def validate_final_evidence_path(value: str, pack_dir: str, final_evidence_dir: str) -> tuple[bool, str]:
    if not value.strip():
        return False, "FINAL_EVIDENCE_PATH_BLANK"
    evidence_path = Path(value)
    if not evidence_path.exists():
        return False, "FINAL_EVIDENCE_PATH_NOT_FOUND"
    pack_path = Path(pack_dir)
    final_path = Path(final_evidence_dir)
    if evidence_path.resolve() == pack_path.resolve():
        return False, "PREPARED_PACK_ROOT_IS_NOT_FINAL_EVIDENCE"
    if is_relative_to(evidence_path, pack_path) and not is_relative_to(evidence_path, final_path):
        return False, "PACK_PREPARATION_FILE_IS_NOT_FINAL_EVIDENCE"
    return True, ""


def read_template_filenames(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            str(row.get("example_filename", "")).strip()
            for row in csv.DictReader(handle)
            if str(row.get("example_filename", "")).strip()
        ]


def template_filename_pattern(template: str) -> re.Pattern[str]:
    escaped = re.escape(template)
    escaped = escaped.replace("YYYYMMDD", r"\d{8}")
    escaped = escaped.replace("HHMMSS", r"\d{6}")
    return re.compile(rf"^{escaped}$")


def validate_final_evidence_filenames(
    final_evidence_path: str,
    template_path: str,
) -> tuple[bool, int, int, str, str]:
    files = non_empty_evidence_files(final_evidence_path)
    if not files:
        return False, 0, 0, "NO_FINAL_EVIDENCE_FILES", ""
    template_names = read_template_filenames(Path(template_path))
    if not template_names:
        return False, 0, len(files), "FILENAME_TEMPLATE_MISSING", ", ".join(file.name for file in files)
    patterns = [template_filename_pattern(name) for name in template_names]
    mismatches = [
        file.name
        for file in files
        if not any(pattern.fullmatch(file.name) for pattern in patterns)
    ]
    match_count = len(files) - len(mismatches)
    issue = "FILENAME_TEMPLATE_MISMATCH" if mismatches else ""
    return len(mismatches) == 0, match_count, len(mismatches), issue, ", ".join(mismatches)


def file_size_bytes(value: str) -> int:
    if not value.strip():
        return 0
    path = Path(value)
    if not path.is_file():
        return 0
    return path.stat().st_size


def file_sha256(value: str) -> str:
    if not value.strip():
        return ""
    path = Path(value)
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_bundle_matches(path: Path, bundle: str) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return str(payload.get("bundle", "")) == bundle


def checklist_mentions_boundary(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return "prepared evidence container" in text and "Do not use this pack alone as approval" in text


def operator_fields_complete(row: dict[str, str]) -> bool:
    return all(row.get(field, "").strip() for field in OPERATOR_FIELDS)


def operator_field_issue(row: dict[str, str], ignored_fields: set[str] | None = None) -> str:
    ignored = ignored_fields or set()
    missing = [
        field.upper() + "_BLANK"
        for field in OPERATOR_FIELDS
        if field not in ignored
        if not row.get(field, "").strip()
    ]
    return ", ".join(missing)


def sync_result_has_all_row_evidence(sync_result: dict[str, Any]) -> bool:
    rows = sync_result.get("rows", [])
    if not isinstance(rows, list) or not rows:
        return False
    return all(
        isinstance(row, dict)
        and row.get("final_evidence_exists") is True
        and row.get("final_evidence_has_content") is True
        and row.get("final_evidence_under_final_dir") is True
        for row in rows
    )


def sync_result_final_evidence_path(sync_result: dict[str, Any]) -> str:
    rows = sync_result.get("rows", [])
    if not isinstance(rows, list):
        return ""
    if len(rows) == 1 and isinstance(rows[0], dict):
        return str(rows[0].get("final_evidence_path", "")).strip()
    return str(sync_result.get("final_evidence_dir", "")).strip()


def resolve_final_evidence_path(
    operator_row: dict[str, str],
    sync_result: dict[str, Any],
) -> tuple[str, str]:
    operator_path = operator_row.get("evidence_path", "").strip()
    if operator_path:
        return operator_path, "operator_sheet"
    if sync_result_has_all_row_evidence(sync_result):
        return sync_result_final_evidence_path(sync_result), "final_evidence_intake_sync"
    return "", ""


def build_scenario_reference_checks(pack: dict[str, Any]) -> list[ScenarioReferenceCheck]:
    rows = []
    for row in pack.get("scenario_evidence", []):
        source = str(row.get("source", ""))
        current_reference = str(row.get("current_reference_evidence", ""))
        rows.append(
            ScenarioReferenceCheck(
                scenario=str(row.get("scenario", "")),
                source=source,
                source_exists=bool(row.get("source_exists")),
                source_exists_now=path_exists(source),
                source_size_bytes=file_size_bytes(source),
                source_sha256=file_sha256(source),
                current_reference_evidence=current_reference,
                current_reference_exists=bool(row.get("current_reference_exists")),
                current_reference_exists_now=path_exists(current_reference),
                current_reference_size_bytes=file_size_bytes(current_reference),
                current_reference_sha256=file_sha256(current_reference),
            )
        )
    return rows


def build_bundle_check(
    pack: dict[str, Any],
    operator_rows: dict[str, dict[str, str]],
    intake_sync_rows: dict[str, dict[str, Any]] | None = None,
) -> BundlePackCheck:
    bundle = str(pack.get("bundle", ""))
    pack_dir = str(pack.get("pack_dir", ""))
    manifest_path = str(pack.get("manifest_path", ""))
    checklist_path = str(pack.get("checklist_path", ""))
    intake_path = str(pack.get("intake_path", Path(pack_dir) / "final_evidence_intake.csv"))
    filename_template_path = str(
        pack.get("filename_template_path", Path(pack_dir) / "operator_evidence_filename_template.csv")
    )
    filename_template_markdown_path = str(
        pack.get(
            "filename_template_markdown_path",
            Path(pack_dir) / "operator_evidence_filename_template.md",
        )
    )
    final_evidence_dir = str(pack.get("final_evidence_dir", Path(pack_dir) / "final_evidence"))
    operator_row = operator_rows.get(bundle, {})
    intake_sync_row = (intake_sync_rows or {}).get(bundle, {})
    final_evidence_path, final_evidence_path_source = resolve_final_evidence_path(
        operator_row,
        intake_sync_row,
    )
    complete_operator_fields = operator_fields_complete(operator_row)
    ignored_operator_fields = (
        {"evidence_path"}
        if final_evidence_path_source == "final_evidence_intake_sync"
        else set()
    )
    field_issue = operator_field_issue(operator_row, ignored_operator_fields)
    final_evidence_exists = path_exists(final_evidence_path)
    final_evidence_items = evidence_item_count(final_evidence_path)
    final_evidence_allowed, final_evidence_issue = validate_final_evidence_path(
        final_evidence_path,
        pack_dir,
        final_evidence_dir,
    )
    (
        final_filenames_match,
        final_filename_match_count,
        final_filename_mismatch_count,
        final_filename_issue,
        final_filename_mismatches,
    ) = validate_final_evidence_filenames(final_evidence_path, filename_template_path)
    return BundlePackCheck(
        bundle=bundle,
        scenarios=str(pack.get("scenarios", "")),
        scenario_count=int(pack.get("scenario_count", 0)),
        pack_dir=pack_dir,
        pack_dir_exists=path_exists(pack_dir),
        manifest_path=manifest_path,
        manifest_exists=path_exists(manifest_path),
        checklist_path=checklist_path,
        checklist_exists=path_exists(checklist_path),
        numbered_checklist_exists=path_exists(f"{checklist_path}.numbered"),
        intake_path=intake_path,
        intake_exists=path_exists(intake_path),
        filename_template_path=filename_template_path,
        filename_template_exists=path_exists(filename_template_path),
        filename_template_markdown_path=filename_template_markdown_path,
        filename_template_markdown_exists=path_exists(filename_template_markdown_path),
        numbered_filename_template_markdown_exists=path_exists(f"{filename_template_markdown_path}.numbered"),
        final_evidence_dir=final_evidence_dir,
        final_evidence_dir_exists=path_exists(final_evidence_dir),
        manifest_bundle_matches=manifest_bundle_matches(Path(manifest_path), bundle),
        checklist_mentions_boundary=checklist_mentions_boundary(Path(checklist_path)),
        final_evidence_path=final_evidence_path,
        final_evidence_path_source=final_evidence_path_source,
        final_evidence_path_exists=final_evidence_exists,
        final_evidence_path_allowed=final_evidence_allowed,
        final_evidence_path_issue=final_evidence_issue,
        final_evidence_has_content=final_evidence_items > 0,
        final_evidence_item_count=final_evidence_items,
        final_evidence_filenames_match=final_filenames_match,
        final_evidence_filename_match_count=final_filename_match_count,
        final_evidence_filename_mismatch_count=final_filename_mismatch_count,
        final_evidence_filename_issue=final_filename_issue,
        final_evidence_filename_mismatches=final_filename_mismatches,
        operator_fields_complete=complete_operator_fields,
        operator_field_issue=field_issue,
        final_evidence_ready=complete_operator_fields
        and final_evidence_exists
        and final_evidence_allowed
        and final_evidence_items > 0
        and final_filenames_match,
        scenario_references=build_scenario_reference_checks(pack),
    )


def build_payload(
    pack_json: Path,
    operator_sheet: Path,
    intake_sync_json: Path | None = None,
) -> dict[str, Any]:
    pack_payload = read_json(pack_json)
    operator_rows = read_operator_sheet(operator_sheet)
    intake_sync_rows = read_intake_sync(intake_sync_json)
    checks = [
        build_bundle_check(pack, operator_rows, intake_sync_rows)
        for pack in pack_payload.get("packs", [])
    ]
    missing_prepared_pack_count = sum(1 for check in checks if not check.prepared_pack_ready)
    final_evidence_ready_count = sum(1 for check in checks if check.final_evidence_ready)
    source_reference_count = sum(len(check.scenario_references) for check in checks)
    source_reference_exists_now_count = sum(
        1
        for check in checks
        for row in check.scenario_references
        if row.source_exists_now and row.current_reference_exists_now
    )
    source_reference_hashed_now_count = sum(
        1
        for check in checks
        for row in check.scenario_references
        if row.source_sha256 and row.current_reference_sha256
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "prepared_pack_validation_passed": missing_prepared_pack_count == 0,
        "final_evidence_complete": final_evidence_ready_count == len(checks) and bool(checks),
        "safety": "read-only validation of prepared evidence folders and operator evidence paths",
        "pack_json": str(pack_json),
        "operator_sheet": str(operator_sheet),
        "intake_sync_json": str(intake_sync_json) if intake_sync_json else "",
        "bundle_count": len(checks),
        "prepared_pack_ready_count": len(checks) - missing_prepared_pack_count,
        "missing_prepared_pack_count": missing_prepared_pack_count,
        "final_evidence_ready_count": final_evidence_ready_count,
        "source_reference_count": source_reference_count,
        "source_reference_exists_now_count": source_reference_exists_now_count,
        "source_reference_hashed_now_count": source_reference_hashed_now_count,
        "checks": [
            {
                **asdict(check),
                "prepared_pack_ready": check.prepared_pack_ready,
                "scenario_references": [
                    asdict(row)
                    for row in check.scenario_references
                ],
            }
            for check in checks
        ],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    checks = payload["checks"]
    assert isinstance(checks, list)
    lines = [
        "# 6束証跡パック検証 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- prepared_pack_validation_passed: `{payload['prepared_pack_validation_passed']}`",
        f"- final_evidence_complete: `{payload['final_evidence_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- bundle_count: `{payload['bundle_count']}`",
        f"- prepared_pack_ready_count: `{payload['prepared_pack_ready_count']}`",
        f"- missing_prepared_pack_count: `{payload['missing_prepared_pack_count']}`",
        f"- final_evidence_ready_count: `{payload['final_evidence_ready_count']}`",
        f"- source_reference_exists_now_count: `{payload['source_reference_exists_now_count']}/{payload['source_reference_count']}`",
        f"- source_reference_hashed_now_count: `{payload['source_reference_hashed_now_count']}/{payload['source_reference_count']}`",
        "",
        "## Boundary",
        "",
        "- This validates prepared folders and operator-provided evidence paths only.",
        "- It does not approve production completion, payment execution, mail sending, printing, RK10 runtime, or Azure OCR.",
        "",
        "## Bundle Checks",
        "",
        "| Bundle | Prepared Pack Ready | Final Evidence Ready | Final Evidence Items | Final Evidence Path | Evidence Path Issue | Missing Prepared Items |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for check in checks:
        missing_items = []
        for field in (
            "pack_dir_exists",
            "manifest_exists",
            "checklist_exists",
            "numbered_checklist_exists",
            "intake_exists",
            "filename_template_exists",
            "filename_template_markdown_exists",
            "numbered_filename_template_markdown_exists",
            "final_evidence_dir_exists",
            "manifest_bundle_matches",
            "checklist_mentions_boundary",
        ):
            if not check[field]:
                missing_items.append(field)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(check["bundle"]),
                    "YES" if check["prepared_pack_ready"] else "NO",
                    "YES" if check["final_evidence_ready"] else "NO",
                    str(check["final_evidence_item_count"]),
                    f"`{check['final_evidence_path']}`" if check["final_evidence_path"] else "-",
                    "; ".join(
                        item
                        for item in [
                            str(check["final_evidence_path_issue"]),
                            str(check["final_evidence_filename_issue"]),
                            str(check["final_evidence_filename_mismatches"]),
                            str(check["operator_field_issue"]),
                        ]
                        if item
                    )
                    or "-",
                    ", ".join(missing_items) if missing_items else "-",
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
    json_path = out_dir / "bundle_evidence_pack_validation.json"
    md_path = out_dir / "bundle_evidence_pack_validation.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate six bundle evidence packs.")
    parser.add_argument("--pack-json", type=Path, default=DEFAULT_PACK_JSON)
    parser.add_argument("--operator-sheet", type=Path, default=DEFAULT_OPERATOR_SHEET)
    parser.add_argument("--intake-sync-json", type=Path, default=DEFAULT_INTAKE_SYNC_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.pack_json, args.operator_sheet, args.intake_sync_json)
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["prepared_pack_validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
