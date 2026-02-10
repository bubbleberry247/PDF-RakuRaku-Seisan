"""
phase2_describe.py - Normalize steps and generate Japanese PDD descriptions.

Phase 2 of Video2PDD v2 pipeline:
1. Normalize: Clean element names, track window context, mark duplicates
2. Describe: Generate Japanese step descriptions using rule-based templates
3. Flow phases: Group steps by window context into logical phases

Output fields added to each step (in-place):
  - element_alias: Human-readable element name (Japanese)
  - window_alias: Human-readable window name (Japanese)
  - description: Full Japanese step description
  - duplicate_count: Count of consecutive duplicate actions (on first only)
  - merged_into: Step num this was merged into (on duplicate steps)
"""
from __future__ import annotations

import re
from typing import Any

from .event_log import (
    PHASE_FLOW_SUMMARY,
    PHASE_SCREENSHOTS,
    create_flow_phase,
    is_phase_completed,
    is_video_pipeline,
    mark_phase_completed,
    mark_phase_failed,
    mark_phase_started,
)


# ------------------------------------------------------------------ #
#  Constants: Element type → Japanese
# ------------------------------------------------------------------ #

# (element_type_ja_label, template_with_{name}_placeholder)
ELEMENT_TYPE_JA: dict[str, tuple[str, str]] = {
    "Button": ("ボタン", "「{name}」ボタン"),
    "Input submit": ("ボタン", "「{name}」ボタン"),
    "Input text": ("テキスト入力欄", "「{name}」テキスト入力欄"),
    "Input password": ("パスワード入力欄", "「{name}」パスワード入力欄"),
    "Input checkbox": ("チェックボックス", "「{name}」チェックボックス"),
    "Input radio": ("ラジオボタン", "「{name}」ラジオボタン"),
    "Select": ("ドロップダウン", "「{name}」ドロップダウン"),
    "Textarea": ("テキストエリア", "「{name}」テキストエリア"),
    "Div": ("エリア", "{name}エリア"),
    "Span": ("テキスト", "{name}"),
    "List Item": ("リスト項目", "「{name}」リスト項目"),
    "Document": ("ドキュメント", "「{name}」ドキュメント"),
    "Group": ("グループ", "グループ要素「{name}」"),
    "Pane": ("ペイン", "「{name}」ペイン"),
    "Custom": ("カスタム要素", "カスタム要素「{name}」"),
    "Table": ("テーブル", "「{name}」テーブル"),
    "Image": ("画像", "「{name}」画像"),
    "Link": ("リンク", "「{name}」リンク"),
    "A": ("リンク", "「{name}」リンク"),
}


# ------------------------------------------------------------------ #
#  Constants: Click type → Japanese
# ------------------------------------------------------------------ #

CLICK_TYPE_JA: dict[str | None, str] = {
    "LeftClick": "クリック",
    "DoubleClick": "ダブルクリック",
    "RightClick": "右クリック",
    None: "クリック",
}


# ------------------------------------------------------------------ #
#  Constants: SendKeys special key → display name
# ------------------------------------------------------------------ #

KEY_DISPLAY: dict[str, str] = {
    "{lmenu}": "Alt", "{rmenu}": "Alt",
    "{lcontrol}": "Ctrl", "{rcontrol}": "Ctrl",
    "{lshift}": "Shift", "{rshift}": "Shift",
    "{alt}": "Alt", "{control}": "Ctrl", "{shift}": "Shift",
    "{tab}": "Tab", "{return}": "Enter", "{enter}": "Enter",
    "{escape}": "Esc", "{delete}": "Delete",
    "{backspace}": "BackSpace", "{space}": "Space",
    "{up}": "↑", "{down}": "↓", "{left}": "←", "{right}": "→",
    "{home}": "Home", "{end}": "End",
    "{pgup}": "PageUp", "{pgdn}": "PageDown",
}
# Add F1-F12
for _n in range(1, 13):
    KEY_DISPLAY[f"{{f{_n}}}"] = f"F{_n}"

# Modifier keys (for detection)
_MODIFIER_KEYS = {
    "{lmenu}", "{rmenu}", "{lcontrol}", "{rcontrol}",
    "{lshift}", "{rshift}", "{alt}", "{control}", "{shift}",
}


# ------------------------------------------------------------------ #
#  Regex patterns
# ------------------------------------------------------------------ #

# Parse "Type 'Name'" from raw PAD element string
ELEMENT_PARSE_RE = re.compile(r"^(.+?)\s+'(.*)'$")

# Extract title from "Window 'Title Here'"
WINDOW_TITLE_RE = re.compile(r"^Window\s+'(.+)'$")

# Noise removal in element names
NOISE_RE = re.compile(r"\s*\.{3,}\s*.*$")
RIGHTS_RE = re.compile(r"\s*Rights Reserved\.?\s*$", re.IGNORECASE)


