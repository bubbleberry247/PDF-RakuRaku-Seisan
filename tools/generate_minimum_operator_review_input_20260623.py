"""Generate a minimal operator-review input UI for remaining active rows.

This tool keeps existing operator fields when present. It also exposes a
separate Codex auto-evidence path that records OK only after the fixed safe
check summary passes and each row has a latest evidence file.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_REMAINING_INPUT_CSV = (
    REPORTS / "remaining_operator_input_packet_20260623" / "remaining_operator_input.csv"
)
DEFAULT_INPUT_PACKET_JSON = (
    REPORTS
    / "remaining_operator_input_packet_20260623"
    / "remaining_operator_input_packet.json"
)
DEFAULT_FINAL_REVIEW_JSON = (
    REPORTS
    / "remaining_operator_final_review_pack_active_scope_20260623"
    / "operator_final_review_pack.json"
)
DEFAULT_OUT_DIR = REPORTS / "minimum_operator_review_input_20260623"
DEFAULT_EXISTING_MINIMUM_CSV = DEFAULT_OUT_DIR / "minimum_operator_review_input.csv"
APPLY_SCRIPT_NAME = "apply_minimum_operator_review_input.py"
OPEN_BAT_NAME = "OPEN_minimum_operator_review_input.bat"
APPLY_BAT_NAME = "APPLY_AND_RUN_AFTER_FILL_minimum_operator_review_input.bat"
GUIDED_FILL_PS1_NAME = "GUIDED_FILL_minimum_operator_review_input.ps1"
GUIDED_FILL_BAT_NAME = "GUIDED_FILL_minimum_operator_review_input.bat"
AUTO_FILL_AND_APPLY_BAT_NAME = (
    "AUTO_FILL_AND_APPLY_FROM_CODEX_EVIDENCE_minimum_operator_review_input.bat"
)
START_HERE_NAME = "START_HERE_minimum_operator_review.md"
MINIMUM_CSV_NAME = "minimum_operator_review_input.csv"
PACK_JSON_NAME = "minimum_operator_review_pack.json"
PACK_MD_NAME = "minimum_operator_review_pack.md"
SUMMARY_MD_NAME = "minimum_operator_review_input_summary.md"
HTML_NAME = "minimum_operator_review_input.html"
OPERATOR_FIELDS = ("operator_result", "reviewer", "reviewed_at")
ALLOWED_OPERATOR_RESULT = "OK / NG / HOLD"
SAFETY_TEXT = (
    "manual input aid plus optional Codex auto-evidence fill; preserves filled fields; "
    "no RK10 ButtonRun; no production write; no mail; no print; no submit; "
    "no payment; no paid Azure OCR"
)
MINIMUM_CSV_FIELDS = [
    "bundle",
    "scenario",
    "operator_result",
    "reviewer",
    "reviewed_at",
    "allowed_operator_result",
    "latest_evidence_file",
    "source_remaining_operator_input_csv",
    "source_packet_csv",
    "source_unified_input_csv",
    "status",
    "blockers",
    "evidence_success_signals",
    "evidence_attention_signals",
    "evidence_safety_signals",
    "human_or_external_input_needed",
    "attention_terms",
]


@dataclass(frozen=True)
class MinimumReviewRow:
    row_number: int
    bundle: str
    scenario: str
    operator_result: str
    reviewer: str
    reviewed_at: str
    allowed_operator_result: str
    latest_evidence_file: str
    latest_evidence_exists: str
    latest_evidence_uri: str
    evidence_path: str
    source_remaining_operator_input_csv: str
    source_packet_csv: str
    source_unified_input_csv: str
    status: str
    blockers: str
    evidence_success_signals: str
    evidence_attention_signals: str
    evidence_safety_signals: str
    human_or_external_input_needed: str
    attention_terms: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def entry_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("bundle", "")).strip(), str(row.get("scenario", "")).strip()


def rows_by_key(rows: Sequence[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = entry_key(row)
        if key[0] and key[1]:
            output[key] = row
    return output


def existing_operator_fields(
    path: Path | None,
) -> dict[tuple[str, str], dict[str, str]]:
    output: dict[tuple[str, str], dict[str, str]] = {}
    for row in read_csv_rows(path):
        key = entry_key(row)
        if not key[0] or not key[1]:
            continue
        output[key] = {
            field: str(row.get(field, "")).strip() for field in OPERATOR_FIELDS
        }
    return output


def file_uri(path_text: str) -> str:
    if not path_text:
        return ""
    try:
        return Path(path_text).absolute().as_uri()
    except ValueError:
        return ""


def path_exists_text(path_text: str) -> str:
    if not path_text.strip():
        return "NO"
    return "YES" if Path(path_text).exists() else "NO"


def compact_signal(text: str, max_length: int = 180) -> str:
    value = " ".join(text.strip().split())
    if len(value) <= max_length:
        return value
    return value[: max_length - 3].rstrip() + "..."


def evidence_signals(path_text: str) -> dict[str, str]:
    if not path_text.strip() or not Path(path_text).exists():
        return {
            "evidence_success_signals": "",
            "evidence_attention_signals": "latest evidence file missing",
            "evidence_safety_signals": "",
        }
    lines = Path(path_text).read_text(encoding="utf-8", errors="replace").splitlines()
    success_terms = (
        "exit_code=0",
        "exit=0",
        "errors=0",
        "error_count=0",
        "エラー0",
        "OK_CANDIDATE",
        "OK_FOR_OPEN_BUILD_TEST",
        "OK_FOR_SAFE_STOP_TEST",
        "success=",
        "verify_message:",
        "py_compile_exit=0",
    )
    attention_terms = (
        "UNCONFIRMED",
        "NG_META_MISSING",
        "exit_code=1",
        "exit=1",
        "exit_code=2",
        "overflow",
        "not_found=",
        "Unknown supplier",
        "missing evidence",
        "未確認",
    )
    safety_terms = (
        "dry-run",
        "no-mail",
        "no-send",
        "no print",
        "no submit",
        "no payment",
        "mail_sent: `False`",
        "submitted: False",
        "payment_execute_performed: `False`",
        "RK10 ButtonRun",
        "本番登録",
        "実送信",
        "実印刷",
    )
    buckets = {
        "evidence_success_signals": [],
        "evidence_attention_signals": [],
        "evidence_safety_signals": [],
    }
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if len(buckets["evidence_success_signals"]) < 4 and any(
            term in stripped for term in success_terms
        ):
            buckets["evidence_success_signals"].append(compact_signal(stripped))
        if len(buckets["evidence_attention_signals"]) < 4 and any(
            term in stripped for term in attention_terms
        ):
            buckets["evidence_attention_signals"].append(compact_signal(stripped))
        if len(buckets["evidence_safety_signals"]) < 4 and any(
            term in stripped for term in safety_terms
        ):
            buckets["evidence_safety_signals"].append(compact_signal(stripped))
    return {key: " / ".join(values) for key, values in buckets.items()}


def operator_field_value(
    source_row: dict[str, str],
    preserved: dict[str, str],
    field: str,
) -> str:
    source_value = str(source_row.get(field, "")).strip()
    if source_value:
        return source_value
    return str(preserved.get(field, "")).strip()


def complete_operator_fields(row: dict[str, Any]) -> bool:
    return all(str(row.get(field, "")).strip() for field in OPERATOR_FIELDS)


def any_operator_fields(row: dict[str, Any]) -> bool:
    return any(str(row.get(field, "")).strip() for field in OPERATOR_FIELDS)


def build_rows(
    remaining_rows: Sequence[dict[str, str]],
    final_review_rows: Sequence[dict[str, Any]],
    remaining_input_csv: Path,
    existing_minimum_csv: Path | None,
) -> list[MinimumReviewRow]:
    final_by_key = rows_by_key(final_review_rows)
    preserved_by_key = existing_operator_fields(existing_minimum_csv)
    output: list[MinimumReviewRow] = []
    for index, source_row in enumerate(remaining_rows, 1):
        key = entry_key(source_row)
        final_row = final_by_key.get(key, {})
        preserved = preserved_by_key.get(key, {})
        latest_evidence = str(
            source_row.get("latest_evidence_file")
            or final_row.get("latest_evidence_file")
            or ""
        ).strip()
        signals = evidence_signals(latest_evidence)
        output.append(
            MinimumReviewRow(
                row_number=index,
                bundle=key[0],
                scenario=key[1],
                operator_result=operator_field_value(
                    source_row, preserved, "operator_result"
                ),
                reviewer=operator_field_value(source_row, preserved, "reviewer"),
                reviewed_at=operator_field_value(source_row, preserved, "reviewed_at"),
                allowed_operator_result=str(
                    source_row.get("allowed_operator_result_values")
                    or source_row.get("allowed_operator_result")
                    or ALLOWED_OPERATOR_RESULT
                ).strip(),
                latest_evidence_file=latest_evidence,
                latest_evidence_exists=path_exists_text(latest_evidence),
                latest_evidence_uri=file_uri(latest_evidence),
                evidence_path=str(
                    source_row.get("evidence_path") or final_row.get("evidence_path") or ""
                ).strip(),
                source_remaining_operator_input_csv=str(remaining_input_csv),
                source_packet_csv=str(
                    source_row.get("source_packet_csv")
                    or final_row.get("source_packet_csv")
                    or ""
                ).strip(),
                source_unified_input_csv=str(
                    source_row.get("source_unified_input_csv")
                    or final_row.get("source_unified_input_csv")
                    or ""
                ).strip(),
                status=str(final_row.get("status", "")).strip(),
                blockers=str(final_row.get("blockers", "")).strip(),
                evidence_success_signals=signals["evidence_success_signals"],
                evidence_attention_signals=signals["evidence_attention_signals"],
                evidence_safety_signals=signals["evidence_safety_signals"],
                human_or_external_input_needed=str(
                    source_row.get("human_or_external_input_needed", "")
                ).strip(),
                attention_terms=str(source_row.get("attention_terms", "")).strip(),
            )
        )
    return output


def count_preserved_operator_fields(
    rows: Sequence[MinimumReviewRow],
    remaining_rows: Sequence[dict[str, str]],
) -> int:
    source_by_key = rows_by_key(remaining_rows)
    count = 0
    for row in rows:
        source_row = source_by_key.get((row.bundle, row.scenario), {})
        for field in OPERATOR_FIELDS:
            source_value = str(source_row.get(field, "")).strip()
            output_value = str(getattr(row, field)).strip()
            if output_value and not source_value:
                count += 1
    return count


def build_payload(
    remaining_input_csv: Path = DEFAULT_REMAINING_INPUT_CSV,
    final_review_json: Path = DEFAULT_FINAL_REVIEW_JSON,
    input_packet_json: Path = DEFAULT_INPUT_PACKET_JSON,
    existing_minimum_csv: Path | None = DEFAULT_EXISTING_MINIMUM_CSV,
) -> dict[str, Any]:
    remaining_rows = read_csv_rows(remaining_input_csv)
    final_review_payload = read_json(final_review_json)
    input_packet_payload = read_json(input_packet_json)
    final_review_rows = [
        row for row in final_review_payload.get("rows", []) if isinstance(row, dict)
    ]
    rows = build_rows(
        remaining_rows,
        final_review_rows,
        remaining_input_csv,
        existing_minimum_csv,
    )
    row_dicts = [asdict(row) for row in rows]
    complete_count = sum(complete_operator_fields(row) for row in row_dicts)
    partial_count = sum(
        any_operator_fields(row) and not complete_operator_fields(row)
        for row in row_dicts
    )
    source_operator_field_count = sum(
        1
        for row in remaining_rows
        for field in OPERATOR_FIELDS
        if str(row.get(field, "")).strip()
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": SAFETY_TEXT,
        "remaining_input_csv": str(remaining_input_csv),
        "remaining_input_csv_exists": remaining_input_csv.exists(),
        "final_review_json": str(final_review_json),
        "final_review_json_exists": final_review_json.exists(),
        "input_packet_json": str(input_packet_json),
        "input_packet_json_exists": input_packet_json.exists(),
        "existing_minimum_csv": str(existing_minimum_csv) if existing_minimum_csv else "",
        "existing_minimum_csv_exists": bool(
            existing_minimum_csv and existing_minimum_csv.exists()
        ),
        "row_count": len(rows),
        "complete_operator_row_count": complete_count,
        "blank_operator_row_count": sum(
            not any_operator_fields(row) for row in row_dicts
        ),
        "partial_operator_row_count": partial_count,
        "source_operator_field_count": source_operator_field_count,
        "operator_fields_preserved_from_existing_minimum_csv": count_preserved_operator_fields(
            rows, remaining_rows
        ),
        "latest_evidence_file_exists_count": sum(
            row.latest_evidence_exists == "YES" for row in rows
        ),
        "scope_exclusion_count": final_review_payload.get("scope_exclusion_count", 0),
        "packet_raw_row_count": final_review_payload.get(
            "packet_raw_row_count", input_packet_payload.get("raw_row_count", 0)
        ),
        "packet_scope_excluded_row_count": final_review_payload.get(
            "packet_scope_excluded_row_count",
            input_packet_payload.get("scope_excluded_row_count", 0),
        ),
        "packet_scope_excluded_scenarios": final_review_payload.get(
            "packet_scope_excluded_scenarios",
            input_packet_payload.get("scope_excluded_scenarios", []),
        ),
        "minimum_input_csv": str(DEFAULT_OUT_DIR / MINIMUM_CSV_NAME),
        "html_input_ui": str(DEFAULT_OUT_DIR / HTML_NAME),
        "open_ui_bat": str(DEFAULT_OUT_DIR / OPEN_BAT_NAME),
        "guided_fill_ps1": str(DEFAULT_OUT_DIR / GUIDED_FILL_PS1_NAME),
        "guided_fill_bat": str(DEFAULT_OUT_DIR / GUIDED_FILL_BAT_NAME),
        "auto_fill_and_apply_bat": str(DEFAULT_OUT_DIR / AUTO_FILL_AND_APPLY_BAT_NAME),
        "apply_bat": str(DEFAULT_OUT_DIR / APPLY_BAT_NAME),
        "apply_script": str(DEFAULT_OUT_DIR / APPLY_SCRIPT_NAME),
        "apply_script_exists": (DEFAULT_OUT_DIR / APPLY_SCRIPT_NAME).exists(),
        "rows": row_dicts,
    }


def csv_row_from_review_row(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field, "") for field in MINIMUM_CSV_FIELDS}


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MINIMUM_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(csv_row_from_review_row(row))


def build_summary_markdown(payload: dict[str, Any]) -> str:
    scenarios = ", ".join(
        str(row.get("scenario", "")) for row in payload.get("rows", [])
    )
    excluded = ", ".join(str(value) for value in payload["packet_scope_excluded_scenarios"])
    return "\n".join(
        [
            "# Minimum Operator Review Input Summary 2026-06-23",
            "",
            f"- generated_at: `{payload['generated_at']}`",
            f"- row_count: `{payload['row_count']}`",
            f"- complete_operator_row_count: `{payload['complete_operator_row_count']}`",
            f"- blank_operator_row_count: `{payload['blank_operator_row_count']}`",
            f"- partial_operator_row_count: `{payload['partial_operator_row_count']}`",
            f"- latest_evidence_file_exists_count: `{payload['latest_evidence_file_exists_count']}`",
            f"- scope_exclusion_count: `{payload['scope_exclusion_count']}`",
            f"- packet_scope_excluded_scenarios: `{excluded}`",
            f"- scenarios: `{scenarios}`",
            f"- safety: `{payload['safety']}`",
            "- Codex自動確認: `fixed safe-check summary passed + latest evidence file exists => OK`",
            "",
            "## Files",
            "",
            f"- minimum_input_csv: `{payload['minimum_input_csv']}`",
            f"- auto_fill_and_apply_bat: `{payload['auto_fill_and_apply_bat']}`",
            f"- guided_fill_bat: `{payload['guided_fill_bat']}`",
            f"- html_input_ui: `{payload['html_input_ui']}`",
            f"- open_ui_bat: `{payload['open_ui_bat']}`",
            f"- apply_bat: `{payload['apply_bat']}`",
            f"- remaining_input_csv: `{payload['remaining_input_csv']}`",
            f"- final_review_json: `{payload['final_review_json']}`",
            f"- input_packet_json: `{payload['input_packet_json']}`",
        ]
    ) + "\n"


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Minimum Operator Review Input Pack 2026-06-23",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- complete_operator_row_count: `{payload['complete_operator_row_count']}`",
        f"- blank_operator_row_count: `{payload['blank_operator_row_count']}`",
        f"- partial_operator_row_count: `{payload['partial_operator_row_count']}`",
        f"- source_operator_field_count: `{payload['source_operator_field_count']}`",
        f"- operator_fields_preserved_from_existing_minimum_csv: `{payload['operator_fields_preserved_from_existing_minimum_csv']}`",
        f"- latest_evidence_file_exists_count: `{payload['latest_evidence_file_exists_count']}`",
        f"- scope_exclusion_count: `{payload['scope_exclusion_count']}`",
        f"- packet_raw_row_count: `{payload['packet_raw_row_count']}`",
        f"- packet_scope_excluded_row_count: `{payload['packet_scope_excluded_row_count']}`",
        f"- packet_scope_excluded_scenarios: `{', '.join(payload['packet_scope_excluded_scenarios'])}`",
        f"- safety: `{payload['safety']}`",
        "",
        "## How To Use",
        "",
        f"1. 目視確認なしで進める場合は `{AUTO_FILL_AND_APPLY_BAT_NAME}` を実行する。",
        "2. Codex自動確認は fixed safe-check summary が passed かつ latest evidence file が実在する行だけ OK を記録する。",
        f"3. 手動で残したい場合は `{GUIDED_FILL_BAT_NAME}` を開き、対話入力でCSVを作る。",
        f"4. HTML/CSVを使う場合は、CSVを `{MINIMUM_CSV_NAME}` として同じフォルダへ保存する。",
        f"5. 手動入力後は `{APPLY_BAT_NAME}` を実行し、既存の同期/安全ランナーへ渡す。",
        "",
        "## Safety",
        "",
        "- Codex自動確認のOKは、人の目視承認ではなく、固定安全ランナーとlatest evidence実在に基づく機械判定。",
        "- 手動入口は引き続き OK/NG/HOLD を人が入力する用途として残す。",
        "- 実送信・実印刷・本番登録・支払実行・RK10 ButtonRun・有償Azure OCRはしない。",
        "- 43は別システム修正中のため、上流スコープ除外に従いこのPackへ出さない。",
        "",
        "## Rows",
        "",
        "| # | Bundle | Scenario | Latest Evidence | Status | Blockers | Success Signals | Attention Signals | Safety Signals |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                str(value).replace("|", "/")
                for value in [
                    row.get("row_number", ""),
                    row.get("bundle", ""),
                    row.get("scenario", ""),
                    row.get("latest_evidence_file", ""),
                    row.get("status", ""),
                    row.get("blockers", ""),
                    row.get("evidence_success_signals", ""),
                    row.get("evidence_attention_signals", ""),
                    row.get("evidence_safety_signals", ""),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def build_start_here(payload: dict[str, Any], out_dir: Path) -> str:
    return "\n".join(
        [
            "# Minimum Operator Review Input 2026-06-23",
            "",
            "目的: 残10行の `operator_result/reviewer/reviewed_at` を、Codex自動確認または手動入力で記録する補助パックです。",
            "",
            "## 記入するファイル",
            f"- `{out_dir / MINIMUM_CSV_NAME}`",
            "",
            "## 迷わない入口",
            f"- 目視なしでCodex自動確認する場合: `{out_dir / AUTO_FILL_AND_APPLY_BAT_NAME}`",
            f"- 対話入力でCSVを作る場合: `{out_dir / GUIDED_FILL_BAT_NAME}`",
            f"- HTMLで入力する場合: `{out_dir / OPEN_BAT_NAME}`",
            f"- CSVを直接編集する場合: `{out_dir / MINIMUM_CSV_NAME}`",
            "- Codex自動確認は fixed safe-check summary と latest evidence 実在を確認し、通った行だけOKを作成します。",
            "- 対話入力/HTMLは手動入力補助として残します。",
            "",
            "## 記入ルール",
            "- `operator_result`: `OK` / `NG` / `HOLD` のいずれか。",
            "- `reviewer`: Codex自動確認の場合は `CodexAutoEvidenceCheck`、手動の場合は確認した人または確認責任者名。",
            "- `reviewed_at`: 確認日時。例 `2026-06-23T13:00:00`。",
            "- Codex自動確認では、固定安全ランナーが成功していない、またはlatest evidenceが無い行はOKにしない。",
            "- 手動入力では、latest evidence を確認せずに OK を入れない。",
            "",
            "## 記入後",
            f"1. Codex自動確認の場合は `{out_dir / AUTO_FILL_AND_APPLY_BAT_NAME}` だけを実行する。",
            f"2. 対話入力を使う場合は `{out_dir / GUIDED_FILL_BAT_NAME}` を実行し、画面の質問へ人が回答する。",
            f"3. HTMLで入力した場合は、CSVをダウンロードして `{out_dir / MINIMUM_CSV_NAME}` として上書き保存する。",
            f"4. CSVを直接編集した場合は、`{out_dir / MINIMUM_CSV_NAME}` を保存する。",
            f"5. 手動入力後は `{out_dir / APPLY_BAT_NAME}` を実行する。",
            "6. 反映後、既存の安全ランナーが同期と検証を行う。",
            "",
            "## 現在の件数",
            f"- row_count: `{payload['row_count']}`",
            f"- blank_operator_row_count: `{payload['blank_operator_row_count']}`",
            f"- scope_exclusion_count: `{payload['scope_exclusion_count']}`",
            f"- packet_scope_excluded_scenarios: `{', '.join(payload['packet_scope_excluded_scenarios'])}`",
            "",
            "## 既存の元ファイル",
            f"- `{payload['remaining_input_csv']}`",
        ]
    ) + "\n"


def build_html(payload: dict[str, Any], out_dir: Path) -> str:
    rows_json = json.dumps(payload["rows"], ensure_ascii=False)
    output_columns_json = json.dumps(MINIMUM_CSV_FIELDS, ensure_ascii=False)
    csv_path = out_dir / MINIMUM_CSV_NAME
    apply_bat_path = out_dir / APPLY_BAT_NAME
    auto_fill_bat_path = out_dir / AUTO_FILL_AND_APPLY_BAT_NAME
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Minimum Operator Review Input 2026-06-23</title>
<style>
:root {{ color-scheme: light; --bg: #f6f7fb; --panel: #ffffff; --ink: #1f2937; --muted: #667085; --line: #d0d5dd; --accent: #2563eb; --danger: #b42318; --warn: #b54708; --ok: #067647; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: Meiryo, "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }}
header {{ padding: 22px 28px 12px; }}
main {{ padding: 0 28px 28px; }}
h1 {{ margin: 0 0 8px; font-size: 24px; }}
p {{ line-height: 1.6; }}
.panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 16px; box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04); margin-bottom: 16px; }}
.warning {{ border-left: 5px solid var(--warn); }}
.actions {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
button {{ border: 1px solid var(--accent); background: var(--accent); color: white; border-radius: 10px; padding: 10px 14px; font-weight: 700; cursor: pointer; }}
button.secondary {{ background: white; color: var(--accent); }}
button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
.status {{ font-weight: 700; }}
.status.ok {{ color: var(--ok); }}
.status.warn {{ color: var(--warn); }}
.status.danger {{ color: var(--danger); }}
.path {{ font-family: Consolas, "Segoe UI Mono", monospace; overflow-wrap: anywhere; background: #f2f4f7; padding: 2px 5px; border-radius: 5px; }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); }}
th, td {{ border: 1px solid var(--line); padding: 8px; vertical-align: top; }}
th {{ background: #eef2ff; text-align: left; position: sticky; top: 0; z-index: 1; }}
tr.complete {{ background: #ecfdf3; }}
tr.partial {{ background: #fffaeb; }}
select, input {{ width: 100%; min-width: 120px; padding: 8px; border: 1px solid var(--line); border-radius: 8px; font-family: inherit; }}
.evidence {{ min-width: 320px; }}
.small {{ color: var(--muted); font-size: 12px; }}
.output {{ width: 100%; min-height: 150px; font-family: Consolas, "Segoe UI Mono", monospace; white-space: pre; }}
</style>
</head>
<body>
<header>
  <h1>残シナリオ 最小確認入力</h1>
  <div class="small">generated_at: {html.escape(str(payload["generated_at"]))}</div>
</header>
<main>
  <section class="panel warning">
    <p><strong>安全ルール:</strong> 目視なしで進める場合はCodex自動確認BATを使ってください。このHTMLは手動入力補助です。手動でOKを入れる場合はlatest evidenceを確認してください。</p>
    <p>保存先CSV: <span class="path">{html.escape(str(csv_path))}</span></p>
    <p>Codex自動確認: <span class="path">{html.escape(str(auto_fill_bat_path))}</span></p>
    <p>記入後に実行: <span class="path">{html.escape(str(apply_bat_path))}</span></p>
    <p>row_count: <strong>{payload["row_count"]}</strong> / scope_exclusion_count: <strong>{payload["scope_exclusion_count"]}</strong> / excluded: <strong>{html.escape(", ".join(payload["packet_scope_excluded_scenarios"]))}</strong></p>
  </section>

  <section class="panel">
    <div class="actions">
      <button type="button" id="fillReviewedAt" class="secondary">空の確認日時に現在時刻を入れる</button>
      <button type="button" id="buildCsv">CSVを作成</button>
      <button type="button" id="downloadCsv" disabled>CSVをダウンロード</button>
      <span id="completionStatus" class="status warn">未入力</span>
    </div>
    <p class="small">ダウンロードしたCSVを <span class="path">minimum_operator_review_input.csv</span> として同じフォルダへ上書き保存してからBATを実行してください。</p>
  </section>

  <section class="panel">
    <table id="reviewTable" aria-label="minimum operator review input">
      <thead>
        <tr>
          <th>#</th><th>bundle</th><th>scenario</th><th>operator_result</th>
          <th>reviewer</th><th>reviewed_at</th><th>latest evidence</th><th>evidence signals</th><th>status/blockers</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </section>

  <section class="panel">
    <h2>CSVプレビュー</h2>
    <textarea id="csvPreview" class="output" readonly></textarea>
  </section>
</main>
<script>
const reviewRows = {rows_json};
const outputColumns = {output_columns_json};
const tableBody = document.querySelector("#reviewTable tbody");
const completionStatus = document.getElementById("completionStatus");
const csvPreview = document.getElementById("csvPreview");
const downloadButton = document.getElementById("downloadCsv");
let latestCsvText = "";

function escapeHtml(value) {{
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\\\"", "&quot;")
    .replaceAll("'", "&#39;");
}}

function csvEscape(value) {{
  const text = String(value ?? "");
  if (/[",\\r\\n]/.test(text)) {{
    return `"${{text.replaceAll('"', '""')}}"`;
  }}
  return text;
}}

function getInput(rowNumber, fieldName) {{
  return document.querySelector(`[data-row="${{rowNumber}}"][data-field="${{fieldName}}"]`);
}}

function collectRows() {{
  return reviewRows.map((row) => ({{
    ...row,
    operator_result: getInput(row.row_number, "operator_result").value.trim(),
    reviewer: getInput(row.row_number, "reviewer").value.trim(),
    reviewed_at: getInput(row.row_number, "reviewed_at").value.trim()
  }}));
}}

function updateRowStyle(rowNumber) {{
  const result = getInput(rowNumber, "operator_result").value.trim();
  const reviewer = getInput(rowNumber, "reviewer").value.trim();
  const reviewedAt = getInput(rowNumber, "reviewed_at").value.trim();
  const tableRow = document.querySelector(`[data-table-row="${{rowNumber}}"]`);
  tableRow.classList.remove("complete", "partial");
  const filledCount = [result, reviewer, reviewedAt].filter(Boolean).length;
  if (filledCount === 3) {{
    tableRow.classList.add("complete");
  }} else if (filledCount > 0) {{
    tableRow.classList.add("partial");
  }}
}}

function updateStatus() {{
  const rows = collectRows();
  const completeCount = rows.filter((row) => row.operator_result && row.reviewer && row.reviewed_at).length;
  const partialCount = rows.filter((row) => [row.operator_result, row.reviewer, row.reviewed_at].some(Boolean) && !(row.operator_result && row.reviewer && row.reviewed_at)).length;
  completionStatus.textContent = `入力完了 ${{completeCount}} / ${{rows.length}}、途中入力 ${{partialCount}}`;
  completionStatus.className = "status " + (completeCount === rows.length ? "ok" : partialCount ? "danger" : "warn");
  for (const row of rows) {{
    updateRowStyle(row.row_number);
  }}
}}

function renderTable() {{
  tableBody.innerHTML = reviewRows.map((row) => `
    <tr data-table-row="${{row.row_number}}">
      <td>${{row.row_number}}</td>
      <td>${{escapeHtml(row.bundle)}}</td>
      <td>${{escapeHtml(row.scenario)}}</td>
      <td>
        <select data-row="${{row.row_number}}" data-field="operator_result">
          <option value=""></option>
          <option value="OK" ${{row.operator_result === "OK" ? "selected" : ""}}>OK</option>
          <option value="NG" ${{row.operator_result === "NG" ? "selected" : ""}}>NG</option>
          <option value="HOLD" ${{row.operator_result === "HOLD" ? "selected" : ""}}>HOLD</option>
        </select>
      </td>
      <td><input data-row="${{row.row_number}}" data-field="reviewer" value="${{escapeHtml(row.reviewer)}}" placeholder="確認者名"></td>
      <td><input data-row="${{row.row_number}}" data-field="reviewed_at" value="${{escapeHtml(row.reviewed_at)}}" placeholder="2026-06-23T13:00:00"></td>
      <td class="evidence"><a href="${{escapeHtml(row.latest_evidence_uri)}}" target="_blank">開く</a><br><span class="small">${{escapeHtml(row.latest_evidence_file)}}</span></td>
      <td><span class="small"><strong>成功:</strong> ${{escapeHtml(row.evidence_success_signals)}}<br><strong>注意:</strong> ${{escapeHtml(row.evidence_attention_signals)}}<br><strong>安全:</strong> ${{escapeHtml(row.evidence_safety_signals)}}</span></td>
      <td><span class="small">${{escapeHtml(row.status)}}<br>${{escapeHtml(row.blockers)}}</span></td>
    </tr>
  `).join("");
  tableBody.querySelectorAll("select,input").forEach((inputElement) => {{
    inputElement.addEventListener("input", () => {{
      latestCsvText = "";
      csvPreview.value = "";
      downloadButton.disabled = true;
      updateStatus();
    }});
  }});
  updateStatus();
}}

function buildCsv() {{
  const rows = collectRows();
  const lines = [outputColumns.join(",")];
  for (const row of rows) {{
    lines.push(outputColumns.map((columnName) => csvEscape(row[columnName])).join(","));
  }}
  latestCsvText = "\\ufeff" + lines.join("\\r\\n") + "\\r\\n";
  csvPreview.value = latestCsvText;
  downloadButton.disabled = false;
  updateStatus();
}}

function downloadCsv() {{
  if (!latestCsvText) {{
    buildCsv();
  }}
  const blob = new Blob([latestCsvText], {{ type: "text/csv;charset=utf-8" }});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "minimum_operator_review_input.csv";
  document.body.appendChild(link);
  link.click();
  URL.revokeObjectURL(link.href);
  link.remove();
}}

document.getElementById("buildCsv").addEventListener("click", buildCsv);
document.getElementById("downloadCsv").addEventListener("click", downloadCsv);
document.getElementById("fillReviewedAt").addEventListener("click", () => {{
  const now = new Date();
  const offsetMs = now.getTimezoneOffset() * 60000;
  const localIso = new Date(now.getTime() - offsetMs).toISOString().slice(0, 19);
  for (const row of reviewRows) {{
    const reviewedAt = getInput(row.row_number, "reviewed_at");
    if (!reviewedAt.value.trim()) {{
      reviewedAt.value = localIso;
    }}
  }}
  latestCsvText = "";
  csvPreview.value = "";
  downloadButton.disabled = true;
  updateStatus();
}});

renderTable();
</script>
</body>
</html>
"""


