"""Diagnose Scenario 12/13 Outlook COM environment without side effects.

This checker does not start Outlook, send mail, print, save attachments, or
change mailbox state. It only inspects local files, Python module availability,
process list, registry COM registration, and the latest OUTLOOK_COM_BUNDLE log.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_OUT_DIR = REPORTS / "outlook_com_environment_diagnosis_20260620"
EXTERNAL_RUNBOOK_JSON = (
    REPORTS / "external_approval_runbook_20260620" / "external_approval_runbook.json"
)
PYTHON_EXE = Path(r"C:\Users\masam\AppData\Local\Programs\Python\Python313\python.exe")
S12_TOOL = Path(
    r"C:\ProgramData\RK10\Robots"
    r"\12・13受信メールのPDFを保存・一括印刷"
    r"\tools\outlook_save_pdf_and_batch_print.py"
)
S12_PROD_CONFIG = Path(
    r"C:\ProgramData\RK10\Robots"
    r"\12・13受信メールのPDFを保存・一括印刷"
    r"\config\tool_config_prod.json"
)


@dataclass(frozen=True)
class CheckRow:
    check: str
    status: str
    detail: str
    evidence: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def module_status(module_name: str) -> CheckRow:
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return CheckRow(
            check=f"python_module:{module_name}",
            status="MISSING",
            detail=f"{module_name} is not importable",
            evidence="",
        )
    return CheckRow(
        check=f"python_module:{module_name}",
        status="OK",
        detail=f"{module_name} is importable",
        evidence=str(spec.origin or ""),
    )


def path_status(name: str, path: Path) -> CheckRow:
    return CheckRow(
        check=name,
        status="OK" if path.exists() else "MISSING",
        detail=str(path),
        evidence=str(path),
    )


def query_outlook_processes() -> CheckRow:
    command = [
        "tasklist",
        "/FI",
        "IMAGENAME eq OUTLOOK.EXE",
        "/FO",
        "CSV",
        "/NH",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    rows = []
    for row in csv.reader(completed.stdout.splitlines()):
        if row and row[0].strip('"').lower() == "outlook.exe":
            rows.append(row)
    if completed.returncode != 0:
        return CheckRow(
            check="process:OUTLOOK.EXE",
            status="UNKNOWN",
            detail=f"tasklist exit={completed.returncode}",
            evidence=completed.stderr.strip(),
        )
    if rows:
        return CheckRow(
            check="process:OUTLOOK.EXE",
            status="RUNNING",
            detail=f"OUTLOOK.EXE process_count={len(rows)}",
            evidence="; ".join(",".join(row) for row in rows[:3]),
        )
    return CheckRow(
        check="process:OUTLOOK.EXE",
        status="NOT_RUNNING",
        detail="No OUTLOOK.EXE process is visible to this user/session.",
        evidence=completed.stdout.strip(),
    )


def query_outlook_process_details() -> CheckRow:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "$p = Get-CimInstance Win32_Process -Filter \"name='OUTLOOK.EXE'\" "
            "| Select-Object -First 3 ProcessId,SessionId,ExecutablePath;"
            "if ($p) { $p | ConvertTo-Json -Compress }"
        ),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    stdout = (completed.stdout or "").strip()
    if completed.returncode != 0:
        return CheckRow(
            check="process_detail:OUTLOOK.EXE",
            status="UNKNOWN",
            detail=f"Get-CimInstance exit={completed.returncode}",
            evidence=(completed.stderr or "").strip(),
        )
    if not stdout:
        return CheckRow(
            check="process_detail:OUTLOOK.EXE",
            status="NOT_RUNNING",
            detail="No OUTLOOK.EXE process details found.",
            evidence="",
        )
    return CheckRow(
        check="process_detail:OUTLOOK.EXE",
        status="FOUND",
        detail=summarize_process_detail(stdout),
        evidence=stdout,
    )


def summarize_process_detail(process_json: str) -> str:
    try:
        payload = json.loads(process_json)
    except json.JSONDecodeError:
        return "Process details are not valid JSON."
    items = payload if isinstance(payload, list) else [payload]
    details = []
    for item in items:
        if not isinstance(item, dict):
            continue
        process_id = item.get("ProcessId", "")
        session_id = item.get("SessionId", "")
        executable_path = item.get("ExecutablePath", "")
        details.append(
            f"pid={process_id}; session={session_id}; exe={executable_path}"
        )
    return " | ".join(details) if details else "Process details parsed but no process rows found."


def read_registry_value(root: Any, sub_key: str, value_name: str = "") -> str:
    try:
        import winreg

        with winreg.OpenKey(root, sub_key) as key:
            value, _value_type = winreg.QueryValueEx(key, value_name)
            return str(value)
    except Exception:
        return ""


def outlook_com_registry_rows() -> list[CheckRow]:
    try:
        import winreg
    except Exception as exc:
        return [
            CheckRow(
                check="registry:winreg",
                status="MISSING",
                detail=f"winreg unavailable: {type(exc).__name__}",
                evidence="",
            )
        ]
    clsid = read_registry_value(winreg.HKEY_CLASSES_ROOT, r"Outlook.Application\CLSID")
    clsid_status = "OK" if clsid else "MISSING"
    rows = [
        CheckRow(
            check="registry:Outlook.Application\\CLSID",
            status=clsid_status,
            detail=clsid or "Outlook.Application CLSID not registered",
            evidence=clsid,
        )
    ]
    if not clsid:
        return rows
    local_server = read_registry_value(
        winreg.HKEY_CLASSES_ROOT,
        rf"CLSID\{clsid}\LocalServer32",
    )
    server_path = extract_executable_path(local_server)
    if local_server and (not server_path or Path(server_path).exists()):
        status = "OK"
    elif local_server:
        status = "PATH_MISSING"
    else:
        status = "MISSING"
    rows.append(
        CheckRow(
            check="registry:Outlook.Application\\LocalServer32",
            status=status,
            detail=local_server or "LocalServer32 not registered",
            evidence=server_path or local_server,
        )
    )
    return rows


def extract_executable_path(command_line: str) -> str:
    text = command_line.strip()
    if not text:
        return ""
    quoted = re.match(r'^"([^"]+)"', text)
    if quoted:
        return quoted.group(1)
    exe_match = re.match(r"^(.+?\.exe)\b", text, flags=re.IGNORECASE)
    if exe_match:
        return exe_match.group(1)
    return text.split(" ", 1)[0]


def get_last_outlook_result(runbook_json: Path) -> dict[str, Any]:
    return read_json(runbook_json).get("last_outlook_result", {})


def classify_environment(rows: list[CheckRow], last_result: dict[str, Any]) -> tuple[str, str, str]:
    by_check = {row.check: row for row in rows}
    if by_check["path:s12_tool"].status != "OK":
        return (
            "SCRIPT_PATH_MISSING",
            "12/13 tool path is missing.",
            "Restore the scenario 12/13 tool file before retrying OUTLOOK_COM_BUNDLE.",
        )
    if by_check["python_module:win32com.client"].status != "OK":
        return (
            "PYWIN32_MISSING",
            "win32com.client is not importable.",
            "Install/repair pywin32 for the Python executable used by RK10 tooling.",
        )
    registry_status = by_check.get("registry:Outlook.Application\\CLSID")
    if registry_status and registry_status.status != "OK":
        return (
            "CLASSIC_OUTLOOK_COM_REGISTRATION_MISSING",
            "Outlook.Application COM class is not registered.",
            "Install or repair Classic Outlook; New Outlook alone is not enough for COM automation.",
        )
    process_status = by_check.get("process:OUTLOOK.EXE")
    last_status = str(last_result.get("status", ""))
    hresults = ", ".join(str(item) for item in last_result.get("hresult_codes", []))
    if last_status == "OUTLOOK_SCAN_ONLY_DRYRUN_OK":
        return (
            "OUTLOOK_COM_READY",
            "Latest OUTLOOK_COM_BUNDLE completed COM check and scan-only dry-run.",
            "Record the evidence path in the OUTLOOK_COM_BUNDLE CSV and rerun the fixed runner.",
        )
    if (
        last_status == "OUTLOOK_COM_NOT_ATTACHABLE_OR_STARTABLE"
        and process_status
        and process_status.status == "NOT_RUNNING"
    ):
        return (
            "CLASSIC_OUTLOOK_DESKTOP_SESSION_REQUIRED",
            f"Outlook COM is registered but no OUTLOOK.EXE process is visible; latest HRESULT(s): {hresults}.",
            "Open Classic Outlook normally in the same Windows user session, finish any first-run/profile prompts, then rerun OUTLOOK_COM_BUNDLE.",
        )
    if (
        last_status == "OUTLOOK_COM_NOT_ATTACHABLE_OR_STARTABLE"
        and process_status
        and process_status.status == "RUNNING"
    ):
        return (
            "OUTLOOK_RUNNING_BUT_COM_AUTOMATION_REJECTED",
            f"Classic Outlook appears to be running and COM is registered, but automation cannot attach/start; latest HRESULT(s): {hresults}.",
            "Close all Outlook windows, clear any modal/profile/sign-in prompts, reopen Classic Outlook normally in this same user session, then rerun OUTLOOK_COM_BUNDLE.",
        )
    if last_status:
        return (
            "OUTLOOK_COM_HOLD_REMAINS",
            f"Latest OUTLOOK_COM_BUNDLE status={last_status}; HRESULT(s): {hresults or '-'}",
            "Recover Classic Outlook COM in the desktop session, then rerun OUTLOOK_COM_BUNDLE.",
        )
    return (
        "OUTLOOK_COM_NOT_RECHECKED",
        "No OUTLOOK_COM_BUNDLE result is recorded yet.",
        "Run OUTLOOK_COM_BUNDLE once after Classic Outlook is ready.",
    )


def build_payload(runbook_json: Path) -> dict[str, Any]:
    rows = [
        path_status("path:python_executable", PYTHON_EXE),
        path_status("path:s12_tool", S12_TOOL),
        path_status("path:s12_prod_config", S12_PROD_CONFIG),
        module_status("pythoncom"),
        module_status("pywintypes"),
        module_status("win32com.client"),
        query_outlook_processes(),
        query_outlook_process_details(),
        *outlook_com_registry_rows(),
    ]
    last_result = get_last_outlook_result(runbook_json)
    status, diagnosis, next_action = classify_environment(rows, last_result)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": "read-only local environment diagnosis; no Outlook start, no mail, no print, no save",
        "status": status,
        "diagnosis": diagnosis,
        "next_action": next_action,
        "python_executable": sys.executable,
        "runbook_json": str(runbook_json),
        "last_outlook_result": last_result,
        "rows": [asdict(row) for row in rows],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    last_result = payload["last_outlook_result"]
    assert isinstance(last_result, dict)
    lines = [
        "# Outlook COM Environment Diagnosis 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- status: `{payload['status']}`",
        f"- diagnosis: {payload['diagnosis']}",
        f"- next_action: {payload['next_action']}",
        f"- runbook_json: `{payload['runbook_json']}`",
        "",
        "## Latest OUTLOOK_COM_BUNDLE",
        "",
        f"- status: `{last_result.get('status', '')}`",
        f"- check_outlook_com_exit: `{last_result.get('check_outlook_com_exit', '')}`",
        f"- scan_only_dryrun_exit: `{last_result.get('scan_only_dryrun_exit', '')}`",
        f"- hresult_codes: `{', '.join(last_result.get('hresult_codes', []))}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail | Evidence |",
        "|---|---|---|---|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["check"]),
                    str(row["status"]),
                    str(row["detail"]).replace("|", "/"),
                    f"`{row['evidence']}`" if row["evidence"] else "-",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "outlook_com_environment_diagnosis.json"
    md_path = out_dir / "outlook_com_environment_diagnosis.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose Outlook COM environment.")
    parser.add_argument("--runbook-json", type=Path, default=EXTERNAL_RUNBOOK_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.runbook_json)
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
