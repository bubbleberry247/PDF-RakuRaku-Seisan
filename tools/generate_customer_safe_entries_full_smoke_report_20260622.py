from __future__ import annotations

import argparse
import base64
import csv
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORT_DIR = ROOT / "plans" / "reports" / "customer_safe_entries_full_smoke_20260622"
CANONICAL_REPORT_JSON = REPORT_DIR / "customer_safe_entries_full_smoke_20260622.json"
SCENARIO_MATRIX_JSON = REPORT_DIR / "customer_safe_entries_scenario_matrix_20260622.json"
SCENARIO_MATRIX_CSV = REPORT_DIR / "customer_safe_entries_scenario_matrix_20260622.csv"
SCENARIO_MATRIX_MD = REPORT_DIR / "customer_safe_entries_scenario_matrix_20260622.md"
ACTUAL_EXECUTION_TRACE_JSON = (
    REPORT_DIR / "customer_safe_entries_actual_execution_trace_20260623.json"
)
ACTUAL_EXECUTION_TRACE_CSV = (
    REPORT_DIR / "customer_safe_entries_actual_execution_trace_20260623.csv"
)
ACTUAL_EXECUTION_TRACE_MD = (
    REPORT_DIR / "customer_safe_entries_actual_execution_trace_20260623.md"
)
CUSTOMER_SAFE_ENTRY_PS1 = Path(
    r"C:\ProgramData\RK10\Robots\migration\customer_safe_entries_20260622"
    r"\run_customer_safe_entry.ps1"
)

SCENARIO_LABELS_BY_ENTRY: dict[str, tuple[str, ...]] = {
    "12_13_scan": ("12/13",),
    "37_sample": ("37",),
    "37_review": ("37",),
    "38_precheck": ("38",),
    "42_csv_dryrun": ("42",),
    "42_review": ("42",),
    "43_selftest": ("43",),
    "43_noop": ("43",),
    "44_review": ("44",),
    "47_dryrun": ("47",),
    "51_52_excel": ("51/52",),
    "51_52_future": ("51/52",),
    "55_v2": ("55",),
    "56_local": ("56",),
    "56_prod": ("56",),
    "57_dryrun": ("57",),
    "58_gui": ("58",),
    "63_review": ("63",),
    "63_dryrun_8": ("63",),
    "70_review": ("70",),
    "70_confirm": ("70",),
    "71_pytest": ("71",),
}

SCENARIO_MATRIX_FIELDS = [
    "scenario",
    "entry_count",
    "expected_ok_count",
    "unexpected_count",
    "timeout_count",
    "cleanup_remaining_count",
    "entry_names",
    "entry_details",
    "stdout_paths",
    "stderr_paths",
    "safety_scope",
    "production_completion_scope",
    "next_gap",
]
ACTUAL_EXECUTION_TRACE_FIELDS = [
    "scenario",
    "entry_name",
    "bat_path",
    "bat_exists",
    "ps1_path",
    "ps1_exists",
    "ps1_entry",
    "ps1_entry_resolved",
    "command_kind",
    "script_paths",
    "script_exists_count",
    "script_missing_count",
    "file_types",
    "exit_code",
    "expected_exit_codes",
    "expected_ok",
    "timed_out",
    "elapsed_seconds",
    "stdout_path",
    "stdout_exists",
    "stderr_path",
    "stderr_exists",
    "safety_scope",
]


@dataclass(frozen=True)
class ScenarioEvidenceRow:
    scenario: str
    entry_count: int
    expected_ok_count: int
    unexpected_count: int
    timeout_count: int
    cleanup_remaining_count: int
    entry_names: str
    entry_details: str
    stdout_paths: str
    stderr_paths: str
    safety_scope: str
    production_completion_scope: str
    next_gap: str


@dataclass(frozen=True)
class ActualExecutionTraceRow:
    scenario: str
    entry_name: str
    bat_path: str
    bat_exists: str
    ps1_path: str
    ps1_exists: str
    ps1_entry: str
    ps1_entry_resolved: str
    command_kind: str
    script_paths: str
    script_exists_count: int
    script_missing_count: int
    file_types: str
    exit_code: str
    expected_exit_codes: str
    expected_ok: str
    timed_out: str
    elapsed_seconds: str
    stdout_path: str
    stdout_exists: str
    stderr_path: str
    stderr_exists: str
    safety_scope: str


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def bool_text(value: object) -> str:
    return "YES" if value is True else "NO"


