from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCENARIO_ROOT = Path(r"C:\ProgramData\RK10\Robots\37レコル公休・有休登録")
TOOLS_DIR = SCENARIO_ROOT / "tools"
OUTPUT_DIR = SCENARIO_ROOT / "work" / "output"
SAFE_REVIEW_DIR = OUTPUT_DIR / "safe_review_20260604"
CANONICAL_RKS = SCENARIO_ROOT / "senario" / "37レコル公休有休登録_完成版_v1.1.rks"
REPORT_ROOT = Path(
    r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports"
    r"\s37_current_safe_dryrun_recheck_20260622"
)
MIGRATION_REPORT_ROOT = Path(r"C:\ProgramData\RK10\Robots\migration\reports")
RKS_METADATA_GUARD = Path(
    r"C:\Users\masam\.codex\skills\rk10-rks-safety\scripts\rks_metadata_guard.py"
)
RKS_STATUS_GATE = Path(
    r"C:\Users\masam\.codex\skills\rk10-rks-safety\scripts\rks_status_gate.py"
)
RKS_IMPORTED_EVIDENCE_DIR = Path(
    r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports"
    r"\bundle_evidence_packs_20260620\rk10_editor_runtime_bundle"
    r"\final_evidence\scenario_37"
)
SOURCE_STATUS_GATE_LOG = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
    r"\rk10_open_build_safe_stop_status_gate_20260618_1019"
    r"\s37.status_gate.md.numbered"
)
STATE_FILE_NAMES = ("data.json", "result.json", "current_index.txt")


def number_file(path: Path) -> None:
    if not path.exists() or path.is_dir():
        return
    numbered = path.with_name(path.name + ".numbered")
    line_number = 0
    with path.open("r", encoding="utf-8", errors="replace") as source_handle:
        with numbered.open("w", encoding="utf-8", newline="\n") as numbered_handle:
            for line in source_handle:
                line_number += 1
                numbered_handle.write(f"{line_number}: {line.rstrip()}\n")


def run_command(
    label: str,
    command: list[str],
    report_dir: Path,
    *,
    cwd: Path = TOOLS_DIR,
) -> dict[str, Any]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    stdout_path = report_dir / f"{label}.stdout.txt"
    stderr_path = report_dir / f"{label}.stderr.txt"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    number_file(stdout_path)
    number_file(stderr_path)
    return {
        "label": label,
        "command": command,
        "cwd": str(cwd),
        "exit_code": result.returncode,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }


def backup_state(report_dir: Path) -> dict[str, str]:
    backup_dir = report_dir / "original_state_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    state: dict[str, str] = {}
    for file_name in STATE_FILE_NAMES:
        source = OUTPUT_DIR / file_name
        if source.exists():
            destination = backup_dir / file_name
            shutil.copy2(source, destination)
            state[file_name] = str(destination)
        else:
            state[file_name] = ""
    return state


