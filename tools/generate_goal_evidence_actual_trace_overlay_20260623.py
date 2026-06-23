"""Overlay the goal evidence ledger with customer-safe actual execution trace.

This report is read-only. It connects the existing goal evidence ledger rows
to the latest customer-safe BAT -> PowerShell -> PY/tool trace without changing
completion gates or promoting safe-entry evidence to production completion.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "goal_evidence_actual_trace_overlay_20260623"
GOAL_EVIDENCE_LEDGER_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "goal_evidence_ledger_20260620"
    / "goal_evidence_ledger.json"
)
ACTUAL_TRACE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "customer_safe_entries_full_smoke_20260622"
    / "customer_safe_entries_actual_execution_trace_20260623.json"
)
ACTUAL_TRACE_MD = (
    ROOT
    / "plans"
    / "reports"
    / "customer_safe_entries_full_smoke_20260622"
    / "customer_safe_entries_actual_execution_trace_20260623.md.numbered"
)


@dataclass(frozen=True)
class TraceSummary:
    status: str
    entry_count: int
    expected_ok_count: int
    script_missing_count: int
    stdout_missing_count: int
    stderr_missing_count: int


@dataclass(frozen=True)
class OverlayRow:
    scenario: str
    ledger_current_status: str
    ledger_evidence_strength: str
    objective_checkpoint_summary: str
    missing_objective_proofs: str
    actual_trace_status: str
    actual_trace_entry_count: int
    actual_trace_expected_ok_count: int
    actual_trace_script_missing_count: int
    actual_trace_stdout_missing_count: int
    actual_trace_stderr_missing_count: int
    actual_trace_evidence: str
    actual_trace_evidence_exists: bool
    production_completion_scope: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def to_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def is_trace_row_ready(row: dict[str, Any]) -> bool:
    return (
        row.get("expected_ok") == "YES"
        and row.get("bat_exists") == "YES"
        and row.get("ps1_entry_resolved") == "YES"
        and row.get("stdout_exists") == "YES"
        and row.get("stderr_exists") == "YES"
        and to_int(row.get("script_missing_count")) == 0
    )


def build_trace_by_scenario(trace_payload: dict[str, Any]) -> dict[str, TraceSummary]:
    rows = trace_payload.get("actual_execution_trace_rows", [])
    if not isinstance(rows, list):
        rows = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        scenario = str(row.get("scenario", ""))
        if scenario:
            grouped.setdefault(scenario, []).append(row)
    summaries: dict[str, TraceSummary] = {}
    for scenario, scenario_rows in grouped.items():
        entry_count = len(scenario_rows)
        expected_ok_count = sum(1 for row in scenario_rows if is_trace_row_ready(row))
        script_missing_count = sum(to_int(row.get("script_missing_count")) for row in scenario_rows)
        stdout_missing_count = sum(1 for row in scenario_rows if row.get("stdout_exists") != "YES")
        stderr_missing_count = sum(1 for row in scenario_rows if row.get("stderr_exists") != "YES")
        status = "SAFE_ENTRY_TRACE_OK" if expected_ok_count == entry_count else "SAFE_ENTRY_TRACE_INCOMPLETE"
        summaries[scenario] = TraceSummary(
            status=status,
            entry_count=entry_count,
            expected_ok_count=expected_ok_count,
            script_missing_count=script_missing_count,
            stdout_missing_count=stdout_missing_count,
            stderr_missing_count=stderr_missing_count,
        )
    return summaries


def build_overlay_rows(
    ledger_payload: dict[str, Any],
    trace_payload: dict[str, Any],
    trace_markdown_path: Path = ACTUAL_TRACE_MD,
) -> list[OverlayRow]:
    ledger_rows = ledger_payload.get("rows", [])
    if not isinstance(ledger_rows, list):
        ledger_rows = []
    trace_by_scenario = build_trace_by_scenario(trace_payload)
    rows: list[OverlayRow] = []
    for ledger_row in ledger_rows:
        if not isinstance(ledger_row, dict):
            continue
        scenario = str(ledger_row.get("scenario", ""))
        trace_summary = trace_by_scenario.get(
            scenario,
            TraceSummary(
                status="SAFE_ENTRY_TRACE_MISSING",
                entry_count=0,
                expected_ok_count=0,
                script_missing_count=0,
                stdout_missing_count=0,
                stderr_missing_count=0,
            ),
        )
        rows.append(
            OverlayRow(
                scenario=scenario,
                ledger_current_status=str(ledger_row.get("current_status", "")),
                ledger_evidence_strength=str(ledger_row.get("evidence_strength", "")),
                objective_checkpoint_summary=str(
                    ledger_row.get("objective_checkpoint_summary", "")
                ),
                missing_objective_proofs=str(ledger_row.get("missing_objective_proofs", "")),
                actual_trace_status=trace_summary.status,
                actual_trace_entry_count=trace_summary.entry_count,
                actual_trace_expected_ok_count=trace_summary.expected_ok_count,
                actual_trace_script_missing_count=trace_summary.script_missing_count,
                actual_trace_stdout_missing_count=trace_summary.stdout_missing_count,
                actual_trace_stderr_missing_count=trace_summary.stderr_missing_count,
                actual_trace_evidence=str(trace_markdown_path),
                actual_trace_evidence_exists=trace_markdown_path.exists(),
                production_completion_scope=(
                    "SAFE_TRACE_ONLY_NOT_PRODUCTION_COMPLETE"
                ),
            )
        )
    return rows


def build_payload(
    ledger_path: Path = GOAL_EVIDENCE_LEDGER_JSON,
    trace_path: Path = ACTUAL_TRACE_JSON,
    trace_markdown_path: Path = ACTUAL_TRACE_MD,
) -> dict[str, Any]:
    ledger_payload = read_json(ledger_path)
    trace_payload = read_json(trace_path)
    rows = build_overlay_rows(ledger_payload, trace_payload, trace_markdown_path)
    trace_ready_rows = [row for row in rows if row.actual_trace_status == "SAFE_ENTRY_TRACE_OK"]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": (
            "read-only overlay from existing ledger and customer-safe trace; "
            "no RK10 ButtonRun, real mail, print, submit, payment, paid Azure OCR, "
            "or production write"
        ),
        "ledger_path": str(ledger_path),
        "ledger_exists": ledger_path.exists(),
        "actual_trace_json": str(trace_path),
        "actual_trace_json_exists": trace_path.exists(),
        "actual_trace_markdown": str(trace_markdown_path),
        "actual_trace_markdown_exists": trace_markdown_path.exists(),
        "scenario_count": len(rows),
        "trace_ready_scenario_count": len(trace_ready_rows),
        "trace_missing_scenario_count": sum(
            1 for row in rows if row.actual_trace_status == "SAFE_ENTRY_TRACE_MISSING"
        ),
        "trace_script_missing_count": sum(row.actual_trace_script_missing_count for row in rows),
        "production_completion_scope": "SAFE_TRACE_ONLY_NOT_PRODUCTION_COMPLETE",
        "rows": [asdict(row) for row in rows],
    }


def markdown_cell(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.replace("|", "/")
    return text if text else "-"


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 目標証跡台帳 実行トレース接続 2026-06-23",
        "",
        "## Claim",
        (
            f"既存の目標証跡台帳 {payload['scenario_count']} シナリオに対して、"
            f"客先安全入口の実行トレースが {payload['trace_ready_scenario_count']}/"
            f"{payload['scenario_count']} シナリオ接続済みで、"
            f"script_missing_count は {payload['trace_script_missing_count']} 件だった。"
        ),
        "",
        "## Primary Source",
        f"- ledger_path: `{payload['ledger_path']}` exists=`{payload['ledger_exists']}`",
        f"- actual_trace_json: `{payload['actual_trace_json']}` exists=`{payload['actual_trace_json_exists']}`",
        f"- actual_trace_markdown: `{payload['actual_trace_markdown']}` exists=`{payload['actual_trace_markdown_exists']}`",
        "",
        "## Safety Scope",
        f"- {payload['safety']}",
        f"- production_completion_scope: `{payload['production_completion_scope']}`",
        "- This overlay strengthens sample/safe execution trace evidence only; it does not close human/external production gates.",
        "",
        "## Overlay Matrix",
        "",
        "| Scenario | Ledger Status | Ledger Strength | Actual Trace | Trace Entries | Script Missing | Stdout Missing | Stderr Missing | Objective Checkpoints | Missing Objective Proofs | Scope |",
        "|---|---|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row.get("scenario")),
                    markdown_cell(row.get("ledger_current_status")),
                    markdown_cell(row.get("ledger_evidence_strength")),
                    markdown_cell(row.get("actual_trace_status")),
                    f"{row.get('actual_trace_expected_ok_count', 0)}/{row.get('actual_trace_entry_count', 0)}",
                    markdown_cell(row.get("actual_trace_script_missing_count")),
                    markdown_cell(row.get("actual_trace_stdout_missing_count")),
                    markdown_cell(row.get("actual_trace_stderr_missing_count")),
                    markdown_cell(row.get("objective_checkpoint_summary")),
                    markdown_cell(row.get("missing_objective_proofs")),
                    markdown_cell(row.get("production_completion_scope")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Known Facts Check",
            "- RKS production readiness is not inferred from this overlay.",
            "- Final operator approval and irreversible-operation evidence remain separate gates.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "goal_evidence_actual_trace_overlay.json"
    md_path = out_dir / "goal_evidence_actual_trace_overlay.md"
    csv_path = out_dir / "goal_evidence_actual_trace_overlay.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    fieldnames = list(payload["rows"][0].keys()) if payload["rows"] else []
    if fieldnames:
        import csv

        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(payload["rows"])
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    if csv_path.exists():
        write_numbered_copy(csv_path)
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "csv": str(csv_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate actual execution trace overlay for the goal evidence ledger."
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    outputs = write_outputs(payload, args.out_dir)
    print(
        json.dumps(
            {
                "generated_at": payload["generated_at"],
                "scenario_count": payload["scenario_count"],
                "trace_ready_scenario_count": payload["trace_ready_scenario_count"],
                "trace_missing_scenario_count": payload["trace_missing_scenario_count"],
                "trace_script_missing_count": payload["trace_script_missing_count"],
                "outputs": outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
