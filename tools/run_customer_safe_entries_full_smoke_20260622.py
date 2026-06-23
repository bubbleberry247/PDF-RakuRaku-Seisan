"""Run all customer safe-entry BAT files and write a full smoke report.

This runner only calls the curated customer-safe BAT entries. It captures
stdout/stderr, checks expected safe-stop exit codes, and closes the scenario 58
safe GUI launcher process after proving it started. It does not run RK10
ButtonRun, send mail, print, submit, pay, call paid Azure OCR, or write
production files.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
ENTRY_ROOT = Path(r"C:\ProgramData\RK10\Robots\migration\customer_safe_entries_20260622")
REPORT_DIR = ROOT / "plans" / "reports" / "customer_safe_entries_full_smoke_20260622"
CANONICAL_REPORT_MD = REPORT_DIR / "customer_safe_entries_full_smoke_20260622.md"
CANONICAL_REPORT_JSON = REPORT_DIR / "customer_safe_entries_full_smoke_20260622.json"
CANONICAL_REPORT_CSV = REPORT_DIR / "customer_safe_entries_full_smoke_20260622.csv"
VALIDATION_JSON = ENTRY_ROOT / "validation_20260622.json"
S58_PROCESS_MARKER = "s58_launcher_safe_20260604_v2.py"


@dataclass(frozen=True)
class SafeEntry:
    name: str
    bat_name: str
    expected_exit_codes: tuple[int, ...]
    timeout_seconds: int
    note: str = ""
    cleanup_marker: str = ""


@dataclass(frozen=True)
class EntryResult:
    name: str
    bat_path: str
    exit_code: int | None
    expected_exit_codes: str
    expected_ok: bool
    timed_out: bool
    elapsed_seconds: float
    stdout_path: str
    stderr_path: str
    stdout_bytes: int
    stderr_bytes: int
    note: str
    cleanup_found_count: int
    cleanup_remaining_count: int
    cleanup_json_path: str


SAFE_ENTRIES = [
    SafeEntry("12_13_scan", "12_13_SAFE_SCAN_ONLY_MAX1_ここから起動.bat", (0,), 180),
    SafeEntry("37_sample", "37_SAFE_SAMPLE_DRYRUN_ここから起動.bat", (0,), 180),
    SafeEntry("37_review", "37_SAFE_PRE_REGISTER_REVIEW_OFFLINE_ここから起動.bat", (0,), 180),
    SafeEntry("38_precheck", "38_SAFE_PRECHECK_ここから起動.bat", (0, 1), 180, "MainSV到達時は0、未到達時は安全停止1"),
    SafeEntry("42_csv_dryrun", "42_SAFE_CSV_DRYRUN_ここから起動.bat", (0,), 180),
    SafeEntry("42_review", "42_SAFE_REVIEW_ここから起動.bat", (0,), 180),
    SafeEntry("43_selftest", "43_SAFE_SELFTEST_ここから起動.bat", (0,), 180),
    SafeEntry("43_noop", "43_SAFE_NOOP_ここから起動.bat", (0,), 180),
    SafeEntry("44_review", "44_SAFE_REVIEW_ONLY_ここから起動.bat", (0,), 180),
    SafeEntry("47_dryrun", "47_SAFE_DRYRUN_ここから起動.bat", (0,), 180),
    SafeEntry("51_52_excel", "51_52_SAFE_EXCEL_ONLY_DRYRUN_ここから起動.bat", (0,), 240),
    SafeEntry("51_52_future", "51_52_SAFE_FUTURE_SAVE_DRAFT_DRYRUN_ここから起動.bat", (0,), 240),
    SafeEntry("55_v2", "55_SAFE_V2_COPY_WRITE_NO_MAIL_ここから起動.bat", (0,), 900),
    SafeEntry("56_local", "56_SAFE_LOCAL_DRYRUN_NO_MAIL_ここから起動.bat", (0,), 240),
    SafeEntry("56_prod", "56_SAFE_PROD_DRYRUN_NO_MAIL_ここから起動.bat", (0, 1), 240, "MainSV到達時は0、未到達時は安全停止1"),
    SafeEntry("57_dryrun", "57_SAFE_DRYRUN_ここから起動.bat", (0,), 180),
    SafeEntry("58_gui", "58_SAFE_V2_確認画面_ここから起動.bat", (0,), 60, "SAFE GUI起動のみ。起動後に検証プロセスを閉じる", S58_PROCESS_MARKER),
    SafeEntry("63_review", "63_SAFE_REVIEW_ここから起動.bat", (0,), 180),
    SafeEntry("63_dryrun_8", "63_SAFE_DRYRUN_8_ここから起動.bat", (0,), 240),
    SafeEntry("70_review", "70_SAFE_REVIEW_PARAMS_ここから起動.bat", (0,), 180),
    SafeEntry("70_confirm", "70_SAFE_CONFIRM_PREVIEW_ここから起動.bat", (0, 3), 180, "承認前提不足は安全BLOCK 3、条件充足時はconfirm-preview 0"),
    SafeEntry("71_pytest", "71_SAFE_PYTEST_ONLY_ここから起動.bat", (0,), 240),
]


def safe_file_name(value: str) -> str:
    return (
        value.lower()
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace("&", "_")
    )


def run_bat(entry: SafeEntry, run_dir: Path) -> EntryResult:
    bat_path = ENTRY_ROOT / entry.bat_name
    if not bat_path.exists():
        raise FileNotFoundError(str(bat_path))
    stdout_path = run_dir / f"{safe_file_name(entry.name)}.stdout.txt"
    stderr_path = run_dir / f"{safe_file_name(entry.name)}.stderr.txt"
    started = time.monotonic()
    timed_out = False
    exit_code: int | None
    try:
        completed = subprocess.run(
            ["cmd.exe", "/c", str(bat_path)],
            cwd=str(ENTRY_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=entry.timeout_seconds,
            check=False,
        )
        stdout_text = completed.stdout
        stderr_text = completed.stderr
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout_text = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr_text = exc.stderr if isinstance(exc.stderr, str) else ""
        exit_code = None
    elapsed = round(time.monotonic() - started, 3)
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")
    cleanup = cleanup_processes(entry.cleanup_marker, run_dir)
    expected_ok = (not timed_out) and exit_code in entry.expected_exit_codes
    return EntryResult(
        name=entry.name,
        bat_path=str(bat_path),
        exit_code=exit_code,
        expected_exit_codes=",".join(str(code) for code in entry.expected_exit_codes),
        expected_ok=expected_ok,
        timed_out=timed_out,
        elapsed_seconds=elapsed,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        stdout_bytes=stdout_path.stat().st_size,
        stderr_bytes=stderr_path.stat().st_size,
        note=entry.note,
        cleanup_found_count=int(cleanup["found_count"]),
        cleanup_remaining_count=int(cleanup["remaining_count"]),
        cleanup_json_path=str(cleanup["json_path"]) if cleanup["json_path"] else "",
    )


def cleanup_processes(marker: str, run_dir: Path) -> dict[str, object]:
    if not marker:
        return {"found_count": 0, "remaining_count": 0, "json_path": ""}
    time.sleep(8)
    json_path = run_dir / f"{safe_file_name(marker)}.cleanup.json"
    ps_script = f"""
