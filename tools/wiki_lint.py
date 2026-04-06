"""
wiki_lint.py — Knowledge base lint + trust score checker.

Scans memory/*.md, plans/decisions/projects/*.md, .claude/skills/*/SKILL.md, AGENTS.md
for staleness, orphan pages, broken source references, potential contradictions, and bloat.

Usage:
    python tools/wiki_lint.py                  # Full report
    python tools/wiki_lint.py --json           # JSON output
    python tools/wiki_lint.py --critical-only  # Only trust < 50
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
MEMORY_DIR = Path("C:/Users/owner/.claude/projects/c--ProgramData-Generative-AI-Github-PDF-RakuRaku-Seisan/memory")
DECISIONS_DIR = REPO_ROOT / "plans" / "decisions" / "projects"
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
AGENTS_MD = REPO_ROOT / "AGENTS.md"

STALE_DAYS = 90
WARNING_DAYS = 60
BLOAT_LINES_DECISIONS = 500
BLOAT_LINES_GENERAL = 200

# Topics to watch for potential contradictions (keyword: [synonym_patterns])
CONTRADICTION_TOPICS: dict[str, list[str]] = {
    "DPI": [r"\bDPI\s+\d+", r"\bdpi\s*=\s*\d+", r"dpi=\d+"],
    "OCR engine": [r"\byomitoku\b", r"\beasyocr\b", r"\bpaddleocr\b", r"\bgpt-4o\b", r"\bgpt-5\.4\b"],
    "font": [r"\bMeiryo\b", r"\bSegoe UI\b", r"\bメイリオ\b"],
    "deploy": [r"clasp deploy\s+-i", r"clasp deploy(?!\s+-i)"],
    "mail address": [r"kanri\.tic@tokai-ic\.co\.jp", r"karimistk@gmail\.com"],
    "company code": [r"company.?code\s+300", r"--company-code\s+300"],
    "bank holiday": [r"12/31", r"12/30", r"末日"],
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    code: str        # e.g. "STALE", "ORPHAN", "BROKEN_LINK", ...
    message: str
    penalty: int


@dataclass
class ContradictionHit:
    topic: str
    file_a: str
    line_a: int
    snippet_a: str
    file_b: str
    line_b: int
    snippet_b: str


@dataclass
class FileLintResult:
    path: str            # Absolute path as string
    display_path: str    # Short path for display
    issues: list[Issue] = field(default_factory=list)
    line_count: int = 0
    age_days: Optional[int] = None
    trust_score: int = 100

    def compute_trust(self) -> None:
        penalty = sum(i.penalty for i in self.issues)
        self.trust_score = max(0, 100 - penalty)

    @property
    def severity(self) -> str:
        if self.trust_score >= 80:
            return "HEALTHY"
        elif self.trust_score >= 50:
            return "WARNING"
        else:
            return "CRITICAL"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_file_age_days(file_path: Path) -> Optional[int]:
    """Return age in days via git log, fallback to mtime."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ci", "--", str(file_path)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=10,
        )
        raw = result.stdout.strip()
        if raw:
            # Format: "2026-02-11 17:56:58 +0900"
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(tz=timezone.utc)
            return (now - dt).days
    except Exception:
        pass

    # Fallback: filesystem mtime
    try:
        mtime = file_path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        return (now - dt).days
    except Exception:
        return None


def count_lines(file_path: Path) -> int:
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def read_lines(file_path: Path) -> list[str]:
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            return f.readlines()
    except Exception:
        return []


def extract_file_references(lines: list[str]) -> list[str]:
    """Extract file path-like patterns from text."""
    refs: list[str] = []
    # Match patterns like C:\...\file.py, /path/to/file, relative/path.md
    pattern = re.compile(
        r"[`\"]?"
        r"([A-Za-z]:[\\\/][^\s`\"'\]]+\.\w{2,6}"     # Windows absolute
        r"|[\/][^\s`\"'\]]+\.\w{2,6}"                  # Unix absolute
        r"|[A-Za-z0-9_\-\.\/\\]+\.[a-z]{2,6})"         # Relative
        r"[`\"]?",
        re.MULTILINE,
    )
    for line in lines:
        for m in pattern.finditer(line):
            ref = m.group(1).strip("`\"'")
            # Filter noise
            if len(ref) > 4 and not ref.startswith("http"):
                refs.append(ref)
    return refs


def path_exists(ref: str, base_dir: Path) -> bool:
    """Check if a referenced path exists (absolute or relative to repo root)."""
    p = Path(ref)
    if p.is_absolute():
        return p.exists()
    # Try relative to repo root
    if (REPO_ROOT / p).exists():
        return True
    # Try relative to base_dir
    if (base_dir / p).exists():
        return True
    return False


