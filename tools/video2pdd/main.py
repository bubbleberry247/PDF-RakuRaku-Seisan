"""
Video2PDD v3 - Video / PAD Robin script -> PDD + Python automation generator.

Usage:
    # Video input (NEW)
    python -m tools.video2pdd.main --video FILE [--with-audio] [--skip-codegen]

    # Robin input (existing)
    python -m tools.video2pdd.main --robin-file FILE [--control-repo FILE]

    # Common options
    python -m tools.video2pdd.main ... [--output-dir DIR] [--stop-after PHASE] [--resume EVENT_LOG]

v3: Video file as input with Gemini multimodal analysis + Python code generation.
v2: PAD Robin script as primary input (PSR deprecated).
CLI entry point with input validation (pokayoke) and resume support (jidoka).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from .event_log import (
    PHASE_CODE_GEN,
    PHASE_EXCEL_GEN,
    PHASE_FLOW_SUMMARY,
    PHASE_ROBIN_PARSE,
    PHASE_SCREENSHOTS,
    PHASE_VIDEO_ANALYSIS,
    create_event_log,
    create_event_log_video,
    is_phase_completed,
    is_video_pipeline,
    load_event_log,
    save_event_log,
    validate_event_log,
)
from .phase1_robin import run_phase1
from .phase2_describe import run_phase2
from .phase3_excel import run_phase3


# ------------------------------------------------------------------ #
#  Pokayoke: Input validation
# ------------------------------------------------------------------ #

def _validate_robin_file(path: str) -> None:
    """Validate Robin script file exists and is non-empty."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Robin script not found: {path}")

    size = os.path.getsize(path)
    if size == 0:
        raise ValueError(f"Robin script is empty: {path}")

    # Quick sanity check: must contain at least one action-like line
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("@@"):
                return
    raise ValueError(f"Robin script has no action lines: {path}")


def _validate_control_repo(path: str) -> None:
    """Validate ControlRepository JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"ControlRepository not found: {path}")

    import json
    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"ControlRepository is not valid JSON: {e}")


def _validate_obs_video(path: str) -> None:
    """Validate OBS video file (optional input)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"OBS video not found: {path}")

    size = os.path.getsize(path)
    if size < 1024 * 1024:
        raise ValueError(
            f"OBS video too small ({size} bytes). Expected > 1MB: {path}"
        )


def _validate_video_file(path: str) -> None:
    """Validate video file for Gemini analysis."""
    from .phase1_video import _validate_video_file as _validate
    _validate(path)


# ------------------------------------------------------------------ #
#  Pipeline runners
# ------------------------------------------------------------------ #

def _run_robin_pipeline(
    event_log: dict,
    robin_file: str,
    control_repo: str | None,
    output_dir: str,
    stop_after: str | None = None,
) -> None:
    """Run the Robin script pipeline (v2)."""
    # Phase 1: Robin script parsing
    if not is_phase_completed(event_log, PHASE_ROBIN_PARSE):
        print("=" * 60)
        print("Phase 1: Robin script parsing...")
        print("=" * 60)
        summary = run_phase1(event_log, robin_file, control_repo)
        print(f"  Total steps:  {summary['total_steps']}")
        print(f"  Confirmed:    {summary['confirmed']}")
        print(f"  Provisional:  {summary['provisional']}")
        print(f"  Duplicates:   {summary['duplicates']}")
        save_event_log(event_log, output_dir)
    else:
        print("Phase 1: skip (already completed)")

    if stop_after == "phase1":
        print("\n--stop-after phase1: stopped after Phase 1")
        return

    # Phase 2-3: Normalize + Describe
    _run_phase2_3(event_log, output_dir, stop_after)

    # Phase 4: Excel generation
    _run_phase_excel(event_log, output_dir)

    # Summary
    _print_summary(event_log, output_dir)