def build_open_bat(out_dir: Path) -> str:
    return "\r\n".join(
        [
            "@echo off",
            "setlocal",
            'set "PACK_DIR=%~dp0"',
            'start "" "%PACK_DIR%minimum_operator_review_input.html"',
            'start "" "%PACK_DIR%"',
            "",
        ]
    )


def build_guided_fill_ps1() -> str:
    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "$packDir = Split-Path -Parent $MyInvocation.MyCommand.Path",
            "$csvPath = Join-Path $packDir 'minimum_operator_review_input.csv'",
            "if (-not (Test-Path -LiteralPath $csvPath)) { throw \"CSV not found: $csvPath\" }",
            "$rows = @(Import-Csv -LiteralPath $csvPath -Encoding UTF8)",
            "if ($rows.Count -eq 0) { throw \"No rows found in $csvPath\" }",
            "$backupPath = Join-Path $packDir (\"minimum_operator_review_input.csv.before_guided_fill_{0}.csv\" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))",
            "Copy-Item -LiteralPath $csvPath -Destination $backupPath -Force",
            "Write-Host 'Minimum operator review guided input'",
            "Write-Host 'This tool only records human-entered OK/NG/HOLD, reviewer, reviewed_at.'",
            "Write-Host 'It does not auto-approve, run RK10, send mail, print, submit, pay, or call paid OCR.'",
            "Write-Host ('Backup: {0}' -f $backupPath)",
            "$reviewer = Read-Host 'Reviewer name (required)'",
            "while ([string]::IsNullOrWhiteSpace($reviewer)) { $reviewer = Read-Host 'Reviewer name is required' }",
            "$defaultReviewedAt = Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'",
            "$reviewedAt = Read-Host (\"Reviewed_at [{0}]\" -f $defaultReviewedAt)",
            "if ([string]::IsNullOrWhiteSpace($reviewedAt)) { $reviewedAt = $defaultReviewedAt }",
            "$allowed = @('OK', 'NG', 'HOLD')",
            "foreach ($row in $rows) {",
            "  Write-Host ''",
            "  Write-Host ('[{0}] scenario {1}' -f $row.bundle, $row.scenario)",
            "  Write-Host ('Evidence: {0}' -f $row.latest_evidence_file)",
            "  if ($row.evidence_success_signals) { Write-Host ('Success: {0}' -f $row.evidence_success_signals) }",
            "  if ($row.evidence_attention_signals) { Write-Host ('Attention: {0}' -f $row.evidence_attention_signals) }",
            "  if ($row.evidence_safety_signals) { Write-Host ('Safety: {0}' -f $row.evidence_safety_signals) }",
            "  $current = [string]$row.operator_result",
            "  $prompt = 'operator_result OK/NG/HOLD'",
            "  if (-not [string]::IsNullOrWhiteSpace($current)) { $prompt = \"operator_result OK/NG/HOLD [$current]\" }",
            "  $result = Read-Host $prompt",
            "  if ([string]::IsNullOrWhiteSpace($result) -and -not [string]::IsNullOrWhiteSpace($current)) { $result = $current }",
            "  $result = $result.Trim().ToUpperInvariant()",
            "  while ($allowed -notcontains $result) {",
            "    $result = (Read-Host 'Enter exactly OK, NG, or HOLD').Trim().ToUpperInvariant()",
            "  }",
            "  $row.operator_result = $result",
            "  $row.reviewer = $reviewer",
            "  $row.reviewed_at = $reviewedAt",
            "}",
            "$rows | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8",
            "Write-Host ''",
            "Write-Host ('Updated: {0}' -f $csvPath)",
            "Write-Host 'Next: run APPLY_AND_RUN_AFTER_FILL_minimum_operator_review_input.bat'",
            "",
        ]
    )