# ------------------------------------------------------------------ #
#  Element aliasing
# ------------------------------------------------------------------ #

def _clean_element_name(name: str) -> str:
    """Remove PAD noise from element name (ellipsis, copyright text)."""
    name = NOISE_RE.sub("", name)
    name = RIGHTS_RE.sub("", name)
    name = name.strip()
    if len(name) > 30:
        # Truncate at a natural break point
        short = name[:30]
        for ch in (" ", "\u3000", "\u3001", "/"):
            idx = short.rfind(ch)
            if idx > 8:
                short = short[:idx]
                break
        name = short
    return name


def _parse_element(raw: str | None) -> tuple[str, str]:
    """Parse raw element name into (element_type, element_name).

    "Button 'Microsoft Edge 固定済み'" → ("Button", "Microsoft Edge 固定済み")
    "Input submit 'ログイン'" → ("Input submit", "ログイン")
    """
    if not raw:
        return ("", "")
    match = ELEMENT_PARSE_RE.match(raw)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return (raw, "")


def alias_element(raw: str | None) -> str:
    """Convert raw PAD element name to human-readable Japanese alias."""
    if not raw:
        return ""

    elem_type, elem_name = _parse_element(raw)
    elem_name = _clean_element_name(elem_name)

    for known_type, (label, template) in ELEMENT_TYPE_JA.items():
        if elem_type == known_type:
            if elem_name:
                return template.format(name=elem_name)
            return label

    # Unknown type
    if elem_name:
        return f"「{elem_name}」{elem_type}"
    return raw


# ------------------------------------------------------------------ #
#  Window aliasing
# ------------------------------------------------------------------ #

def alias_window(raw: str | None, url: str | None = None) -> str:
    """Convert raw PAD window name to human-readable Japanese alias."""
    if not raw:
        if url:
            return "Webブラウザ"
        return ""

    if raw.lower() == "taskbar":
        return "タスクバー"

    # Web Page pattern
    if raw.startswith("Web Page"):
        if url and "rakurakuseisan" in url:
            return "楽楽精算Webページ"
        if url:
            domain_match = re.search(r"https?://([^/]+)", url)
            if domain_match:
                return f"Webページ（{domain_match.group(1)}）"
        return "Webページ"

    # Window 'Title - AppName' pattern
    win_match = WINDOW_TITLE_RE.match(raw)
    if win_match:
        title = win_match.group(1)
        # Remove zero-width Unicode characters
        title = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", title)
        parts = title.split(" - ")
        if len(parts) >= 2:
            app = parts[-1].strip()
            context = parts[0].strip()
            if len(context) > 20:
                context = context[:20].rstrip()
            return f"{app}（{context}）"
        return title

    return raw


# ------------------------------------------------------------------ #
#  Key description
# ------------------------------------------------------------------ #

def describe_keys(raw: str | None) -> str:
    """Convert SendKeys format to human-readable description.

    "{LMenu}({Tab}{Tab})" → "Alt + Tab × 2"
    "{LControl}c" → "Ctrl + C"
    """
    if not raw:
        return ""

    parts: list[str] = []
    modifiers: list[str] = []
    i = 0

    while i < len(raw):
        if raw[i] == "{":
            end = raw.find("}", i)
            if end == -1:
                break
            key_token = raw[i : end + 1].lower()
            display = KEY_DISPLAY.get(key_token, raw[i + 1 : end])
            if key_token in _MODIFIER_KEYS:
                if display not in modifiers:
                    modifiers.append(display)
            else:
                parts.append(display)
            i = end + 1
        elif raw[i] in ("(", ")"):
            i += 1
        else:
            parts.append(raw[i].upper())
            i += 1

    # Compress consecutive identical keys: Tab, Tab → Tab × 2
    compressed: list[str] = []
    if parts:
        count = 1
        for j in range(1, len(parts)):
            if parts[j] == parts[j - 1]:
                count += 1
            else:
                _append_key(compressed, parts[j - 1], count)
                count = 1
        _append_key(compressed, parts[-1], count)

    return " + ".join(modifiers + compressed) if (modifiers or compressed) else raw


def _append_key(out: list[str], key: str, count: int) -> None:
    """Append key with optional repeat count."""
    if count > 1:
        out.append(f"{key} × {count}")
    else:
        out.append(key)


# ------------------------------------------------------------------ #
#  Description generation (rule-based templates)
# ------------------------------------------------------------------ #