def _run_video_pipeline(
    event_log: dict,
    video_file: str,
    output_dir: str,
    with_audio: bool = False,
    skip_codegen: bool = False,
    stop_after: str | None = None,
) -> None:
    """Run the video analysis pipeline (v3)."""
    from .phase1_video import analyze_video, gemini_to_event_log_steps

    # Phase 1: Gemini video analysis
    if not is_phase_completed(event_log, PHASE_VIDEO_ANALYSIS):
        print("=" * 60)
        print("Phase 1: Gemini video analysis...")
        print("=" * 60)

        from .event_log import mark_phase_started, mark_phase_completed, mark_phase_failed

        mark_phase_started(event_log, PHASE_VIDEO_ANALYSIS)
        try:
            gemini_data = analyze_video(video_file, with_audio=with_audio)
            steps, flow_phases, unresolved = gemini_to_event_log_steps(gemini_data)

            event_log["steps"] = steps
            event_log["flow_phases"] = flow_phases
            event_log["unresolved_items"].extend(unresolved)

            mark_phase_completed(event_log, PHASE_VIDEO_ANALYSIS)

            total = len(steps)
            flagged = sum(1 for s in steps if s.get("gap_flags"))
            print(f"  Total steps:  {total}")
            print(f"  Flagged:      {flagged}")
            print(f"  Unresolved:   {len(unresolved)}")
            print(f"  Flow phases:  {len(flow_phases)}")
            save_event_log(event_log, output_dir)

        except Exception as e:
            mark_phase_failed(event_log, PHASE_VIDEO_ANALYSIS, str(e))
            save_event_log(event_log, output_dir)
            raise
    else:
        print("Phase 1: skip (already completed)")

    if stop_after == "phase1":
        print("\n--stop-after phase1: stopped after Phase 1")
        return

    # Phase 2-3: Normalize + Describe
    _run_phase2_3(event_log, output_dir, stop_after)

    # Phase 3 (Excel): Excel generation
    _run_phase_excel(event_log, output_dir)

    # Phase 4: Python code generation
    if not skip_codegen:
        _run_phase_codegen(event_log, output_dir)
    else:
        print("\nPhase 4 (Code Gen): skip (--skip-codegen)")

    # Summary
    _print_summary(event_log, output_dir)


# ------------------------------------------------------------------ #
#  Shared phase runners
# ------------------------------------------------------------------ #

def _run_phase2_3(
    event_log: dict,
    output_dir: str,
    stop_after: str | None = None,
) -> None:
    """Run Phase 2-3: Normalize + Describe."""
    if not is_phase_completed(event_log, PHASE_FLOW_SUMMARY):
        print()
        print("=" * 60)
        print("Phase 2-3: Normalize + Describe...")
        print("=" * 60)
        summary2 = run_phase2(event_log)
        print(f"  Described:   {summary2['described']}")
        print(f"  Merged:      {summary2['merged_duplicates']}")
        print(f"  Flow phases: {summary2['flow_phases']}")
        save_event_log(event_log, output_dir)
    else:
        print("Phase 2-3: skip (already completed)")

    if stop_after in ("phase2", "phase3"):
        print(f"\n--stop-after {stop_after}: stopped")
        sys.exit(0)


def _run_phase_excel(event_log: dict, output_dir: str) -> None:
    """Run Excel generation phase."""
    if not is_phase_completed(event_log, PHASE_EXCEL_GEN):
        print()
        print("=" * 60)
        print("Phase 3 (Excel): Excel generation...")
        print("=" * 60)
        summary3 = run_phase3(event_log, output_dir)
        print(f"  Excel:       {summary3['excel_path']}")
        print(f"  Sheets:      {summary3['sheets']}")
        print(f"  Unresolved:  {summary3['unresolved_count']}")
        save_event_log(event_log, output_dir)
    else:
        print("Phase 3 (Excel): skip (already completed)")


def _run_phase_codegen(event_log: dict, output_dir: str) -> None:
    """Run Python code generation phase."""
    from .phase4_codegen import run_phase4

    if not is_phase_completed(event_log, PHASE_CODE_GEN):
        print()
        print("=" * 60)
        print("Phase 4: Python code generation...")
        print("=" * 60)
        summary4 = run_phase4(event_log, output_dir)
        print(f"  Code:        {summary4['code_path']}")
        print(f"  Web steps:   {summary4['web_steps']}")
        print(f"  Desktop:     {summary4['desktop_steps']}")
        print(f"  TODO items:  {summary4['todo_count']}")
        save_event_log(event_log, output_dir)
    else:
        print("Phase 4 (Code Gen): skip (already completed)")


def _print_summary(event_log: dict, output_dir: str) -> None:
    """Print pipeline completion summary."""
    print()
    print("=" * 60)
    print("Pipeline complete")
    print("=" * 60)
    steps = event_log["steps"]
    unresolved = [
        u for u in event_log.get("unresolved_items", [])
        if u.get("resolved_at") is None
    ]
    print(f"  Steps:            {len(steps)}")
    print(f"  Unresolved items: {len(unresolved)}")
    print(f"  event_log:        {os.path.join(output_dir, 'event_log.json')}")


# ------------------------------------------------------------------ #
#  CLI
# ------------------------------------------------------------------ #

