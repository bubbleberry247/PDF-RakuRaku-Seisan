"""
event_log.py v3 - SSOT (Single Source of Truth) for Video2PDD pipeline.

v3 changes: Video file as input (Gemini multimodal analysis).
- Added: timestamp, app_type, confidence, selector_hint to steps
- Added: video_file input support alongside robin_script
- Added: phase1_video_analysis, phase5_code_generation phases
- v2 (Robin) input remains fully compatible

v2 changes: PAD Robin script as primary input (PSR deprecated).
- Removed: sync section, psr_zip input, needs_gemini/gemini_query/gemini_result/coords
- Added: raw_line, action_category, target_window, target_element, click_type, input_value, url
- Added: screenshot_path (ControlRepository), obs_frame_path (OBS)
- Phases: 4 (robin_parse, screenshots, flow_summary, excel_generation)
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_VERSION = "video2pdd-v3.0.0"

# Verification statuses
VERIFIED_CONFIRMED = "confirmed"
VERIFIED_PROVISIONAL = "provisional"
VERIFIED_PENDING = "pending_review"

# Unresolved categories
CATEGORY_KEYBOARD_COMPLEX = "keyboard_complex"
CATEGORY_ELEMENT_AMBIGUOUS = "element_ambiguous"
CATEGORY_GEMINI_ERROR = "gemini_error"
CATEGORY_LOW_CONFIDENCE = "low_confidence"
CATEGORY_OTHER = "other"

# App types (for code generation target framework)
APP_TYPE_WEB = "web"
APP_TYPE_DESKTOP = "desktop"
APP_TYPE_UNKNOWN = "unknown"

# Review states
REVIEW_PENDING = "pending_review"
REVIEW_REVIEWED = "reviewed"
REVIEW_APPROVED = "approved"

# Phase names (Robin pipeline)
PHASE_ROBIN_PARSE = "phase1_robin_parse"
PHASE_SCREENSHOTS = "phase2_screenshots"
PHASE_FLOW_SUMMARY = "phase3_flow_summary"
PHASE_EXCEL_GEN = "phase4_excel_generation"

# Phase names (Video pipeline)
PHASE_VIDEO_ANALYSIS = "phase1_video_analysis"
PHASE_CODE_GEN = "phase5_code_generation"

ALL_PHASES_ROBIN = [PHASE_ROBIN_PARSE, PHASE_SCREENSHOTS, PHASE_FLOW_SUMMARY, PHASE_EXCEL_GEN]
ALL_PHASES_VIDEO = [PHASE_VIDEO_ANALYSIS, PHASE_FLOW_SUMMARY, PHASE_EXCEL_GEN, PHASE_CODE_GEN]
ALL_PHASES = ALL_PHASES_ROBIN  # Default for backward compatibility


def _sha256_file(path: str, max_bytes: int = 10 * 1024 * 1024) -> str:
    """Compute SHA-256 of a file (first max_bytes for large files)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        data = f.read(max_bytes)
        h.update(data)
    return h.hexdigest()


def _now_iso() -> str:
    """Return current time as ISO 8601 string with timezone."""
    return datetime.now(timezone.utc).astimezone().isoformat()


def _generate_run_id() -> str:
    """Generate unique run ID: YYYYMMDD_HHmmss_<random6>."""
    now = datetime.now()
    rand = secrets.token_hex(3)
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{rand}"


def create_run_metadata(
    robin_script: str,
    output_dir: str,
    control_repository: str | None = None,
    obs_video: str | None = None,
) -> dict[str, Any]:
    """Create run_metadata section for v2 (PAD input)."""
    input_files: dict[str, Any] = {
        "robin_script": str(Path(robin_script).resolve()),
        "robin_script_sha256": _sha256_file(robin_script),
        "control_repository": str(Path(control_repository).resolve()) if control_repository else None,
        "obs_video": str(Path(obs_video).resolve()) if obs_video else None,
        "obs_video_sha256": _sha256_file(obs_video) if obs_video else None,
    }
    return {
        "run_id": _generate_run_id(),
        "created_at": _now_iso(),
        "tool_version": TOOL_VERSION,
        "input_files": input_files,
        "output_dir": str(Path(output_dir).resolve()),
        "user": os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
        "hostname": platform.node(),
    }


