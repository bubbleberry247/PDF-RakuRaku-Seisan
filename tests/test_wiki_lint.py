"""
Unit tests for wiki_lint.py

Run: python -m pytest tests/test_wiki_lint.py -v
  or: python tests/test_wiki_lint.py
"""

import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Allow importing from tools/
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from wiki_lint import (
    FileLintResult,
    Issue,
    ContradictionHit,
    STALE_DAYS,
    WARNING_DAYS,
    BLOAT_LINES_DECISIONS,
    BLOAT_LINES_GENERAL,
    load_memory_index,
    find_broken_memory_links,
    find_contradictions,
    build_topic_index,
    check_size,
    check_staleness,
    check_orphan,
    render_text_report,
    render_json_report,
    short_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_result(trust: int = 100, issues: list[Issue] | None = None) -> FileLintResult:
    r = FileLintResult(path="/tmp/test.md", display_path="test.md")
    r.issues = issues or []
    r.trust_score = trust
    return r


def write_temp_file(content: str, suffix: str = ".md") -> Path:
    """Write content to a temp file and return its path."""
    fd, fpath = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return Path(fpath)


# ---------------------------------------------------------------------------
# Trust Score tests
# ---------------------------------------------------------------------------


class TestTrustScore:
    def test_base_score_is_100(self):
        r = FileLintResult(path="/tmp/x.md", display_path="x.md")
        r.compute_trust()
        assert r.trust_score == 100

    def test_stale_penalty_30(self):
        r = FileLintResult(path="/tmp/x.md", display_path="x.md")
        r.issues = [Issue("STALE", "120 days", penalty=30)]
        r.compute_trust()
        assert r.trust_score == 70

    def test_orphan_penalty_20(self):
        r = FileLintResult(path="/tmp/x.md", display_path="x.md")
        r.issues = [Issue("ORPHAN", "not in index", penalty=20)]
        r.compute_trust()
        assert r.trust_score == 80

    def test_multiple_penalties_accumulate(self):
        r = FileLintResult(path="/tmp/x.md", display_path="x.md")
        r.issues = [
            Issue("STALE", "200d", penalty=30),
            Issue("ORPHAN", "missing", penalty=20),
            Issue("BLOATED", "600 lines", penalty=10),
        ]
        r.compute_trust()
        assert r.trust_score == 40

    def test_trust_never_below_zero(self):
        r = FileLintResult(path="/tmp/x.md", display_path="x.md")
        r.issues = [
            Issue("STALE", "200d", penalty=30),
            Issue("ORPHAN", "missing", penalty=20),
            Issue("BLOATED", "600 lines", penalty=10),
            Issue("SOURCE_MISSING", "file1", penalty=25),
            Issue("SOURCE_MISSING", "file2", penalty=25),
        ]
        r.compute_trust()
        assert r.trust_score == 0

    def test_severity_healthy(self):
        r = make_result(trust=90)
        assert r.severity == "HEALTHY"

    def test_severity_warning_boundary(self):
        r = make_result(trust=79)
        assert r.severity == "WARNING"
        r2 = make_result(trust=50)
        assert r2.severity == "WARNING"

    def test_severity_critical(self):
        r = make_result(trust=49)
        assert r.severity == "CRITICAL"

    def test_severity_critical_zero(self):
        r = make_result(trust=0)
        assert r.severity == "CRITICAL"


# ---------------------------------------------------------------------------
# Staleness tests
# ---------------------------------------------------------------------------


class TestStaleness:
    def _result_for_age(self, age_days: int) -> FileLintResult:
        """Create a temp file and manipulate its mtime to simulate age."""
        content = "# Test\n\nSome content\n"
        fp = write_temp_file(content)
        try:
            # Override mtime
            past_ts = (datetime.now(tz=timezone.utc) - timedelta(days=age_days)).timestamp()
            os.utime(fp, (past_ts, past_ts))
            result = FileLintResult(path=str(fp), display_path=fp.name)
            check_staleness(result, fp)
            result.compute_trust()
            return result
        finally:
            fp.unlink(missing_ok=True)

    def test_fresh_file_no_issue(self):
        result = self._result_for_age(10)
        codes = [i.code for i in result.issues]
        assert "STALE" not in codes
        assert "AGE_WARNING" not in codes

    def test_warning_at_75_days(self):
        result = self._result_for_age(75)
        codes = [i.code for i in result.issues]
        assert "AGE_WARNING" in codes
        assert "STALE" not in codes

    def test_stale_at_100_days(self):
        result = self._result_for_age(100)
        codes = [i.code for i in result.issues]
        assert "STALE" in codes

    def test_stale_penalty_reduces_trust(self):
        result = self._result_for_age(120)
        assert result.trust_score == 70  # 100 - 30

    def test_warning_penalty_reduces_trust(self):
        result = self._result_for_age(70)
        assert result.trust_score == 90  # 100 - 10


# ---------------------------------------------------------------------------
# Orphan Detection tests
# ---------------------------------------------------------------------------


class TestOrphanDetection:
    def _make_memory_md(self, links: list[str]) -> Path:
        content = "# MEMORY.md\n\n## Project Memories\n"
        for link in links:
            content += f"- [label]({link})\n"
        return write_temp_file(content)

    def test_load_memory_index_extracts_links(self):
        mem_md = self._make_memory_md(["feedback_ocr.md", "project_foo.md"])
        try:
            index = load_memory_index(mem_md)
            assert "feedback_ocr.md" in index
            assert "project_foo.md" in index
        finally:
            mem_md.unlink(missing_ok=True)

    def test_load_memory_index_empty(self):
        mem_md = write_temp_file("# MEMORY.md\nNo links here.\n")
        try:
            index = load_memory_index(mem_md)
            assert len(index) == 0
        finally:
            mem_md.unlink(missing_ok=True)

    def test_orphan_flag_when_not_in_index(self):
        memory_index = {"feedback_ocr.md", "project_foo.md"}
        fp = write_temp_file("# Orphan\n")
        fp_named = fp.parent / "unknown_file.md"
        fp.rename(fp_named)
        try:
            result = FileLintResult(path=str(fp_named), display_path=fp_named.name)
            check_orphan(result, fp_named, memory_index)
            codes = [i.code for i in result.issues]
            assert "ORPHAN" in codes
        finally:
            fp_named.unlink(missing_ok=True)

    def test_no_orphan_when_in_index(self):
        memory_index = {"feedback_ocr.md"}
        fp = write_temp_file("# OCR feedback\n")
        fp_named = fp.parent / "feedback_ocr.md"
        fp.rename(fp_named)
        try:
            result = FileLintResult(path=str(fp_named), display_path=fp_named.name)
            check_orphan(result, fp_named, memory_index)
            codes = [i.code for i in result.issues]
            assert "ORPHAN" not in codes
        finally:
            fp_named.unlink(missing_ok=True)

    def test_memory_md_itself_not_flagged(self):
        memory_index: set[str] = set()
        fp = write_temp_file("# MEMORY.md\n")
        fp_named = fp.parent / "MEMORY.md"
        fp.rename(fp_named)
        try:
            result = FileLintResult(path=str(fp_named), display_path=fp_named.name)
            check_orphan(result, fp_named, memory_index)
            codes = [i.code for i in result.issues]
            assert "ORPHAN" not in codes
        finally:
            fp_named.unlink(missing_ok=True)

    def test_broken_link_detection(self):
        mem_md = self._make_memory_md(["existing.md", "nonexistent_xyz_abc.md"])
        mem_dir = mem_md.parent
        # Create existing.md
        existing = mem_dir / "existing.md"
        existing.write_text("# Existing\n")
        try:
            broken = find_broken_memory_links(mem_md, mem_dir)
            assert "nonexistent_xyz_abc.md" in broken
            assert "existing.md" not in broken
        finally:
            mem_md.unlink(missing_ok=True)
            existing.unlink(missing_ok=True)

    def test_no_broken_links_when_all_exist(self):
        mem_dir = Path(tempfile.mkdtemp())
        mem_md = mem_dir / "MEMORY.md"
        mem_md.write_text("# MEMORY.md\n- [label](child.md)\n")
        child = mem_dir / "child.md"
        child.write_text("# Child\n")
        try:
            broken = find_broken_memory_links(mem_md, mem_dir)
            assert len(broken) == 0
        finally:
            mem_md.unlink(missing_ok=True)
            child.unlink(missing_ok=True)
            mem_dir.rmdir()


# ---------------------------------------------------------------------------
# Size Alert tests
# ---------------------------------------------------------------------------


class TestSizeAlert:
    def _file_with_lines(self, n: int) -> Path:
        content = "\n".join([f"line {i}" for i in range(n)]) + "\n"
        return write_temp_file(content)

    def test_no_bloat_under_threshold(self):
        fp = self._file_with_lines(100)
        try:
            result = FileLintResult(path=str(fp), display_path=fp.name)
            check_size(result, fp, is_decisions=False)
            codes = [i.code for i in result.issues]
            assert "BLOATED" not in codes
        finally:
            fp.unlink(missing_ok=True)

    def test_bloat_general_at_200_lines(self):
        fp = self._file_with_lines(BLOAT_LINES_GENERAL + 1)
        try:
            result = FileLintResult(path=str(fp), display_path=fp.name)
            check_size(result, fp, is_decisions=False)
            codes = [i.code for i in result.issues]
            assert "BLOATED" in codes
        finally:
            fp.unlink(missing_ok=True)

    def test_bloat_decisions_threshold_higher(self):
        # 300 lines: OK for decisions but BLOATED for general
        n = 300
        fp = self._file_with_lines(n)
        try:
            result_gen = FileLintResult(path=str(fp), display_path=fp.name)
            check_size(result_gen, fp, is_decisions=False)
            assert any(i.code == "BLOATED" for i in result_gen.issues)

            result_dec = FileLintResult(path=str(fp), display_path=fp.name)
            check_size(result_dec, fp, is_decisions=True)
            assert not any(i.code == "BLOATED" for i in result_dec.issues)
        finally:
            fp.unlink(missing_ok=True)

    def test_bloat_decisions_triggered_at_500(self):
        fp = self._file_with_lines(BLOAT_LINES_DECISIONS + 1)
        try:
            result = FileLintResult(path=str(fp), display_path=fp.name)
            check_size(result, fp, is_decisions=True)
            codes = [i.code for i in result.issues]
            assert "BLOATED" in codes
        finally:
            fp.unlink(missing_ok=True)

    def test_line_count_stored(self):
        fp = self._file_with_lines(42)
        try:
            result = FileLintResult(path=str(fp), display_path=fp.name)
            check_size(result, fp)
            assert result.line_count == 42
        finally:
            fp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Contradiction Detection tests
# ---------------------------------------------------------------------------


class TestContradictionDetection:
    def test_no_contradiction_single_file(self):
        fp = write_temp_file("DPI 300\nDPI = 300\n")
        try:
            topic_hits = build_topic_index([fp])
            contradictions = find_contradictions(topic_hits)
            assert len(contradictions) == 0
        finally:
            fp.unlink(missing_ok=True)

    def test_contradiction_across_two_files(self):
        fp1 = write_temp_file("DPI 144\n")
        fp2 = write_temp_file("DPI 300\n")
        try:
            topic_hits = build_topic_index([fp1, fp2])
            contradictions = find_contradictions(topic_hits)
            dpi_hits = [c for c in contradictions if c.topic == "DPI"]
            assert len(dpi_hits) >= 1
        finally:
            fp1.unlink(missing_ok=True)
            fp2.unlink(missing_ok=True)

    def test_same_content_no_contradiction(self):
        fp1 = write_temp_file("DPI 300\n")
        fp2 = write_temp_file("DPI 300\n")
        try:
            topic_hits = build_topic_index([fp1, fp2])
            contradictions = find_contradictions(topic_hits)
            dpi_hits = [c for c in contradictions if c.topic == "DPI"]
            assert len(dpi_hits) == 0
        finally:
            fp1.unlink(missing_ok=True)
            fp2.unlink(missing_ok=True)

    def test_no_contradiction_topic_absent(self):
        fp1 = write_temp_file("# No DPI here\n")
        fp2 = write_temp_file("# Also no DPI\n")
        try:
            topic_hits = build_topic_index([fp1, fp2])
            contradictions = find_contradictions(topic_hits)
            dpi_hits = [c for c in contradictions if c.topic == "DPI"]
            assert len(dpi_hits) == 0
        finally:
            fp1.unlink(missing_ok=True)
            fp2.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Report rendering smoke tests
# ---------------------------------------------------------------------------


class TestReportRendering:
    def _sample_data(self) -> tuple:
        r1 = FileLintResult(path="/tmp/a.md", display_path="a.md")
        r1.trust_score = 90
        r1.age_days = 10
        r2 = FileLintResult(path="/tmp/b.md", display_path="b.md")
        r2.trust_score = 60
        r2.age_days = 75
        r2.issues = [Issue("AGE_WARNING", "75d", 10)]
        r3 = FileLintResult(path="/tmp/c.md", display_path="c.md")
        r3.trust_score = 40
        r3.age_days = 120
        r3.issues = [Issue("STALE", "120d", 30), Issue("ORPHAN", "missing", 20)]
        return [r1, r2, r3], [], []

    def test_text_report_contains_sections(self):
        results, contradictions, broken = self._sample_data()
        report = render_text_report(results, contradictions, broken)
        assert "Wiki Lint Report" in report
        assert "Critical Issues" in report
        assert "Warnings" in report
        assert "Healthy" in report
        assert "Summary" in report

    def test_text_report_critical_only(self):
        results, contradictions, broken = self._sample_data()
        report = render_text_report(results, contradictions, broken, critical_only=True)
        assert "Critical Issues" in report
        assert "Warnings" not in report

    def test_json_report_structure(self):
        import json
        results, contradictions, broken = self._sample_data()
        raw = render_json_report(results, contradictions, broken)
        data = json.loads(raw)
        assert "files" in data
        assert "summary" in data
        assert "contradictions" in data
        assert "broken_links" in data
        assert data["summary"]["total"] == 3

    def test_json_summary_counts(self):
        import json
        results, contradictions, broken = self._sample_data()
        raw = render_json_report(results, contradictions, broken)
        data = json.loads(raw)
        s = data["summary"]
        assert s["healthy"] == 1
        assert s["warning"] == 1
        assert s["critical"] == 1


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import traceback

    test_classes = [
        TestTrustScore,
        TestStaleness,
        TestOrphanDetection,
        TestSizeAlert,
        TestContradictionDetection,
        TestReportRendering,
    ]

    passed = 0
    failed = 0

    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        for method in methods:
            try:
                getattr(instance, method)()
                print(f"  PASS  {cls.__name__}.{method}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {cls.__name__}.{method}: {e}")
                traceback.print_exc()
                failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
