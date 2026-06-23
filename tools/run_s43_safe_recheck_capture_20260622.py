from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCENARIO_ROOT = Path(r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成")
TOOLS_DIR = SCENARIO_ROOT / "tools"
PDF_TOOLS_DIR = TOOLS_DIR / "pdf_annotate"
ENTRY_BAT = SCENARIO_ROOT / "run_scenario43_external_pipeline_v92.bat"
CURRENT_RKS = (
    SCENARIO_ROOT
    / "scenario"
    / "本番インストール版　４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版_v93_operator_select_first.rks"
)
LATEST_MANIFEST = (
    SCENARIO_ROOT
    / "work"
    / "pdf_out"
    / "【申請用】日本情報サービス協同組合_20260519_83049.xlsx.manifest.json"
)
LATEST_COMPLETION = SCENARIO_ROOT / "Temp" / "scenario43_external_pipeline_v92_last_completion.json"
REPORT_ROOT = Path(
    r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports"
    r"\s43_current_safe_recheck_20260622"
)
MIGRATION_REPORT_ROOT = Path(r"C:\ProgramData\RK10\Robots\migration\reports")
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as binary_handle:
        for chunk in iter(lambda: binary_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(
    label: str,
    command: list[str],
    report_dir: Path,
    *,
    cwd: Path = SCENARIO_ROOT,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8:backslashreplace"}
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout_seconds,
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


def copy_artifact(source: Path, report_dir: Path, *, destination_name: str | None = None) -> str:
    if not source.exists():
        return ""
    destination = report_dir / (destination_name or source.name)
    if source.resolve() == destination.resolve():
        number_file(source)
        return str(source)
    shutil.copy2(source, destination)
    number_file(destination)
    return str(destination)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else {}


def manifest_verification(manifest_path: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    excel_spec = manifest.get("excel_spec") if isinstance(manifest.get("excel_spec"), dict) else {}
    pdf = manifest.get("pdf") if isinstance(manifest.get("pdf"), dict) else {}
    source_workbook = manifest.get("source_workbook") if isinstance(manifest.get("source_workbook"), dict) else {}
    output_workbook = manifest.get("output_workbook") if isinstance(manifest.get("output_workbook"), dict) else {}
    saved_amounts = excel_spec.get("saved_amounts") if isinstance(excel_spec.get("saved_amounts"), list) else []
    excluded_amounts = excel_spec.get("excluded_amounts") if isinstance(excel_spec.get("excluded_amounts"), list) else []
    saved_amount_total = sum(int(row[1]) for row in saved_amounts if isinstance(row, list) and len(row) >= 2)
    excluded_amount_total = sum(int(row[1]) for row in excluded_amounts if isinstance(row, list) and len(row) >= 2)
    pdf_path = Path(str(pdf.get("path", "")))
    xlsx_path = Path(str(output_workbook.get("path", "")))
    source_path = Path(str(source_workbook.get("path", "")))
    checks = {
        "manifest_exists": manifest_path.exists(),
        "manifest_status_ok": manifest.get("status") == "OK",
        "pdf_exists": pdf_path.exists(),
        "xlsx_exists": xlsx_path.exists(),
        "source_workbook_exists": source_path.exists(),
        "saved_total_matches_application": saved_amount_total == int(excel_spec.get("rakuraku_application_total", -1)),
        "output_total_matches_application": int(output_workbook.get("total_amount", -1)) == int(excel_spec.get("rakuraku_application_total", -2)),
        "pdf_total_matches_application": int(pdf.get("rakuraku_application_amount", -1)) == int(excel_spec.get("rakuraku_application_total", -2)),
        "source_total_matches_manifest": int(source_workbook.get("total_amount", -1)) == int(excel_spec.get("source_invoice_total", -2)),
    }
    file_hashes = {}
    for key, file_path in (("pdf", pdf_path), ("xlsx", xlsx_path), ("source_workbook", source_path)):
        if file_path.exists():
            file_hashes[key] = sha256_file(file_path)
    return {
        "manifest_path": str(manifest_path),
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "source_invoice_total": excel_spec.get("source_invoice_total"),
        "rakuraku_application_total": excel_spec.get("rakuraku_application_total"),
        "saved_amounts": saved_amounts,
        "saved_amount_total": saved_amount_total,
        "excluded_amounts": excluded_amounts,
        "excluded_amount_total": excluded_amount_total,
        "pdf": pdf,
        "source_workbook": source_workbook,
        "output_workbook": output_workbook,
        "file_hashes": file_hashes,
    }


def write_summary_md(summary: dict[str, Any], report_dir: Path) -> str:
    manifest = summary["manifest_verification"]
    runs = summary["runs"]
    run_rows = [
        f"| {run['label']} | {run['exit_code']} | `{run['stdout']}` | `{run['stderr']}` |"
        for run in runs
    ]
    md_path = report_dir / "s43_current_safe_recheck.md"
    lines = [
        "# Scenario 43 Current Safe Recheck 2026-06-22",
        "",
        "## Conclusion",
        "",
        "- `PYTHON_PRECHECK_OK`: 主要Pythonは `py_compile` exit 0。",
        "- `SAFE_SELF_TEST_OK`: 外部パイプラインの `--self-test` は exit 0。",
        "- `SAFE_NOOP_OK`: `--skip-pdf --skip-rakuraku` は exit 0。ETCサイト、楽楽精算、一時保存、メール送信は実行していない。",
        "- `BUSINESS_AMOUNT_EVIDENCE_OK`: 最新manifestは status OK、楽楽申請額83,049円、請求元総額350,914円を保持。",
        "- `RKS_STRUCTURE_OK_CANDIDATE`: v93 RKS metadata guard は exit 0。",
        "- `RKS_STATUS_UNCONFIRMED`: v93 RKSのRK10 editor open/build/runtime/latest clean logは、この実行では未確認。",
        "- `NOT_PRODUCTION_FINAL`: 最終申請、実メール、本番支払、実RKS ButtonRunは未実行。",
        "",
        "## Scope",
        "",
        f"- scenario_root: `{summary['scenario_root']}`",
        f"- current_rks: `{summary['current_rks']}`",
        f"- entry_bat: `{summary['entry_bat']}`",
        f"- report_dir: `{summary['report_dir']}`",
        f"- safety: `{summary['scope']}`",
        "",
        "## Business Amount Evidence",
        "",
        f"- manifest: `{manifest['manifest_path']}`",
        f"- all_checks_passed: `{manifest['all_checks_passed']}`",
        f"- source_invoice_total: `{manifest['source_invoice_total']}`",
        f"- rakuraku_application_total: `{manifest['rakuraku_application_total']}`",
        f"- saved_amount_total: `{manifest['saved_amount_total']}`",
        f"- excluded_amount_total: `{manifest['excluded_amount_total']}`",
        f"- saved_amounts: `{json.dumps(manifest['saved_amounts'], ensure_ascii=False)}`",
        f"- excluded_amounts: `{json.dumps(manifest['excluded_amounts'], ensure_ascii=False)}`",
        "",
        "## Runs",
        "",
        "| Label | Exit | Stdout | Stderr |",
        "|---|---:|---|---|",
        *run_rows,
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
            "- RK10 Editorでv93 RKSを開く、build、safe-stop/runtime、latest clean logを現地証跡化する。",
            "- 実ETCダウンロード、楽楽精算一時保存、完了メールは承認後の別ゲートで扱う。",
            "- 最終申請クリックは自動化せず、担当者確認後の手動操作として維持する。",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    number_file(md_path)
    return str(md_path)


def copy_report_to_migration(report_dir: Path, timestamp: str) -> str:
    destination = MIGRATION_REPORT_ROOT / f"s43_current_safe_recheck_{timestamp}"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(report_dir, destination)
    return str(destination)


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = REPORT_ROOT / f"run_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    python_executable = sys.executable
    noop_log = report_dir / "pipeline_noop.log"
    noop_trace = report_dir / "pipeline_noop_trace"

    key_python_files = [
        TOOLS_DIR / "scenario43_external_pipeline_v92.py",
        TOOLS_DIR / "main_v2026.06.08.1.py",
        TOOLS_DIR / "download_latest_etc_zip_v92.py",
        TOOLS_DIR / "stage_latest_etc_zip_v85.py",
        TOOLS_DIR / "rakuraku_apply_ready_stop_v60-1_operator_2price.py",
        TOOLS_DIR / "rakuraku_temporary_save_v83_5_operator_2price.py",
        PDF_TOOLS_DIR / "scenario43_amount_policy.py",
        PDF_TOOLS_DIR / "gen_application_xlsx_v85.py",
        PDF_TOOLS_DIR / "send_completion_mail_v88.py",
    ]
    runs: list[dict[str, Any]] = []
    runs.append(
        run_command(
            "py_compile",
            [python_executable, "-X", "utf8", "-m", "py_compile", *[str(path) for path in key_python_files]],
            report_dir,
        )
    )
    runs.append(run_command("external_pipeline_self_test", [str(ENTRY_BAT), "--self-test"], report_dir, timeout_seconds=240))
    runs.append(
        run_command(
            "external_pipeline_noop_skip_pdf_skip_rakuraku",
            [
                str(ENTRY_BAT),
                "--skip-pdf",
                "--skip-rakuraku",
                "--timeout-seconds",
                "60",
                "--log",
                str(noop_log),
                "--trace-dir",
                str(noop_trace),
            ],
            report_dir,
            timeout_seconds=120,
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
                str(CURRENT_RKS),
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
                str(CURRENT_RKS),
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
        "latest_manifest": copy_artifact(LATEST_MANIFEST, report_dir),
        "latest_completion_before_noop": copy_artifact(LATEST_COMPLETION, report_dir, destination_name="latest_completion_after_noop.json"),
        "pipeline_noop_log": copy_artifact(noop_log, report_dir),
    }
    if noop_trace.exists():
        trace_copy = report_dir / "pipeline_noop_trace_copy"
        if trace_copy.exists():
            shutil.rmtree(trace_copy)
        shutil.copytree(noop_trace, trace_copy)
        artifacts["pipeline_noop_trace"] = str(trace_copy)
    manifest_result = manifest_verification(LATEST_MANIFEST)
    expected_exit_codes = {
        "py_compile": {0},
        "external_pipeline_self_test": {0},
        "external_pipeline_noop_skip_pdf_skip_rakuraku": {0},
        "rks_metadata_guard": {0},
        "rks_status_gate_unconfirmed": {1},
    }
    unexpected_failures = [
        run for run in runs if int(run["exit_code"]) not in expected_exit_codes[str(run["label"])]
    ]
    if not manifest_result["all_checks_passed"]:
        unexpected_failures.append(
            {
                "label": "manifest_verification",
                "exit_code": 1,
                "failed_checks": {
                    key: value for key, value in manifest_result["checks"].items() if not value
                },
            }
        )
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scope": (
            "safe self-test/no-op/manifest verification only; no ETC login/download, "
            "no Rakuraku temporary save, no real mail, no final submit, no RK10 ButtonRun"
        ),
        "scenario_root": str(SCENARIO_ROOT),
        "current_rks": str(CURRENT_RKS),
        "entry_bat": str(ENTRY_BAT),
        "report_dir": str(report_dir),
        "runs": runs,
        "manifest_verification": manifest_result,
        "artifacts": artifacts,
        "unexpected_failure_count": len(unexpected_failures),
        "unexpected_failures": unexpected_failures,
    }
    summary_path = report_dir / "s43_safe_recheck_summary.json"
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
