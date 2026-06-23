"""Classify final-evidence intake rows by safe autonomous boundary.

This report is intentionally non-approving. It reads the unified final evidence
intake CSV and tells operators which rows are already filled, which rows Codex
can still support with safe evidence collection, and which rows need human or
external approval before production readiness can be claimed.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_UNIFIED_CSV = (
    REPORTS
    / "unified_final_evidence_intake_20260621"
    / "unified_final_evidence_input.csv"
)
DEFAULT_OUT_DIR = REPORTS / "final_input_autonomous_boundary_20260622"
DEFAULT_RKS_MATRIX_JSON = (
    REPORTS / "rks_gate_matrix_20260620" / "rks_gate_matrix.json"
)
SCOPE_EXCLUSIONS_JSON = (
    REPORTS / "objective_scope_exclusions_20260623" / "objective_scope_exclusions.json"
)

REQUIRED_FINAL_FIELDS = (
    "final_evidence_path",
    "operator_result",
    "reviewer",
    "reviewed_at",
)
HUMAN_APPROVAL_BUNDLES = {
    "BUSINESS_DATA_APPROVAL_BUNDLE",
    "BUSINESS_REVIEW_BUNDLE",
    "PAYMENT_APPROVAL_BUNDLE",
    "PAID_AZURE_OCR_BUNDLE",
}
RK10_BUNDLE = "RK10_EDITOR_RUNTIME_BUNDLE"
RKS_HUMAN_DECISION_STATUSES = {
    "N_A_NO_PRIMARY_RKS",
    "RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION",
}
RKS_FINAL_SYNC_STATUSES = {
    "RKS_RUNTIME_EVIDENCE_CONFIRMED",
}


@dataclass(frozen=True)
class BoundaryRow:
    bundle: str
    scenario: str
    boundary_class: str
    current_status: str
    final_evidence_path_exists: str
    suggested_folder_exists: str
    missing_fields: str
    codex_can_continue_with: str
    human_or_external_input_needed: str
    forbidden_scope: str
    source_intake_path: str


def raise_csv_field_limit() -> None:
    csv.field_size_limit(sys.maxsize)


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    raise_csv_field_limit()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def exists_text(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    return "YES" if Path(text).exists() else "NO"


def missing_required_fields(row: dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_FINAL_FIELDS if not row.get(field, "").strip()]


def joined_forbidden_scope(row: dict[str, str]) -> str:
    values = [
        row.get("hard_stops", "").strip(),
        row.get("still_forbidden", "").strip(),
    ]
    return " / ".join(value for value in values if value)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def scenario_tokens(value: str) -> set[str]:
    tokens = {value.strip()} if value.strip() else set()
    for chunk in value.replace("、", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        tokens.add(chunk)
        if "/" in chunk and all(part.strip().isdigit() for part in chunk.split("/")):
            tokens.update(part.strip() for part in chunk.split("/") if part.strip())
    return tokens


def load_scope_exclusions(path: Path = SCOPE_EXCLUSIONS_JSON) -> list[dict[str, str]]:
    payload = read_json(path)
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
        if not scenario:
            continue
        rows.append(
            {
                "scenario": scenario,
                "reason": str(row.get("reason", "")).strip(),
                "requested_by": str(row.get("requested_by", "")).strip(),
                "requested_at": str(row.get("requested_at", "")).strip(),
                "evidence": str(row.get("evidence", "")).strip(),
            }
        )
    return rows


def excluded_scenario_tokens(exclusions: list[dict[str, str]]) -> set[str]:
    tokens: set[str] = set()
    for row in exclusions:
        tokens.update(scenario_tokens(row.get("scenario", "")))
    return tokens


def input_row_is_excluded(row: dict[str, str], excluded_tokens: set[str]) -> bool:
    if not excluded_tokens:
        return False
    return bool(scenario_tokens(str(row.get("scenario", ""))) & excluded_tokens)


def build_rks_status_by_scenario(rks_matrix_json: Path | None) -> dict[str, str]:
    if rks_matrix_json is None:
        return {}
    payload = read_json(rks_matrix_json)
    statuses: dict[str, str] = {}
    for row in payload.get("rows", []):
        if not isinstance(row, dict):
            continue
        scenario = str(row.get("scenario", "")).strip()
        status = str(row.get("runtime_intake_status", "")).strip()
        if scenario and status:
            statuses[scenario] = status
    return statuses


def classify_row(
    row: dict[str, str],
    rks_status_by_scenario: dict[str, str] | None = None,
) -> tuple[str, str, str]:
    missing_fields = missing_required_fields(row)
    if not missing_fields:
        return (
            "FILLED_READY_FOR_VALIDATION_SYNC",
            "固定ランナー再実行、証跡検証、配布先同期",
            "本番移行OKの最終宣言は完了ゲート確認後",
        )

    bundle = row.get("bundle", "")
    if bundle == RK10_BUNDLE:
        scenario = row.get("scenario", "").strip()
        runtime_status = (rks_status_by_scenario or {}).get(scenario, "")
        if runtime_status in RKS_HUMAN_DECISION_STATUSES:
            return (
                "HUMAN_OR_EXTERNAL_APPROVAL_REQUIRED_NO_AUTO_APPROVAL",
                (
                    "RKS要否/入口選択の判断材料と入力先案内まで。"
                    "RK10を開く場合もAI開発版の既定ラジオを触らずOKのみ"
                ),
                "RKS要否、入口選択、または前提条件の人手判断",
            )
        if runtime_status in RKS_FINAL_SYNC_STATUSES:
            return (
                "MANUAL_REVIEW_REQUIRED_NO_AUTO_APPROVAL",
                "確認済みRKS証跡の同期先と不足欄の案内まで",
                "operator_result/reviewer/reviewed_at の最終確認",
            )
        return (
            "SAFE_TECHNICAL_EVIDENCE_CAN_CONTINUE_NO_AUTO_APPROVAL",
            (
                "RK10を開く場合はAI開発版の既定ラジオを触らずOKのみ。"
                "実行/本番書込なしでopen/build/safe-stop証跡を追加"
            ),
            "operator_result/reviewer/reviewed_at は証跡確認後に人が記入",
        )

    if bundle in HUMAN_APPROVAL_BUNDLES:
        return (
            "HUMAN_OR_EXTERNAL_APPROVAL_REQUIRED_NO_AUTO_APPROVAL",
            "証跡フォルダ、差分表、入力箇所の案内まで",
            "operator_result/reviewer/reviewed_at の人手承認または外部実行結果",
        )

    return (
        "MANUAL_REVIEW_REQUIRED_NO_AUTO_APPROVAL",
        "証跡整理と不足欄の案内まで",
        "operator_result/reviewer/reviewed_at の確認",
    )


def build_boundary_rows(
    rows: list[dict[str, str]],
    rks_status_by_scenario: dict[str, str] | None = None,
) -> list[BoundaryRow]:
    boundary_rows: list[BoundaryRow] = []
    for row in rows:
        boundary_class, codex_next, human_gate = classify_row(row, rks_status_by_scenario)
        missing_fields = missing_required_fields(row)
        current_status = "FILLED" if not missing_fields else "MISSING_FINAL_INPUT"
        boundary_rows.append(
            BoundaryRow(
                bundle=row.get("bundle", ""),
                scenario=row.get("scenario", ""),
                boundary_class=boundary_class,
                current_status=current_status,
                final_evidence_path_exists=exists_text(row.get("final_evidence_path", "")),
                suggested_folder_exists=exists_text(
                    row.get("suggested_final_evidence_folder", "")
                ),
                missing_fields=", ".join(missing_fields),
                codex_can_continue_with=codex_next,
                human_or_external_input_needed=human_gate,
                forbidden_scope=joined_forbidden_scope(row),
                source_intake_path=row.get("source_intake_path", ""),
            )
        )
    return boundary_rows


def count_by(rows: list[BoundaryRow], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(getattr(row, field_name))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def build_payload(
    unified_csv: Path,
    rks_matrix_json: Path | None = None,
    scope_exclusions_json: Path = SCOPE_EXCLUSIONS_JSON,
) -> dict[str, Any]:
    input_rows = read_csv_dicts(unified_csv)
    scope_exclusions = load_scope_exclusions(scope_exclusions_json)
    excluded_tokens = excluded_scenario_tokens(scope_exclusions)
    active_input_rows = [
        row for row in input_rows if not input_row_is_excluded(row, excluded_tokens)
    ]
    excluded_input_rows = [
        row for row in input_rows if input_row_is_excluded(row, excluded_tokens)
    ]
    rks_status_by_scenario = build_rks_status_by_scenario(rks_matrix_json)
    boundary_rows = build_boundary_rows(active_input_rows, rks_status_by_scenario)
    filled_count = sum(row.current_status == "FILLED" for row in boundary_rows)
    missing_count = len(boundary_rows) - filled_count
    safe_technical_count = sum(
        row.boundary_class == "SAFE_TECHNICAL_EVIDENCE_CAN_CONTINUE_NO_AUTO_APPROVAL"
        for row in boundary_rows
    )
    human_external_count = sum(
        row.boundary_class == "HUMAN_OR_EXTERNAL_APPROVAL_REQUIRED_NO_AUTO_APPROVAL"
        for row in boundary_rows
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_csv": str(unified_csv),
        "summary": {
            "row_count": len(boundary_rows),
            "raw_row_count": len(input_rows),
            "scope_exclusion_count": len(scope_exclusions),
            "excluded_row_count": len(excluded_input_rows),
            "scope_exclusions_path": str(scope_exclusions_json),
            "filled_row_count": filled_count,
            "missing_final_input_row_count": missing_count,
            "safe_technical_evidence_can_continue_count": safe_technical_count,
            "human_or_external_approval_required_count": human_external_count,
            "auto_approval_performed": False,
            "rks_matrix_json": str(rks_matrix_json) if rks_matrix_json else "",
            "rk10_license_dialog_policy": (
                "RPA開発版AI付きが既定選択ならラジオボタンは変更せずOKのみ"
            ),
            "boundary_counts": count_by(boundary_rows, "boundary_class"),
        },
        "rows": [asdict(row) for row in boundary_rows],
        "scope_exclusions": scope_exclusions,
        "excluded_rows": excluded_input_rows,
    }


def write_csv(path: Path, rows: list[BoundaryRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(BoundaryRow)]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Final Input Autonomous Boundary",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- source_csv: `{payload['source_csv']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- raw_row_count: `{summary.get('raw_row_count', summary['row_count'])}`",
        f"- scope_exclusion_count: `{summary.get('scope_exclusion_count', 0)}`",
        f"- excluded_row_count: `{summary.get('excluded_row_count', 0)}`",
        f"- filled_row_count: `{summary['filled_row_count']}`",
        f"- missing_final_input_row_count: `{summary['missing_final_input_row_count']}`",
        "- auto_approval_performed: `False`",
        f"- rk10_license_dialog_policy: `{summary['rk10_license_dialog_policy']}`",
        "",
        "## Boundary Counts",
        "",
    ]
    for boundary_class, count in summary["boundary_counts"].items():
        lines.append(f"- {boundary_class}: `{count}`")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Bundle | Scenario | Boundary | Status | Missing Fields | Codex Can Continue With | Human Or External Input Needed |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["bundle"],
                    row["scenario"],
                    row["boundary_class"],
                    row["current_status"],
                    row["missing_fields"],
                    row["codex_can_continue_with"],
                    row["human_or_external_input_needed"],
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [BoundaryRow(**row) for row in payload["rows"]]
    json_path = out_dir / "final_input_autonomous_boundary.json"
    csv_path = out_dir / "final_input_autonomous_boundary.csv"
    md_path = out_dir / "final_input_autonomous_boundary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, rows)
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(csv_path)
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a non-approving final input autonomous boundary report."
    )
    parser.add_argument("--unified-csv", type=Path, default=DEFAULT_UNIFIED_CSV)
    parser.add_argument("--rks-matrix-json", type=Path, default=DEFAULT_RKS_MATRIX_JSON)
    parser.add_argument("--scope-exclusions-json", type=Path, default=SCOPE_EXCLUSIONS_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        args.unified_csv,
        args.rks_matrix_json,
        args.scope_exclusions_json,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
