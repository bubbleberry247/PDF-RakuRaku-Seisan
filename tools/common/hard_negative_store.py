"""Auto-save OCR normalization failures as hard-negative benchmark cases.

When a normalization produces wrong results and is manually corrected,
save the case so future regressions are automatically caught.

Storage: tests/ocr_hard_negatives/{field_type}_{timestamp}.json

Usage example:
    from tools.common.hard_negative_store import save_hard_negative, run_regression
    from tools.common.jp_field_pack import parse_amount

    # Save a failure case discovered during manual review
    save_hard_negative(
        field_type="amount",
        raw_input="参萬六千五百円",
        wrong_output="0",
        correct_output="36500",
        rule_context="kanji_to_int: 参(3)×万(10000) path",
        source_file="invoice_2025_01.pdf",
    )

    # Later: run regression against updated parse_amount
    report = run_regression(
        normalize_fn=lambda raw: str(parse_amount(raw).value),
        field_type="amount",
    )
    print(f"{report['passed']}/{report['total']} passed")
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Storage configuration
# ---------------------------------------------------------------------------

def _get_store_dir() -> Path:
    """Resolve hard-negative storage directory.

    Priority:
    1. HARD_NEGATIVE_DIR environment variable
    2. tests/ocr_hard_negatives/ relative to this file's repo root
    """
    env_dir = os.environ.get("HARD_NEGATIVE_DIR")
    if env_dir:
        return Path(env_dir)

    # Navigate: tools/common/hard_negative_store.py → repo_root/tests/ocr_hard_negatives
    this_file = Path(__file__).resolve()
    repo_root = this_file.parent.parent.parent  # tools/common → tools → repo_root
    return repo_root / "tests" / "ocr_hard_negatives"


VALID_FIELD_TYPES = frozenset({"amount", "date", "company", "invoice_no", "text"})


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _make_case(
    field_type: str,
    raw_input: str,
    wrong_output: str,
    correct_output: str,
    rule_context: str = "",
    source_file: str = "",
) -> dict[str, Any]:
    """Build a hard-negative case dict."""
    return {
        "field_type": field_type,
        "raw_input": raw_input,
        "wrong_output": wrong_output,
        "correct_output": correct_output,
        "rule_context": rule_context,
        "source_file": source_file,
        "created_at": datetime.now().isoformat(),
        "version": 1,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_hard_negative(
    field_type: str,
    raw_input: str,
    wrong_output: str,
    correct_output: str,
    rule_context: str = "",
    source_file: str = "",
) -> str:
    """Save a hard-negative case for regression testing.

    Args:
        field_type: One of "amount", "date", "company", "invoice_no", "text".
        raw_input: Original OCR text that was fed to the normalizer.
        wrong_output: What the normalizer incorrectly produced.
        correct_output: What it should have produced (ground truth).
        rule_context: Optional description of which rule failed or was missing.
        source_file: Optional PDF/image filename that triggered this case.

    Returns:
        Absolute path to the saved JSON file.

    Raises:
        ValueError: If field_type is not one of the valid types.
    """
    if field_type not in VALID_FIELD_TYPES:
        raise ValueError(
            f"Invalid field_type '{field_type}'. "
            f"Must be one of: {sorted(VALID_FIELD_TYPES)}"
        )

    store_dir = _get_store_dir()
    store_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{field_type}_{timestamp}.json"
    filepath = store_dir / filename

    case = _make_case(
        field_type=field_type,
        raw_input=raw_input,
        wrong_output=wrong_output,
        correct_output=correct_output,
        rule_context=rule_context,
        source_file=source_file,
    )

    with filepath.open("w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=2)

    return str(filepath)


def load_hard_negatives(field_type: str | None = None) -> list[dict[str, Any]]:
    """Load all hard-negative cases, optionally filtered by field_type.

    Args:
        field_type: If provided, only return cases of this type.
                    If None, return all cases.

    Returns:
        List of case dicts sorted by created_at ascending.
    """
    store_dir = _get_store_dir()
    if not store_dir.exists():
        return []

    cases: list[dict[str, Any]] = []

    pattern = f"{field_type}_*.json" if field_type else "*.json"
    for filepath in sorted(store_dir.glob(pattern)):
        try:
            with filepath.open(encoding="utf-8") as f:
                case = json.load(f)
            # Validate minimum schema
            if "raw_input" in case and "correct_output" in case:
                cases.append(case)
        except (json.JSONDecodeError, OSError):
            pass  # Skip corrupted files silently

    # Sort by creation time
    cases.sort(key=lambda c: c.get("created_at", ""))
    return cases


def run_regression(
    normalize_fn: Callable[[str], Any],
    field_type: str | None = None,
) -> dict[str, Any]:
    """Run all hard-negative cases through normalize_fn and report pass/fail.

    Args:
        normalize_fn: Callable that takes raw_input (str) and returns a value
                      that will be compared (as string) to correct_output.
        field_type: If provided, only run cases of this type.

    Returns:
        {
            "total": 15,
            "passed": 14,
            "failed": 1,
            "pass_rate": 0.933,
            "failures": [
                {
                    "raw": "...",
                    "expected": "...",
                    "got": "...",
                    "rule_context": "...",
                    "source_file": "...",
                }
            ]
        }
    """
    cases = load_hard_negatives(field_type=field_type)

    total = len(cases)
    passed = 0
    failures: list[dict[str, Any]] = []

    for case in cases:
        raw = case["raw_input"]
        expected = str(case["correct_output"])

        try:
            got_raw = normalize_fn(raw)
            got = str(got_raw) if got_raw is not None else "None"
        except Exception as exc:
            got = f"ERROR: {exc}"

        if got == expected:
            passed += 1
        else:
            failures.append({
                "raw": raw,
                "expected": expected,
                "got": got,
                "rule_context": case.get("rule_context", ""),
                "source_file": case.get("source_file", ""),
                "created_at": case.get("created_at", ""),
            })

    pass_rate = passed / total if total > 0 else 1.0

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(pass_rate, 4),
        "failures": failures,
    }


def delete_hard_negative(raw_input: str, field_type: str | None = None) -> int:
    """Delete hard-negative cases matching raw_input.

    Useful for removing obsolete cases after the underlying bug is fixed
    and the normalizer now handles the input correctly.

    Returns:
        Number of files deleted.
    """
    store_dir = _get_store_dir()
    if not store_dir.exists():
        return 0

    deleted = 0
    pattern = f"{field_type}_*.json" if field_type else "*.json"
    for filepath in store_dir.glob(pattern):
        try:
            with filepath.open(encoding="utf-8") as f:
                case = json.load(f)
            if case.get("raw_input") == raw_input:
                filepath.unlink()
                deleted += 1
        except (json.JSONDecodeError, OSError):
            pass

    return deleted


def summarize_store() -> dict[str, Any]:
    """Return a summary of all stored hard-negative cases by field_type."""
    all_cases = load_hard_negatives()
    by_type: dict[str, int] = {}
    for case in all_cases:
        ft = case.get("field_type", "unknown")
        by_type[ft] = by_type.get(ft, 0) + 1

    return {
        "total": len(all_cases),
        "by_field_type": by_type,
        "store_dir": str(_get_store_dir()),
    }
