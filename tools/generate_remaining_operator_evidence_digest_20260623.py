"""Generate a digest for the remaining operator approval rows.

This report is intentionally non-approving. It summarizes the latest evidence
file for each row still missing operator fields, so a human reviewer can fill
the remaining packet without hunting through many folders.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_EXECUTION_VALIDATION_JSON = (
    REPORTS
    / "goal_execution_packet_validation_20260620"
    / "goal_execution_packet_validation.json"
)
DEFAULT_BOUNDARY_JSON = (
    REPORTS
    / "final_input_autonomous_boundary_20260622"
    / "final_input_autonomous_boundary.json"
)
DEFAULT_SCOPE_EXCLUSIONS_JSON = (
    REPORTS / "objective_scope_exclusions_20260623" / "objective_scope_exclusions.json"
)
DEFAULT_OUT_DIR = REPORTS / "remaining_operator_evidence_digest_20260623"

ATTENTION_PATTERNS = (
    "Traceback",
    "Exception",
    "ERROR",
    "FAILED",
    "LATEST_RUN_ERROR_NG",
    "RK10_BUILD_NG",
    "RK10_EDITOR_OPEN_NG",
    "NG_META_MISSING",
    "OVERFLOW",
    "未転記",
)
SIDE_EFFECT_PATTERNS = (
    "not executed",
    "実行していない",
    "実送信なし",
    "実印刷なし",
    "Payment execution",
    "production writes",
    "RK10 ButtonRun",
    "paid Azure OCR",
    "no production",
    "dry-run",
    "DRY-RUN",
)


@dataclass(frozen=True)
class DigestRow:
    bundle: str
    scenario: str
    status: str
    missing_fields: str
    evidence_path: str
    evidence_exists: str
    evidence_file_count: int
    latest_evidence_file: str
    latest_evidence_file_exists: str
    latest_evidence_modified_at: str
    attention_terms: str
    side_effect_boundary_lines: str
    boundary_class: str
    codex_can_continue_with: str
    human_or_external_input_needed: str
    source_packet_csv: str


def raise_csv_field_limit() -> None:
    csv.field_size_limit(sys.maxsize)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def read_text_sample(path: Path, max_chars: int = 20000) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")[:max_chars]
    except OSError:
        return ""


def evidence_files(evidence_path: str) -> list[Path]:
    folder = Path(evidence_path)
    if not folder.exists():
        return []
    return sorted(
        [path for path in folder.rglob("*") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def modified_at(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def detected_attention_terms(text: str) -> list[str]:
    detected: list[str] = []
    for pattern in ATTENTION_PATTERNS:
        if pattern in text:
            detected.append(pattern)
    return detected


def side_effect_lines(text: str, max_lines: int = 3) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        if any(pattern in line for pattern in SIDE_EFFECT_PATTERNS):
            cleaned = re.sub(r"\s+", " ", line).strip()
            if cleaned and cleaned not in lines:
                lines.append(cleaned[:220])
        if len(lines) >= max_lines:
            break
    return lines


def boundary_by_key(boundary_payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in boundary_payload.get("rows", []):
        if not isinstance(row, dict):
            continue
        key = (str(row.get("bundle", "")), str(row.get("scenario", "")))
        rows[key] = row
    return rows


def scenario_tokens(value: str) -> set[str]:
    tokens = {part.strip() for part in value.split("/") if part.strip()}
    return tokens or {value.strip()}


def load_scope_excluded_scenarios(scope_payload: dict[str, Any]) -> set[str]:
    exclusions = scope_payload.get("exclusions", [])
    if not isinstance(exclusions, list):
        return set()
    excluded: set[str] = set()
    for item in exclusions:
        if not isinstance(item, dict) or item.get("active") is False:
            continue
        scenario = str(item.get("scenario", "")).strip()
        if scenario:
            excluded.update(scenario_tokens(scenario))
    return excluded


def row_is_scope_excluded(row: dict[str, Any], excluded_scenarios: set[str]) -> bool:
    if not excluded_scenarios:
        return False
    return bool(scenario_tokens(str(row.get("scenario", ""))) & excluded_scenarios)


def build_digest_rows(
    execution_payload: dict[str, Any],
    boundary_payload: dict[str, Any],
    excluded_scenarios: set[str] | None = None,
) -> list[DigestRow]:
    boundaries = boundary_by_key(boundary_payload)
    excluded_scenarios = excluded_scenarios or set()
    digest_rows: list[DigestRow] = []
    for row in execution_payload.get("rows", []):
        if not isinstance(row, dict) or row.get("approved") is True:
            continue
        if row_is_scope_excluded(row, excluded_scenarios):
            continue

        files = evidence_files(str(row.get("evidence_path", "")))
        latest_file = files[0] if files else None
        latest_text = read_text_sample(latest_file) if latest_file else ""
        key = (str(row.get("bundle", "")), str(row.get("scenario", "")))
        boundary = boundaries.get(key, {})
        digest_rows.append(
            DigestRow(
                bundle=str(row.get("bundle", "")),
                scenario=str(row.get("scenario", "")),
                status=str(row.get("status", "")),
                missing_fields=str(row.get("missing_fields", "")),
                evidence_path=str(row.get("evidence_path", "")),
                evidence_exists="YES" if row.get("evidence_exists") is True else "NO",
                evidence_file_count=len(files),
                latest_evidence_file=str(latest_file) if latest_file else "",
                latest_evidence_file_exists="YES" if latest_file else "NO",
                latest_evidence_modified_at=modified_at(latest_file),
                attention_terms=", ".join(detected_attention_terms(latest_text)),
                side_effect_boundary_lines=" / ".join(side_effect_lines(latest_text)),
                boundary_class=str(boundary.get("boundary_class", "")),
                codex_can_continue_with=str(boundary.get("codex_can_continue_with", "")),
                human_or_external_input_needed=str(
                    boundary.get("human_or_external_input_needed", "")
                ),
                source_packet_csv=str(row.get("csv_path", "")),
            )
        )
    return digest_rows


def count_by(rows: list[DigestRow], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(getattr(row, field_name))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def build_payload(
    execution_validation_json: Path = DEFAULT_EXECUTION_VALIDATION_JSON,
    boundary_json: Path = DEFAULT_BOUNDARY_JSON,
    scope_exclusions_json: Path = DEFAULT_SCOPE_EXCLUSIONS_JSON,
) -> dict[str, Any]:
    execution_payload = read_json(execution_validation_json)
    boundary_payload = read_json(boundary_json)
    scope_payload = read_json(scope_exclusions_json)
    excluded_scenarios = load_scope_excluded_scenarios(scope_payload)
    raw_rows = build_digest_rows(execution_payload, boundary_payload)
    rows = build_digest_rows(execution_payload, boundary_payload, excluded_scenarios)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "execution_validation_json": str(execution_validation_json),
        "boundary_json": str(boundary_json),
        "scope_exclusions_json": str(scope_exclusions_json),
        "safety": (
            "read-only evidence digest; no auto approval; no RK10 ButtonRun; "
            "no mail/print/payment/final submit/production write/paid Azure OCR"
        ),
        "rk10_license_dialog_policy": (
            "RPA開発版AI付きが既定選択ならラジオボタンは変更せずOKのみ"
        ),
        "raw_pending_row_count": len(raw_rows),
        "scope_excluded_scenarios": sorted(excluded_scenarios),
        "scope_excluded_row_count": len(raw_rows) - len(rows),
        "pending_row_count": len(rows),
        "evidence_exists_count": sum(row.evidence_exists == "YES" for row in rows),
        "latest_file_exists_count": sum(
            row.latest_evidence_file_exists == "YES" for row in rows
        ),
        "attention_row_count": sum(bool(row.attention_terms) for row in rows),
        "boundary_counts": count_by(rows, "boundary_class"),
        "rows": [asdict(row) for row in rows],
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(DigestRow)]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Remaining Operator Evidence Digest 2026-06-23",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- pending_row_count: `{payload['pending_row_count']}`",
        f"- raw_pending_row_count: `{payload['raw_pending_row_count']}`",
        f"- scope_excluded_row_count: `{payload['scope_excluded_row_count']}`",
        f"- evidence_exists_count: `{payload['evidence_exists_count']}`",
        f"- latest_file_exists_count: `{payload['latest_file_exists_count']}`",
        f"- attention_row_count: `{payload['attention_row_count']}`",
        f"- safety: `{payload['safety']}`",
        f"- rk10_license_dialog_policy: `{payload['rk10_license_dialog_policy']}`",
        "",
        "## Boundary Counts",
        "",
    ]
    for key, count in payload["boundary_counts"].items():
        lines.append(f"- {key or '(blank)'}: `{count}`")
    lines.extend(
        [
            "",
            "## Pending Rows",
            "",
            (
                "| Bundle | Scenario | Evidence Files | Latest Evidence | "
                "Attention Terms | Human/External Needed |"
            ),
            "|---|---|---:|---|---|---|",
        ]
    )
    for row in payload["rows"]:
        latest = row["latest_evidence_file"].replace("|", "/")
        needed = row["human_or_external_input_needed"].replace("|", "/")
        lines.append(
            "| "
            + " | ".join(
                [
                    row["bundle"],
                    row["scenario"],
                    str(row["evidence_file_count"]),
                    f"`{latest}`" if latest else "",
                    row["attention_terms"].replace("|", "/"),
                    needed,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Sources",
            "",
            f"- execution_validation_json: `{payload['execution_validation_json']}`",
            f"- boundary_json: `{payload['boundary_json']}`",
            f"- scope_exclusions_json: `{payload['scope_exclusions_json']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "remaining_operator_evidence_digest.json"
    csv_path = out_dir / "remaining_operator_evidence_digest.csv"
    md_path = out_dir / "remaining_operator_evidence_digest.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, payload["rows"])
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(csv_path)
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a digest for remaining operator evidence."
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
