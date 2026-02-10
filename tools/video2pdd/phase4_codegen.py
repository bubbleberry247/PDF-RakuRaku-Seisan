"""
phase4_codegen.py - Generate Python automation code from event_log.

Phase 4 (video pipeline only): Converts structured steps into executable
Python code using Playwright (web) and pywinauto (desktop).

Generated code is a starting framework with TODO markers for human verification.
Selectors are estimated from video analysis and MUST be verified before use.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from .event_log import (
    APP_TYPE_DESKTOP,
    APP_TYPE_WEB,
    PHASE_CODE_GEN,
    is_phase_completed,
    mark_phase_completed,
    mark_phase_failed,
    mark_phase_started,
)

# ------------------------------------------------------------------ #
#  Code templates
# ------------------------------------------------------------------ #

FILE_HEADER = '''\
"""
Auto-generated automation script from video analysis.
Source: {video_file}
Generated: {generated_at}
Tool: video2pdd v3

WARNING: Selectors are estimated from video analysis.
         Manual verification is required before production use.
         Search for 'TODO:' to find items needing review.
"""
'''

IMPORTS_WEB = """\
import asyncio
from playwright.async_api import async_playwright
"""

IMPORTS_DESKTOP = """\
from pywinauto import Application, Desktop
from pywinauto import keyboard as pwa_keyboard
import time
"""

IMPORTS_MIXED = """\
import asyncio
import time
from playwright.async_api import async_playwright
from pywinauto import Application, Desktop
from pywinauto import keyboard as pwa_keyboard
"""

# Web action templates (Playwright async)
WEB_TEMPLATES: dict[str, str] = {
    "Navigate": '    await page.goto("{value}")',
    "Click": '    await page.locator("{selector}").click()',
    "DoubleClick": '    await page.locator("{selector}").dblclick()',
    "RightClick": '    await page.locator("{selector}").click(button="right")',
    "Input": '    await page.locator("{selector}").fill("{value}")',
    "Select": '    await page.locator("{selector}").select_option("{value}")',
    "Wait": "    await page.wait_for_timeout({wait_ms})",
    "KeyShortcut": '    await page.keyboard.press("{value}")',
    "Scroll": "    await page.mouse.wheel(0, 300)",
    "FileOpen": '    await page.locator("{selector}").set_input_files("{value}")',
}

# Desktop action templates (pywinauto)
DESKTOP_TEMPLATES: dict[str, str] = {
    "Click": '    window["{target}"].click_input()',
    "DoubleClick": '    window["{target}"].double_click_input()',
    "RightClick": '    window["{target}"].right_click_input()',
    "Input": '    window["{target}"].type_keys("{value}", with_spaces=True)',
    "Select": '    window["{target}"].select("{value}")',
    "Wait": "    time.sleep({wait_sec})",
    "KeyShortcut": '    pwa_keyboard.send_keys("{value}")',
    "Scroll": '    window["{target}"].scroll("down", "page")',
    "Navigate": "    # Navigate: {value}",
    "SwitchWindow": "    # Switch to: {target}",
    "FileOpen": "    # Open file: {value}",
    "FileSave": "    # Save file",
}

# Confidence thresholds for TODO comments
CONF_VERIFIED = 0.9
CONF_WARNING = 0.7


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

def _escape_string(s: str) -> str:
    """Escape a string for use in Python string literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _selector_for_step(step: dict) -> str:
    """Get the best available selector for a step."""
    hint = step.get("selector_hint") or ""
    if hint and hint not in ("", "unknown", "N/A"):
        return _escape_string(hint)
    target = step.get("target_element") or step.get("target") or ""
    if target:
        return _escape_string(f'text="{target}"')
    return "SELECTOR_NEEDED"


def _todo_comment(step: dict) -> str:
    """Generate TODO comment based on confidence and gap flags."""
    confidence = step.get("confidence")
    parts: list[str] = []

    if confidence is not None and confidence < CONF_WARNING:
        parts.append(f"WARNING: LOW CONFIDENCE ({confidence:.2f})")
    elif confidence is not None and confidence < CONF_VERIFIED:
        parts.append(f"VERIFY SELECTOR (confidence: {confidence:.2f})")
    else:
        parts.append("VERIFY SELECTOR")

    gap_flags = step.get("gap_flags", [])
    if gap_flags:
        parts.append(f"Gaps: {', '.join(gap_flags)}")

    return f"    # TODO: {' | '.join(parts)}"


def _source_comment(step: dict) -> str:
    """Generate source reference comment."""
    ts = step.get("timestamp", "")
    action = step.get("action_type", "")
    target = step.get("target_element", "")[:40]
    return f"    # Source: video {ts} - {action} {target}"


def _wait_value(step: dict) -> tuple[str, str]:
    """Extract wait duration in ms and seconds."""
    value = step.get("input_value") or step.get("value") or "1"
    try:
        sec = float(value.replace("s", "").replace("秒", "").strip())
    except (ValueError, AttributeError):
        sec = 1.0
    return str(int(sec * 1000)), str(sec)