def short_path(p: Path) -> str:
    """Return a short display path relative to REPO_ROOT when possible."""
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        try:
            return str(p.relative_to(MEMORY_DIR.parent.parent.parent))
        except ValueError:
            return str(p)


# ---------------------------------------------------------------------------
# Check 1: Staleness
# ---------------------------------------------------------------------------


def check_staleness(result: FileLintResult, file_path: Path) -> None:
    age = get_file_age_days(file_path)
    result.age_days = age
    if age is None:
        return
    if age >= STALE_DAYS:
        result.issues.append(Issue(
            code="STALE",
            message=f"Last updated {age} days ago (threshold: {STALE_DAYS}d)",
            penalty=30,
        ))
    elif age >= WARNING_DAYS:
        result.issues.append(Issue(
            code="AGE_WARNING",
            message=f"Last updated {age} days ago (approaching stale at {STALE_DAYS}d)",
            penalty=10,
        ))


# ---------------------------------------------------------------------------
# Check 2: Orphan Detection
# ---------------------------------------------------------------------------


def load_memory_index(memory_md: Path) -> set[str]:
    """Parse MEMORY.md and return set of referenced filenames (stem only)."""
    referenced: set[str] = set()
    if not memory_md.exists():
        return referenced
    lines = read_lines(memory_md)
    # Match markdown links like [label](filename.md)
    link_pattern = re.compile(r"\[.*?\]\(([^)]+\.md)\)")
    for line in lines:
        for m in link_pattern.finditer(line):
            fname = Path(m.group(1)).name
            referenced.add(fname)
    return referenced


def check_orphan(result: FileLintResult, file_path: Path, memory_index: set[str]) -> None:
    """Flag memory/*.md files not listed in MEMORY.md."""
    if file_path.name == "MEMORY.md":
        return
    if file_path.name not in memory_index:
        result.issues.append(Issue(
            code="ORPHAN",
            message=f"Not referenced in MEMORY.md",
            penalty=20,
        ))


def find_broken_memory_links(memory_md: Path, memory_dir: Path) -> list[str]:
    """Return list of filenames referenced in MEMORY.md but missing on disk."""
    broken: list[str] = []
    if not memory_md.exists():
        return broken
    lines = read_lines(memory_md)
    link_pattern = re.compile(r"\[.*?\]\(([^)]+\.md)\)")
    for line in lines:
        for m in link_pattern.finditer(line):
            fname = m.group(1)
            target = memory_dir / fname
            if not target.exists():
                broken.append(fname)
    return broken


# ---------------------------------------------------------------------------
# Check 3: Source Verification
# ---------------------------------------------------------------------------


def check_source_references(result: FileLintResult, file_path: Path) -> None:
    """Check that file paths referenced in the document actually exist."""
    lines = read_lines(file_path)
    refs = extract_file_references(lines)
    checked: set[str] = set()
    for ref in refs:
        if ref in checked:
            continue
        checked.add(ref)
        # Skip very short or obviously non-path strings
        if len(ref) < 5 or ref.count(".") == 0:
            continue
        # Skip URLs and common false positives
        if any(ref.startswith(p) for p in ("http", "www.", "*.py", "*.md", "*.xlsx", "*.csv")):
            continue
        if not path_exists(ref, file_path.parent):
            result.issues.append(Issue(
                code="SOURCE_MISSING",
                message=f"Referenced path not found: {ref}",
                penalty=25,
            ))


# ---------------------------------------------------------------------------
# Check 4: Size Alert
# ---------------------------------------------------------------------------


def check_size(result: FileLintResult, file_path: Path, is_decisions: bool = False) -> None:
    n = count_lines(file_path)
    result.line_count = n
    threshold = BLOAT_LINES_DECISIONS if is_decisions else BLOAT_LINES_GENERAL
    if n >= threshold:
        result.issues.append(Issue(
            code="BLOATED",
            message=f"{n} lines (threshold: {threshold})",
            penalty=10,
        ))


# ---------------------------------------------------------------------------
# Check 5: Contradiction Detection
# ---------------------------------------------------------------------------


def build_topic_index(all_files: list[Path]) -> dict[str, list[tuple[str, int, str]]]:
    """
    For each contradiction topic, find all (file, line_num, snippet) matches.
    Returns: {topic: [(display_path, line_num, snippet), ...]}
    """
    topic_hits: dict[str, list[tuple[str, int, str]]] = {t: [] for t in CONTRADICTION_TOPICS}

    for file_path in all_files:
        lines = read_lines(file_path)
        display = short_path(file_path)
        for topic, patterns in CONTRADICTION_TOPICS.items():
            for lno, line in enumerate(lines, start=1):
                for pat in patterns:
                    m = re.search(pat, line, re.IGNORECASE)
                    if m:
                        snippet = line.strip()[:80]
                        topic_hits[topic].append((display, lno, snippet))
                        break  # one match per line per topic

    return topic_hits


