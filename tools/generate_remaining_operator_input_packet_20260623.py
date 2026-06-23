"""Generate one consolidated operator-input packet for unapproved rows.

The packet is an operator aid only. It does not approve rows, submit data,
send mail, print, pay, run RK10, call Azure, or write production files.
"""

from __future__ import annotations

import csv
import json
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
DEFAULT_FILL_QUEUE_JSON = (
    REPORTS / "final_evidence_fill_queue_20260621" / "final_evidence_fill_queue.json"
)
DEFAULT_UNIFIED_INPUT_CSV = (
    REPORTS
    / "unified_final_evidence_intake_20260621"
    / "unified_final_evidence_input.csv"
)
DEFAULT_OUT_DIR = REPORTS / "remaining_operator_input_packet_20260623"
DEFAULT_EXISTING_INPUT_CSV = DEFAULT_OUT_DIR / "remaining_operator_input.csv"
DEFAULT_EVIDENCE_DIGEST_JSON = (
    REPORTS
    / "remaining_operator_evidence_digest_20260623"
    / "remaining_operator_evidence_digest.json"
)
DEFAULT_EVIDENCE_DIGEST_MD = (
    REPORTS
    / "remaining_operator_evidence_digest_20260623"
    / "remaining_operator_evidence_digest.md.numbered"
)
DEFAULT_SCOPE_EXCLUSIONS_JSON = (
    REPORTS / "objective_scope_exclusions_20260623" / "objective_scope_exclusions.json"
)
BLANK_OPERATOR_FIELDS = ("operator_result", "reviewer", "reviewed_at")
FIXED_SAFE_RUNNER = (
    ROOT / "tools" / "run_safe_goal_checks_20260620_ai_default_probe_20260622.py"
)
READY_VALIDATOR = (
    ROOT / "tools" / "validate_remaining_operator_input_ready_20260623.py"
)
FIELD_RUNNER_PYTHON = Path(
    r"C:\Users\masam\AppData\Local\Programs\Python\Python313\python.exe"
)
AFTER_FILL_BAT_NAME = "RUN_AFTER_FILL_remaining_operator_input.bat"
OPEN_REVIEW_BAT_NAME = "OPEN_REVIEW_remaining_operator_evidence.bat"
START_HERE_NAME = "START_HERE_remaining_operator_input.md"
LICENSE_POLICY = (
    "RK10ライセンス画面は既定のRPA開発版AI付きのまま、"
    "ラジオボタンを変更せずOKのみ押す。"
)


@dataclass(frozen=True)
class RemainingOperatorInputRow:
    bundle: str
    scenario: str
    operator_result: str
    reviewer: str
    reviewed_at: str
    evidence_path: str
    evidence_exists: str
    missing_fields: str
    source_packet_csv: str
    source_unified_input_csv: str
    start_here_path: str
    current_safe_evidence: str
    current_safe_evidence_scope: str
    latest_evidence_file: str
    attention_terms: str
    human_or_external_input_needed: str
    allowed_operator_result_values: str
    hard_stop: str
    after_action_command: str
    copy_instruction: str


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def packet_row_lookup(paths: list[str]) -> dict[tuple[str, str], dict[str, str]]:
    rows_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for path_text in sorted(set(paths)):
        path = Path(path_text)
        for row in read_csv_rows(path):
            key = (
                str(row.get("bundle", "")).strip(),
                str(row.get("scenario", "")).strip(),
            )
            if key[0] and key[1]:
                rows_by_key[key] = row
    return rows_by_key


def entry_key(bundle: str, scenario: str) -> tuple[str, str]:
    return bundle.strip(), scenario.strip()


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


def existing_operator_fields(path: Path | None) -> dict[tuple[str, str], dict[str, str]]:
    if path is None:
        return {}
    rows = read_csv_rows(path)
    values_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = entry_key(str(row.get("bundle", "")), str(row.get("scenario", "")))
        if not key[0] or not key[1]:
            continue
        values_by_key[key] = {
            field: str(row.get(field, "")).strip() for field in BLANK_OPERATOR_FIELDS
        }
    return values_by_key


def fill_queue_by_bundle(fill_queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = fill_queue.get("rows", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("bundle", "")).strip(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("bundle", "")).strip()
    }


