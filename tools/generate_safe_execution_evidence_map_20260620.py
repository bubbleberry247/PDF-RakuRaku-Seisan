"""Generate a read-only scenario safe-execution evidence map.

This consolidates the current safe sample suite results into one per-scenario
artifact. It does not run RK10, Outlook, Rakuraku, Azure, printers, mail,
payment, MainSV, or production writes.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "safe_execution_evidence_map_20260620"
SAFE_SUITE_DIR = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\other_scenarios_safe_sample_suite_clean_20260620_092405"
)
SAFE_SUITE_RESULTS = SAFE_SUITE_DIR / "results.json"
SAFE_SUITE_SUMMARY = SAFE_SUITE_DIR / "summary.tsv.numbered"
SAFE_SUITE_AUDIT = SAFE_SUITE_DIR / "stderr_and_keyword_audit.txt.numbered"
OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "outlook_bundle_evidence_collect_20260620"
    / "outlook_bundle_evidence_collect.json"
)
OUTLOOK_COM_SAFE_READY_STATUS = "OUTLOOK_COM_BUNDLE_DRYRUN_NO_PRINT_NO_MAIL_EXIT0"
SCENARIOS = [
    "12/13",
    "37",
    "38",
    "42",
    "43",
    "44",
    "47",
    "51/52",
    "55",
    "56",
    "57",
    "58",
    "63",
    "70",
    "71",
]


@dataclass(frozen=True)
class SafeTask:
    name: str
    scenario: str
    status: str
    exit_code: int | None
    elapsed_sec: float | None
    safety: str
    stdout: str
    stderr: str
    stdout_exists: bool
    stderr_exists: bool
    stderr_bytes: int | None
    passed: bool


@dataclass(frozen=True)
class ScenarioSafeEvidence:
    scenario: str
    safe_suite_status: str
    task_count: int
    passed_task_count: int
    stderr_zero_count: int
    task_names: str
    safety_scopes: str
    stdout_paths: str
    stderr_paths: str
    evidence_strength: str
    production_ready: bool
    remaining_gap: str


def normalize_scenario(value: str) -> str:
    if value in {"51", "52"}:
        return "51/52"
    return value


def read_results(results_path: Path) -> list[dict[str, Any]]:
    if not results_path.exists():
        return []
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    if not isinstance(results, list):
        return []
    return [item for item in results if isinstance(item, dict)]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def is_outlook_com_bundle_safe_evidence_ready(
    path: Path | None = None,
) -> bool:
    payload = load_json(path or OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON)
    log_status = payload.get("log_status", {})
    if not isinstance(log_status, dict):
        return False
    return (
        payload.get("status") == "READY_FOR_FINAL_EVIDENCE_INTAKE"
        and payload.get("ready_for_intake") is True
        and str(log_status.get("check_exit")) == "0"
        and str(log_status.get("scan_exit")) == "0"
    )


def to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def task_from_result(item: dict[str, Any]) -> SafeTask:
    stdout = str(item.get("stdout", ""))
    stderr = str(item.get("stderr", ""))
    stdout_path = Path(stdout) if stdout else None
    stderr_path = Path(stderr) if stderr else None
    stderr_bytes = stderr_path.stat().st_size if stderr_path and stderr_path.exists() else None
    status = str(item.get("status", ""))
    exit_code = to_int(item.get("exit_code"))
    passed = status == "EXITED" and exit_code == 0 and stderr_bytes == 0
    return SafeTask(
        name=str(item.get("name", "")),
        scenario=normalize_scenario(str(item.get("scenario", ""))),
        status=status,
        exit_code=exit_code,
        elapsed_sec=to_float(item.get("elapsed_sec")),
        safety=str(item.get("safety", "")),
        stdout=stdout,
        stderr=stderr,
        stdout_exists=stdout_path.exists() if stdout_path else False,
        stderr_exists=stderr_path.exists() if stderr_path else False,
        stderr_bytes=stderr_bytes,
        passed=passed,
    )


def build_task_map(results_path: Path = SAFE_SUITE_RESULTS) -> dict[str, list[SafeTask]]:
    grouped: dict[str, list[SafeTask]] = {}
    for item in read_results(results_path):
        task = task_from_result(item)
        grouped.setdefault(task.scenario, []).append(task)
    return grouped


def summarize_scenario(scenario: str, tasks: list[SafeTask]) -> ScenarioSafeEvidence:
    if scenario == "12/13":
        if is_outlook_com_bundle_safe_evidence_ready():
            payload = load_json(OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON)
            log_status = payload.get("log_status", {})
            if not isinstance(log_status, dict):
                log_status = {}
            return ScenarioSafeEvidence(
                scenario=scenario,
                safe_suite_status=OUTLOOK_COM_SAFE_READY_STATUS,
                task_count=1,
                passed_task_count=1,
                stderr_zero_count=1,
                task_names="outlook_com_bundle_check_and_scan_only_dryrun",
                safety_scopes="Outlook COM check + scan-only dry-run/no-print/no-mail",
                stdout_paths=str(log_status.get("scan_log_path", "")),
                stderr_paths="",
                evidence_strength="OUTLOOK_COM_DRYRUN_NO_PRINT_NO_MAIL_EVIDENCE",
                production_ready=False,
                remaining_gap="real print/send/mail-state changes and final operator approval remain separate gates",
            )
        return ScenarioSafeEvidence(
            scenario=scenario,
            safe_suite_status="NOT_IN_SAFE_SUITE_OUTLOOK_COM_HOLD",
            task_count=0,
            passed_task_count=0,
            stderr_zero_count=0,
            task_names="",
            safety_scopes="Outlook COM check is tracked separately",
            stdout_paths="",
            stderr_paths="",
            evidence_strength="NO_SAFE_SUITE_ROW",
            production_ready=False,
            remaining_gap="Outlook COM exit 0 then dry-run/no-print/no-mail",
        )
    if not tasks:
        return ScenarioSafeEvidence(
            scenario=scenario,
            safe_suite_status="MISSING_SAFE_SUITE_TASK",
            task_count=0,
            passed_task_count=0,
            stderr_zero_count=0,
            task_names="",
            safety_scopes="",
            stdout_paths="",
            stderr_paths="",
            evidence_strength="MISSING_SAFE_SUITE_EVIDENCE",
            production_ready=False,
            remaining_gap="safe sample suite task evidence is missing",
        )

    passed_tasks = [task for task in tasks if task.passed]
    stderr_zero_tasks = [task for task in tasks if task.stderr_bytes == 0]
    all_passed = len(passed_tasks) == len(tasks)
    status = "SAFE_SUITE_EXIT0_STDERR0" if all_passed else "SAFE_SUITE_NEEDS_REVIEW"
    return ScenarioSafeEvidence(
        scenario=scenario,
        safe_suite_status=status,
        task_count=len(tasks),
        passed_task_count=len(passed_tasks),
        stderr_zero_count=len(stderr_zero_tasks),
        task_names=", ".join(task.name for task in tasks),
        safety_scopes="; ".join(task.safety for task in tasks),
        stdout_paths="; ".join(task.stdout for task in tasks),
        stderr_paths="; ".join(task.stderr for task in tasks),
        evidence_strength="SAFE_SAMPLE_OR_DRYRUN_EVIDENCE" if all_passed else "PARTIAL_OR_FAILED_SAFE_EVIDENCE",
        production_ready=False,
        remaining_gap="irreversible operations and RK10 production runtime remain separate gates",
    )


def build_rows(results_path: Path = SAFE_SUITE_RESULTS) -> list[ScenarioSafeEvidence]:
    task_map = build_task_map(results_path)
    return [summarize_scenario(scenario, task_map.get(scenario, [])) for scenario in SCENARIOS]


def build_payload(results_path: Path = SAFE_SUITE_RESULTS) -> dict[str, object]:
    generated_at = datetime.now().isoformat(timespec="seconds")
    rows = build_rows(results_path)
    covered_rows = [
        row
        for row in rows
        if row.safe_suite_status in {"SAFE_SUITE_EXIT0_STDERR0", OUTLOOK_COM_SAFE_READY_STATUS}
    ]
    missing_rows = [
        row
        for row in rows
        if row.safe_suite_status in {"MISSING_SAFE_SUITE_TASK", "NOT_IN_SAFE_SUITE_OUTLOOK_COM_HOLD"}
    ]
    review_rows = [row for row in rows if row.safe_suite_status == "SAFE_SUITE_NEEDS_REVIEW"]
    return {
        "generated_at": generated_at,
        "safety": (
            "read-only consolidation of existing safe suite result files; "
            "no external operation"
        ),
        "source_results": str(results_path),
        "source_summary": str(SAFE_SUITE_SUMMARY),
        "source_audit": str(SAFE_SUITE_AUDIT),
        "scenario_count": len(rows),
        "safe_suite_passed_scenario_count": len(covered_rows),
        "missing_or_separate_scenario_count": len(missing_rows),
        "needs_review_scenario_count": len(review_rows),
        "production_ready_count": 0,
        "rows": [asdict(row) for row in rows],
    }


def csv_fields() -> list[str]:
    return [
        "scenario",
        "safe_suite_status",
        "task_count",
        "passed_task_count",
        "stderr_zero_count",
        "task_names",
        "safety_scopes",
        "stdout_paths",
        "stderr_paths",
        "evidence_strength",
        "production_ready",
        "remaining_gap",
    ]


def build_markdown(payload: dict[str, object]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# Safe Execution Evidence Map 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- safety: `{payload['safety']}`",
        f"- source_results: `{payload['source_results']}`",
        f"- source_summary: `{payload['source_summary']}`",
        f"- source_audit: `{payload['source_audit']}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- safe_suite_passed_scenario_count: `{payload['safe_suite_passed_scenario_count']}`",
        f"- missing_or_separate_scenario_count: `{payload['missing_or_separate_scenario_count']}`",
        f"- needs_review_scenario_count: `{payload['needs_review_scenario_count']}`",
        f"- production_ready_count: `{payload['production_ready_count']}`",
        "",
        "## Meaning",
        "",
        "- `SAFE_SUITE_EXIT0_STDERR0` proves only safe sample/dry-run/self-test scope.",
        "- It does not prove production execution, mail/print, payment execution, Rakuraku final submit, MainSV writes, Azure paid OCR, or RK10 production runtime.",
        "",
        "## Scenario Safe Suite Map",
        "",
        "| Scenario | Safe Suite Status | Tasks | Passed | Stderr 0 | Evidence Strength | Remaining Gap |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    str(row["safe_suite_status"]).replace("|", "/"),
                    str(row["task_count"]),
                    str(row["passed_task_count"]),
                    str(row["stderr_zero_count"]),
                    str(row["evidence_strength"]).replace("|", "/"),
                    str(row["remaining_gap"]).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Task Details", ""])
    for row in rows:
        assert isinstance(row, dict)
        lines.append(f"- {row['scenario']}: {row['task_names'] or '(none)'}")
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, object], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "safe_execution_evidence_map.json"
    md_path = out_dir / "safe_execution_evidence_map.md"
    csv_path = out_dir / "safe_execution_evidence_map.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=csv_fields())
        writer.writeheader()
        rows = payload["rows"]
        assert isinstance(rows, list)
        writer.writerows(rows)
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "csv": str(csv_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate safe execution evidence map.")
    parser.add_argument("--results", type=Path, default=SAFE_SUITE_RESULTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.results)
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
