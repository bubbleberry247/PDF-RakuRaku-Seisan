"""Run a guarded RK10 editor open/build-artifact probe for focused RKS rows.

Default mode is plan-only. GUI automation runs only with ``--execute-gui``.
The probe opens an RKS in RK10 editor, handles the development-license dialog,
waits for the editor window, reconciles Debugger artifacts, and closes only
new RK10 editor processes it started. It never presses ButtonRun and never
executes business operations.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import tkinter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import generate_rks_debugger_artifact_reconcile_20260620 as debugger_reconcile


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_FOCUS_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "rks_runtime_operator_pack_20260620"
    / "rks_runtime_operator_focus.csv"
)
DEFAULT_RK10_EXE = Path(r"C:\Program Files\KEYENCE\RK-10\RkScenarioManager.exe")
DEFAULT_REPORT_ROOT = Path(r"C:\ProgramData\RK10\Robots\migration\reports")
DEFAULT_REPO_OUT_DIR = ROOT / "plans" / "reports" / "rks_editor_open_build_probe_20260620"
HARD_STOPS = (
    "no ButtonRun; no RunScenario; no business execution; no production write; "
    "no mail; no print; no payment; no final submit"
)


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class ProbeTarget:
    scenario: str
    rks_path: str
    expected_name: str
    required_next_gate: str
    blocked_operations: str


@dataclass(frozen=True)
class ProcessInfo:
    process_id: int
    process_name: str
    main_window_title: str
    path: str


@dataclass(frozen=True)
class ProbeRow:
    scenario: str
    rks_path: str
    planned: bool
    executed: bool
    rks_exists: bool
    rk10_exe_exists: bool
    launch_mode: str
    metadata_guard_returncode: int | None
    license_action: str
    home_load_action: str
    editor_open_status: str
    build_artifact_found: bool
    debugger_program_match_count: int
    button_run_clicked: bool
    new_process_ids: str
    stopped_process_ids: str
    top_window_titles: str
    top_window_details_path: str
    error: str
    evidence_path: str


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_file_token(value: str) -> str:
    unsafe_chars = '<>:"/\\|?*'
    token = "".join("_" if char in unsafe_chars else char for char in value)
    token = token.strip().strip(".")
    return token or "unknown"


def read_focus_targets(path: Path, scenarios: set[str]) -> list[ProbeTarget]:
    if not path.exists():
        raise FileNotFoundError(f"focus CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        targets: list[ProbeTarget] = []
        for row in csv.DictReader(handle):
            scenario = str(row.get("scenario", "")).strip()
            if scenarios and scenario not in scenarios:
                continue
            rks_path = str(row.get("rks_path", "")).strip()
            if not scenario or not rks_path:
                continue
            targets.append(
                ProbeTarget(
                    scenario=scenario,
                    rks_path=rks_path,
                    expected_name=Path(rks_path).name,
                    required_next_gate=str(row.get("required_next_gate", "")),
                    blocked_operations=str(row.get("blocked_operations", "")),
                )
            )
    return targets


def get_rk10_processes() -> list[ProcessInfo]:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Get-Process RkScenarioManager -ErrorAction SilentlyContinue | "
            "Select-Object Id,ProcessName,MainWindowTitle,Path | ConvertTo-Json -Compress"
        ),
    ]
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    payload = json.loads(completed.stdout)
    if isinstance(payload, dict):
        payload = [payload]
    return [
        ProcessInfo(
            process_id=int(row.get("Id", 0)),
            process_name=str(row.get("ProcessName", "")),
            main_window_title=str(row.get("MainWindowTitle", "")),
            path=str(row.get("Path", "")),
        )
        for row in payload
        if isinstance(row, dict)
    ]


def run_metadata_guard(rks_path: Path, out_dir: Path, scenario: str) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    scenario_token = safe_file_token(scenario)
    stdout_path = out_dir / f"s{scenario_token}_metadata_guard.stdout.txt"
    stderr_path = out_dir / f"s{scenario_token}_metadata_guard.stderr.txt"
    command = [
        sys.executable,
        r"C:\Users\masam\.codex\skills\rk10-rks-safety\scripts\rks_metadata_guard.py",
        "scan",
        str(rks_path),
        "--fail-on-risk",
    ]
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    return completed.returncode


def invoke_if_possible(control: Any) -> None:
    try:
        control.invoke()
        return
    except Exception:
        pass
    control.click_input()


def control_text(control: Any) -> str:
    try:
        return control.window_text()
    except Exception:
        return ""


def control_automation_id(control: Any) -> str:
    return str(getattr(control.element_info, "automation_id", ""))


def control_type(control: Any) -> str:
    return str(getattr(control.element_info, "control_type", ""))


def accept_license_dialog_once() -> bool:
    """Press OK only and leave the default AI development license radio unchanged."""
    from pywinauto import Desktop

    for window in Desktop(backend="uia").windows():
        try:
            descendants = window.descendants()
        except Exception:
            continue
        has_license_dialog = "ライセンス" in control_text(window) or any(
            control_automation_id(control)
            in {"DevelopmentLicenseCheckBox", "DevelopmentWithAiLicenseCheckBox"}
            or control_text(control) == "ライセンス"
            for control in descendants
        )
        if not has_license_dialog:
            continue
        try:
            window.set_focus()
        except Exception:
            pass
        try:
            descendants = window.descendants()
        except Exception:
            pass
        for control in descendants:
            if control_text(control) == "OK" and control_type(control) == "Button":
                invoke_if_possible(control)
                return True
    return False


def accept_license_warning_once() -> bool:
    from pywinauto import Desktop

    for window in Desktop(backend="uia").windows():
        try:
            descendants = window.descendants()
        except Exception:
            continue
        has_expired_warning = any(
            "ライセンスの有効期限" in control_text(control) for control in descendants
        )
        if not has_expired_warning:
            continue
        try:
            window.set_focus()
        except Exception:
            pass
        for control in descendants:
            if control_text(control) == "OK" and control_type(control) == "Button":
                try:
                    control.click_input()
                except Exception:
                    invoke_if_possible(control)
                return True
    return False


def handle_license_dialog(timeout_seconds: float) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if accept_license_dialog_once():
            return "ok_invoked"
        time.sleep(0.5)
    return "not_found"


def handle_license_warning(timeout_seconds: float) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if accept_license_warning_once():
            return "expiry_ok_invoked"
        time.sleep(0.5)
    return "not_found"


def wait_for_editor_window(expected_name: str, timeout_seconds: float) -> str:
    from pywinauto import Desktop

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        for window in Desktop(backend="uia").windows():
            title = window.window_text()
            if expected_name in title and "KEYENCE" in title:
                return "RK10_EDITOR_OPEN_CONFIRMED"
        time.sleep(1.0)
    return "RK10_EDITOR_OPEN_TIMEOUT"


def click_home_load_button_once() -> bool:
    from pywinauto import Desktop

    for window in Desktop(backend="uia").windows():
        if "KEYENCE RK-10" not in control_text(window):
            continue
        try:
            descendants = window.descendants()
        except Exception:
            continue
        for control in descendants:
            if control_text(control) == "シナリオを読み込む":
                invoke_if_possible(control)
                return True
    return False


def wait_for_open_dialog(timeout_seconds: float) -> Any | None:
    from pywinauto import Desktop

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        for window in Desktop(backend="uia").windows():
            title = control_text(window)
            if title in {"開く", "Open"}:
                return window
            try:
                descendants = window.descendants()
            except Exception:
                continue
            has_open_button = any(
                control_type(control) == "Button"
                and (control_text(control).startswith("開く") or control_text(control).lower().startswith("open"))
                for control in descendants
            )
            has_filename_label = any("ファイル名" in control_text(control) for control in descendants)
            if has_open_button and has_filename_label:
                return window
        time.sleep(0.5)
    return None


def choose_file_in_open_dialog(dialog: Any, rks_path: Path) -> bool:
    from pywinauto.keyboard import send_keys

    try:
        dialog.set_focus()
    except Exception:
        pass
    if choose_file_in_open_dialog_win32(dialog, rks_path):
        return True
    try:
        descendants = dialog.descendants()
    except Exception:
        descendants = []
    filename_controls = [
        control for control in descendants if control_automation_id(control) == "1148"
    ]
    value_was_set = False
    if filename_controls:
        try:
            filename_controls[0].set_edit_text(str(rks_path))
            value_was_set = True
        except Exception:
            value_was_set = False

    old_clipboard = set_clipboard_text(str(rks_path))
    try:
        if not value_was_set:
            send_keys("%n")
            time.sleep(0.3)
            send_keys("^a")
            send_keys("^v")
            time.sleep(0.3)
        try:
            descendants = dialog.descendants()
        except Exception:
            descendants = []
        for control in descendants:
            text = control_text(control)
            if control_type(control) == "Button" and (
                text.startswith("開く") or text.lower().startswith("open")
            ):
                invoke_if_possible(control)
                return True
        send_keys("{ENTER}")
        return True
    finally:
        restore_clipboard_text(old_clipboard)


def choose_file_in_open_dialog_win32(dialog: Any, rks_path: Path) -> bool:
    try:
        from pywinauto import Application

        process_id = int(dialog.process_id())
        app = Application(backend="win32").connect(process=process_id)
        candidates = [
            window
            for window in app.windows()
            if window.window_text() in {"開く", "Open"}
        ]
        if not candidates:
            return False
        win32_dialog = candidates[0]
        win32_dialog.set_focus()
        edit = win32_dialog.child_window(class_name="Edit")
        edit.set_edit_text(str(rks_path))
        button = win32_dialog.child_window(title_re="^(開く|Open).*", class_name="Button")
        button.click()
        return True
    except Exception:
        return False


def set_clipboard_text(text: str) -> str | None:
    root = tkinter.Tk()
    root.withdraw()
    try:
        try:
            old_value = root.clipboard_get()
        except Exception:
            old_value = None
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        return old_value
    finally:
        root.destroy()


def restore_clipboard_text(text: str | None) -> None:
    if text is None:
        return
    root = tkinter.Tk()
    root.withdraw()
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    finally:
        root.destroy()


def open_rks_from_home(target: ProbeTarget, timeout_seconds: float) -> str:
    if not click_home_load_button_once():
        return "home_load_button_not_found"
    dialog = wait_for_open_dialog(timeout_seconds=timeout_seconds)
    warning_action = "not_found"
    if dialog is None:
        warning_action = handle_license_warning(timeout_seconds=10.0)
        if warning_action != "not_found" and click_home_load_button_once():
            dialog = wait_for_open_dialog(timeout_seconds=timeout_seconds)
    if dialog is None:
        return f"home_load_clicked;license_warning={warning_action};open_dialog_not_found"
    if choose_file_in_open_dialog(dialog, Path(target.rks_path)):
        return f"home_load_clicked;license_warning={warning_action};open_dialog_file_invoked"
    return "home_load_clicked;open_dialog_file_ng"


def collect_top_window_titles() -> list[str]:
    from pywinauto import Desktop

    titles: list[str] = []
    for window in Desktop(backend="uia").windows():
        title = window.window_text()
        if title:
            titles.append(title)
    return titles


def describe_control(control: Any, index: int) -> dict[str, str | int]:
    element = control.element_info
    try:
        rectangle = str(control.rectangle())
    except Exception:
        rectangle = ""
    try:
        text = control.window_text()
    except Exception:
        text = ""
    return {
        "index": index,
        "text": text[:200],
        "automation_id": str(getattr(element, "automation_id", "")),
        "control_type": str(getattr(element, "control_type", "")),
        "class_name": str(getattr(element, "class_name", "")),
        "rectangle": rectangle,
    }


def write_top_window_details(
    out_dir: Path,
    target: ProbeTarget,
    new_process_ids: set[int],
    max_descendants_per_window: int = 200,
) -> str:
    from pywinauto import Desktop

    details: list[dict[str, Any]] = []
    for index, window in enumerate(Desktop(backend="uia").windows()):
        try:
            title = window.window_text()
            process_id = int(window.process_id())
            include_window = (
                process_id in new_process_ids
                or "KEYENCE" in title
                or "ライセンス" in title
                or target.expected_name in title
            )
            if not include_window:
                continue
            descendants: list[dict[str, str | int]] = []
            try:
                for descendant_index, control in enumerate(
                    window.descendants()[:max_descendants_per_window]
                ):
                    descendants.append(describe_control(control, descendant_index))
            except Exception as exc:
                descendants.append(
                    {
                        "index": -1,
                        "text": f"DESCENDANTS_ERROR: {type(exc).__name__}: {exc}",
                        "automation_id": "",
                        "control_type": "",
                        "class_name": "",
                        "rectangle": "",
                    }
                )
            details.append(
                {
                    "index": index,
                    "process_id": process_id,
                    "title": title,
                    "class_name": str(getattr(window.element_info, "class_name", "")),
                    "control_type": str(getattr(window.element_info, "control_type", "")),
                    "descendant_count_captured": len(descendants),
                    "descendants": descendants,
                }
            )
        except Exception as exc:
            details.append(
                {
                    "index": index,
                    "error": f"{type(exc).__name__}: {exc}",
                    "descendants": [],
                }
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    detail_path = out_dir / f"s{safe_file_token(target.scenario)}_top_window_details.json"
    detail_path.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(detail_path)


def stop_new_processes(before: list[ProcessInfo], after: list[ProcessInfo]) -> list[int]:
    before_ids = {process.process_id for process in before}
    stopped: list[int] = []
    for process in after:
        if process.process_id in before_ids:
            continue
        subprocess.run(
            ["taskkill", "/PID", str(process.process_id), "/T", "/F"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        stopped.append(process.process_id)
    return stopped


def build_artifact_evidence(target: ProbeTarget) -> tuple[bool, int]:
    signature = debugger_reconcile.read_rks_program_signature(Path(target.rks_path))
    programs = debugger_reconcile.scan_debugger_programs(debugger_reconcile.DEFAULT_DEBUGGER_DIR)
    matches = [
        program
        for program in programs
        if signature is not None
        and program.signature.normalized_sha256 == signature.normalized_sha256
    ]
    build_artifact_found = any(program.build_artifact_paths for program in matches)
    return build_artifact_found, len(matches)


def launch_rks(rks_path: Path, rk10_exe: Path, launch_mode: str) -> None:
    if launch_mode == "startfile":
        startfile = getattr(os, "startfile", None)
        if startfile is None:
            raise RuntimeError("os.startfile is not available on this platform")
        startfile(str(rks_path))
        return
    subprocess.Popen([str(rk10_exe), str(rks_path)], cwd=str(rks_path.parent))


def execute_probe(
    target: ProbeTarget,
    rk10_exe: Path,
    out_dir: Path,
    hold_seconds: int,
    launch_mode: str,
) -> ProbeRow:
    rks_path = Path(target.rks_path)
    before = get_rk10_processes()
    metadata_guard_returncode = run_metadata_guard(rks_path, out_dir, target.scenario)
    if metadata_guard_returncode != 0:
        return ProbeRow(
            scenario=target.scenario,
            rks_path=target.rks_path,
            planned=True,
            executed=False,
            rks_exists=rks_path.exists(),
            rk10_exe_exists=rk10_exe.exists(),
            launch_mode=launch_mode,
            metadata_guard_returncode=metadata_guard_returncode,
            license_action="SKIPPED",
            home_load_action="SKIPPED",
            editor_open_status="SKIPPED_METADATA_GUARD_FAILED",
            build_artifact_found=False,
            debugger_program_match_count=0,
            button_run_clicked=False,
            new_process_ids="",
            stopped_process_ids="",
            top_window_titles="",
            top_window_details_path="",
            error="metadata guard failed",
            evidence_path=str(out_dir),
        )
    try:
        launch_rks(rks_path, rk10_exe, launch_mode)
        license_action = handle_license_dialog(timeout_seconds=90.0)
        license_warning_action = handle_license_warning(timeout_seconds=20.0)
        if license_warning_action != "not_found":
            license_action = f"{license_action};{license_warning_action}"
        editor_status = wait_for_editor_window(target.expected_name, timeout_seconds=15.0)
        home_load_action = "not_needed"
        if editor_status != "RK10_EDITOR_OPEN_CONFIRMED":
            home_load_action = open_rks_from_home(target, timeout_seconds=30.0)
            editor_status = wait_for_editor_window(target.expected_name, timeout_seconds=90.0)
        after = get_rk10_processes()
        before_ids = {item.process_id for item in before}
        new_process_ids = {
            process.process_id for process in after if process.process_id not in before_ids
        }
        top_window_titles = collect_top_window_titles()
        top_window_details_path = write_top_window_details(out_dir, target, new_process_ids)
        time.sleep(max(0, hold_seconds))
        final_after = get_rk10_processes()
        stopped = stop_new_processes(before, final_after)
        build_artifact_found, match_count = build_artifact_evidence(target)
        error = "" if editor_status == "RK10_EDITOR_OPEN_CONFIRMED" else editor_status
        if not (license_action == "not_found" or license_action.startswith("ok_invoked")):
            error = f"{error}; license_action={license_action}".strip("; ")
        return ProbeRow(
            scenario=target.scenario,
            rks_path=target.rks_path,
            planned=True,
            executed=True,
            rks_exists=rks_path.exists(),
            rk10_exe_exists=rk10_exe.exists(),
            launch_mode=launch_mode,
            metadata_guard_returncode=metadata_guard_returncode,
            license_action=license_action,
            home_load_action=home_load_action,
            editor_open_status=editor_status,
            build_artifact_found=build_artifact_found,
            debugger_program_match_count=match_count,
            button_run_clicked=False,
            new_process_ids=";".join(str(process_id) for process_id in sorted(new_process_ids)),
            stopped_process_ids=";".join(str(process_id) for process_id in stopped),
            top_window_titles="; ".join(top_window_titles[:20]),
            top_window_details_path=top_window_details_path,
            error=error,
            evidence_path=str(out_dir),
        )
    except Exception as exc:
        after = get_rk10_processes()
        stopped = stop_new_processes(before, after)
        try:
            top_window_titles = collect_top_window_titles()
        except Exception:
            top_window_titles = []
        try:
            top_window_details_path = write_top_window_details(
                out_dir,
                target,
                {
                    process.process_id
                    for process in after
                    if process.process_id not in {item.process_id for item in before}
                },
            )
        except Exception:
            top_window_details_path = ""
        return ProbeRow(
            scenario=target.scenario,
            rks_path=target.rks_path,
            planned=True,
            executed=True,
            rks_exists=rks_path.exists(),
            rk10_exe_exists=rk10_exe.exists(),
            launch_mode=launch_mode,
            metadata_guard_returncode=metadata_guard_returncode,
            license_action="ERROR",
            home_load_action="ERROR",
            editor_open_status="RK10_EDITOR_OPEN_NG",
            build_artifact_found=False,
            debugger_program_match_count=0,
            button_run_clicked=False,
            new_process_ids=";".join(str(process.process_id) for process in after if process.process_id not in {item.process_id for item in before}),
            stopped_process_ids=";".join(str(process_id) for process_id in stopped),
            top_window_titles="; ".join(top_window_titles[:20]),
            top_window_details_path=top_window_details_path,
            error=f"{type(exc).__name__}: {exc}",
            evidence_path=str(out_dir),
        )


def build_plan_row(
    target: ProbeTarget,
    rk10_exe: Path,
    out_dir: Path,
    launch_mode: str,
) -> ProbeRow:
    rks_path = Path(target.rks_path)
    return ProbeRow(
        scenario=target.scenario,
        rks_path=target.rks_path,
        planned=True,
        executed=False,
        rks_exists=rks_path.exists(),
        rk10_exe_exists=rk10_exe.exists(),
        launch_mode=launch_mode,
        metadata_guard_returncode=None,
        license_action="PLANNED",
        home_load_action="PLANNED",
        editor_open_status="PLANNED_NOT_EXECUTED",
        build_artifact_found=False,
        debugger_program_match_count=0,
        button_run_clicked=False,
        new_process_ids="",
        stopped_process_ids="",
        top_window_titles="",
        top_window_details_path="",
        error="",
        evidence_path=str(out_dir),
    )


def build_payload(rows: list[ProbeRow], execute_gui: bool, out_dir: Path) -> dict[str, Any]:
    editor_confirmed_count = sum(
        1 for row in rows if row.editor_open_status == "RK10_EDITOR_OPEN_CONFIRMED"
    )
    build_artifact_count = sum(1 for row in rows if row.build_artifact_found)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": HARD_STOPS,
        "execute_gui": execute_gui,
        "out_dir": str(out_dir),
        "row_count": len(rows),
        "editor_confirmed_count": editor_confirmed_count,
        "build_artifact_count": build_artifact_count,
        "button_run_clicked_count": sum(1 for row in rows if row.button_run_clicked),
        "rows": [asdict(row) for row in rows],
    }


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "rks_editor_open_build_probe.json"
    md_path = out_dir / "rks_editor_open_build_probe.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# RK10 Editor Open/Build Probe 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- execute_gui: `{payload['execute_gui']}`",
        f"- safety: `{payload['safety']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- editor_confirmed_count: `{payload['editor_confirmed_count']}`",
        f"- build_artifact_count: `{payload['build_artifact_count']}`",
        f"- button_run_clicked_count: `{payload['button_run_clicked_count']}`",
        "",
        "## Rows",
        "",
        "| Scenario | Executed | Launch | License | Home Load | Editor Open | Build Artifact | ButtonRun Clicked | UI Details | Error | RKS |",
        "|---|---:|---|---|---|---|---:|---:|---|---|---|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    "YES" if row["executed"] else "NO",
                    str(row["launch_mode"]),
                    str(row["license_action"]),
                    str(row["home_load_action"]),
                    str(row["editor_open_status"]),
                    "YES" if row["build_artifact_found"] else "NO",
                    "YES" if row["button_run_clicked"] else "NO",
                    f"`{row['top_window_details_path']}`" if row.get("top_window_details_path") else "-",
                    str(row["error"]).replace("|", "/") or "-",
                    f"`{row['rks_path']}`",
                ]
            )
            + " |"
        )
        if row.get("top_window_titles"):
            lines.append(
                f"| {row['scenario']} top windows | - | - | - | - | - | - | "
                f"{str(row['top_window_titles']).replace('|', '/')} | - |"
            )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded RK10 editor open/build probe.")
    parser.add_argument("--focus-csv", type=Path, default=DEFAULT_FOCUS_CSV)
    parser.add_argument("--rk10-exe", type=Path, default=DEFAULT_RK10_EXE)
    parser.add_argument("--repo-out-dir", type=Path, default=DEFAULT_REPO_OUT_DIR)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--hold-seconds", type=int, default=15)
    parser.add_argument("--launch-mode", choices=["startfile", "exe"], default="exe")
    parser.add_argument("--execute-gui", action="store_true")
    return parser.parse_args()


def main() -> int:
    configure_stdout()
    args = parse_args()
    scenarios = {str(scenario) for scenario in (args.scenario or ["58"])}
    targets = read_focus_targets(args.focus_csv, scenarios)
    out_dir = (
        args.report_root / f"rks_editor_open_build_probe_20260620_{now_stamp()}"
        if args.execute_gui
        else args.repo_out_dir
    )
    if args.execute_gui and not args.rk10_exe.exists():
        raise FileNotFoundError(f"RK10 editor executable not found: {args.rk10_exe}")
    rows = [
        execute_probe(target, args.rk10_exe, out_dir, args.hold_seconds, args.launch_mode)
        if args.execute_gui
        else build_plan_row(target, args.rk10_exe, out_dir, args.launch_mode)
        for target in targets
    ]
    payload = build_payload(rows, args.execute_gui, out_dir)
    write_outputs(payload, out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