$marker = {json.dumps(marker)}
$before = @(Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like \"*$marker*\" -and $_.ProcessId -ne $PID }})
$before | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath {json.dumps(str(json_path) + ".before.json")} -Encoding UTF8
foreach($proc in $before) {{
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}}
Start-Sleep -Seconds 2
$after = @(Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like \"*$marker*\" -and $_.ProcessId -ne $PID }})
$after | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath {json.dumps(str(json_path) + ".after.json")} -Encoding UTF8
[pscustomobject]@{{
    marker = $marker
    found_count = $before.Count
    remaining_count = $after.Count
}} | ConvertTo-Json -Depth 4
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        payload = {
            "marker": marker,
            "found_count": 0,
            "remaining_count": -1,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    else:
        payload = json.loads(completed.stdout)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["json_path"] = json_path
    return payload


def build_payload(results: list[EntryResult], run_dir: Path) -> dict[str, Any]:
    expected_ok_count = sum(1 for result in results if result.expected_ok)
    timeout_count = sum(1 for result in results if result.timed_out)
    cleanup_remaining_count = sum(result.cleanup_remaining_count for result in results)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(run_dir),
        "total": len(results),
        "expected_ok_count": expected_ok_count,
        "unexpected_count": len(results) - expected_ok_count,
        "timeout_count": timeout_count,
        "cleanup_remaining_count": cleanup_remaining_count,
        "validation_json": str(VALIDATION_JSON),
        "safety": (
            "customer-safe BAT entries only; no RK10 ButtonRun; no real mail; "
            "no real print; no final submit; no payment execution; no paid Azure OCR"
        ),
        "results": [asdict(result) for result in results],
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(asdict(EntryResult("", "", None, "", False, False, 0, "", "", 0, 0, "", 0, 0, "")).keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 客先安全入口 全22件フルスモーク再実行 2026-06-22",
        "",
        "## Claim",
        f"全{payload['total']}件の客先安全入口BATを現在のASCIIランナー版で実行し、"
        f"期待終了コード一致 {payload['expected_ok_count']}/{payload['total']} 件、"
        f"unexpected {payload['unexpected_count']} 件、timeout {payload['timeout_count']} 件だった。",
        "",
        "## Primary Source",
        f"- 結果JSON: `{CANONICAL_REPORT_JSON}`",
        f"- 結果CSV: `{CANONICAL_REPORT_CSV}`",
        f"- run_dir: `{payload['run_dir']}`",
        f"- validation: `{payload['validation_json']}`",
        f"- safety: {payload['safety']}",
        "",
        "## Safety Scope",
        "- 実メールなし、実印刷なし、最終申請なし、本支払確定なし、paid Azure OCRなし。",
        "- RK10 ButtonRun、RKS runtime実行、本番書込は実行しない。",
        "- 38/56 PRODはMainSV未到達なら安全停止1、到達済みなら0を期待値として許容する。",
        "- 70 confirm-previewは承認前提不足なら安全BLOCK 3、条件充足時のpreview 0を許容する。",
        "- 58 GUIは起動確認後、検証起動分の `s58_launcher_safe_20260604_v2.py` プロセスを閉じる。",
        "- RK10ライセンス画面が出る場合は、既定の `RPA開発版AI付き` のまま、ラジオボタンを変更せずOKのみ押す。",
        "",
        "## Results",
        "",
        "| Entry | Exit | Expected | Expected OK | Timeout | Seconds | Stderr bytes | Cleanup remaining | Note |",
        "|---|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for result in payload["results"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(result["name"]),
                    str(result["exit_code"]),
                    str(result["expected_exit_codes"]),
                    "YES" if result["expected_ok"] else "NO",
                    "YES" if result["timed_out"] else "NO",
                    str(result["elapsed_seconds"]),
                    str(result["stderr_bytes"]),
                    str(result["cleanup_remaining_count"]),
                    str(result["note"]) or "-",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Known Facts Check",
            "- このフルスモークは安全入口の起動・dry-run・safe-stop確認であり、本番移行OKではない。",
            "- MainSV到達、楽楽一時保存、実メール、実印刷、支払確定、RK10 build/runtime/latest clean logは別ゲート。",
            "",
            "## Confidence",
            "High for customer-safe BAT execution results because each row has captured stdout/stderr and exit code in the run directory.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], run_dir: Path) -> None:
    run_json = run_dir / "full_smoke_results.json"
    run_csv = run_dir / "full_smoke_results.csv"
    run_md = run_dir / "full_smoke_results.md"
    report_text = build_markdown(payload)
    run_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(run_csv, payload["results"])
    run_md.write_text(report_text, encoding="utf-8")
    CANONICAL_REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(CANONICAL_REPORT_CSV, payload["results"])
    CANONICAL_REPORT_MD.write_text(report_text, encoding="utf-8")
    for path in (run_json, run_csv, run_md, CANONICAL_REPORT_JSON, CANONICAL_REPORT_CSV, CANONICAL_REPORT_MD):
        write_numbered_copy(path)


def run_all(run_dir: Path) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    results = [run_bat(entry, run_dir) for entry in SAFE_ENTRIES]
    payload = build_payload(results, run_dir)
    write_outputs(payload, run_dir)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run customer safe-entry full smoke.")
    parser.add_argument("--out-dir", type=Path, default=REPORT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = args.out_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    payload = run_all(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["unexpected_count"] == 0 and payload["timeout_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