def build_guided_fill_bat() -> str:
    return "\r\n".join(
        [
            "@echo off",
            "setlocal",
            'set "PACK_DIR=%~dp0"',
            f'set "SCRIPT=%PACK_DIR%{GUIDED_FILL_PS1_NAME}"',
            'if not exist "%SCRIPT%" (',
            '  echo Missing guided fill script: "%SCRIPT%"',
            "  pause",
            "  exit /b 1",
            ")",
            'powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"',
            "if errorlevel 1 (",
            "  echo Guided input failed.",
            "  pause",
            "  exit /b 1",
            ")",
            "pause",
            "",
        ]
    )


def build_auto_fill_and_apply_bat() -> str:
    return "\r\n".join(
        [
            "@echo off",
            "setlocal",
            'set "PACK_DIR=%~dp0"',
            'for %%I in ("%PACK_DIR%..") do set "REPORTS_DIR=%%~fI"',
            'for %%I in ("%REPORTS_DIR%\\..\\..") do set "ROOT_DIR=%%~fI"',
            'set "PY=C:\\Users\\masam\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"',
            'if not exist "%PY%" set "PY=python"',
            'set "AUTO_FILL_TOOL=%ROOT_DIR%\\tools\\auto_fill_minimum_operator_review_input_20260623.py"',
            'set "MINIMUM_CSV=%PACK_DIR%minimum_operator_review_input.csv"',
            'set "SAFE_JSON=%REPORTS_DIR%\\safe_goal_checks_20260620\\safe_goal_checks_summary.json"',
            'set "SAFE_MD=%REPORTS_DIR%\\safe_goal_checks_20260620\\safe_goal_checks_summary.md.numbered"',
            'set "APPLY_BAT=%PACK_DIR%APPLY_AND_RUN_AFTER_FILL_minimum_operator_review_input.bat"',
            "",
            'if not exist "%AUTO_FILL_TOOL%" (',
            '  echo Missing Codex auto evidence tool: "%AUTO_FILL_TOOL%"',
            "  echo Run this from the canonical working repository, not from a detached review-only copy.",
            "  pause",
            "  exit /b 1",
            ")",
            'if not exist "%MINIMUM_CSV%" (',
            '  echo Missing minimum CSV: "%MINIMUM_CSV%"',
            "  pause",
            "  exit /b 1",
            ")",
            'if not exist "%APPLY_BAT%" (',
            '  echo Missing apply BAT: "%APPLY_BAT%"',
            "  pause",
            "  exit /b 1",
            ")",
            "",
            "echo [1/2] Codex auto evidence review fills the final 10 rows...",
            '"%PY%" -X utf8 "%AUTO_FILL_TOOL%" --minimum-csv "%MINIMUM_CSV%" --safe-summary-json "%SAFE_JSON%" --safe-summary-md "%SAFE_MD%" --out-dir "%PACK_DIR%codex_auto_evidence_review"',
            "if errorlevel 1 (",
            '  echo Codex auto evidence review failed. Check "%PACK_DIR%codex_auto_evidence_review".',
            "  pause",
            "  exit /b 1",
            ")",
            "",
            "echo [2/2] Applying filled rows and running fixed safe checks...",
            'call "%APPLY_BAT%"',
            "exit /b %ERRORLEVEL%",
            "",
        ]
    )