# ------------------------------------------------------------------ #
#  Phase grouping for code structure
# ------------------------------------------------------------------ #

def _group_steps_by_phase(
    steps: list[dict],
    flow_phases: list[dict],
) -> list[dict[str, Any]]:
    """Group steps into phase-based functions.

    Returns list of:
        {"phase_id": int, "phase_name": str, "app_type": str, "steps": [...]}
    """
    if not flow_phases:
        # No phases: single function with all steps
        app_type = _dominant_app_type(steps)
        return [{
            "phase_id": 1,
            "phase_name": "main_flow",
            "app_type": app_type,
            "steps": steps,
        }]

    groups: list[dict[str, Any]] = []
    for phase in flow_phases:
        sr = phase.get("step_range", [1, 1])
        phase_steps = [
            s for s in steps
            if sr[0] <= int(s.get("num", "0")) <= sr[1]
        ]
        app_type = _dominant_app_type(phase_steps)

        groups.append({
            "phase_id": phase.get("phase_id", len(groups) + 1),
            "phase_name": phase.get("phase_name", f"phase_{len(groups) + 1}"),
            "app_type": app_type,
            "steps": phase_steps,
        })

    return groups


def _dominant_app_type(steps: list[dict]) -> str:
    """Determine the dominant app_type for a group of steps."""
    web_count = sum(1 for s in steps if s.get("app_type") == APP_TYPE_WEB)
    desktop_count = sum(1 for s in steps if s.get("app_type") == APP_TYPE_DESKTOP)
    if web_count >= desktop_count:
        return APP_TYPE_WEB
    return APP_TYPE_DESKTOP


def _sanitize_func_name(name: str) -> str:
    """Convert phase name to a valid Python function name."""
    import re
    # Replace non-alphanumeric with underscore
    clean = re.sub(r"[^a-zA-Z0-9_\u3040-\u9fff]", "_", name)
    clean = re.sub(r"_+", "_", clean).strip("_")
    if not clean:
        clean = "unnamed"
    return clean.lower()


# ------------------------------------------------------------------ #
#  Code generation
# ------------------------------------------------------------------ #

def _generate_step_code(step: dict, app_type: str) -> list[str]:
    """Generate Python code lines for a single step."""
    lines: list[str] = []
    action = step.get("action_type", "")
    is_merged = bool(step.get("merged_into"))

    if is_merged:
        return []  # Skip merged duplicates

    # Source reference
    lines.append(_source_comment(step))

    # TODO comment
    lines.append(_todo_comment(step))

    # Select template based on app type
    if app_type == APP_TYPE_WEB:
        templates = WEB_TEMPLATES
    else:
        templates = DESKTOP_TEMPLATES

    template = templates.get(action, f"    # Unsupported action: {action}")

    # Build substitution values
    selector = _selector_for_step(step)
    value = _escape_string(step.get("input_value") or step.get("value") or "")
    target = _escape_string(step.get("target_element") or "")
    wait_ms, wait_sec = _wait_value(step)

    try:
        code = template.format(
            selector=selector,
            value=value,
            target=target,
            wait_ms=wait_ms,
            wait_sec=wait_sec,
        )
    except (KeyError, IndexError):
        code = f"    # Code generation failed for: {action} {target}"

    lines.append(code)
    lines.append("")  # Blank line between steps

    return lines


def _generate_web_function(group: dict) -> list[str]:
    """Generate an async Playwright function for a web phase."""
    phase_id = group["phase_id"]
    phase_name = _sanitize_func_name(group["phase_name"])
    func_name = f"phase_{phase_id}_{phase_name}"

    lines: list[str] = []
    lines.append(f'async def {func_name}(page):')
    lines.append(f'    """{group["phase_name"]}"""')
    lines.append("")

    for step in group["steps"]:
        lines.extend(_generate_step_code(step, APP_TYPE_WEB))

    if not group["steps"]:
        lines.append("    pass")

    lines.append("")
    return lines


def _generate_desktop_function(group: dict) -> list[str]:
    """Generate a pywinauto function for a desktop phase."""
    phase_id = group["phase_id"]
    phase_name = _sanitize_func_name(group["phase_name"])
    func_name = f"phase_{phase_id}_{phase_name}"

    lines: list[str] = []
    lines.append(f'def {func_name}(app=None):')
    lines.append(f'    """{group["phase_name"]}"""')
    lines.append("")

    # Connect to application if not provided
    window_context = group["steps"][0].get("target_window", "") if group["steps"] else ""
    if window_context:
        safe_title = _escape_string(window_context)
        lines.append(f'    if app is None:')
        lines.append(f'        app = Application(backend="uia").connect(title_re=".*{safe_title}.*")')
        lines.append(f'    window = app.window(title_re=".*{safe_title}.*")')
        lines.append("")

    for step in group["steps"]:
        lines.extend(_generate_step_code(step, APP_TYPE_DESKTOP))

    if not group["steps"]:
        lines.append("    pass")

    lines.append("")
    return lines