def find_contradictions(topic_hits: dict[str, list[tuple[str, int, str]]]) -> list[ContradictionHit]:
    """
    Flag topics where the same keyword appears in multiple files with potentially different values.
    We pair up every pair of files that have different snippets.
    """
    hits: list[ContradictionHit] = []
    for topic, occurrences in topic_hits.items():
        if len(occurrences) < 2:
            continue
        # Group by file
        by_file: dict[str, list[tuple[int, str]]] = {}
        for display, lno, snippet in occurrences:
            by_file.setdefault(display, []).append((lno, snippet))
        files = list(by_file.keys())
        if len(files) < 2:
            continue
        # Emit one pair per distinct file pair (avoid combinatorial explosion)
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                fa = files[i]
                fb = files[j]
                la, sa = by_file[fa][0]
                lb, sb = by_file[fb][0]
                # Only flag if snippets differ (crude check)
                if sa != sb:
                    hits.append(ContradictionHit(
                        topic=topic,
                        file_a=fa, line_a=la, snippet_a=sa,
                        file_b=fb, line_b=lb, snippet_b=sb,
                    ))
    return hits


# ---------------------------------------------------------------------------
# Collect all files to scan
# ---------------------------------------------------------------------------


def collect_files() -> dict[str, list[Path]]:
    """Return categorised file lists."""
    groups: dict[str, list[Path]] = {
        "memory": [],
        "decisions": [],
        "skills": [],
        "agents": [],
    }

    # memory/*.md
    if MEMORY_DIR.exists():
        groups["memory"] = sorted(MEMORY_DIR.glob("*.md"))

    # plans/decisions/projects/*.md
    if DECISIONS_DIR.exists():
        groups["decisions"] = sorted(DECISIONS_DIR.glob("*.md"))

    # .claude/skills/*/SKILL.md
    if SKILLS_DIR.exists():
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                groups["skills"].append(skill_md)

    # AGENTS.md
    if AGENTS_MD.exists():
        groups["agents"] = [AGENTS_MD]

    return groups


# ---------------------------------------------------------------------------
# Main lint runner
# ---------------------------------------------------------------------------


