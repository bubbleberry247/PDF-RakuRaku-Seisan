"""
phase1_video.py - Gemini multimodal video analysis for Video2PDD pipeline.

Uploads a video file to Gemini and extracts structured step data via
the google-genai Python SDK (multimodal prompting).
Returns parsed JSON compatible with event_log v3 schema.

Requires: pip install google-genai
Auth: Set GEMINI_API_KEY environment variable (get from https://aistudio.google.com/apikey)
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from . import event_log as el

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SEC = 5
SUPPORTED_FORMATS = {".mp4", ".avi", ".mkv", ".webm", ".mov"}
MAX_VIDEO_SIZE_MB = 500
GEMINI_MODEL = "gemini-2.5-flash"

# Gap flags (video-specific)
GAP_LOW_CONFIDENCE = "low_confidence"
GAP_AMBIGUOUS_SELECTOR = "ambiguous_selector"
GAP_DUPLICATE_ACTION = "duplicate_action"

CONFIDENCE_THRESHOLD_WARN = 0.7
CONFIDENCE_THRESHOLD_FLAG = 0.9

# MIME type mapping
MIME_TYPES = {
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}


def _validate_video_file(video_path: str) -> None:
    """Validate video file exists, format, and size (pokayoke)."""
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {video_path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format: {suffix}. "
            f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_VIDEO_SIZE_MB:
        logger.warning(
            "Video file is %.0f MB (limit: %d MB). "
            "Gemini may truncate or fail.",
            size_mb, MAX_VIDEO_SIZE_MB,
        )


def _get_api_key() -> str:
    """Get Gemini API key from environment variable."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable not set.\n"
            "Get a free API key from: https://aistudio.google.com/apikey\n"
            "Then set it: set GEMINI_API_KEY=your_key_here"
        )
    return key


def _call_gemini(
    video_path: str,
    prompt_text: str,
) -> str:
    """Call Gemini API with video file and return raw text output."""
    from google import genai
    from google.genai import types

    api_key = _get_api_key()
    client = genai.Client(api_key=api_key)

    video_file = Path(video_path)
    mime_type = MIME_TYPES.get(video_file.suffix.lower(), "video/mp4")

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(
            "Gemini API call attempt %d/%d...", attempt, MAX_RETRIES,
        )
        try:
            # Upload video file
            logger.info("Uploading video file: %s", video_file.name)
            uploaded = client.files.upload(
                file=str(video_file.resolve()),
                config=types.UploadFileConfig(
                    mime_type=mime_type,
                ),
            )
            logger.info(
                "Upload complete: %s (state=%s)",
                uploaded.name, uploaded.state,
            )

            # Wait until file is ACTIVE (ready for use)
            wait_count = 0
            while uploaded.state is None or "ACTIVE" not in str(uploaded.state).upper():
                state_str = str(uploaded.state).upper() if uploaded.state else "UNKNOWN"
                if "FAILED" in state_str:
                    raise RuntimeError(f"Video processing failed: {uploaded.state}")
                if wait_count > 60:
                    raise RuntimeError(
                        f"Video processing timed out (>60 polls). "
                        f"Last state: {uploaded.state}"
                    )
                wait_count += 1
                logger.info(
                    "Waiting for processing... (%d) state=%s",
                    wait_count, uploaded.state,
                )
                time.sleep(5)
                uploaded = client.files.get(name=uploaded.name)

            logger.info("File ready: state=%s", uploaded.state)

            # Generate content with video + prompt
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_uri(
                        file_uri=uploaded.uri,
                        mime_type=mime_type,
                    ),
                    prompt_text,
                ],
            )

            text = response.text.strip() if response.text else ""
            if text:
                # Clean up uploaded file
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:
                    pass  # Non-critical
                return text

            logger.warning(
                "Gemini attempt %d returned empty response", attempt,
            )

        except RuntimeError:
            raise
        except Exception as e:
            logger.warning(
                "Gemini attempt %d failed: %s", attempt, str(e)[:200],
            )

        if attempt < MAX_RETRIES:
            logger.info("Retrying in %d seconds...", RETRY_DELAY_SEC)
            time.sleep(RETRY_DELAY_SEC)

    raise RuntimeError(
        f"Gemini API failed after {MAX_RETRIES} attempts. "
        "Check your API key and network connection."
    )


def _extract_json(raw_output: str) -> dict[str, Any]:
    """Extract JSON from Gemini output (handles markdown fences)."""
    text = raw_output.strip()

    # Remove markdown code fences if present
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()

    # Try parsing as-is first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try finding the first { ... } block
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not parse Gemini output as JSON. "
        f"First 200 chars: {raw_output[:200]}"
    )


def _validate_gemini_output(data: dict[str, Any]) -> list[str]:
    """Validate Gemini JSON output structure. Returns list of errors."""
    errors: list[str] = []

    if "steps" not in data:
        errors.append("Missing 'steps' array")
        return errors

    if not isinstance(data["steps"], list):
        errors.append("'steps' must be an array")
        return errors

    if len(data["steps"]) == 0:
        errors.append("'steps' array is empty - no actions detected in video")

    required_step_fields = ["num", "timestamp", "application", "action"]
    for i, step in enumerate(data["steps"]):
        for field in required_step_fields:
            if field not in step:
                errors.append(f"Step {i+1}: missing '{field}'")

    return errors