def _generate_main_function(groups: list[dict]) -> list[str]:
    """Generate the main() function that calls all phase functions."""
    has_web = any(g["app_type"] == APP_TYPE_WEB for g in groups)
    has_desktop = any(g["app_type"] == APP_TYPE_DESKTOP for g in groups)

    lines: list[str] = []

    if has_web:
        lines.append("async def main():")
        lines.append('    """Run all phases."""')
        lines.append("    async with async_playwright() as p:")
        lines.append("        browser = await p.chromium.launch(headless=False)")
        lines.append("        page = await browser.new_page()")
        lines.append("")

        for group in groups:
            phase_id = group["phase_id"]
            phase_name = _sanitize_func_name(group["phase_name"])
            func_name = f"phase_{phase_id}_{phase_name}"

            if group["app_type"] == APP_TYPE_WEB:
                lines.append(f"        await {func_name}(page)")
            else:
                lines.append(f"        {func_name}()")

        lines.append("")
        lines.append("        await browser.close()")
    else:
        lines.append("def main():")
        lines.append('    """Run all phases."""')

        for group in groups:
            phase_id = group["phase_id"]
            phase_name = _sanitize_func_name(group["phase_name"])
            func_name = f"phase_{phase_id}_{phase_name}"
            lines.append(f"    {func_name}()")

    lines.append("")
    lines.append("")

    if has_web:
        lines.append('if __name__ == "__main__":')
        lines.append("    asyncio.run(main())")
    else:
        lines.append('if __name__ == "__main__":')
        lines.append("    main()")

    lines.append("")
    return lines


# ------------------------------------------------------------------ #
#  Public API
# ------------------------------------------------------------------ #

def generate_code(event_log: dict) -> str:
    """Generate Python automation code from event_log.

    Returns:
        Complete Python source code as a string.
    """
    steps = event_log.get("steps", [])
    flow_phases = event_log.get("flow_phases", [])
    rm = event_log.get("run_metadata", {})
    inp = rm.get("input_files", {})

    video_file = inp.get("video_file", "unknown")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Group steps by phase
    groups = _group_steps_by_phase(steps, flow_phases)

    # Determine imports needed
    has_web = any(g["app_type"] == APP_TYPE_WEB for g in groups)
    has_desktop = any(g["app_type"] == APP_TYPE_DESKTOP for g in groups)

    lines: list[str] = []

    # Header
    lines.append(FILE_HEADER.format(
        video_file=video_file,
        generated_at=generated_at,
    ))

    # Imports
    if has_web and has_desktop:
        lines.append(IMPORTS_MIXED)
    elif has_web:
        lines.append(IMPORTS_WEB)
    elif has_desktop:
        lines.append(IMPORTS_DESKTOP)

    lines.append("")

    # Phase functions
    for group in groups:
        if group["app_type"] == APP_TYPE_WEB:
            lines.extend(_generate_web_function(group))
        else:
            lines.extend(_generate_desktop_function(group))

    # Main function
    lines.extend(_generate_main_function(groups))

    return "\n".join(lines)


def write_code(event_log: dict, output_dir: str) -> str:
    """Generate and save Python automation code.

    Returns:
        Path to the generated Python file.
    """
    code = generate_code(event_log)

    os.makedirs(output_dir, exist_ok=True)
    run_id = event_log.get("run_metadata", {}).get("run_id", "output")
    filename = f"automation_{run_id}.py"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)

    return filepath


# ------------------------------------------------------------------ #
#  Phase runner
# ------------------------------------------------------------------ #

def run_phase4(event_log: dict, output_dir: str) -> dict[str, Any]:
    """Execute Phase 4: Python code generation.

    Returns:
        Summary dict with output path and statistics.
    """
    if is_phase_completed(event_log, PHASE_CODE_GEN):
        return {"code_path": "", "generated": True}

    mark_phase_started(event_log, PHASE_CODE_GEN)

    try:
        code_path = write_code(event_log, output_dir)
        mark_phase_completed(event_log, PHASE_CODE_GEN)

        steps = event_log.get("steps", [])
        active_steps = [s for s in steps if not s.get("merged_into")]
        web_steps = sum(1 for s in active_steps if s.get("app_type") == APP_TYPE_WEB)
        desktop_steps = sum(1 for s in active_steps if s.get("app_type") == APP_TYPE_DESKTOP)
        todo_count = sum(
            1 for s in active_steps
            if (s.get("confidence") or 1.0) < CONF_VERIFIED
        )

        return {
            "code_path": code_path,
            "generated": True,
            "total_active_steps": len(active_steps),
            "web_steps": web_steps,
            "desktop_steps": desktop_steps,
            "todo_count": todo_count,
        }

    except Exception as e:
        mark_phase_failed(event_log, PHASE_CODE_GEN, str(e))
        raise