def digest_by_key(digest: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = digest.get("rows", [])
    if not isinstance(rows, list):
        return {}
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = entry_key(str(row.get("bundle", "")), str(row.get("scenario", "")))
        if key[0] and key[1]:
            output[key] = row
    return output


def build_rows(
    execution_validation: dict[str, Any],
    fill_queue: dict[str, Any],
    unified_input_csv: Path,
    evidence_digest: dict[str, Any] | None = None,
    preserved_operator_fields: dict[tuple[str, str], dict[str, str]] | None = None,
    excluded_scenarios: set[str] | None = None,
) -> list[RemainingOperatorInputRow]:
    validation_rows = execution_validation.get("rows", [])
    if not isinstance(validation_rows, list):
        validation_rows = []
    packet_paths = [
        str(row.get("csv_path", "")).strip()
        for row in validation_rows
        if isinstance(row, dict) and str(row.get("csv_path", "")).strip()
    ]
    packet_rows = packet_row_lookup(packet_paths)
    queue_by_bundle = fill_queue_by_bundle(fill_queue)
    digest_rows = digest_by_key(evidence_digest or {})
    preserved_operator_fields = preserved_operator_fields or {}
    excluded_scenarios = excluded_scenarios or set()
    output_rows: list[RemainingOperatorInputRow] = []
    for row in validation_rows:
        if not isinstance(row, dict) or bool(row.get("approved")):
            continue
        if row_is_scope_excluded(row, excluded_scenarios):
            continue
        bundle = str(row.get("bundle", "")).strip()
        scenario = str(row.get("scenario", "")).strip()
        packet_row = packet_rows.get((bundle, scenario), {})
        queue_row = queue_by_bundle.get(bundle, {})
        digest_row = digest_rows.get((bundle, scenario), {})
        preserved = preserved_operator_fields.get((bundle, scenario), {})
        output_rows.append(
            RemainingOperatorInputRow(
                bundle=bundle,
                scenario=scenario,
                operator_result=preserved.get("operator_result", ""),
                reviewer=preserved.get("reviewer", ""),
                reviewed_at=preserved.get("reviewed_at", ""),
                evidence_path=str(row.get("evidence_path", "")).strip(),
                evidence_exists=str(bool(row.get("evidence_exists"))),
                missing_fields=str(row.get("missing_fields", "")).strip(),
                source_packet_csv=str(row.get("csv_path", "")).strip(),
                source_unified_input_csv=str(unified_input_csv),
                start_here_path=str(queue_row.get("start_here_path", "")).strip(),
                current_safe_evidence=str(packet_row.get("current_safe_evidence", "")).strip(),
                current_safe_evidence_scope=str(
                    packet_row.get("current_safe_evidence_scope", "")
                ).strip(),
                latest_evidence_file=str(digest_row.get("latest_evidence_file", "")).strip(),
                attention_terms=str(digest_row.get("attention_terms", "")).strip(),
                human_or_external_input_needed=str(
                    digest_row.get("human_or_external_input_needed", "")
                ).strip(),
                allowed_operator_result_values="OK / NG / HOLD",
                hard_stop=str(queue_row.get("forbidden", "")).strip(),
                after_action_command=str(queue_row.get("after_action_command", "")).strip(),
                copy_instruction=(
                    "Fill only operator_result/reviewer/reviewed_at, then run the "
                    "fixed safe runner. The sync tool copies complete stamps to "
                    "source_packet_csv and source_unified_input_csv."
                ),
            )
        )
    return output_rows


def build_payload(
    execution_validation_json: Path = DEFAULT_EXECUTION_VALIDATION_JSON,
    fill_queue_json: Path = DEFAULT_FILL_QUEUE_JSON,
    unified_input_csv: Path = DEFAULT_UNIFIED_INPUT_CSV,
    existing_input_csv: Path | None = DEFAULT_EXISTING_INPUT_CSV,
    evidence_digest_json: Path = DEFAULT_EVIDENCE_DIGEST_JSON,
    scope_exclusions_json: Path = DEFAULT_SCOPE_EXCLUSIONS_JSON,
) -> dict[str, Any]:
    execution_validation = read_json(execution_validation_json)
    fill_queue = read_json(fill_queue_json)
    evidence_digest = read_optional_json(evidence_digest_json)
    scope_payload = read_optional_json(scope_exclusions_json)
    excluded_scenarios = load_scope_excluded_scenarios(scope_payload)
    preserved = existing_operator_fields(existing_input_csv)
    raw_rows = build_rows(
        execution_validation,
        fill_queue,
        unified_input_csv,
        evidence_digest,
        preserved,
    )
    rows = build_rows(
        execution_validation,
        fill_queue,
        unified_input_csv,
        evidence_digest,
        preserved,
        excluded_scenarios,
    )
    bundles = sorted({row.bundle for row in rows})
    preserved_row_count = sum(
        1
        for row in rows
        if any(getattr(row, field) for field in BLANK_OPERATOR_FIELDS)
    )
    preserved_complete_row_count = sum(
        1
        for row in rows
        if all(getattr(row, field) for field in BLANK_OPERATOR_FIELDS)
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": (
            "operator aid only; no approval, no external operation, no production "
            "write, no RK10 ButtonRun"
        ),
        "source_execution_validation_json": str(execution_validation_json),
        "source_fill_queue_json": str(fill_queue_json),
        "source_unified_input_csv": str(unified_input_csv),
        "source_evidence_digest_json": str(evidence_digest_json),
        "source_evidence_digest_exists": evidence_digest_json.exists(),
        "source_evidence_digest_markdown": str(DEFAULT_EVIDENCE_DIGEST_MD),
        "source_scope_exclusions_json": str(scope_exclusions_json),
        "scope_excluded_scenarios": sorted(excluded_scenarios),
        "scope_excluded_row_count": len(raw_rows) - len(rows),
        "raw_row_count": len(raw_rows),
        "row_count": len(rows),
        "bundle_count": len(bundles),
        "bundles": bundles,
        "operator_fields_prefilled": 0,
        "operator_fields_preserved_from_existing_csv": preserved_row_count,
        "operator_complete_rows_preserved_from_existing_csv": preserved_complete_row_count,
        "blank_operator_fields": list(BLANK_OPERATOR_FIELDS),
        "after_fill_bat_name": AFTER_FILL_BAT_NAME,
        "open_review_bat_name": OPEN_REVIEW_BAT_NAME,
        "start_here_name": START_HERE_NAME,
        "after_fill_command": (
            f'"{FIELD_RUNNER_PYTHON}" -X utf8 "{FIXED_SAFE_RUNNER}" --s12-exit-code 2'
        ),
        "after_fill_precheck_command": (
            f'"{FIELD_RUNNER_PYTHON}" -X utf8 "{READY_VALIDATOR}" --fail-on-not-ready'
        ),
        "license_policy": LICENSE_POLICY,
        "rows": [asdict(row) for row in rows],
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(RemainingOperatorInputRow)]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Remaining Operator Input Packet 2026-06-23",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- bundle_count: `{payload['bundle_count']}`",
        f"- operator_fields_prefilled: `{payload['operator_fields_prefilled']}`",
        f"- operator_fields_preserved_from_existing_csv: `{payload['operator_fields_preserved_from_existing_csv']}`",
        f"- operator_complete_rows_preserved_from_existing_csv: `{payload['operator_complete_rows_preserved_from_existing_csv']}`",
        f"- blank_operator_fields: `{', '.join(payload['blank_operator_fields'])}`",
        f"- source_evidence_digest_json: `{payload['source_evidence_digest_json']}`",
        f"- source_evidence_digest_exists: `{payload['source_evidence_digest_exists']}`",
        f"- source_evidence_digest_markdown: `{payload['source_evidence_digest_markdown']}`",
        f"- source_scope_exclusions_json: `{payload['source_scope_exclusions_json']}`",
        f"- raw_row_count: `{payload['raw_row_count']}`",
        f"- scope_excluded_row_count: `{payload['scope_excluded_row_count']}`",
        f"- start_here: `{payload['start_here_name']}`",
        f"- open_review_bat: `{payload['open_review_bat_name']}`",
        f"- after_fill_bat: `{payload['after_fill_bat_name']}`",
        f"- after_fill_precheck_command: `{payload['after_fill_precheck_command']}`",
        f"- after_fill_command: `{payload['after_fill_command']}`",
        f"- license_policy: `{payload['license_policy']}`",
        f"- safety: `{payload['safety']}`",
        "",
        "## How To Use",
        "",
        f"1. Open `{payload['start_here_name']}` first.",
        f"2. Double-click `{payload['open_review_bat_name']}` to open the review digest and input CSV together.",
        "3. Fill only `operator_result`, `reviewer`, and `reviewed_at` in `remaining_operator_input.csv`.",
        f"4. Save the CSV, then double-click `{payload['after_fill_bat_name']}`.",
        "5. The sync step copies complete stamps to each row's `source_packet_csv` and `source_unified_input_csv`.",
        "6. Do not run production registration, mail, print, payment, Azure paid OCR, or RK10 ButtonRun from this packet.",
        "",
        "## Rows",
        "",
        "| Bundle | Scenario | Missing Fields | Evidence Exists | Attention | Latest Evidence | Human/External Needed | Hard Stop |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                str(row.get(key, "")).replace("|", "/")
                for key in [
                    "bundle",
                    "scenario",
                    "missing_fields",
                    "evidence_exists",
                    "attention_terms",
                    "latest_evidence_file",
                    "human_or_external_input_needed",
                    "hard_stop",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def build_after_fill_bat() -> str:
    return "\n".join(
        [
            "@echo off",
            "setlocal",
            f'set "REPO={ROOT}"',
            f'set "PY={FIELD_RUNNER_PYTHON}"',
            'set "PRECHECK=%REPO%\\tools\\validate_remaining_operator_input_ready_20260623.py"',
            'set "RUNNER=%REPO%\\tools\\run_safe_goal_checks_20260620_ai_default_probe_20260622.py"',
            'if not exist "%PY%" set "PY=python"',
            'cd /d "%REPO%"',
            "echo [1/2] Validating remaining_operator_input.csv before safe checks.",
            '"%PY%" -X utf8 "%PRECHECK%" --fail-on-not-ready',
            'set "PRECHECK_RC=%ERRORLEVEL%"',
            'if not "%PRECHECK_RC%"=="0" echo Remaining operator input is not ready. Fix the CSV before running safe checks.',
            'if not "%PRECHECK_RC%"=="0" pause',
            'if not "%PRECHECK_RC%"=="0" exit /b %PRECHECK_RC%',
            "echo [2/2] Running fixed safe checks after remaining_operator_input.csv update.",
            '"%PY%" -X utf8 "%RUNNER%" --s12-exit-code 2',
            'set "RC=%ERRORLEVEL%"',
            "echo Exit code: %RC%",
            "echo Check report:",
            "echo %REPO%\\plans\\reports\\goal_completion_gate_20260620\\goal_completion_gate.md.numbered",
            'if not "%RC%"=="0" echo Safe runner failed. Do not proceed.',
            "pause",
            "exit /b %RC%",
        ]
    ) + "\n"


def build_open_review_bat(out_dir: Path, payload: dict[str, Any]) -> str:
    start_here = out_dir / str(payload["start_here_name"])
    input_csv = out_dir / "remaining_operator_input.csv"
    digest_md = Path(str(payload["source_evidence_digest_markdown"]))
    return "\n".join(
        [
            "@echo off",
            "setlocal",
            f'start "" "{start_here}"',
            f'start "" "{input_csv}"',
            f'if exist "{digest_md}" start "" "{digest_md}"',
            "exit /b 0",
        ]
    ) + "\n"


def build_start_here_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Remaining Operator Input START HERE 2026-06-23",
            "",
            "## Purpose",
            "",
            "- This packet is only for entering the remaining operator review stamps.",
            "- It does not approve rows automatically and does not run production operations.",
            "",
            "## Fill These Fields Only",
            "",
            "- `operator_result`: use `OK`, `NG`, or `HOLD`.",
            "- `reviewer`: enter the reviewer/operator name.",
            "- `reviewed_at`: enter the review timestamp.",
            "",
            "## One-Click After Fill",
            "",
            f"1. Save `remaining_operator_input.csv` in this folder.",
            f"2. If you need to review evidence first, double-click `{payload['open_review_bat_name']}`.",
            f"3. Double-click `{payload['after_fill_bat_name']}`.",
            "4. Confirm `goal_completion_gate.md.numbered` after the runner finishes.",
            "",
            "## Review Evidence First",
            "",
            f"- Review digest: `{payload['source_evidence_digest_markdown']}`",
            f"- Digest exists now: `{payload['source_evidence_digest_exists']}`",
            f"- Open helper: `{payload['open_review_bat_name']}`",
            "",
            "## Safety Boundary",
            "",
            f"- {payload['license_policy']}",
            "- Do not run RK10 ButtonRun from this packet.",
            "- Do not perform production writes, real mail, real print, final submit, payment execution, paid Azure OCR, or temporary Rakuraku data creation/deletion from this packet.",
            "",
            "## Current Counts",
            "",
            f"- row_count: `{payload['row_count']}`",
            f"- bundle_count: `{payload['bundle_count']}`",
            f"- operator_fields_preserved_from_existing_csv: `{payload['operator_fields_preserved_from_existing_csv']}`",
            f"- operator_complete_rows_preserved_from_existing_csv: `{payload['operator_complete_rows_preserved_from_existing_csv']}`",
            "",
        ]
    )


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "remaining_operator_input_packet.json"
    csv_path = out_dir / "remaining_operator_input.csv"
    md_path = out_dir / "remaining_operator_input_packet.md"
    start_here_path = out_dir / str(payload["start_here_name"])
    after_fill_bat_path = out_dir / str(payload["after_fill_bat_name"])
    open_review_bat_path = out_dir / str(payload["open_review_bat_name"])
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, payload["rows"])
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    start_here_path.write_text(build_start_here_markdown(payload), encoding="utf-8")
    after_fill_bat_path.write_text(build_after_fill_bat(), encoding="ascii")
    open_review_bat_path.write_text(build_open_review_bat(out_dir, payload), encoding="ascii")
    write_numbered_copy(json_path)
    write_numbered_copy(csv_path)
    write_numbered_copy(md_path)
    write_numbered_copy(start_here_path)


def main() -> int:
    payload = build_payload()
    write_outputs(payload)
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
