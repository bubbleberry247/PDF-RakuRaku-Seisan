"""Tests for RPA Drift Watchdog.

Coverage:
- Same snapshot comparison → no changes
- Header rename detection
- Column count change detection (severity=critical)
- Button add/remove detection
- Form input change detection
- Severity judgment logic
- Baseline save/load round-trip
- Manual snapshot creation
- Target list
"""
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

from tools.rpa_drift_watchdog import (
    DOMSnapshot,
    DriftReport,
    DriftWatchdog,
    create_manual_snapshot,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_watchdog(tmp_path: Path) -> DriftWatchdog:
    """DriftWatchdog with a temporary baseline directory."""
    return DriftWatchdog(baseline_dir=tmp_path / "baselines")


def _make_snapshot(
    target: str = "rakuraku",
    url: str = "https://example.com",
    table_headers: list[list[str]] | None = None,
    buttons: list[str] | None = None,
    form_inputs: list[dict] | None = None,
    nav_items: list[str] | None = None,
    timestamp: str = "2026-04-06T10:00:00",
) -> DOMSnapshot:
    return DOMSnapshot(
        target=target,
        url=url,
        timestamp=timestamp,
        table_headers=table_headers or [],
        buttons=buttons or [],
        form_inputs=form_inputs or [],
        nav_items=nav_items or [],
    )


# ---------------------------------------------------------------------------
# Test: No drift when snapshots are identical
# ---------------------------------------------------------------------------

def test_no_drift_on_identical_snapshots(tmp_watchdog: DriftWatchdog) -> None:
    snapshot = _make_snapshot(
        table_headers=[["No.", "申請者", "件名", "状態", "金額"]],
        buttons=["ログイン", "検索"],
        form_inputs=[{"name": "email", "type": "email", "label": "メールアドレス"}],
        nav_items=["ホーム", "経費申請"],
    )
    report = tmp_watchdog.compare(snapshot, snapshot)

    assert not report.has_changes
    assert report.severity == "info"
    assert report.summary() == "[rakuraku] No drift detected"


# ---------------------------------------------------------------------------
# Test: Header rename detection
# ---------------------------------------------------------------------------

def test_header_renamed(tmp_watchdog: DriftWatchdog) -> None:
    baseline = _make_snapshot(
        table_headers=[["No.", "申請者", "件名", "状態", "金額"]],
        timestamp="2026-04-01T10:00:00",
    )
    current = _make_snapshot(
        table_headers=[["No.", "申請者", "件名", "ステータス", "金額"]],
        timestamp="2026-04-06T10:00:00",
    )
    report = tmp_watchdog.compare(baseline, current)

    assert report.has_changes
    assert len(report.header_changes) == 1
    change = report.header_changes[0]
    assert change["action"] == "header_renamed"
    assert change["old"] == "状態"
    assert change["new"] == "ステータス"
    assert change["table_idx"] == 0
    assert change["column_idx"] == 3


# ---------------------------------------------------------------------------
# Test: Column count change → severity=critical
# ---------------------------------------------------------------------------

def test_column_count_changed_is_critical(tmp_watchdog: DriftWatchdog) -> None:
    baseline = _make_snapshot(
        table_headers=[["No.", "申請者", "件名", "状態", "金額"]],
    )
    current = _make_snapshot(
        table_headers=[["No.", "申請者", "件名", "状態", "金額", "承認者"]],
    )
    report = tmp_watchdog.compare(baseline, current)

    assert report.has_changes
    assert report.severity == "critical"
    assert len(report.header_changes) == 1
    change = report.header_changes[0]
    assert change["action"] == "column_count_changed"
    assert change["old_count"] == 5
    assert change["new_count"] == 6


# ---------------------------------------------------------------------------
# Test: Button add/remove detection
# ---------------------------------------------------------------------------

def test_button_added_detected(tmp_watchdog: DriftWatchdog) -> None:
    baseline = _make_snapshot(buttons=["ログイン", "検索"])
    current = _make_snapshot(buttons=["ログイン", "検索", "CSV出力"])
    report = tmp_watchdog.compare(baseline, current)

    assert report.has_changes
    added = [c for c in report.button_changes if c["action"] == "added"]
    assert len(added) == 1
    assert added[0]["value"] == "CSV出力"


def test_button_removed_detected(tmp_watchdog: DriftWatchdog) -> None:
    baseline = _make_snapshot(buttons=["ログイン", "検索", "CSV出力"])
    current = _make_snapshot(buttons=["ログイン", "検索"])
    report = tmp_watchdog.compare(baseline, current)

    assert report.has_changes
    removed = [c for c in report.button_changes if c["action"] == "removed"]
    assert len(removed) == 1
    assert removed[0]["value"] == "CSV出力"


# ---------------------------------------------------------------------------
# Test: Form input change detection
# ---------------------------------------------------------------------------

def test_form_input_removed(tmp_watchdog: DriftWatchdog) -> None:
    baseline = _make_snapshot(
        form_inputs=[
            {"name": "email", "type": "email", "label": "メールアドレス"},
            {"name": "password", "type": "password", "label": "パスワード"},
        ]
    )
    current = _make_snapshot(
        form_inputs=[
            {"name": "email", "type": "email", "label": "メールアドレス"},
        ]
    )
    report = tmp_watchdog.compare(baseline, current)

    assert report.has_changes
    removed = [c for c in report.input_changes if c["action"] == "removed"]
    assert len(removed) == 1
    assert removed[0]["name"] == "password"


def test_form_input_modified(tmp_watchdog: DriftWatchdog) -> None:
    baseline = _make_snapshot(
        form_inputs=[{"name": "user_id", "type": "text", "label": "ユーザーID"}]
    )
    current = _make_snapshot(
        form_inputs=[{"name": "user_id", "type": "email", "label": "メールアドレス"}]
    )
    report = tmp_watchdog.compare(baseline, current)

    assert report.has_changes
    modified = [c for c in report.input_changes if c["action"] == "modified"]
    assert len(modified) == 1
    assert modified[0]["name"] == "user_id"
    assert modified[0]["old"]["type"] == "text"
    assert modified[0]["new"]["type"] == "email"


# ---------------------------------------------------------------------------
# Test: Severity judgment
# ---------------------------------------------------------------------------

def test_severity_critical_for_header_change(tmp_watchdog: DriftWatchdog) -> None:
    baseline = _make_snapshot(table_headers=[["A", "B", "C"]])
    current = _make_snapshot(table_headers=[["A", "B", "D"]])
    report = tmp_watchdog.compare(baseline, current)
    assert report.severity == "critical"


def test_severity_warning_for_input_change(tmp_watchdog: DriftWatchdog) -> None:
    baseline = _make_snapshot(
        form_inputs=[{"name": "q", "type": "text", "label": "検索"}]
    )
    current = _make_snapshot(
        form_inputs=[{"name": "query", "type": "text", "label": "検索"}]
    )
    report = tmp_watchdog.compare(baseline, current)
    assert report.severity == "warning"


def test_severity_info_for_button_change(tmp_watchdog: DriftWatchdog) -> None:
    baseline = _make_snapshot(buttons=["検索"])
    current = _make_snapshot(buttons=["絞り込み"])
    report = tmp_watchdog.compare(baseline, current)
    assert report.severity == "info"


def test_severity_info_when_no_changes(tmp_watchdog: DriftWatchdog) -> None:
    snapshot = _make_snapshot(buttons=["ログイン"])
    report = tmp_watchdog.compare(snapshot, snapshot)
    assert report.severity == "info"


# ---------------------------------------------------------------------------
# Test: Baseline save/load round-trip
# ---------------------------------------------------------------------------

def test_baseline_save_and_load(tmp_watchdog: DriftWatchdog) -> None:
    original = _make_snapshot(
        table_headers=[["No.", "申請者", "金額"]],
        buttons=["ログイン"],
        form_inputs=[{"name": "email", "type": "email", "label": ""}],
        nav_items=["ホーム"],
    )
    tmp_watchdog.save_baseline(original)

    loaded = tmp_watchdog.load_baseline("rakuraku")
    assert loaded is not None
    assert loaded.target == original.target
    assert loaded.table_headers == original.table_headers
    assert loaded.buttons == original.buttons
    assert loaded.form_inputs == original.form_inputs
    assert loaded.nav_items == original.nav_items


def test_load_baseline_returns_none_when_missing(tmp_watchdog: DriftWatchdog) -> None:
    result = tmp_watchdog.load_baseline("nonexistent_target")
    assert result is None


# ---------------------------------------------------------------------------
# Test: Check result history saved
# ---------------------------------------------------------------------------

def test_save_check_result_creates_file(tmp_watchdog: DriftWatchdog) -> None:
    baseline = _make_snapshot(buttons=["検索"])
    current = _make_snapshot(buttons=["絞り込み"])
    report = tmp_watchdog.compare(baseline, current)

    path_str = tmp_watchdog.save_check_result(report)
    path = Path(path_str)
    assert path.exists()

    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["target"] == "rakuraku"
    assert saved["severity"] == "info"


# ---------------------------------------------------------------------------
# Test: Manual snapshot creation
# ---------------------------------------------------------------------------

def test_create_manual_snapshot() -> None:
    snap = create_manual_snapshot(
        target="rakuraku",
        url="https://example.com",
        table_headers=[["No.", "申請者", "金額"]],
        buttons=["ログイン"],
    )
    assert snap.target == "rakuraku"
    assert snap.table_headers == [["No.", "申請者", "金額"]]
    assert snap.buttons == ["ログイン"]
    assert snap.form_inputs == []
    assert snap.nav_items == []
    assert snap.timestamp  # non-empty


def test_create_manual_snapshot_defaults() -> None:
    snap = create_manual_snapshot(target="recoru", url="")
    assert snap.table_headers == []
    assert snap.buttons == []
    assert snap.form_inputs == []
    assert snap.nav_items == []


# ---------------------------------------------------------------------------
# Test: Target list
# ---------------------------------------------------------------------------

def test_list_targets_returns_all_known(tmp_watchdog: DriftWatchdog) -> None:
    targets = tmp_watchdog.list_targets()
    names = [t["name"] for t in targets]
    assert "rakuraku" in names
    assert "recoru" in names


def test_list_targets_no_baseline_initially(tmp_watchdog: DriftWatchdog) -> None:
    targets = tmp_watchdog.list_targets()
    for t in targets:
        assert t["has_baseline"] is False
        assert t["baseline_date"] is None


def test_list_targets_shows_baseline_after_save(tmp_watchdog: DriftWatchdog) -> None:
    snap = _make_snapshot(target="rakuraku")
    tmp_watchdog.save_baseline(snap)

    targets = tmp_watchdog.list_targets()
    rakuraku = next(t for t in targets if t["name"] == "rakuraku")
    assert rakuraku["has_baseline"] is True
    assert rakuraku["baseline_date"] is not None


# ---------------------------------------------------------------------------
# Test: DOMSnapshot round-trip serialization
# ---------------------------------------------------------------------------

def test_snapshot_to_dict_and_from_dict() -> None:
    original = _make_snapshot(
        table_headers=[["A", "B"], ["C", "D"]],
        buttons=["OK", "Cancel"],
        form_inputs=[{"name": "q", "type": "text", "label": ""}],
        nav_items=["Home"],
    )
    restored = DOMSnapshot.from_dict(original.to_dict())
    assert restored.target == original.target
    assert restored.table_headers == original.table_headers
    assert restored.buttons == original.buttons
    assert restored.form_inputs == original.form_inputs
    assert restored.nav_items == original.nav_items


# ---------------------------------------------------------------------------
# Test: Affected scripts populated on change
# ---------------------------------------------------------------------------

def test_affected_scripts_populated_when_header_changes(tmp_watchdog: DriftWatchdog) -> None:
    baseline = _make_snapshot(
        target="rakuraku",
        table_headers=[["No.", "申請者", "金額"]],
    )
    current = _make_snapshot(
        target="rakuraku",
        table_headers=[["No.", "申請者", "金額", "備考"]],
    )
    report = tmp_watchdog.compare(baseline, current)
    assert report.has_changes
    assert len(report.affected_scripts) > 0
    assert any("rakuraku_scraper" in s for s in report.affected_scripts)


def test_affected_scripts_empty_when_no_changes(tmp_watchdog: DriftWatchdog) -> None:
    snap = _make_snapshot(target="rakuraku", table_headers=[["A", "B"]])
    report = tmp_watchdog.compare(snap, snap)
    assert report.affected_scripts == []