def to_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def split_paths(rows: list[dict[str, Any]], field_name: str) -> str:
    return " / ".join(str(row.get(field_name, "")) for row in rows if row.get(field_name))


def decode_b64_text(value: str) -> str:
    return base64.b64decode(value).decode("utf-8", errors="replace")


def decode_ps1_variables(ps1_text: str) -> dict[str, str]:
    variables: dict[str, str] = {}
    for match in re.finditer(r"\$(\w+)\s*=\s*\"([A-Za-z0-9+/=]+)\"", ps1_text):
        variable_name = match.group(1)
        encoded_value = match.group(2)
        try:
            variables[variable_name] = decode_b64_text(encoded_value)
        except (ValueError, UnicodeDecodeError):
            continue
    return variables


def extract_balanced_block(text: str, start_index: int) -> str:
    open_index = text.find("{", start_index)
    if open_index < 0:
        return ""
    depth = 0
    for index in range(open_index, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_index + 1 : index]
    return ""


def parse_switch_entries(ps1_text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    switch_index = ps1_text.find("$code = switch ($Entry)")
    if switch_index < 0:
        return entries
    switch_block = extract_balanced_block(ps1_text, switch_index)
    for match in re.finditer(r'"([^"]+)"\s*\{', switch_block):
        entry_name = match.group(1)
        entries[entry_name] = extract_balanced_block(switch_block, match.start())
    return entries


def parse_function_blocks(ps1_text: str) -> dict[str, str]:
    functions: dict[str, str] = {}
    for match in re.finditer(r"function\s+([A-Za-z0-9_-]+)\s*\{", ps1_text):
        functions[match.group(1)] = extract_balanced_block(ps1_text, match.start())
    return functions


def parse_bat_entry(bat_text: str) -> str:
    match = re.search(r"-Entry\s+([A-Za-z0-9_]+)", bat_text)
    return match.group(1) if match else ""


def classify_command_kind(entry_body: str) -> str:
    if "Invoke-S58" in entry_body:
        return "GUI_PYTHON_SCRIPT_STARTED_AND_CLEANED"
    if "Invoke-S57" in entry_body:
        return "PYTHON_SCRIPT_WITH_RK10_CLOSE_WATCHER"
    if "Invoke-PythonSteps" in entry_body:
        return "PYTHON_SCRIPT_SEQUENCE"
    if "Invoke-PythonModuleStep" in entry_body:
        return "PYTHON_MODULE_OR_PYTEST"
    if "Invoke-PythonStep" in entry_body:
        return "PYTHON_SCRIPT"
    return "UNKNOWN"


def collect_referenced_variables(entry_body: str, functions: dict[str, str]) -> tuple[set[str], set[str]]:
    bodies = [entry_body]
    for function_name in re.findall(r"\b(Invoke-S\d+)\b", entry_body):
        function_body = functions.get(function_name, "")
        if function_body:
            bodies.append(function_body)
    combined_body = "\n".join(bodies)
    script_refs = set(re.findall(r"\$([A-Za-z0-9_]*script[A-Za-z0-9_]*)", combined_body, re.IGNORECASE))
    root_refs = set(re.findall(r"\$([A-Za-z0-9_]*root[A-Za-z0-9_]*)", combined_body, re.IGNORECASE))
    return script_refs, root_refs


def path_exists_text(path_text: str) -> str:
    return "YES" if path_text and Path(path_text).exists() else "NO"


def join_existing_paths(paths: list[str]) -> str:
    return " / ".join(path for path in paths if path)


def file_types_for(row: dict[str, Any], ps1_path: Path, script_paths: list[str]) -> str:
    suffixes = set()
    if row.get("bat_path"):
        suffixes.add(".bat")
    if ps1_path.suffix:
        suffixes.add(ps1_path.suffix.lower())
    for script_path in script_paths:
        suffix = Path(script_path).suffix.lower()
        if suffix:
            suffixes.add(suffix)
    if any(".py" == suffix for suffix in suffixes):
        suffixes.add("python")
    return ", ".join(sorted(suffixes))


def build_entry_detail(row: dict[str, Any]) -> str:
    return (
        f"{row.get('name', '')}: exit={row.get('exit_code', '')}, "
        f"expected={row.get('expected_exit_codes', '')}, "
        f"expected_ok={bool_text(row.get('expected_ok'))}, "
        f"timeout={bool_text(row.get('timed_out'))}, "
        f"cleanup_remaining={row.get('cleanup_remaining_count', '')}, "
        f"note={row.get('note', '') or '-'}"
    )


def group_results_by_scenario(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        entry_name = str(result.get("name", ""))
        for scenario in SCENARIO_LABELS_BY_ENTRY.get(entry_name, (entry_name,)):
            grouped[scenario].append(result)
    return dict(grouped)


def scenario_for_entry(entry_name: str) -> str:
    return ", ".join(SCENARIO_LABELS_BY_ENTRY.get(entry_name, (entry_name,)))


def build_scenario_rows(payload: dict[str, Any]) -> list[ScenarioEvidenceRow]:
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise TypeError("results must be a list")
    grouped = group_results_by_scenario([row for row in results if isinstance(row, dict)])
    rows: list[ScenarioEvidenceRow] = []
    for scenario in sorted(grouped, key=scenario_sort_key):
        scenario_results = grouped[scenario]
        entry_count = len(scenario_results)
        expected_ok_count = sum(1 for row in scenario_results if row.get("expected_ok") is True)
        timeout_count = sum(1 for row in scenario_results if row.get("timed_out") is True)
        cleanup_remaining_count = sum(
            to_int(row.get("cleanup_remaining_count")) for row in scenario_results
        )
        rows.append(
            ScenarioEvidenceRow(
                scenario=scenario,
                entry_count=entry_count,
                expected_ok_count=expected_ok_count,
                unexpected_count=entry_count - expected_ok_count,
                timeout_count=timeout_count,
                cleanup_remaining_count=cleanup_remaining_count,
                entry_names=", ".join(str(row.get("name", "")) for row in scenario_results),
                entry_details=" / ".join(build_entry_detail(row) for row in scenario_results),
                stdout_paths=split_paths(scenario_results, "stdout_path"),
                stderr_paths=split_paths(scenario_results, "stderr_path"),
                safety_scope=str(payload.get("safety", "")),
                production_completion_scope=(
                    "SAFE_ENTRY_ONLY_NOT_PRODUCTION_COMPLETE"
                ),
                next_gap=(
                    "final operator approval and irreversible-operation evidence remain separate; "
                    "RK10 ButtonRun, real mail, real print, submit, payment, paid Azure OCR, "
                    "and production writes were not performed"
                ),
            )
        )
    return rows


def build_actual_execution_trace_rows(
    payload: dict[str, Any],
    ps1_path: Path = CUSTOMER_SAFE_ENTRY_PS1,
) -> list[ActualExecutionTraceRow]:
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise TypeError("results must be a list")
    ps1_text = read_text_if_exists(ps1_path)
    variables = decode_ps1_variables(ps1_text)
    switch_entries = parse_switch_entries(ps1_text)
    functions = parse_function_blocks(ps1_text)
    rows: list[ActualExecutionTraceRow] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        entry_name = str(result.get("name", ""))
        bat_path_text = str(result.get("bat_path", ""))
        bat_text = read_text_if_exists(Path(bat_path_text)) if bat_path_text else ""
        ps1_entry = parse_bat_entry(bat_text)
        entry_body = switch_entries.get(ps1_entry, "")
        script_refs, _root_refs = collect_referenced_variables(entry_body, functions)
        script_paths = sorted(
            variables[script_ref]
            for script_ref in script_refs
            if script_ref in variables
        )
        script_exists_count = sum(1 for script_path in script_paths if Path(script_path).exists())
        stdout_path = str(result.get("stdout_path", ""))
        stderr_path = str(result.get("stderr_path", ""))
        rows.append(
            ActualExecutionTraceRow(
                scenario=scenario_for_entry(entry_name),
                entry_name=entry_name,
                bat_path=bat_path_text,
                bat_exists=path_exists_text(bat_path_text),
                ps1_path=str(ps1_path),
                ps1_exists=path_exists_text(str(ps1_path)),
                ps1_entry=ps1_entry,
                ps1_entry_resolved="YES" if ps1_entry and entry_body else "NO",
                command_kind=classify_command_kind(entry_body),
                script_paths=join_existing_paths(script_paths),
                script_exists_count=script_exists_count,
                script_missing_count=len(script_paths) - script_exists_count,
                file_types=file_types_for(result, ps1_path, script_paths),
                exit_code=str(result.get("exit_code", "")),
                expected_exit_codes=str(result.get("expected_exit_codes", "")),
                expected_ok=bool_text(result.get("expected_ok")),
                timed_out=bool_text(result.get("timed_out")),
                elapsed_seconds=str(result.get("elapsed_seconds", "")),
                stdout_path=stdout_path,
                stdout_exists=path_exists_text(stdout_path),
                stderr_path=stderr_path,
                stderr_exists=path_exists_text(stderr_path),
                safety_scope="SAFE_ENTRY_ACTUAL_BAT_TO_PS1_TO_TOOL_TRACE_NOT_PRODUCTION_COMPLETE",
            )
        )
    return rows


def scenario_sort_key(value: str) -> tuple[int, str]:
    first = value.split("/")[0]
    return (to_int(first), value)


def build_payload(smoke_payload: dict[str, Any]) -> dict[str, Any]:
    rows = build_scenario_rows(smoke_payload)
    trace_rows = build_actual_execution_trace_rows(smoke_payload)
    scenario_count = len(rows)
    scenario_all_expected_ok_count = sum(1 for row in rows if row.unexpected_count == 0)
    trace_entry_count = len(trace_rows)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_json": str(CANONICAL_REPORT_JSON),
        "source_generated_at": str(smoke_payload.get("generated_at", "")),
        "source_run_dir": str(smoke_payload.get("run_dir", "")),
        "source_total_entries": to_int(smoke_payload.get("total")),
        "source_expected_ok_count": to_int(smoke_payload.get("expected_ok_count")),
        "source_unexpected_count": to_int(smoke_payload.get("unexpected_count")),
        "source_timeout_count": to_int(smoke_payload.get("timeout_count")),
        "scenario_count": scenario_count,
        "scenario_all_expected_ok_count": scenario_all_expected_ok_count,
        "scenario_unexpected_count": scenario_count - scenario_all_expected_ok_count,
        "actual_trace_entry_count": trace_entry_count,
        "actual_trace_expected_ok_count": sum(
            1 for row in trace_rows if row.expected_ok == "YES"
        ),
        "actual_trace_bat_exists_count": sum(
            1 for row in trace_rows if row.bat_exists == "YES"
        ),
        "actual_trace_ps1_entry_resolved_count": sum(
            1 for row in trace_rows if row.ps1_entry_resolved == "YES"
        ),
        "actual_trace_script_missing_count": sum(
            row.script_missing_count for row in trace_rows
        ),
        "actual_trace_stdout_missing_count": sum(
            1 for row in trace_rows if row.stdout_exists != "YES"
        ),
        "actual_trace_stderr_missing_count": sum(
            1 for row in trace_rows if row.stderr_exists != "YES"
        ),
        "safety": (
            "read-only report generation from existing customer-safe smoke JSON; "
            "no RK10 ButtonRun; no real mail; no real print; no submit; no payment; "
            "no paid Azure OCR; no production write"
        ),
        "license_policy": (
            "RK10ライセンス画面は既定のRPA開発版AI付きのまま、"
            "ラジオボタンを変更せずOKのみ押す。"
        ),
        "rows": [asdict(row) for row in rows],
        "actual_execution_trace_rows": [asdict(row) for row in trace_rows],
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def markdown_cell(value: object) -> str:
    if value is None:
        return "-"
    text = str(value).replace("|", "/")
    return text if text else "-"


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 客先安全入口 シナリオ別証跡マトリクス 2026-06-22",
        "",
        "## Claim",
        (
            f"全{payload['source_total_entries']}件の客先安全入口スモーク結果を"
            f"{payload['scenario_count']}シナリオへ展開し、シナリオ別でも"
            f"期待終了コード一致 {payload['scenario_all_expected_ok_count']}/"
            f"{payload['scenario_count']} 件、unexpected "
            f"{payload['scenario_unexpected_count']} 件だった。"
        ),
        "",
        "## Primary Source",
        f"- source_json: `{payload['source_json']}`",
        f"- source_generated_at: `{payload['source_generated_at']}`",
        f"- source_run_dir: `{payload['source_run_dir']}`",
        f"- source_entry_progress: `{payload['source_expected_ok_count']}/{payload['source_total_entries']}`",
        f"- source_unexpected_count: `{payload['source_unexpected_count']}`",
        f"- source_timeout_count: `{payload['source_timeout_count']}`",
        "",
        "## Safety Scope",
        f"- {payload['safety']}",
        f"- license_policy: `{payload['license_policy']}`",
        "- This matrix is safe-entry evidence only; it is not production completion evidence.",
        "",
        "## Scenario Matrix",
        "",
        "| Scenario | Entries | Expected OK | Unexpected | Timeout | Cleanup Remaining | Entry Names | Scope | Next Gap |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["scenario"]),
                    markdown_cell(row["entry_count"]),
                    markdown_cell(row["expected_ok_count"]),
                    markdown_cell(row["unexpected_count"]),
                    markdown_cell(row["timeout_count"]),
                    markdown_cell(row["cleanup_remaining_count"]),
                    markdown_cell(row["entry_names"]),
                    markdown_cell(row["production_completion_scope"]),
                    markdown_cell(row["next_gap"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Actual Execution Trace",
            "",
            "- BAT実行結果から、客先入口BAT→共通PowerShell→実PY/ツール呼び出しまでを照合した。",
            f"- trace_entry_progress: `{payload['actual_trace_expected_ok_count']}/{payload['actual_trace_entry_count']}`",
            f"- bat_exists_count: `{payload['actual_trace_bat_exists_count']}/{payload['actual_trace_entry_count']}`",
            f"- ps1_entry_resolved_count: `{payload['actual_trace_ps1_entry_resolved_count']}/{payload['actual_trace_entry_count']}`",
            f"- script_missing_count: `{payload['actual_trace_script_missing_count']}`",
            f"- stdout_missing_count: `{payload['actual_trace_stdout_missing_count']}`",
            f"- stderr_missing_count: `{payload['actual_trace_stderr_missing_count']}`",
            "- scope: `SAFE_ENTRY_ACTUAL_BAT_TO_PS1_TO_TOOL_TRACE_NOT_PRODUCTION_COMPLETE`",
            "",
            "| Scenario | Entry | Kind | File Types | Script Missing | Exit | Expected OK | Timeout | BAT | Stdout | Stderr |",
            "|---|---|---|---|---:|---:|---|---|---|---|---|",
        ]
    )
    for row in payload["actual_execution_trace_rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["scenario"]),
                    markdown_cell(row["entry_name"]),
                    markdown_cell(row["command_kind"]),
                    markdown_cell(row["file_types"]),
                    markdown_cell(row["script_missing_count"]),
                    markdown_cell(row["exit_code"]),
                    markdown_cell(row["expected_ok"]),
                    markdown_cell(row["timed_out"]),
                    markdown_cell(row["bat_path"]),
                    markdown_cell(row["stdout_path"]),
                    markdown_cell(row["stderr_path"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Known Facts Check",
            "- Full-smoke expected OK is consistent with the canonical smoke JSON.",
            "- Actual execution trace is derived from the same BAT paths and latest stdout/stderr logs recorded by the canonical smoke JSON.",
            "- RKS production-ready status is not inferred from this matrix.",
            "- Human approval fields and irreversible-operation logs remain separate gates.",
            "",
            "## Output Files",
            f"- json: `{SCENARIO_MATRIX_JSON}`",
            f"- csv: `{SCENARIO_MATRIX_CSV}`",
            f"- markdown: `{SCENARIO_MATRIX_MD}`",
            f"- actual_trace_json: `{ACTUAL_EXECUTION_TRACE_JSON}`",
            f"- actual_trace_csv: `{ACTUAL_EXECUTION_TRACE_CSV}`",
            f"- actual_trace_markdown: `{ACTUAL_EXECUTION_TRACE_MD}`",
        ]
    )
    return "\n".join(lines) + "\n"


def build_actual_execution_trace_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 客先安全入口 実行トレース 2026-06-23",
        "",
        "## Claim",
        (
            "客先安全入口BATから共通PowerShellを経由して実際に呼ばれるPY/ツールまでを照合し、"
            f"trace_entry_progress {payload['actual_trace_expected_ok_count']}/"
            f"{payload['actual_trace_entry_count']}、script_missing_count "
            f"{payload['actual_trace_script_missing_count']} 件だった。"
        ),
        "",
        "## Primary Source",
        f"- source_json: `{payload['source_json']}`",
        f"- source_generated_at: `{payload['source_generated_at']}`",
        f"- source_run_dir: `{payload['source_run_dir']}`",
        f"- actual_trace_json: `{ACTUAL_EXECUTION_TRACE_JSON}`",
        f"- actual_trace_csv: `{ACTUAL_EXECUTION_TRACE_CSV}`",
        "",
        "## Safety Scope",
        f"- {payload['safety']}",
        f"- license_policy: `{payload['license_policy']}`",
        "- scope: `SAFE_ENTRY_ACTUAL_BAT_TO_PS1_TO_TOOL_TRACE_NOT_PRODUCTION_COMPLETE`",
        "- This trace proves the safe-entry BAT/PS1/tool wiring only; it is not production completion evidence.",
        "",
        "## Trace Summary",
        f"- trace_entry_progress: `{payload['actual_trace_expected_ok_count']}/{payload['actual_trace_entry_count']}`",
        f"- bat_exists_count: `{payload['actual_trace_bat_exists_count']}/{payload['actual_trace_entry_count']}`",
        f"- ps1_entry_resolved_count: `{payload['actual_trace_ps1_entry_resolved_count']}/{payload['actual_trace_entry_count']}`",
        f"- script_missing_count: `{payload['actual_trace_script_missing_count']}`",
        f"- stdout_missing_count: `{payload['actual_trace_stdout_missing_count']}`",
        f"- stderr_missing_count: `{payload['actual_trace_stderr_missing_count']}`",
        "",
        "## Actual Execution Trace",
        "",
        "| Scenario | Entry | Kind | File Types | Script Missing | Exit | Expected OK | Timeout | BAT | PS1 Entry | Script Paths | Stdout | Stderr |",
        "|---|---|---|---|---:|---:|---|---|---|---|---|---|---|",
    ]
    for row in payload["actual_execution_trace_rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["scenario"]),
                    markdown_cell(row["entry_name"]),
                    markdown_cell(row["command_kind"]),
                    markdown_cell(row["file_types"]),
                    markdown_cell(row["script_missing_count"]),
                    markdown_cell(row["exit_code"]),
                    markdown_cell(row["expected_ok"]),
                    markdown_cell(row["timed_out"]),
                    markdown_cell(row["bat_path"]),
                    markdown_cell(row["ps1_entry"]),
                    markdown_cell(row["script_paths"]),
                    markdown_cell(row["stdout_path"]),
                    markdown_cell(row["stderr_path"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Known Facts Check",
            "- Actual execution trace is derived from the latest canonical smoke JSON and its captured stdout/stderr paths.",
            "- RKS production-ready status, final approval, real mail, real print, submit, payment, paid Azure OCR, and production writes remain separate gates.",
            "",
            "## Confidence",
            "High for BAT/PS1/tool wiring because each row is derived from decoded safe-entry BAT and PowerShell references plus existing script paths.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SCENARIO_MATRIX_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(SCENARIO_MATRIX_CSV, list(payload["rows"]), SCENARIO_MATRIX_FIELDS)
    write_csv(
        ACTUAL_EXECUTION_TRACE_CSV,
        list(payload["actual_execution_trace_rows"]),
        ACTUAL_EXECUTION_TRACE_FIELDS,
    )
    SCENARIO_MATRIX_MD.write_text(build_markdown(payload), encoding="utf-8")
    ACTUAL_EXECUTION_TRACE_JSON.write_text(
        json.dumps(
            {
                key: value
                for key, value in payload.items()
                if key != "rows"
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ACTUAL_EXECUTION_TRACE_MD.write_text(
        build_actual_execution_trace_markdown(payload),
        encoding="utf-8",
    )
    write_numbered_copy(SCENARIO_MATRIX_JSON)
    write_numbered_copy(SCENARIO_MATRIX_CSV)
    write_numbered_copy(SCENARIO_MATRIX_MD)
    write_numbered_copy(ACTUAL_EXECUTION_TRACE_JSON)
    write_numbered_copy(ACTUAL_EXECUTION_TRACE_CSV)
    write_numbered_copy(ACTUAL_EXECUTION_TRACE_MD)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a scenario-level matrix from the customer safe-entry smoke JSON."
    )
    parser.add_argument("--source-json", type=Path, default=CANONICAL_REPORT_JSON)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    smoke_payload = read_json(args.source_json)
    payload = build_payload(smoke_payload)
    write_outputs(payload)
    print(
        json.dumps(
            {
                key: payload[key]
                for key in payload
                if key not in {"rows", "actual_execution_trace_rows"}
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