def main() -> None:
    """CLI entry point."""
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Video2PDD v3: Video/Robin -> PDD + Python automation",
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--video",
        help="Path to video file (MP4/AVI/MKV/WEBM/MOV) for Gemini analysis",
    )
    input_group.add_argument(
        "--robin-file",
        help="Path to PAD Robin script file",
    )
    input_group.add_argument(
        "--resume",
        metavar="EVENT_LOG_PATH",
        help="Resume from existing event_log.json",
    )

    parser.add_argument(
        "--with-audio",
        action="store_true",
        help="Use audio-aware Gemini prompt (video mode only)",
    )
    parser.add_argument(
        "--skip-codegen",
        action="store_true",
        help="Skip Python code generation (PDD Excel only)",
    )
    parser.add_argument(
        "--control-repo",
        help="Path to PAD ControlRepository JSON file (robin mode only)",
    )
    parser.add_argument(
        "--obs-video",
        help="Path to OBS video file (robin mode only)",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory (default: auto-generated)",
    )
    parser.add_argument(
        "--stop-after",
        choices=["phase1", "phase2", "phase3"],
        help="Stop after specified phase (for testing)",
    )

    args = parser.parse_args()

    try:
        if args.resume:
            # Resume mode
            print(f"Resuming from: {args.resume}")
            event_log = load_event_log(args.resume)
            errors = validate_event_log(event_log)
            if errors:
                print("ERROR: Invalid event_log.json:")
                for e in errors:
                    print(f"  - {e}")
                sys.exit(1)

            rm = event_log["run_metadata"]
            output_dir = rm["output_dir"]

            if is_video_pipeline(event_log):
                video_file = rm["input_files"]["video_file"]
                _run_video_pipeline(
                    event_log, video_file, output_dir,
                    with_audio=rm["input_files"].get("with_audio", False),
                    skip_codegen=args.skip_codegen,
                    stop_after=args.stop_after,
                )
            else:
                robin_file = rm["input_files"]["robin_script"]
                control_repo = rm["input_files"].get("control_repository")
                _validate_robin_file(robin_file)
                _run_robin_pipeline(
                    event_log, robin_file, control_repo, output_dir, args.stop_after,
                )

        elif args.video:
            # Video mode (v3)
            video_file = args.video
            print("Validating inputs...")
            _validate_video_file(video_file)
            size_mb = os.path.getsize(video_file) / (1024 * 1024)
            print(f"  OK: Video file ({size_mb:.1f} MB)")

            if args.with_audio:
                print("  Audio mode: enabled")

            # Output directory
            output_dir = args.output_dir
            if not output_dir:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = os.path.join(
                    os.path.dirname(os.path.abspath(video_file)),
                    f"video2pdd_output_{ts}",
                )
            os.makedirs(output_dir, exist_ok=True)

            # Create event log
            event_log = create_event_log_video(
                video_file=video_file,
                output_dir=output_dir,
                with_audio=args.with_audio,
            )
            save_event_log(event_log, output_dir)
            print(f"  event_log: {os.path.join(output_dir, 'event_log.json')}")
            print()

            _run_video_pipeline(
                event_log, video_file, output_dir,
                with_audio=args.with_audio,
                skip_codegen=args.skip_codegen,
                stop_after=args.stop_after,
            )

        else:
            # Robin mode (v2)
            robin_file = args.robin_file
            control_repo = args.control_repo
            obs_video = args.obs_video

            print("Validating inputs...")
            _validate_robin_file(robin_file)
            print(f"  OK: Robin script ({os.path.getsize(robin_file)} bytes)")

            if control_repo:
                _validate_control_repo(control_repo)
                print(f"  OK: ControlRepository ({os.path.getsize(control_repo)} bytes)")

            if obs_video:
                _validate_obs_video(obs_video)
                print(f"  OK: OBS video ({os.path.getsize(obs_video)} bytes)")

            # Output directory
            output_dir = args.output_dir
            if not output_dir:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = os.path.join(
                    os.path.dirname(os.path.abspath(robin_file)),
                    f"video2pdd_output_{ts}",
                )
            os.makedirs(output_dir, exist_ok=True)

            # Create event log
            event_log = create_event_log(
                robin_script=robin_file,
                output_dir=output_dir,
                control_repository=control_repo,
                obs_video=obs_video,
            )
            save_event_log(event_log, output_dir)
            print(f"  event_log: {os.path.join(output_dir, 'event_log.json')}")
            print()

            _run_robin_pipeline(
                event_log, robin_file, control_repo, output_dir, args.stop_after,
            )

    except KeyboardInterrupt:
        print("\nInterrupted. Use --resume to continue.")
        sys.exit(130)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