def _build_description(
    step: dict,
    element_alias: str,
    window_alias: str,
    prev_window_alias: str | None,
) -> str:
    """Generate Japanese PDD step description from normalized step data."""
    category = step["action_category"]
    action_type = step["action_type"]
    click_type = step.get("click_type")
    input_value = step.get("input_value")
    url = step.get("url")

    # Window context prefix (only when window changes)
    prefix = ""
    if window_alias and window_alias != prev_window_alias:
        prefix = f"{window_alias}で、"

    click_ja = CLICK_TYPE_JA.get(click_type, "クリック")

    # --- Wait ---
    if category == "wait":
        wait_str = (input_value or "").replace("s", "秒")
        return f"{wait_str}待機する"

    # --- Keyboard ---
    if category == "keyboard" and action_type == "send_keys":
        key_desc = describe_keys(input_value)
        return f"{prefix}キーボードで {key_desc} を送信する"

    # --- Browser launch/navigate/close (no window prefix — action is self-descriptive) ---
    if action_type == "launch_browser":
        if url:
            return f"Edgeブラウザで {url} を開く"
        return f"Edgeブラウザを起動する"

    if action_type == "navigate":
        if url:
            return f"{prefix}{url} に移動する"
        return f"{prefix}ページを移動する"

    if action_type == "close_browser":
        return f"{prefix}ブラウザを閉じる"

    # --- Text input/output ---
    if action_type == "set_text":
        if input_value:
            return f"{prefix}{element_alias}に「{input_value}」と入力する"
        return f"{prefix}{element_alias}に入力する"

    if action_type == "get_text":
        return f"{prefix}{element_alias}のテキストを取得する"

    # --- Button press ---
    if action_type == "press_button":
        return f"{prefix}{element_alias}を押す"

    # --- Click ---
    if action_type in ("click", "mouse_click"):
        return f"{prefix}{element_alias}を{click_ja}する"

    # --- Drag & drop ---
    if action_type == "drag_drop":
        return f"{prefix}{element_alias}をドラッグ＆ドロップする"

    # --- Menu ---
    if action_type == "select_menu":
        return f"{prefix}{element_alias}のメニューを選択する"

    # --- Variable/control flow (non-PDD steps, include for completeness) ---
    if action_type == "set_variable":
        return "変数を設定する"

    if action_type in ("condition", "loop"):
        raw_short = step.get("raw_line", "")[:60]
        return f"制御フロー: {raw_short}"

    # --- Fallback ---
    if element_alias:
        return f"{prefix}{element_alias}に対して{action_type}を実行する"
    return f"{prefix}{action_type}を実行する"


# ------------------------------------------------------------------ #
#  Step normalization
# ------------------------------------------------------------------ #

def normalize_steps(event_log: dict) -> None:
    """Add element_alias, window_alias, description to each step.

    Also marks consecutive duplicates with merged_into/duplicate_count.
    Mutates event_log in place.
    """
    steps = event_log.get("steps", [])
    if not steps:
        return

    # Track last known URL for web page window alias resolution
    last_url: str | None = None
    prev_window_alias: str | None = None

    for step in steps:
        # Track URL propagation (launch_browser sets URL for later web steps)
        if step.get("url"):
            last_url = step["url"]

        # Resolve URL for window alias
        target_win = step.get("target_window") or ""
        window_url = step.get("url")
        if not window_url and target_win.startswith("Web Page"):
            window_url = last_url

        # Compute aliases
        element_alias = alias_element(step.get("target_element"))
        window_alias = alias_window(target_win or None, window_url)

        step["element_alias"] = element_alias
        step["window_alias"] = window_alias

        # Generate description
        step["description"] = _build_description(
            step, element_alias, window_alias, prev_window_alias,
        )

        # Track window context (only update when non-empty)
        if window_alias:
            prev_window_alias = window_alias

    # Mark consecutive duplicates
    _mark_duplicates(steps)


def _mark_duplicates(steps: list[dict]) -> None:
    """Mark consecutive duplicate steps with merged_into/duplicate_count."""
    i = 0
    while i < len(steps):
        step = steps[i]
        # Count consecutive duplicates following this step
        j = i + 1
        while j < len(steps) and "duplicate_action" in steps[j].get("gap_flags", []):
            steps[j]["merged_into"] = step["num"]
            j += 1

        count = j - i
        if count > 1:
            step["duplicate_count"] = count

        i = j


# ------------------------------------------------------------------ #
#  Flow phases builder
# ------------------------------------------------------------------ #

def build_flow_phases(event_log: dict) -> None:
    """Group steps into flow_phases by window context.

    Each phase represents consecutive steps in the same window.
    Steps with empty window inherit the previous window context.
    Mutates event_log["flow_phases"] in place.
    """
    steps = event_log.get("steps", [])
    if not steps:
        return

    phases: list[dict] = []
    phase_id = 0
    current_window = ""
    phase_step_nums: list[str] = []

    for step in steps:
        window = step.get("window_alias", "") or current_window

        if window != current_window and current_window:
            # Close previous phase
            phase_id += 1
            phases.append(create_flow_phase(
                phase_id=phase_id,
                phase_name=current_window,
                step_range=[int(phase_step_nums[0]), int(phase_step_nums[-1])],
                summary=f"{current_window}での操作",
                summary_source="rule_based",
                window_context=current_window,
            ))
            phase_step_nums = []

        current_window = window
        phase_step_nums.append(step["num"])

    # Close last phase
    if phase_step_nums and current_window:
        phase_id += 1
        phases.append(create_flow_phase(
            phase_id=phase_id,
            phase_name=current_window,
            step_range=[int(phase_step_nums[0]), int(phase_step_nums[-1])],
            summary=f"{current_window}での操作",
            summary_source="rule_based",
            window_context=current_window,
        ))

    event_log["flow_phases"] = phases


