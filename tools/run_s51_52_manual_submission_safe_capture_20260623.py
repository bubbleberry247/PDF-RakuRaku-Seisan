from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SCENARIO_ROOT = Path(r"C:\ProgramData\RK10\Robots\51&52ソフトバンク部門集計楽楽精算申請")
TOOLS_DIR = SCENARIO_ROOT / "tools"
DATA_RESULT_DIR = SCENARIO_ROOT / "data" / "result"
LOG_DIR = SCENARIO_ROOT / "log"
CANONICAL_RKS = (
    SCENARIO_ROOT
    / "scenario"
    / "51&52_ソフトバンク_PROD_担当者選択_合算分離_Excel保存まで_20260608.rks"
)
REPORT_ROOT = Path(
    r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports"
    r"\s51_52_manual_submission_safe_recheck_20260623"
)
RKS_METADATA_GUARD = Path(
    r"C:\Users\masam\.codex\skills\rk10-rks-safety\scripts\rks_metadata_guard.py"
)
RKS_STATUS_GATE = Path(
    r"C:\Users\masam\.codex\skills\rk10-rks-safety\scripts\rks_status_gate.py"
)


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


def run_command(label: str, command: list[str], report_dir: Path) -> dict[str, object]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        command,
        cwd=SCENARIO_ROOT,
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
        "exit_code": result.returncode,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }


def copy_artifact(source: Path, report_dir: Path) -> str:
    if not source.exists() or not source.is_file():
        return ""
    destination = report_dir / source.name
    shutil.copy2(source, destination)
    number_file(destination)
    return str(destination)


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = REPORT_ROOT / f"run_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)

    python_executable = sys.executable
    runs: list[dict[str, object]] = []
    runs.append(
        run_command(
            "py_compile",
            [
                python_executable,
                "-X",
                "utf8",
                "-m",
                "py_compile",
                str(TOOLS_DIR / "main_51.py"),
                str(TOOLS_DIR / "main_52.py"),
                str(TOOLS_DIR / "run_pipeline.py"),
                str(TOOLS_DIR / "mail_sender.py"),
            ],
            report_dir,
        )
    )
    runs.append(
        run_command(
            "pipeline_excel_only_dryrun_no_mail",
            [
                python_executable,
                "-X",
                "utf8",
                str(TOOLS_DIR / "run_pipeline.py"),
                "--month",
                "2026-05",
                "--env",
                "PROD",
                "--dry-run",
                "--no-mail",
            ],
            report_dir,
        )
    )
    runs.append(
        run_command(
            "main52_manual_submission_record_no_mail",
            [
                python_executable,
                "-X",
                "utf8",
                str(TOOLS_DIR / "main_52.py"),
                "--month",
                "2026-05",
                "--env",
                "LOCAL",
                "--no-mail",
            ],
            report_dir,
        )
    )
    runs.append(
        run_command(
            "dangerous_rakuraku_flag_blocked",
            [
                python_executable,
                "-X",
                "utf8",
                str(TOOLS_DIR / "run_pipeline.py"),
                "--month",
                "2026-05",
                "--env",
                "LOCAL",
                "--dry-run",
                "--allow-rakuraku-application",
                "--save-draft",
                "--no-mail",
            ],
            report_dir,
        )
    )
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
        )
    )
    runs.append(
        run_command(
            "rks_status_gate_unconfirmed",
            [
                python_executable,
                "-X",
                "utf8",
                str(RKS_STATUS_GATE),
                str(CANONICAL_RKS),
                "--rk10-open",
                "unconfirmed",
                "--rk10-build",
                "unconfirmed",
                "--runtime",
                "unconfirmed",
                "--latest-log",
                "none",
                "--scope",
                "safe-stop",
            ],
            report_dir,
        )
    )

    artifacts = {
        "scenario51_result_2026_05": copy_artifact(
            DATA_RESULT_DIR / "scenario51_result_2026-05.json",
            report_dir,
        ),
        "scenario52_result_2026_05": copy_artifact(
            DATA_RESULT_DIR / "scenario52_result_2026-05.json",
            report_dir,
        ),
        "scenario51_latest_log": copy_artifact(
            max(LOG_DIR.glob("scenario_51_*.log"), default=Path()),
            report_dir,
        ),
        "scenario52_latest_log": copy_artifact(
            max(LOG_DIR.glob("scenario_52_*.log"), default=Path()),
            report_dir,
        ),
    }
    expected_exit_codes = {
        "py_compile": {0},
        "pipeline_excel_only_dryrun_no_mail": {0},
        "main52_manual_submission_record_no_mail": {0},
        "dangerous_rakuraku_flag_blocked": {2},
        "rks_metadata_guard": {0},
        "rks_status_gate_unconfirmed": {1},
    }
    unexpected_failures = [
        run
        for run in runs
        if int(run["exit_code"]) not in expected_exit_codes[str(run["label"])]
    ]
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scope": (
            "dry-run/no-mail plus manual-submission record only; SoftBank Rakuraku "
            "submission is manual by customer staff after combining scenario-created "
            "documents and postal invoice; no Rakuraku login, no draft save, no final "
            "submit, no mail"
        ),
        "scenario_root": str(SCENARIO_ROOT),
        "canonical_rks": str(CANONICAL_RKS),
        "report_dir": str(report_dir),
        "runs": runs,
        "artifacts": artifacts,
        "expected_exit_codes": {
            label: sorted(codes) for label, codes in expected_exit_codes.items()
        },
        "unexpected_failure_count": len(unexpected_failures),
        "unexpected_failures": unexpected_failures,
    }
    summary_path = report_dir / "s51_52_manual_submission_safe_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    number_file(summary_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not unexpected_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