def build_apply_bat(out_dir: Path) -> str:
    return "\r\n".join(
        [
            "@echo off",
            "setlocal",
            'set "PACK_DIR=%~dp0"',
            'for %%I in ("%PACK_DIR%..") do set "REPORTS_DIR=%%~fI"',
            'for %%I in ("%REPORTS_DIR%\\..\\..") do set "ROOT_DIR=%%~fI"',
            'set "TOOLS_RUNNER=%ROOT_DIR%\\tools\\run_safe_goal_checks_20260620_ai_default_probe_20260622.py"',
            'set "MINIMUM_CSV=%PACK_DIR%minimum_operator_review_input.csv"',
            f'set "APPLY_SCRIPT=%PACK_DIR%{APPLY_SCRIPT_NAME}"',
            'set "TARGET_CSV=%REPORTS_DIR%\\remaining_operator_input_packet_20260623\\remaining_operator_input.csv"',
            'set "AFTER_FILL_BAT=%REPORTS_DIR%\\remaining_operator_input_packet_20260623\\RUN_AFTER_FILL_remaining_operator_input.bat"',
            'set "PY=C:\\Users\\masam\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"',
            'if not exist "%PY%" set "PY=python"',
            "",
            'if not exist "%TOOLS_RUNNER%" (',
            "  echo This copied kit is review/input only.",
            "  echo Final apply and safe runner must be executed from the canonical working repository.",
            '  echo Missing: "%TOOLS_RUNNER%"',
            "  pause",
            "  exit /b 1",
            ")",
            'if not exist "%APPLY_SCRIPT%" (',
            '  echo Missing apply script: "%APPLY_SCRIPT%"',
            "  pause",
            "  exit /b 1",
            ")",
            'if not exist "%TARGET_CSV%" (',
            '  echo Missing target CSV: "%TARGET_CSV%"',
            "  pause",
            "  exit /b 1",
            ")",
            'if not exist "%AFTER_FILL_BAT%" (',
            '  echo Missing after-fill BAT: "%AFTER_FILL_BAT%"',
            "  pause",
            "  exit /b 1",
            ")",
            "",
            'cd /d "%ROOT_DIR%"',
            "echo [1/2] Applying minimum operator review input...",
            '"%PY%" -X utf8 "%APPLY_SCRIPT%" --minimum-csv "%MINIMUM_CSV%" --target-csv "%TARGET_CSV%" --out-dir "%PACK_DIR%apply_results"',
            "if errorlevel 1 (",
            '  echo Apply failed. Check "%PACK_DIR%apply_results".',
            "  pause",
            "  exit /b 1",
            ")",
            "",
            "echo [2/2] Running existing after-fill sync and safe checks...",
            'call "%AFTER_FILL_BAT%"',
            "pause",
            "",
        ]
    )


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / PACK_JSON_NAME
    csv_path = out_dir / MINIMUM_CSV_NAME
    md_path = out_dir / PACK_MD_NAME
    summary_path = out_dir / SUMMARY_MD_NAME
    start_here_path = out_dir / START_HERE_NAME
    html_path = out_dir / HTML_NAME
    open_bat_path = out_dir / OPEN_BAT_NAME
    apply_bat_path = out_dir / APPLY_BAT_NAME
    guided_fill_ps1_path = out_dir / GUIDED_FILL_PS1_NAME
    guided_fill_bat_path = out_dir / GUIDED_FILL_BAT_NAME
    auto_fill_and_apply_bat_path = out_dir / AUTO_FILL_AND_APPLY_BAT_NAME

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, payload["rows"])
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    summary_path.write_text(build_summary_markdown(payload), encoding="utf-8")
    start_here_path.write_text(build_start_here(payload, out_dir), encoding="utf-8")
    html_path.write_text(build_html(payload, out_dir), encoding="utf-8")
    open_bat_path.write_text(build_open_bat(out_dir), encoding="ascii")
    apply_bat_path.write_text(build_apply_bat(out_dir), encoding="ascii")
    guided_fill_ps1_path.write_text(build_guided_fill_ps1(), encoding="utf-8-sig")
    guided_fill_bat_path.write_text(build_guided_fill_bat(), encoding="ascii")
    auto_fill_and_apply_bat_path.write_text(
        build_auto_fill_and_apply_bat(),
        encoding="ascii",
    )
    for path in [
        json_path,
        csv_path,
        md_path,
        summary_path,
        start_here_path,
        html_path,
        open_bat_path,
        apply_bat_path,
        guided_fill_ps1_path,
        guided_fill_bat_path,
        auto_fill_and_apply_bat_path,
    ]:
        write_numbered_copy(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate minimum operator-review input UI."
    )
    parser.add_argument("--remaining-input-csv", type=Path, default=DEFAULT_REMAINING_INPUT_CSV)
    parser.add_argument("--final-review-json", type=Path, default=DEFAULT_FINAL_REVIEW_JSON)
    parser.add_argument("--input-packet-json", type=Path, default=DEFAULT_INPUT_PACKET_JSON)
    parser.add_argument("--existing-minimum-csv", type=Path, default=DEFAULT_EXISTING_MINIMUM_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    payload = build_payload(
        args.remaining_input_csv,
        args.final_review_json,
        args.input_packet_json,
        args.existing_minimum_csv,
    )
    write_outputs(payload, args.out_dir)
    print(
        json.dumps(
            {key: value for key, value in payload.items() if key != "rows"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