# ------------------------------------------------------------------ #
#  Video pipeline: description generation
# ------------------------------------------------------------------ #

# Action type → Japanese description template (video pipeline)
VIDEO_ACTION_JA: dict[str, str] = {
    "Click": "{target}を{click_ja}する",
    "DoubleClick": "{target}をダブルクリックする",
    "RightClick": "{target}を右クリックする",
    "Input": "{target}に「{value}」と入力する",
    "Select": "{target}で「{value}」を選択する",
    "Navigate": "{value} に移動する",
    "Scroll": "画面をスクロールする",
    "Wait": "{value}秒待機する",
    "KeyShortcut": "キーボードで {value} を送信する",
    "FileOpen": "ファイル「{value}」を開く",
    "FileSave": "ファイルを保存する",
    "DragDrop": "{target}をドラッグ＆ドロップする",
    "SwitchWindow": "{target}に切り替える",
}


def _build_description_video(
    step: dict,
    prev_window: str | None,
) -> str:
    """Generate Japanese PDD description for video pipeline steps."""
    action = step.get("action_type", "")
    target = step.get("target_element", "")
    value = step.get("input_value", "") or ""
    window = step.get("target_window", "")
    click_ja = "クリック"

    # Window context prefix (only on change)
    prefix = ""
    if window and window != prev_window:
        prefix = f"{window}で、"

    template = VIDEO_ACTION_JA.get(action, "{target}に対して操作する")
    desc = template.format(
        target=target,
        value=value,
        click_ja=click_ja,
    )

    return f"{prefix}{desc}"


def normalize_video_steps(event_log: dict) -> None:
    """Normalize video pipeline steps with descriptions and aliases.

    Video steps already have target_window and target_element from Gemini.
    This adds element_alias, window_alias, and description fields.
    """
    steps = event_log.get("steps", [])
    if not steps:
        return

    prev_window: str | None = None

    for step in steps:
        target = step.get("target_element", "")
        window = step.get("target_window", "")

        # For video pipeline, element_alias and window_alias are simpler
        step["element_alias"] = target
        step["window_alias"] = window

        # Generate description
        step["description"] = _build_description_video(step, prev_window)

        if window:
            prev_window = window

    # Mark consecutive duplicates
    _mark_duplicates(steps)


# ------------------------------------------------------------------ #
#  Phase runner
# ------------------------------------------------------------------ #

def run_phase2(event_log: dict) -> dict[str, Any]:
    """Execute Phase 2: Normalize + Describe + Flow Phases.

    Also marks phase2_screenshots as completed (skipped per architecture).

    Returns:
        Summary dict with step/phase counts.
    """
    # Skip screenshots phase (not needed per design decision)
    if not is_phase_completed(event_log, PHASE_SCREENSHOTS):
        mark_phase_completed(event_log, PHASE_SCREENSHOTS)

    if is_phase_completed(event_log, PHASE_FLOW_SUMMARY):
        steps = event_log.get("steps", [])
        return {
            "total_steps": len(steps),
            "described": sum(1 for s in steps if s.get("description")),
            "merged_duplicates": sum(1 for s in steps if s.get("merged_into")),
            "flow_phases": len(event_log.get("flow_phases", [])),
        }

    mark_phase_started(event_log, PHASE_FLOW_SUMMARY)

    try:
        if is_video_pipeline(event_log):
            normalize_video_steps(event_log)
            # Video pipeline: use Gemini-provided flow_phases if present
            if not event_log.get("flow_phases"):
                build_flow_phases(event_log)
        else:
            normalize_steps(event_log)
            build_flow_phases(event_log)
        mark_phase_completed(event_log, PHASE_FLOW_SUMMARY)

        steps = event_log.get("steps", [])
        described = sum(1 for s in steps if s.get("description"))
        merged = sum(1 for s in steps if s.get("merged_into"))
        flow_phases = len(event_log.get("flow_phases", []))

        return {
            "total_steps": len(steps),
            "described": described,
            "merged_duplicates": merged,
            "flow_phases": flow_phases,
        }

    except Exception as e:
        mark_phase_failed(event_log, PHASE_FLOW_SUMMARY, str(e))
        raise
