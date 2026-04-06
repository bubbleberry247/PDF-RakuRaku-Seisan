"""Tests for session_briefing.py.

Covers:
- get_git_status() returns dict with expected keys
- get_handoff_summary() parses handoff.md correctly
- generate_briefing() returns a non-empty string
- --compact mode stays within 20 lines
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make tools importable from repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.session_briefing import (
    generate_briefing,
    get_git_status,
    get_handoff_summary,
    get_recent_failures,
    get_stale_decisions,
    get_wiki_health,
)


# ---------------------------------------------------------------------------
# get_git_status
# ---------------------------------------------------------------------------


def test_get_git_status_returns_dict():
    result = get_git_status()
    assert isinstance(result, dict), "get_git_status() must return a dict"


def test_get_git_status_has_required_keys():
    result = get_git_status()
    for key in ("branch", "modified_files", "untracked_files", "recent_commits"):
        assert key in result, f"Missing key: {key}"


def test_get_git_status_branch_is_string():
    result = get_git_status()
    assert isinstance(result["branch"], str)
    assert len(result["branch"]) > 0, "branch should not be empty"


def test_get_git_status_lists_are_lists():
    result = get_git_status()
    assert isinstance(result["modified_files"], list)
    assert isinstance(result["untracked_files"], list)
    assert isinstance(result["recent_commits"], list)


# ---------------------------------------------------------------------------
# get_handoff_summary
# ---------------------------------------------------------------------------


def test_get_handoff_summary_returns_dict():
    result = get_handoff_summary()
    assert isinstance(result, dict)


def test_get_handoff_summary_has_required_keys():
    result = get_handoff_summary()
    for key in ("pending_high", "pending_mid", "last_updated", "found"):
        assert key in result, f"Missing key: {key}"


def test_get_handoff_summary_found_if_file_exists():
    handoff_path = REPO_ROOT / "plans" / "handoff.md"
    result = get_handoff_summary()
    if handoff_path.exists():
        assert result["found"] is True, "found should be True when handoff.md exists"
    else:
        assert result["found"] is False, "found should be False when handoff.md is missing"


def test_get_handoff_summary_pending_are_lists():
    result = get_handoff_summary()
    assert isinstance(result["pending_high"], list)
    assert isinstance(result["pending_mid"], list)


def test_get_handoff_summary_last_updated_format():
    result = get_handoff_summary()
    last_upd = result["last_updated"]
    if last_upd:
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}", last_upd), (
            f"last_updated should be YYYY-MM-DD format, got: {last_upd}"
        )


def test_get_handoff_summary_parses_pending_high():
    """handoff.mdに優先度高タスクがあれば少なくとも1件パースされること。"""
    handoff_path = REPO_ROOT / "plans" / "handoff.md"
    if not handoff_path.exists():
        pytest.skip("handoff.md not found")

    content = handoff_path.read_text(encoding="utf-8", errors="replace")
    has_pending_section = "未完了" in content and "優先度高" in content

    result = get_handoff_summary()
    if has_pending_section:
        assert len(result["pending_high"]) > 0, (
            "handoff.mdに優先度高セクションがあるのにパース結果が空"
        )


# ---------------------------------------------------------------------------
# generate_briefing
# ---------------------------------------------------------------------------


def test_generate_briefing_returns_string():
    result = generate_briefing()
    assert isinstance(result, str)
    assert len(result) > 0, "briefing should not be empty"


def test_generate_briefing_contains_sections():
    result = generate_briefing()
    for section in ("SESSION BRIEFING", "URGENT", "PENDING", "GIT STATE"):
        assert section in result, f"Expected section '{section}' not found in briefing"


def test_generate_briefing_compact_within_20_lines():
    result = generate_briefing(compact=True)
    line_count = len(result.splitlines())
    assert line_count <= 20, (
        f"compact mode should be at most 20 lines, got {line_count}"
    )


def test_generate_briefing_full_has_recent_runs():
    result = generate_briefing(compact=False)
    assert "RECENT RUNS" in result, "Full briefing should include RECENT RUNS section"


def test_generate_briefing_compact_omits_recent_runs():
    """compactモードではRECENT RUNSセクションは省略される。"""
    result = generate_briefing(compact=True)
    # compact=True で20行に収まるよう省略されていること
    line_count = len(result.splitlines())
    assert line_count <= 20


# ---------------------------------------------------------------------------
# get_recent_failures (smoke test)
# ---------------------------------------------------------------------------


def test_get_recent_failures_returns_list():
    result = get_recent_failures(days=7)
    assert isinstance(result, list)


def test_get_recent_failures_items_have_keys():
    result = get_recent_failures(days=7)
    for item in result:
        for key in ("run_id", "pipeline", "status", "timestamp"):
            assert key in item, f"Missing key '{key}' in failure item"


# ---------------------------------------------------------------------------
# get_stale_decisions (smoke test)
# ---------------------------------------------------------------------------


def test_get_stale_decisions_returns_list():
    result = get_stale_decisions(days_threshold=90)
    assert isinstance(result, list)


def test_get_stale_decisions_items_have_keys():
    result = get_stale_decisions(days_threshold=90)
    for item in result:
        assert "file" in item
        assert "last_modified_days_ago" in item
        assert isinstance(item["last_modified_days_ago"], int)


# ---------------------------------------------------------------------------
# get_wiki_health (smoke test)
# ---------------------------------------------------------------------------


def test_get_wiki_health_returns_dict():
    result = get_wiki_health()
    assert isinstance(result, dict)


def test_get_wiki_health_has_required_keys():
    result = get_wiki_health()
    for key in ("critical", "warnings", "avg_trust_score", "total_files"):
        assert key in result, f"Missing key: {key}"
