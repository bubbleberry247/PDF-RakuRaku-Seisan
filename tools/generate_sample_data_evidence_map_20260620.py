"""Generate a read-only sample-data evidence map for the active RK10 goal.

The report consolidates sample, test, review, and dry-run artifacts already
created by the safe suite. It does not run RK10, Outlook, Rakuraku, Azure,
printers, mail, payment systems, MainSV, or production writes.
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
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "sample_data_evidence_map_20260620"
SAFE_SUITE_DIR = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\other_scenarios_safe_sample_suite_clean_20260620_092405"
)
SAFE_SUITE_RESULTS = SAFE_SUITE_DIR / "results.json"
SAFE_SUITE_SUMMARY = SAFE_SUITE_DIR / "summary.tsv.numbered"
S12_13_RECHECK = (
    ROOT
    / "plans"
    / "reports"
    / "s12_13_outlook_com_recheck_20260620"
    / "s12_13_outlook_com_recheck_20260620.md.numbered"
)
OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "outlook_bundle_evidence_collect_20260620"
    / "outlook_bundle_evidence_collect.json"
)
OUTLOOK_COM_SAMPLE_READY_STATUS = "OUTLOOK_COM_BUNDLE_DRYRUN_SAMPLE_REFRESH_READY"
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
class SampleTask:
    name: str
    scenario: str
    status: str
    exit_code: int | None
    safety: str
    working_directory: str
    stdout: str
    stderr: str
    meta: str
    stdout_exists: bool
    stderr_exists: bool
    meta_exists: bool
    passed: bool


@dataclass(frozen=True)
class SampleDataEvidenceRow:
    scenario: str
    sample_data_status: str
    task_count: int
    passed_task_count: int
    artifact_file_count: int
    task_names: str
    safety_scopes: str
    working_directories: str
    artifact_paths: str
    evidence_strength: str
    production_ready: bool
    remaining_gap: str


def normalize_scenario(value: str) -> str:
    if value in {"51", "52"}:
        return "51/52"
    return value


def to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def task_from_result(item: dict[str, Any]) -> SampleTask:
    stdout = str(item.get("stdout", ""))
    stderr = str(item.get("stderr", ""))
    meta = str(item.get("meta", ""))
    stdout_path = Path(stdout) if stdout else None
    stderr_path = Path(stderr) if stderr else None
    meta_path = Path(meta) if meta else None
    status = str(item.get("status", ""))
    exit_code = to_int(item.get("exit_code"))
    return SampleTask(
        name=str(item.get("name", "")),
        scenario=normalize_scenario(str(item.get("scenario", ""))),
        status=status,
        exit_code=exit_code,
        safety=str(item.get("safety", "")),
        working_directory=str(item.get("working_directory", "")),
        stdout=stdout,
        stderr=stderr,
        meta=meta,
        stdout_exists=stdout_path.exists() if stdout_path else False,
        stderr_exists=stderr_path.exists() if stderr_path else False,
        meta_exists=meta_path.exists() if meta_path else False,
        passed=status == "EXITED" and exit_code == 0,
    )


def build_task_map(results_path: Path = SAFE_SUITE_RESULTS) -> dict[str, list[SampleTask]]:
    grouped: dict[str, list[SampleTask]] = {}
    for item in read_results(results_path):
        task = task_from_result(item)
        grouped.setdefault(task.scenario, []).append(task)
    return grouped


def artifact_count(tasks: list[SampleTask]) -> int:
    return sum(
        1
        for task in tasks
        for exists in [task.stdout_exists, task.stderr_exists, task.meta_exists]
        if exists
    )


def summarize_scenario(scenario: str, tasks: list[SampleTask]) -> SampleDataEvidenceRow:
    if scenario == "12/13":
        if is_outlook_com_bundle_safe_evidence_ready():
            evidence_path = str(
                load_json(OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON).get(
                    "evidence_path",
                    OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON,
                )
            )
            return SampleDataEvidenceRow(
                scenario=scenario,
                sample_data_status=OUTLOOK_COM_SAMPLE_READY_STATUS,
                task_count=1,
                passed_task_count=1,
                artifact_file_count=1 if Path(evidence_path).exists() else 0,
                task_names="outlook_com_bundle_check_and_scan_only_dryrun",
                safety_scopes="Outlook COM check + scan-only dry-run/no-print/no-mail",
                working_directories="",
                artifact_paths=evidence_path,
                evidence_strength="OUTLOOK_COM_DRYRUN_SAMPLE_EVIDENCE",
                production_ready=False,
                remaining_gap="real print/send/mail-state changes and final operator approval remain separate gates",
            )
        return SampleDataEvidenceRow(
            scenario=scenario,
            sample_data_status="OUTLOOK_COM_HOLD_SAMPLE_REFRESH_REQUIRED",
            task_count=0,
            passed_task_count=0,
            artifact_file_count=1 if S12_13_RECHECK.exists() else 0,
            task_names="",
            safety_scopes="Outlook COM recovery and dry-run/no-print/no-mail are separate gates",
            working_directories="",
            artifact_paths=str(S12_13_RECHECK),
            evidence_strength="SEPARATE_HOLD_EVIDENCE_ONLY",
            production_ready=False,
            remaining_gap="Outlook COM exit 0 is required before refreshing current 12/13 sample dry-run evidence",
        )
    if not tasks:
        return SampleDataEvidenceRow(
            scenario=scenario,
            sample_data_status="MISSING_SAFE_SUITE_SAMPLE_TASK",
            task_count=0,
            passed_task_count=0,
            artifact_file_count=0,
            task_names="",
            safety_scopes="",
            working_directories="",
            artifact_paths="",
            evidence_strength="MISSING_SAMPLE_EVIDENCE",
            production_ready=False,
            remaining_gap="safe sample suite task evidence is missing",
        )
    passed_tasks = [task for task in tasks if task.passed]
    all_passed = len(passed_tasks) == len(tasks)
    all_artifacts_present = all(
        task.stdout_exists and task.stderr_exists and task.meta_exists
        for task in tasks
    )
    status = (
        "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT"
        if all_passed and all_artifacts_present
        else "SAFE_SUITE_SAMPLE_ARTIFACTS_NEED_REVIEW"
    )
    artifacts = [
        path
        for task in tasks
        for path in [task.stdout, task.stderr, task.meta]
        if path
    ]
    return SampleDataEvidenceRow(
        scenario=scenario,
        sample_data_status=status,
        task_count=len(tasks),
        passed_task_count=len(passed_tasks),
        artifact_file_count=artifact_count(tasks),
        task_names=", ".join(task.name for task in tasks),
        safety_scopes="; ".join(task.safety for task in tasks),
        working_directories="; ".join(sorted({task.working_directory for task in tasks if task.working_directory})),
        artifact_paths="; ".join(artifacts),
        evidence_strength="SAFE_SAMPLE_OR_DRYRUN_ARTIFACT_EVIDENCE" if status.endswith("_PRESENT") else "PARTIAL_SAMPLE_EVIDENCE",
        production_ready=False,
        remaining_gap="sample/dry-run artifacts do not prove production execution or irreversible operations",
    )


def build_rows(results_path: Path = SAFE_SUITE_RESULTS) -> list[SampleDataEvidenceRow]:
    task_map = build_task_map(results_path)
    return [summarize_scenario(scenario, task_map.get(scenario, [])) for scenario in SCENARIOS]


def build_payload(results_path: Path = SAFE_SUITE_RESULTS) -> dict[str, object]:
    rows = build_rows(results_path)
    ready_rows = [
        row
        for row in rows
        if row.sample_data_status
        in {"SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT", OUTLOOK_COM_SAMPLE_READY_STATUS}
    ]
    separate_rows = [
        row
        for row in rows
        if row.sample_data_status == "OUTLOOK_COM_HOLD_SAMPLE_REFRESH_REQUIRED"
    ]
    review_rows = [
        row
        for row in rows
        if row.sample_data_status in {"MISSING_SAFE_SUITE_SAMPLE_TASK", "SAFE_SUITE_SAMPLE_ARTIFACTS_NEED_REVIEW"}
    ]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": "read-only consolidation of existing sample/dry-run artifacts; no external operation",
        "source_results": str(results_path),
        "source_summary": str(SAFE_SUITE_SUMMARY),
        "scenario_count": len(rows),
        "sample_or_dryrun_artifact_ready_count": len(ready_rows),
        "separate_hold_count": len(separate_rows),
        "needs_review_count": len(review_rows),
        "production_ready_count": 0,
        "rows": [asdict(row) for row in rows],
    }


def csv_fields() -> list[str]:
    return [
        "scenario",
        "sample_data_status",
        "task_count",
        "passed_task_count",
        "artifact_file_count",
        "task_names",
        "safety_scopes",
        "working_directories",
        "artifact_paths",
        "evidence_strength",
        "production_ready",
        "remaining_gap",
    ]


def build_markdown(payload: dict[str, object]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# Sample Data Evidence Map 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- safety: `{payload['safety']}`",
        f"- source_results: `{payload['source_results']}`",
        f"- source_summary: `{payload['source_summary']}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- sample_or_dryrun_artifact_ready_count: `{payload['sample_or_dryrun_artifact_ready_count']}`",
        f"- separate_hold_count: `{payload['separate_hold_count']}`",
        f"- needs_review_count: `{payload['needs_review_count']}`",
        f"- production_ready_count: `{payload['production_ready_count']}`",
        "",
        "## Meaning",
        "",
        "- This proves only existing sample/test/review/dry-run artifact presence.",
        "- It does not prove RK10 production runtime, real mail, real print, final submit, payment execution, MainSV write, or paid OCR.",
        "",
        "## Scenario Sample Map",
        "",
        "| Scenario | Sample Data Status | Tasks | Passed | Artifact Files | Evidence Strength | Remaining Gap |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    str(row["sample_data_status"]).replace("|", "/"),
                    str(row["task_count"]),
                    str(row["passed_task_count"]),
                    str(row["artifact_file_count"]),
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
    json_path = out_dir / "sample_data_evidence_map.json"
    md_path = out_dir / "sample_data_evidence_map.md"
    csv_path = out_dir / "sample_data_evidence_map.csv"
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
    return {"json": str(json_path), "markdown": str(md_path), "csv": str(csv_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate sample-data evidence map.")
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