def _detect_duplicates(steps: list[dict]) -> list[dict]:
    """Detect consecutive duplicate actions and flag them."""
    for i in range(1, len(steps)):
        prev = steps[i - 1]
        curr = steps[i]
        if (
            prev.get("action") == curr.get("action")
            and prev.get("target") == curr.get("target")
            and prev.get("application") == curr.get("application")
        ):
            if GAP_DUPLICATE_ACTION not in curr.get("gap_flags", []):
                curr.setdefault("gap_flags", []).append(GAP_DUPLICATE_ACTION)
                curr["gap_notes"] = curr.get("gap_notes", "") + " Duplicate of previous step."

    return steps


def _apply_gap_flags(steps: list[dict]) -> list[dict]:
    """Apply gap flags based on confidence and selector quality."""
    for step in steps:
        confidence = step.get("confidence", 1.0)
        gap_flags = step.get("gap_flags", [])

        if confidence < CONFIDENCE_THRESHOLD_WARN:
            if GAP_LOW_CONFIDENCE not in gap_flags:
                gap_flags.append(GAP_LOW_CONFIDENCE)

        selector = step.get("selector_hint", "")
        if not selector or selector in ("", "unknown", "N/A"):
            if GAP_AMBIGUOUS_SELECTOR not in gap_flags:
                gap_flags.append(GAP_AMBIGUOUS_SELECTOR)

        step["gap_flags"] = gap_flags

    return steps


def analyze_video(
    video_path: str,
    with_audio: bool = False,
    prompts_dir: str | None = None,
) -> dict[str, Any]:
    """Analyze a video file using Gemini and return structured step data.

    Args:
        video_path: Path to the video file (MP4, AVI, MKV, WEBM, MOV).
        with_audio: If True, use audio-aware prompt.
        prompts_dir: Directory containing prompt files. Defaults to
            tools/video2pdd/prompts/.

    Returns:
        Parsed Gemini JSON output with gap flags applied.
    """
    _validate_video_file(video_path)

    if prompts_dir is None:
        prompts_dir = str(Path(__file__).parent / "prompts")

    prompt_file = "video_analysis_audio.txt" if with_audio else "video_analysis.txt"
    prompt_path = os.path.join(prompts_dir, prompt_file)

    if not Path(prompt_path).exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    prompt_text = Path(prompt_path).read_text(encoding="utf-8")

    logger.info(
        "Analyzing video: %s (audio=%s)",
        Path(video_path).name, with_audio,
    )

    raw_output = _call_gemini(video_path, prompt_text)
    data = _extract_json(raw_output)

    errors = _validate_gemini_output(data)
    if errors:
        raise ValueError(
            f"Gemini output validation failed:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    steps = data.get("steps", [])
    steps = _apply_gap_flags(steps)
    steps = _detect_duplicates(steps)
    data["steps"] = steps

    # Statistics
    total = len(steps)
    flagged = sum(1 for s in steps if s.get("gap_flags"))
    low_conf = sum(1 for s in steps if (s.get("confidence") or 1.0) < CONFIDENCE_THRESHOLD_WARN)

    logger.info(
        "Video analysis complete: %d steps, %d flagged, %d low-confidence",
        total, flagged, low_conf,
    )

    return data


def gemini_to_event_log_steps(
    gemini_data: dict[str, Any],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Convert Gemini output to event_log steps, flow_phases, and unresolved_items.

    Returns:
        (steps, flow_phases, unresolved_items)
    """
    steps: list[dict] = []
    unresolved: list[dict] = []

    for raw_step in gemini_data.get("steps", []):
        num = raw_step.get("num", len(steps) + 1)
        app_type = raw_step.get("app_type", el.APP_TYPE_UNKNOWN)
        confidence = raw_step.get("confidence", 1.0)

        step = el.create_step_video(
            num=num,
            timestamp=raw_step.get("timestamp", ""),
            application=raw_step.get("application", ""),
            app_type=app_type,
            action_type=raw_step.get("action", ""),
            target=raw_step.get("target", ""),
            value=raw_step.get("value"),
            result=raw_step.get("result"),
            confidence=confidence,
            selector_hint=raw_step.get("selector_hint"),
            notes=raw_step.get("notes", ""),
        )

        # Copy gap flags from Gemini analysis
        step["gap_flags"] = raw_step.get("gap_flags", [])
        step["gap_notes"] = raw_step.get("gap_notes", "")

        steps.append(step)

        # Create unresolved items for flagged steps
        if confidence < CONFIDENCE_THRESHOLD_WARN:
            unresolved.append(el.create_unresolved_item(
                step_num=step["num"],
                category=el.CATEGORY_LOW_CONFIDENCE,
                description=f"Low confidence ({confidence:.2f}): {raw_step.get('action', '')} on {raw_step.get('target', '')}",
                provisional_value=raw_step.get("selector_hint"),
            ))

    # Convert flow_phases
    flow_phases: list[dict] = []
    for i, phase in enumerate(gemini_data.get("flow_phases", []), start=1):
        flow_phases.append(el.create_flow_phase(
            phase_id=i,
            phase_name=phase.get("phase_name", f"Phase {i}"),
            step_range=phase.get("step_range", [1, 1]),
            summary=phase.get("summary", ""),
            summary_source="gemini_video",
            window_context=phase.get("window_context", ""),
        ))

    # Add unresolved items from ambiguities
    for amb in gemini_data.get("ambiguities", []):
        unresolved.append(el.create_unresolved_item(
            step_num=str(amb.get("step_num", "")).zfill(2) if amb.get("step_num") else None,
            category=el.CATEGORY_ELEMENT_AMBIGUOUS,
            description=amb.get("description", ""),
        ))

    return steps, flow_phases, unresolved
