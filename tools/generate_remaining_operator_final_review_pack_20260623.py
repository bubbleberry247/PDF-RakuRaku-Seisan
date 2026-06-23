"""Generate a human final-review pack for remaining operator rows.

This tool is intentionally non-approving. It reads the active rows from the
remaining-operator readiness validation JSON and writes a small HTML/CSV/README
pack so a human reviewer can inspect evidence and fill the packet. It does not
write approvals, run RK10, send mail, print, submit, pay, call Azure, or write
production systems.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_VALIDATION_JSON = (
    REPORTS
    / "remaining_operator_input_ready_validation_20260623"
    / "remaining_operator_input_ready_validation.json"
)
DEFAULT_REMAINING_INPUT_CSV = (
    REPORTS / "remaining_operator_input_packet_20260623" / "remaining_operator_input.csv"
)
DEFAULT_INPUT_PACKET_JSON = (
    REPORTS
    / "remaining_operator_input_packet_20260623"
    / "remaining_operator_input_packet.json"
)
DEFAULT_OUT_DIR = REPORTS / "remaining_operator_final_review_pack_active_scope_20260623"


@dataclass(frozen=True)
class ReviewRow:
    bundle: str
    scenario: str
    status: str
    blockers: str
    evidence_path: str
    latest_evidence_file: str
    source_packet_csv: str
    source_unified_input_csv: str
    next_action: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def path_exists_text(value: str) -> str:
    if not value.strip():
        return "NO"
    return "YES" if Path(value).exists() else "NO"


def build_next_action(row: dict[str, Any]) -> str:
    blockers = str(row.get("blockers", ""))
    if "MISSING_OPERATOR_FIELDS" in blockers:
        return "latest evidenceを確認し、operator_result/reviewer/reviewed_atを人が記入する"
    if "NON_APPROVED_OPERATOR_RESULT" in blockers:
        return "operator_resultをOK/PASS/完了/承認済などの最終承認値へ修正する"
    if "EVIDENCE" in blockers:
        return "evidence_path/latest_evidence_fileを実在する証跡へ修正する"
    return "行のstatus/blockersに従い、人が最終確認する"


def build_review_rows(validation_payload: dict[str, Any]) -> list[ReviewRow]:
    rows: list[ReviewRow] = []
    for row in validation_payload.get("rows", []):
        if not isinstance(row, dict):
            continue
        rows.append(
            ReviewRow(
                bundle=str(row.get("bundle", "")),
                scenario=str(row.get("scenario", "")),
                status=str(row.get("status", "")),
                blockers=str(row.get("blockers", "")),
                evidence_path=str(row.get("evidence_path", "")),
                latest_evidence_file=str(row.get("latest_evidence_file", "")),
                source_packet_csv=str(row.get("source_packet_csv", "")),
                source_unified_input_csv=str(row.get("source_unified_input_csv", "")),
                next_action=build_next_action(row),
            )
        )
    return rows


def build_payload(
    validation_json: Path = DEFAULT_VALIDATION_JSON,
    remaining_input_csv: Path = DEFAULT_REMAINING_INPUT_CSV,
    input_packet_json: Path = DEFAULT_INPUT_PACKET_JSON,
) -> dict[str, Any]:
    validation_payload = read_json(validation_json)
    input_packet_payload = read_json(input_packet_json)
    rows = build_review_rows(validation_payload)
    packet_raw_row_count = input_packet_payload.get(
        "raw_row_count",
        validation_payload.get("raw_row_count", validation_payload.get("row_count", 0)),
    )
    packet_scope_excluded_row_count = input_packet_payload.get(
        "scope_excluded_row_count",
        validation_payload.get("excluded_row_count", 0),
    )
    packet_scope_excluded_scenarios = input_packet_payload.get(
        "scope_excluded_scenarios",
        [],
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "validation_json": str(validation_json),
        "remaining_input_csv": str(remaining_input_csv),
        "input_packet_json": str(input_packet_json),
        "input_packet_json_exists": input_packet_json.exists(),
        "safety": (
            "human review aid only; no auto approval; no RK10 ButtonRun; "
            "no production write; no mail; no print; no submit; no payment; "
            "no paid Azure OCR"
        ),
        "row_count": len(rows),
        "not_ready_row_count": sum(row.status != "READY_FOR_SYNC" for row in rows),
        "evidence_path_exists_count": sum(
            path_exists_text(row.evidence_path) == "YES" for row in rows
        ),
        "latest_evidence_file_exists_count": sum(
            path_exists_text(row.latest_evidence_file) == "YES" for row in rows
        ),
        "source_scope": "active rows from remaining operator readiness validation",
        "raw_row_count": validation_payload.get("raw_row_count", validation_payload.get("row_count", 0)),
        "scope_exclusion_count": validation_payload.get("scope_exclusion_count", 0),
        "excluded_row_count": validation_payload.get("excluded_row_count", 0),
        "packet_raw_row_count": packet_raw_row_count,
        "packet_scope_excluded_row_count": packet_scope_excluded_row_count,
        "packet_scope_excluded_scenarios": packet_scope_excluded_scenarios,
        "rows": [asdict(row) for row in rows],
    }


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(ReviewRow)]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def file_uri(path_text: str) -> str:
    if not path_text:
        return ""
    return Path(path_text).absolute().as_uri()


def build_html(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    lines = [
        "<!doctype html>",
        '<html lang="ja">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Remaining Operator Final Review Pack</title>",
        "<style>",
        "body{font-family:Meiryo,Segoe UI,sans-serif;margin:24px;line-height:1.5}",
        "table{border-collapse:collapse;width:100%;font-size:13px}",
        "th,td{border:1px solid #ccc;padding:6px;vertical-align:top}",
        "th{background:#f4f6f8}",
        ".warn{color:#8a4b00;font-weight:bold}",
        "</style>",
        "</head>",
        "<body>",
        "<h1>Remaining Operator Final Review Pack</h1>",
        f"<p>generated_at: <code>{html.escape(str(payload['generated_at']))}</code></p>",
        f"<p>row_count: <strong>{payload['row_count']}</strong> / scope_exclusion_count: <strong>{payload['scope_exclusion_count']}</strong></p>",
        f"<p>packet_raw_row_count: <strong>{payload['packet_raw_row_count']}</strong> / packet_scope_excluded_row_count: <strong>{payload['packet_scope_excluded_row_count']}</strong></p>",
        '<p class="warn">This pack is a review aid only. It does not approve, submit, print, send mail, run RK10, pay, or write production systems.</p>',
        "<table>",
        "<thead><tr><th>Bundle</th><th>Scenario</th><th>Status</th><th>Blockers</th><th>Latest Evidence</th><th>Next Action</th></tr></thead>",
        "<tbody>",
    ]
    for row in rows:
        assert isinstance(row, dict)
        latest = str(row.get("latest_evidence_file", ""))
        latest_link = (
            f'<a href="{html.escape(file_uri(latest))}">{html.escape(latest)}</a>'
            if latest
            else ""
        )
        lines.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('bundle', '')))}</td>"
            f"<td>{html.escape(str(row.get('scenario', '')))}</td>"
            f"<td>{html.escape(str(row.get('status', '')))}</td>"
            f"<td>{html.escape(str(row.get('blockers', '')))}</td>"
            f"<td>{latest_link}</td>"
            f"<td>{html.escape(str(row.get('next_action', '')))}</td>"
            "</tr>"
        )
    lines.extend(["</tbody>", "</table>", "</body>", "</html>"])
    return "\n".join(lines) + "\n"


def build_markdown(payload: dict[str, Any], out_dir: Path) -> str:
    html_path = out_dir / "operator_final_review_index.html"
    csv_path = out_dir / "operator_final_review_index.csv"
    bat_path = out_dir / "OPEN_OPERATOR_FINAL_REVIEW_PACK.bat"
    return "\n".join(
        [
            "# Remaining Operator Final Review Pack 2026-06-23",
            "",
            f"- generated_at: `{payload['generated_at']}`",
            f"- row_count: `{payload['row_count']}`",
            f"- not_ready_row_count: `{payload['not_ready_row_count']}`",
            f"- evidence_path_exists_count: `{payload['evidence_path_exists_count']}`",
            f"- latest_evidence_file_exists_count: `{payload['latest_evidence_file_exists_count']}`",
            f"- raw_row_count: `{payload['raw_row_count']}`",
            f"- scope_exclusion_count: `{payload['scope_exclusion_count']}`",
            f"- excluded_row_count: `{payload['excluded_row_count']}`",
            f"- packet_raw_row_count: `{payload['packet_raw_row_count']}`",
            f"- packet_scope_excluded_row_count: `{payload['packet_scope_excluded_row_count']}`",
            f"- packet_scope_excluded_scenarios: `{', '.join(payload['packet_scope_excluded_scenarios'])}`",
            f"- safety: `{payload['safety']}`",
            "",
            "## Operator Steps",
            "",
            "1. `operator_final_review_index.html` を開き、各行の latest evidence を確認する。",
            "2. `remaining_operator_input.csv` の同じ scenario 行へ `operator_result/reviewer/reviewed_at` を人が記入する。",
            "3. `RUN_AFTER_FILL_remaining_operator_input.bat` を実行して、同期と安全ランナーを再確認する。",
            "",
            "## Files",
            "",
            f"- review_html: `{html_path}`",
            f"- review_csv: `{csv_path}`",
            f"- opener_bat: `{bat_path}`",
            f"- remaining_input_csv: `{payload['remaining_input_csv']}`",
            f"- validation_json: `{payload['validation_json']}`",
            f"- input_packet_json: `{payload['input_packet_json']}`",
        ]
    ) + "\n"


def build_opener_bat(payload: dict[str, Any], out_dir: Path) -> str:
    return "\r\n".join(
        [
            "@echo off",
            "setlocal",
            f'start "" "{out_dir / "operator_final_review_index.html"}"',
            f'start "" "{out_dir / "operator_final_review_index.csv"}"',
            f'start "" "{payload["remaining_input_csv"]}"',
            "exit /b 0",
            "",
        ]
    )


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "operator_final_review_pack.json"
    csv_path = out_dir / "operator_final_review_index.csv"
    html_path = out_dir / "operator_final_review_index.html"
    md_path = out_dir / "START_HERE_operator_final_review.md"
    bat_path = out_dir / "OPEN_OPERATOR_FINAL_REVIEW_PACK.bat"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, payload["rows"])
    html_path.write_text(build_html(payload), encoding="utf-8")
    md_path.write_text(build_markdown(payload, out_dir), encoding="utf-8")
    bat_path.write_text(build_opener_bat(payload, out_dir), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(csv_path)
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a non-approving final review pack for remaining operator rows."
    )
    parser.add_argument("--validation-json", type=Path, default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--remaining-input-csv", type=Path, default=DEFAULT_REMAINING_INPUT_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.validation_json, args.remaining_input_csv)
    write_outputs(payload, args.out_dir)
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
