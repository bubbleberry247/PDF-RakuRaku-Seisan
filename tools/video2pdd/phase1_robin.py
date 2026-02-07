"""
phase1_robin.py - Parse PAD Robin script into event_log steps.

Reads Robin script files exported from Power Automate Desktop recorder,
extracts structured action data, and populates event_log.steps[].

Supported Robin actions:
  UIAutomation.Click, UIAutomation.PressButton
  WebAutomation.Click, WebAutomation.PressButton, WebAutomation.LaunchEdge
  MouseAndKeyboard.SendKeys
  WAIT
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .event_log import (
    CATEGORY_ELEMENT_AMBIGUOUS,
    CATEGORY_KEYBOARD_COMPLEX,
    CATEGORY_OTHER,
    PHASE_ROBIN_PARSE,
    VERIFIED_CONFIRMED,
    VERIFIED_PROVISIONAL,
    create_step,
    create_unresolved_item,
    mark_phase_completed,
    mark_phase_failed,
    mark_phase_started,
)

# --- Action category constants ---
ACT_UI = "ui_automation"
ACT_WEB = "web_automation"
ACT_KEYBOARD = "keyboard"
ACT_WAIT = "wait"
ACT_VARIABLE = "variable"
ACT_CONTROL = "control_flow"
ACT_UNKNOWN = "unknown"

# --- Gap flag constants ---
GAP_COMPLEX_KEYS = "complex_key_combo"
GAP_COORDINATE_CLICK = "coordinate_only_click"
GAP_DUPLICATE_ACTION = "duplicate_action"
GAP_AMBIGUOUS_ELEMENT = "ambiguous_element"

# --- Compiled regex patterns ---
APPMASK_RE = re.compile(
    r"appmask\['((?:[^'\\]|\\.)*)'\]\['((?:[^'\\]|\\.)*)'\]"
)
URL_RE = re.compile(r"TabUrl:\s*'([^']*)'")
CLICK_TYPE_RE = re.compile(r"ClickType:\s*\S+\.(\w+)")
SEND_KEYS_RE = re.compile(r"TextToSend:\s*'([^']*)'")
OFFSET_RE = re.compile(r"Offset[XY]:\s*(-?\d+)")
WAIT_RE = re.compile(r"^WAIT\s+(\d+(?:\.\d+)?)", re.IGNORECASE)

# Keys that signal complex keyboard combos (need human review)
MODIFIER_KEYS = {
    "{lmenu}", "{rmenu}", "{lcontrol}", "{rcontrol}",
    "{lshift}", "{rshift}", "{lwin}", "{rwin}",
    "{alt}", "{control}", "{shift}",
}

# Generic UI element prefixes (likely need better targeting)
GENERIC_ELEMENT_PREFIXES = ("Div ", "Document ", "Group ", "Pane ", "Custom ")


def _unescape_robin(text: str) -> str:
    """Unescape Robin string (\\' -> ')."""
    return text.replace("\\'", "'")


def _classify_action(raw_line: str) -> tuple[str, str]:
    """Classify Robin action into (category, action_type)."""
    line = raw_line.strip()
    cmd = line.split()[0] if line.split() else ""

    if line.upper().startswith("WAIT"):
        return ACT_WAIT, "wait"

    if cmd.startswith("UIAutomation."):
        if "PressButton" in cmd:
            return ACT_UI, "press_button"
        if "Click" in cmd:
            return ACT_UI, "click"
        if "DragAndDrop" in cmd:
            return ACT_UI, "drag_drop"
        if "SelectMenuItem" in cmd:
            return ACT_UI, "select_menu"
        if "SetText" in cmd:
            return ACT_UI, "set_text"
        if "GetText" in cmd:
            return ACT_UI, "get_text"
        return ACT_UI, "other"

    if cmd.startswith("WebAutomation."):
        if "Launch" in cmd or "AttachTo" in cmd:
            return ACT_WEB, "launch_browser"
        if "PressButton" in cmd:
            return ACT_WEB, "press_button"
        if "Click" in cmd:
            return ACT_WEB, "click"
        if "SetText" in cmd or "PopulateTextField" in cmd:
            return ACT_WEB, "set_text"
        if "GetText" in cmd or "GetDetails" in cmd:
            return ACT_WEB, "get_text"
        if "GoToWebPage" in cmd:
            return ACT_WEB, "navigate"
        if "CloseWebBrowser" in cmd:
            return ACT_WEB, "close_browser"
        return ACT_WEB, "other"

    if cmd.startswith("MouseAndKeyboard."):
        if "SendKeys" in cmd:
            return ACT_KEYBOARD, "send_keys"
        if "MoveMouse" in cmd:
            return ACT_KEYBOARD, "move_mouse"
        if "Click" in cmd:
            return ACT_KEYBOARD, "mouse_click"
        return ACT_KEYBOARD, "other"

    if line.startswith("SET ") or cmd.startswith("Variables."):
        return ACT_VARIABLE, "set_variable"
    if any(line.startswith(kw) for kw in ("IF ", "ELSE", "END IF")):
        return ACT_CONTROL, "condition"
    if any(line.startswith(kw) for kw in ("LOOP", "END LOOP")):
        return ACT_CONTROL, "loop"

    return ACT_UNKNOWN, "unknown"


def _extract_appmask(raw_line: str) -> tuple[str | None, str | None]:
    """Extract (window, element) from appmask['...']['...'] pattern."""
    match = APPMASK_RE.search(raw_line)
    if not match:
        return None, None
    window = _unescape_robin(match.group(1))
    element = _unescape_robin(match.group(2))
    return window, element


def _extract_url(raw_line: str) -> str | None:
    """Extract URL from TabUrl or Url parameter."""
    match = URL_RE.search(raw_line)
    if match:
        return match.group(1)
    go_match = re.search(r"Url:\s*'([^']*)'", raw_line)
    return go_match.group(1) if go_match else None


def _extract_click_type(raw_line: str) -> str | None:
    """Extract click type (LeftClick, DoubleClick, etc.)."""
    match = CLICK_TYPE_RE.search(raw_line)
    return match.group(1) if match else None


def _extract_input_value(raw_line: str) -> str | None:
    """Extract text from SendKeys TextToSend or SetText Text parameter."""
    match = SEND_KEYS_RE.search(raw_line)
    if match:
        return match.group(1)
    text_match = re.search(r"Text:\s*'([^']*)'", raw_line)
    return text_match.group(1) if text_match else None


def _has_offset_coordinates(raw_line: str) -> bool:
    """Check if action uses pixel offset coordinates."""
    return bool(OFFSET_RE.search(raw_line))


def _is_complex_keys(input_value: str | None) -> bool:
    """Detect modifier key combinations that need human review."""
    if not input_value:
        return False
    lower = input_value.lower()
    if any(mod in lower for mod in MODIFIER_KEYS):
        return True
    if "(" in input_value and "{" in input_value:
        return True
    return False


def _is_generic_element(element: str | None) -> bool:
    """Check if element name is generic (Div, Group, etc.)."""
    if not element:
        return False
    if element.startswith(tuple(GENERIC_ELEMENT_PREFIXES)):
        return True
    # Numeric-only identifier (e.g. Group '30094')
    if re.match(r"\w+\s+'?\d+'?$", element):
        return True
    return False


def _is_duplicate(step: dict, prev: dict | None) -> bool:
    """Detect consecutive duplicate actions on the same element."""
    if prev is None:
        return False
    return (
        step["action_category"] == prev["action_category"]
        and step["action_type"] == prev["action_type"]
        and step["target_window"] == prev["target_window"]
        and step["target_element"] == prev["target_element"]
        and step["click_type"] == prev["click_type"]
    )


# ------------------------------------------------------------------ #
#  Main parser
# ------------------------------------------------------------------ #

def parse_robin_script(robin_text: str) -> list[dict[str, Any]]:
    """Parse Robin script text into a list of step dicts.

    Skips comments (#), source annotations (@@source), and blank lines.
    Returns list of dicts created by event_log.create_step().
    """
    steps: list[dict[str, Any]] = []
    step_num = 0
    prev_step: dict | None = None

    for line in robin_text.splitlines():
        stripped = line.strip()

        # Skip non-action lines
        if not stripped or stripped.startswith("#") or stripped.startswith("@@"):
            continue

        category, action_type = _classify_action(stripped)
        target_window, target_element = _extract_appmask(stripped)
        url = _extract_url(stripped)
        click_type = _extract_click_type(stripped)
        input_value = _extract_input_value(stripped)

        # WAIT duration as input_value
        if category == ACT_WAIT:
            wait_match = WAIT_RE.match(stripped)
            if wait_match:
                input_value = f"{wait_match.group(1)}s"

        step_num += 1
        step = create_step(
            num=str(step_num),
            raw_line=stripped,
            action_category=category,
            action_type=action_type,
            target_window=target_window,
            target_element=target_element,
            click_type=click_type,
            input_value=input_value,
            url=url,
        )

        # --- Gap detection ---
        flags: list[str] = []
        notes: list[str] = []

        # Complex keyboard shortcuts
        if category == ACT_KEYBOARD and _is_complex_keys(input_value):
            flags.append(GAP_COMPLEX_KEYS)
            notes.append(f"Complex key combo: {input_value}")

        # Coordinate-dependent click on generic element
        if action_type == "click" and _has_offset_coordinates(stripped):
            if _is_generic_element(target_element):
                flags.append(GAP_COORDINATE_CLICK)
                notes.append("Click uses coordinates on generic element")

        # Ambiguous element (generic containers)
        if (
            action_type == "click"
            and _is_generic_element(target_element)
            and GAP_COORDINATE_CLICK not in flags
        ):
            flags.append(GAP_AMBIGUOUS_ELEMENT)
            notes.append(f"Generic element: {(target_element or '')[:60]}")

        # Duplicate action
        if _is_duplicate(step, prev_step):
            flags.append(GAP_DUPLICATE_ACTION)
            notes.append("Duplicate of previous action")

        step["gap_flags"] = flags
        step["gap_notes"] = "; ".join(notes)
        step["verification_status"] = (
            VERIFIED_PROVISIONAL if flags else VERIFIED_CONFIRMED
        )

        steps.append(step)
        prev_step = step

    return steps


# ------------------------------------------------------------------ #
#  Phase runner
# ------------------------------------------------------------------ #

def run_phase1(
    event_log: dict[str, Any],
    robin_script_path: str,
    control_repo_path: str | None = None,
) -> dict[str, Any]:
    """Execute Phase 1: Robin script parsing.

    Populates event_log["steps"] and event_log["unresolved_items"].
    Optionally links ControlRepository screenshots to steps.

    Returns:
        Summary dict with step counts and gap statistics.
    """
    mark_phase_started(event_log, PHASE_ROBIN_PARSE)

    try:
        robin_path = Path(robin_script_path)
        if not robin_path.exists():
            raise FileNotFoundError(f"Robin script not found: {robin_script_path}")

        robin_text = robin_path.read_text(encoding="utf-8")
        steps = parse_robin_script(robin_text)
        event_log["steps"] = steps

        # ControlRepository → element thumbnails
        if control_repo_path:
            _link_control_repo(event_log, control_repo_path)

        # Generate unresolved items for provisional steps
        for step in steps:
            if step["verification_status"] != VERIFIED_CONFIRMED:
                for flag in step["gap_flags"]:
                    event_log["unresolved_items"].append(
                        create_unresolved_item(
                            step_num=step["num"],
                            category=_gap_to_category(flag),
                            description=step["gap_notes"],
                            provisional_value=step.get("target_element"),
                        )
                    )

        mark_phase_completed(event_log, PHASE_ROBIN_PARSE)

        total = len(steps)
        confirmed = sum(
            1 for s in steps if s["verification_status"] == VERIFIED_CONFIRMED
        )
        provisional = total - confirmed
        duplicates = sum(
            1 for s in steps if GAP_DUPLICATE_ACTION in s["gap_flags"]
        )

        return {
            "total_steps": total,
            "confirmed": confirmed,
            "provisional": provisional,
            "duplicates": duplicates,
        }

    except Exception as e:
        mark_phase_failed(event_log, PHASE_ROBIN_PARSE, str(e))
        raise


# ------------------------------------------------------------------ #
#  ControlRepository helper
# ------------------------------------------------------------------ #

def _link_control_repo(event_log: dict, control_repo_path: str) -> None:
    """Match ControlRepository element screenshots to steps."""
    repo_path = Path(control_repo_path)
    if not repo_path.exists():
        return

    try:
        with open(repo_path, "r", encoding="utf-8") as f:
            repo = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Truncated or corrupt file - skip silently
        return

    screenshots: dict[str, str] = {}
    _collect_screenshots(repo, screenshots)

    for step in event_log["steps"]:
        element = step.get("target_element")
        if element and element in screenshots:
            step["screenshot_path"] = screenshots[element]


def _collect_screenshots(obj: Any, result: dict[str, str]) -> None:
    """Recursively collect element name -> base64 screenshot mappings."""
    if isinstance(obj, dict):
        name = obj.get("Name") or obj.get("name") or obj.get("DisplayName")
        img = obj.get("Screenshot") or obj.get("screenshot") or obj.get("Image")
        if name and img and isinstance(img, str):
            result[name] = img
        for value in obj.values():
            _collect_screenshots(value, result)
    elif isinstance(obj, list):
        for item in obj:
            _collect_screenshots(item, result)


def _gap_to_category(flag: str) -> str:
    """Map gap flag to unresolved_item category."""
    return {
        GAP_COMPLEX_KEYS: CATEGORY_KEYBOARD_COMPLEX,
        GAP_COORDINATE_CLICK: CATEGORY_ELEMENT_AMBIGUOUS,
        GAP_AMBIGUOUS_ELEMENT: CATEGORY_ELEMENT_AMBIGUOUS,
        GAP_DUPLICATE_ACTION: CATEGORY_OTHER,
    }.get(flag, CATEGORY_OTHER)