def lint_all(verbose_source_check: bool = False) -> tuple[list[FileLintResult], list[ContradictionHit], list[str]]:
    groups = collect_files()
    all_files: list[Path] = []
    for files in groups.values():
        all_files.extend(files)

    memory_md = MEMORY_DIR / "MEMORY.md"
    memory_index = load_memory_index(memory_md)
    broken_links = find_broken_memory_links(memory_md, MEMORY_DIR)

    results: list[FileLintResult] = []

    for category, files in groups.items():
        for fp in files:
            result = FileLintResult(
                path=str(fp),
                display_path=short_path(fp),
            )

            # Staleness
            check_staleness(result, fp)

            # Size
            is_decisions = category == "decisions"
            check_size(result, fp, is_decisions=is_decisions)

            # Orphan check (memory files only)
            if category == "memory":
                check_orphan(result, fp, memory_index)

            # Source verification (skip AGENTS.md for now — too many false positives)
            if category in ("decisions", "skills") and verbose_source_check:
                check_source_references(result, fp)

            result.compute_trust()
            results.append(result)

    # Contradiction detection across all files
    topic_hits = build_topic_index(all_files)
    contradictions = find_contradictions(topic_hits)

    # Apply contradiction penalty to results
    mentioned_files: dict[str, set[str]] = {}  # display_path -> set of topics
    for ch in contradictions:
        mentioned_files.setdefault(ch.file_a, set()).add(ch.topic)
        mentioned_files.setdefault(ch.file_b, set()).add(ch.topic)

    for result in results:
        topics = mentioned_files.get(result.display_path, set())
        for topic in topics:
            result.issues.append(Issue(
                code="CONTRADICTION_FLAG",
                message=f"Potential contradiction on topic '{topic}'",
                penalty=5,
            ))
        if topics:
            result.compute_trust()  # recompute after adding penalties

    return results, contradictions, broken_links


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def render_text_report(
    results: list[FileLintResult],
    contradictions: list[ContradictionHit],
    broken_links: list[str],
    critical_only: bool = False,
) -> str:
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    lines: list[str] = []

    lines.append("=== Wiki Lint Report ===")
    lines.append(f"Scanned: {now}")
    lines.append(f"Files checked: {len(results)}")
    lines.append("")

    critical = [r for r in results if r.severity == "CRITICAL"]
    warnings = [r for r in results if r.severity == "WARNING"]
    healthy = [r for r in results if r.severity == "HEALTHY"]

    # Critical
    lines.append("## Critical Issues (Trust < 50)")
    if critical:
        for r in sorted(critical, key=lambda x: x.trust_score):
            issue_tags = ", ".join(f"{i.code}: {i.message}" for i in r.issues)
            age_str = f", age={r.age_days}d" if r.age_days is not None else ""
            lines.append(f"- {r.display_path}: Trust={r.trust_score}{age_str} [{issue_tags}]")
    else:
        lines.append("  (none)")
    lines.append("")

    if not critical_only:
        # Warnings
        lines.append("## Warnings (Trust 50-79)")
        if warnings:
            for r in sorted(warnings, key=lambda x: x.trust_score):
                issue_tags = ", ".join(f"{i.code}: {i.message}" for i in r.issues)
                age_str = f", age={r.age_days}d" if r.age_days is not None else ""
                lines.append(f"- {r.display_path}: Trust={r.trust_score}{age_str} [{issue_tags}]")
        else:
            lines.append("  (none)")
        lines.append("")

        # Healthy
        lines.append("## Healthy (Trust >= 80)")
        for r in sorted(healthy, key=lambda x: -x.trust_score):
            age_str = f", age={r.age_days}d" if r.age_days is not None else ""
            lines.append(f"- {r.display_path}: Trust={r.trust_score}{age_str}")
        if not healthy:
            lines.append("  (none)")
        lines.append("")

    # Contradictions
    lines.append("## Potential Contradictions")
    if contradictions:
        for ch in contradictions:
            lines.append(f'- Topic "{ch.topic}":')
            lines.append(f'    {ch.file_a} (line {ch.line_a}): "{ch.snippet_a}"')
            lines.append(f'    {ch.file_b} (line {ch.line_b}): "{ch.snippet_b}"')
    else:
        lines.append("  (none detected)")
    lines.append("")

    # Orphan / broken links
    memory_files = [r for r in results if "memory" in r.display_path.replace("\\", "/").lower()]
    orphans = [r for r in memory_files if any(i.code == "ORPHAN" for i in r.issues)]
    lines.append("## Orphan Files")
    if orphans:
        for r in orphans:
            lines.append(f"- {r.display_path}: Not referenced in MEMORY.md")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("## Broken Links in MEMORY.md")
    if broken_links:
        for bl in broken_links:
            lines.append(f"- {bl}: Referenced but file does not exist")
    else:
        lines.append("  (none)")
    lines.append("")

    # Summary
    avg_trust = sum(r.trust_score for r in results) / len(results) if results else 0
    lines.append("## Summary")
    lines.append(f"Total files: {len(results)}, Healthy: {len(healthy)}, Warning: {len(warnings)}, Critical: {len(critical)}")
    lines.append(f"Average Trust Score: {avg_trust:.1f}")
    if broken_links:
        lines.append(f"Broken MEMORY.md links: {len(broken_links)}")

    return "\n".join(lines)


def render_json_report(
    results: list[FileLintResult],
    contradictions: list[ContradictionHit],
    broken_links: list[str],
) -> str:
    data = {
        "scanned_at": datetime.now().isoformat(),
        "files": [
            {
                "path": r.display_path,
                "trust_score": r.trust_score,
                "severity": r.severity,
                "age_days": r.age_days,
                "line_count": r.line_count,
                "issues": [{"code": i.code, "message": i.message, "penalty": i.penalty} for i in r.issues],
            }
            for r in sorted(results, key=lambda x: x.trust_score)
        ],
        "contradictions": [
            {
                "topic": c.topic,
                "file_a": c.file_a, "line_a": c.line_a, "snippet_a": c.snippet_a,
                "file_b": c.file_b, "line_b": c.line_b, "snippet_b": c.snippet_b,
            }
            for c in contradictions
        ],
        "broken_links": broken_links,
        "summary": {
            "total": len(results),
            "healthy": sum(1 for r in results if r.severity == "HEALTHY"),
            "warning": sum(1 for r in results if r.severity == "WARNING"),
            "critical": sum(1 for r in results if r.severity == "CRITICAL"),
            "avg_trust": round(sum(r.trust_score for r in results) / len(results), 1) if results else 0,
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    # Ensure UTF-8 output on Windows (avoids CP932 encode errors for Japanese text)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Wiki Lint -- knowledge base trust checker")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    parser.add_argument("--critical-only", action="store_true", help="Show only critical issues (trust < 50)")
    parser.add_argument("--source-check", action="store_true", help="Enable source reference existence checks (slow)")
    args = parser.parse_args()

    results, contradictions, broken_links = lint_all(verbose_source_check=args.source_check)

    if args.json:
        print(render_json_report(results, contradictions, broken_links))
    else:
        print(render_text_report(results, contradictions, broken_links, critical_only=args.critical_only))


if __name__ == "__main__":
    main()