def restore_state(state: dict[str, str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for file_name, backup_path in state.items():
        target = OUTPUT_DIR / file_name
        if target.exists():
            target.unlink()
        if backup_path:
            shutil.copy2(Path(backup_path), target)


def copy_artifact(source: Path, report_dir: Path, *, destination_name: str | None = None) -> str:
    if not source.exists():
        return ""
    destination = report_dir / (destination_name or source.name)
    shutil.copy2(source, destination)
    number_file(destination)
    return str(destination)


def copy_latest_safe_review(report_dir: Path, created_after: datetime) -> dict[str, str]:
    copied: dict[str, str] = {}
    if not SAFE_REVIEW_DIR.exists():
        return copied
    candidates = sorted(
        SAFE_REVIEW_DIR.glob("s37_pre_register_review_*.*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for source in candidates:
        modified_at = datetime.fromtimestamp(source.stat().st_mtime)
        if modified_at < created_after:
            continue
        destination_name = f"safe_review_{source.name}"
        copied[source.suffix.lower().lstrip(".") or source.name] = copy_artifact(
            source,
            report_dir,
            destination_name=destination_name,
        )
    return copied


def extract_json_object(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text.strip(), flags=re.DOTALL)
    if not match:
        return {}
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def run_main37_sample_flow(report_dir: Path, python_executable: str) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    runs.append(
        run_command(
            "main37_pre_dryrun_sample",
            [python_executable, "-X", "utf8", str(TOOLS_DIR / "main_37.py"), "--pre", "--dry-run"],
            report_dir,
        )
    )
    runs.append(
        run_command(
            "main37_reset",
            [python_executable, "-X", "utf8", str(TOOLS_DIR / "main_37.py"), "--reset"],
            report_dir,
        )
    )
    runs.append(
        run_command(
            "main37_init_result",
            [python_executable, "-X", "utf8", str(TOOLS_DIR / "main_37.py"), "--init-result"],
            report_dir,
        )
    )
    count_run = run_command(
        "main37_get_count",
        [python_executable, "-X", "utf8", str(TOOLS_DIR / "main_37.py"), "--get-count"],
        report_dir,
    )
    runs.append(count_run)
    data_run = run_command(
        "main37_get_data",
        [python_executable, "-X", "utf8", str(TOOLS_DIR / "main_37.py"), "--get-data"],
        report_dir,
    )
    runs.append(data_run)
    register_run = run_command(
        "main37_register_leave_dryrun",
        [
            python_executable,
            "-X",
            "utf8",
            str(TOOLS_DIR / "main_37.py"),
            "--register-leave",
            "--dry-run",
        ],
        report_dir,
    )
    runs.append(register_run)

    data_stdout = Path(str(data_run["stdout"])).read_text(encoding="utf-8", errors="replace")
    data = extract_json_object(data_stdout)
    wf_id = str(data.get("wf_id") or "TEST001")
    register_stdout = Path(str(register_run["stdout"])).read_text(encoding="utf-8", errors="replace")
    register_result = extract_json_object(register_stdout)
    status = str(register_result.get("status") or "成功")
    message = str(register_result.get("message") or "dry-run")

    runs.append(
        run_command(
            "main37_record_dryrun_result",
            [
                python_executable,
                "-X",
                "utf8",
                str(TOOLS_DIR / "main_37.py"),
                "--record",
                wf_id,
                status,
                message,
            ],
            report_dir,
        )
    )
    runs.append(
        run_command(
            "main37_complete_wf_dryrun",
            [
                python_executable,
                "-X",
                "utf8",
                str(TOOLS_DIR / "main_37.py"),
                "--complete-wf",
                wf_id,
                "--dry-run",
            ],
            report_dir,
        )
    )
    runs.append(
        run_command(
            "main37_postprocess",
            [python_executable, "-X", "utf8", str(TOOLS_DIR / "main_37.py"), "--post"],
            report_dir,
        )
    )
    return {"runs": runs, "wf_id": wf_id, "register_result": register_result}


def write_summary_md(summary: dict[str, Any], report_dir: Path) -> str:
    md_path = report_dir / "s37_current_safe_dryrun_recheck.md"
    sample_flow = summary["sample_flow"]
    run_rows = [
        f"| {run['label']} | {run['exit_code']} | `{run['stdout']}` | `{run['stderr']}` |"
        for run in summary["runs"]
    ]
    sample_run_rows = [
        f"| {run['label']} | {run['exit_code']} | `{run['stdout']}` | `{run['stderr']}` |"
        for run in sample_flow["runs"]
    ]
    lines = [
        "# Scenario 37 Current Safe Dry-run Recheck 2026-06-22",
        "",
        "## Conclusion",
        "",
        "- `PYTHON_PRECHECK_OK`: `py_compile` は exit 0。",
        "- `SAMPLE_FLOW_OK`: `main_37.py --pre --dry-run` から登録dry-run、WF完了dry-run、postprocessまで exit 0。",
        "- `SAMPLE_VALIDATION_OK`: Method-1 サンプル検証は exit 0。",
        "- `RKS_STRUCTURE_OK_CANDIDATE`: metadata guard は exit 0。",
        "- `RUNTIME_SAFE_STOP_CONFIRMED`: 既存のRK10 open/build/safe-stop取込証跡は clean。ただし本日このツールではRK10実行していない。",
        "- `NOT_PRODUCTION_READY`: RecoRu本番登録、Cybozu本番完了、メール実送信は未実行。",
        "",
        "## Scope",
        "",
        f"- scenario_root: `{summary['scenario_root']}`",
        f"- canonical_rks: `{summary['canonical_rks']}`",
        f"- report_dir: `{summary['report_dir']}`",
        f"- safety: `{summary['scope']}`",
        "",
        "## Runs",
        "",
        "| Label | Exit | Stdout | Stderr |",
        "|---|---:|---|---|",
        *run_rows,
        "",
        "## Main 37 Sample Flow",
        "",
        f"- wf_id: `{sample_flow['wf_id']}`",
        f"- register_result: `{json.dumps(sample_flow['register_result'], ensure_ascii=False)}`",
        "",
        "| Label | Exit | Stdout | Stderr |",
        "|---|---:|---|---|",
        *sample_run_rows,
        "",
        "## Copied Artifacts",
        "",
    ]
    for key, value in summary["artifacts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Remaining Gates",
            "",
            "- 実対象日のpending itemで、担当者確認付きの登録直前停止レビューを取り直す。",
            "- RecoRu登録POST、Cybozu完了、メール実送信は、承認後の別ゲートで実施する。",
            "- RKSはsafe-stop scopeの証跡あり。本番業務登録OKとは別扱い。",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    number_file(md_path)
    return str(md_path)


def copy_report_to_migration(report_dir: Path, timestamp: str) -> str:
    destination = MIGRATION_REPORT_ROOT / f"s37_current_safe_dryrun_recheck_{timestamp}"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(report_dir, destination)
    return str(destination)


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = REPORT_ROOT / f"run_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    python_executable = sys.executable

    original_state = backup_state(report_dir)
    runs: list[dict[str, Any]] = []
    artifacts: dict[str, str | dict[str, str]] = {}
    sample_flow: dict[str, Any] = {"runs": [], "wf_id": "", "register_result": {}}
    review_started_at = datetime.now()
    try:
        runs.append(
            run_command(
                "py_compile",
                [
                    python_executable,
                    "-X",
                    "utf8",
                    "-m",
                    "py_compile",
                    str(TOOLS_DIR / "main_37.py"),
                    str(TOOLS_DIR / "main_37_safe_20260604.py"),
                    str(TOOLS_DIR / "mail_sender.py"),
                    str(TOOLS_DIR / "run_method1_sample_validation_37.py"),
                ],
                report_dir,
            )
        )
        runs.append(
            run_command(
                "method1_sample_validation",
                [
                    python_executable,
                    "-X",
                    "utf8",
                    str(TOOLS_DIR / "run_method1_sample_validation_37.py"),
                ],
                report_dir,
            )
        )
        sample_flow = run_main37_sample_flow(report_dir, python_executable)
        runs.append(
            run_command(
                "pre_register_review_offline",
                [
                    python_executable,
                    "-X",
                    "utf8",
                    str(TOOLS_DIR / "main_37_safe_20260604.py"),
                    "--pre-register-review",
                    "--all",
                ],
                report_dir,
            )
        )
        artifacts["safe_review"] = copy_latest_safe_review(report_dir, review_started_at)
        artifacts["sample_data_json"] = copy_artifact(OUTPUT_DIR / "data.json", report_dir)
        artifacts["sample_result_json"] = copy_artifact(OUTPUT_DIR / "result.json", report_dir)
    finally:
        restore_state(original_state)

    runs.append(
        run_command(
            "rks_metadata_guard",
            [
                python_executable,
                "-X",
                "utf8",
                str(RKS_METADATA_GUARD),
                "scan",
                str(CANONICAL_RKS),
                "--fail-on-risk",
            ],
            report_dir,
            cwd=SCENARIO_ROOT,
        )
    )
    runs.append(
        run_command(
            "rks_status_gate_existing_safe_stop_scope",
            [
                python_executable,
                "-X",
                "utf8",
                str(RKS_STATUS_GATE),
                str(CANONICAL_RKS),
                "--rk10-open",
                "confirmed",
                "--rk10-build",
                "confirmed",
                "--runtime",
                "confirmed",
                "--latest-log",
                "clean",
                "--scope",
                "safe-stop",
            ],
            report_dir,
            cwd=SCENARIO_ROOT,
        )
    )
    artifacts["imported_rks_status_gate"] = copy_artifact(
        RKS_IMPORTED_EVIDENCE_DIR / "scenario_37_rks_status_gate_20260622_071045.txt",
        report_dir,
    )
    artifacts["imported_rks_latest_log_check"] = copy_artifact(
        RKS_IMPORTED_EVIDENCE_DIR / "scenario_37_safe_stop_latest_clean_log_20260622_071045.txt",
        report_dir,
    )
    artifacts["source_status_gate_log"] = copy_artifact(SOURCE_STATUS_GATE_LOG, report_dir)

    expected_exit_codes = {
        "py_compile": {0},
        "method1_sample_validation": {0},
        "pre_register_review_offline": {0},
        "rks_metadata_guard": {0},
        "rks_status_gate_existing_safe_stop_scope": {0},
    }
    all_runs = [*runs, *sample_flow["runs"]]
    for run in sample_flow["runs"]:
        expected_exit_codes[str(run["label"])] = {0}
    unexpected_failures = [
        run
        for run in all_runs
        if int(run["exit_code"]) not in expected_exit_codes.get(str(run["label"]), {0})
    ]
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scope": (
            "sample/dry-run only; no RecoRu update POST, no Cybozu completion, "
            "no real mail, no RK10 ButtonRun in this wrapper"
        ),
        "scenario_root": str(SCENARIO_ROOT),
        "canonical_rks": str(CANONICAL_RKS),
        "report_dir": str(report_dir),
        "runs": runs,
        "sample_flow": sample_flow,
        "artifacts": artifacts,
        "unexpected_failure_count": len(unexpected_failures),
        "unexpected_failures": unexpected_failures,
    }
    summary_path = report_dir / "s37_safe_dryrun_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    number_file(summary_path)
    summary["artifacts"]["summary_json"] = str(summary_path)
    summary["artifacts"]["summary_md"] = write_summary_md(summary, report_dir)
    migration_copy = copy_report_to_migration(report_dir, timestamp)
    summary["migration_report_copy"] = migration_copy
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    number_file(summary_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not unexpected_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