def create_run_metadata_video(
    video_file: str,
    output_dir: str,
    with_audio: bool = False,
) -> dict[str, Any]:
    """Create run_metadata section for v3 (video input)."""
    input_files: dict[str, Any] = {
        "video_file": str(Path(video_file).resolve()),
        "video_file_sha256": _sha256_file(video_file),
        "with_audio": with_audio,
        "robin_script": None,
        "robin_script_sha256": None,
        "control_repository": None,
        "obs_video": None,
        "obs_video_sha256": None,
    }
    return {
        "run_id": _generate_run_id(),
        "created_at": _now_iso(),
        "tool_version": TOOL_VERSION,
        "input_files": input_files,
        "output_dir": str(Path(output_dir).resolve()),
        "user": os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
        "hostname": platform.node(),
    }


def create_step(
    num: str,
    raw_line: str,
    action_category: str,
    action_type: str,
    target_window: str | None = None,
    target_element: str | None = None,
    click_type: str | None = None,
    input_value: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """Create a v2 step entry (Robin pipeline)."""
    return {
        "num": num.zfill(2),
        "raw_line": raw_line,
        "action_category": action_category,
        "action_type": action_type,
        "target_window": target_window,
        "target_element": target_element,
        "click_type": click_type,
        "input_value": input_value,
        "url": url,
        "timestamp": None,
        "app_type": None,
        "confidence": None,
        "selector_hint": None,
        "screenshot_path": None,
        "obs_frame_path": None,
        "gap_flags": [],
        "gap_notes": "",
        "verification_status": VERIFIED_PENDING,
        "notes": "",
    }


def create_step_video(
    num: int,
    timestamp: str,
    application: str,
    app_type: str,
    action_type: str,
    target: str,
    value: str | None = None,
    result: str | None = None,
    confidence: float = 1.0,
    selector_hint: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Create a v3 step entry (video pipeline)."""
    return {
        "num": str(num).zfill(2),
        "raw_line": f"[{timestamp}] {application}: {action_type} {target}",
        "action_category": app_type,
        "action_type": action_type,
        "target_window": application,
        "target_element": target,
        "click_type": "LeftClick" if action_type == "Click" else None,
        "input_value": value,
        "url": value if action_type == "Navigate" else None,
        "timestamp": timestamp,
        "app_type": app_type,
        "confidence": confidence,
        "selector_hint": selector_hint,
        "screenshot_path": None,
        "obs_frame_path": None,
        "gap_flags": [],
        "gap_notes": "",
        "verification_status": VERIFIED_CONFIRMED if confidence >= 0.9
        else VERIFIED_PROVISIONAL if confidence >= 0.7
        else VERIFIED_PENDING,
        "result": result,
        "notes": notes,
    }


def create_flow_phase(
    phase_id: int,
    phase_name: str,
    step_range: list[int],
    summary: str = "",
    summary_source: str = "pending",
    window_context: str = "",
) -> dict[str, Any]:
    """Create a flow_phases entry."""
    return {
        "phase_id": phase_id,
        "phase_name": phase_name,
        "step_range": step_range,
        "summary": summary,
        "summary_source": summary_source,
        "window_context": window_context,
        "unresolved": False,
    }


def create_unresolved_item(
    step_num: str | None,
    category: str,
    description: str,
    provisional_value: str | None = None,
) -> dict[str, Any]:
    """Create an unresolved_items entry."""
    item_id = f"U{secrets.token_hex(3).upper()}"
    return {
        "item_id": item_id,
        "step_num": step_num,
        "category": category,
        "description": description,
        "provisional_value": provisional_value,
        "created_at": _now_iso(),
        "resolved_at": None,
        "resolution": None,
    }


def create_phase_status() -> dict[str, dict[str, Any]]:
    """Create initial phase_status with all 4 phases pending."""
    return {
        p: {"completed": False, "completed_at": None, "error": None}
        for p in ALL_PHASES
    }


def create_review_status() -> dict[str, Any]:
    """Create initial review_status."""
    return {
        "state": REVIEW_PENDING,
        "notified_at": None,
        "unresolved_count": 0,
    }


def create_event_log(
    robin_script: str,
    output_dir: str,
    control_repository: str | None = None,
    obs_video: str | None = None,
) -> dict[str, Any]:
    """Create a complete v2 event_log structure (Robin pipeline)."""
    return {
        "run_metadata": create_run_metadata(
            robin_script, output_dir, control_repository, obs_video,
        ),
        "steps": [],
        "flow_phases": [],
        "unresolved_items": [],
        "phase_status": create_phase_status(),
        "review_status": create_review_status(),
    }


def create_event_log_video(
    video_file: str,
    output_dir: str,
    with_audio: bool = False,
) -> dict[str, Any]:
    """Create a complete v3 event_log structure (video pipeline)."""
    phase_status = {
        p: {"completed": False, "completed_at": None, "error": None}
        for p in ALL_PHASES_VIDEO
    }
    return {
        "run_metadata": create_run_metadata_video(
            video_file, output_dir, with_audio,
        ),
        "steps": [],
        "flow_phases": [],
        "unresolved_items": [],
        "phase_status": phase_status,
        "review_status": create_review_status(),
    }


# --- Phase status helpers ---

def mark_phase_started(event_log: dict, phase_name: str) -> None:
    """Mark a phase as running (in-place mutation)."""
    status = event_log["phase_status"].get(phase_name)
    if status:
        status["completed"] = False
        status["completed_at"] = None
        status["error"] = None


def mark_phase_completed(event_log: dict, phase_name: str) -> None:
    """Mark a phase as completed (in-place mutation)."""
    status = event_log["phase_status"].get(phase_name)
    if status:
        status["completed"] = True
        status["completed_at"] = _now_iso()
        status["error"] = None


def mark_phase_failed(event_log: dict, phase_name: str, error: str) -> None:
    """Mark a phase as failed (in-place mutation)."""
    status = event_log["phase_status"].get(phase_name)
    if status:
        status["completed"] = False
        status["completed_at"] = None
        status["error"] = error


def is_phase_completed(event_log: dict, phase_name: str) -> bool:
    """Check if a phase is already completed."""
    status = event_log["phase_status"].get(phase_name, {})
    return status.get("completed", False)


def update_unresolved_count(event_log: dict) -> None:
    """Update review_status.unresolved_count from unresolved_items."""
    count = sum(
        1 for item in event_log.get("unresolved_items", [])
        if item.get("resolved_at") is None
    )
    event_log["review_status"]["unresolved_count"] = count


# --- Persistence ---

def save_event_log(event_log: dict, output_dir: str) -> str:
    """Save event_log.json to output directory. Returns file path."""
    update_unresolved_count(event_log)
    path = os.path.join(output_dir, "event_log.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(event_log, f, ensure_ascii=False, indent=2)
    return path


def load_event_log(path: str) -> dict[str, Any]:
    """Load event_log.json from file path."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_event_log(event_log: dict) -> list[str]:
    """Validate v2/v3 event_log structure. Returns list of errors (empty = valid)."""
    errors: list[str] = []
    required_sections = [
        "run_metadata", "steps", "flow_phases",
        "unresolved_items", "phase_status", "review_status",
    ]
    for section in required_sections:
        if section not in event_log:
            errors.append(f"Missing required section: {section}")

    rm = event_log.get("run_metadata", {})
    for field in ["run_id", "created_at", "tool_version", "input_files"]:
        if field not in rm:
            errors.append(f"Missing run_metadata.{field}")

    inp = rm.get("input_files", {})
    has_robin = inp.get("robin_script") is not None
    has_video = inp.get("video_file") is not None
    if not has_robin and not has_video:
        errors.append("Missing input: need robin_script or video_file")

    return errors


def is_video_pipeline(event_log: dict) -> bool:
    """Check if this event_log uses the video pipeline."""
    inp = event_log.get("run_metadata", {}).get("input_files", {})
    return inp.get("video_file") is not None
