"""Session Briefing Generator (Open-Loop Resurfacer).

Generates a concise briefing at session start by scanning:
1. Recent Evidence Ledger entries (failures, partial runs)
2. Wiki Lint results (stale/critical knowledge)
3. Git status (uncommitted changes, recent commits)
4. Handoff.md (pending tasks)
5. Stale decision files in plans/

Output: Markdown-style briefing with prioritized action items.

Usage:
    python tools/session_briefing.py              # Full briefing
    python tools/session_briefing.py --compact    # One-screen summary
    python tools/session_briefing.py --json       # JSON output
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = PROJECT_ROOT / "evidence"
HANDOFF_PATH = PROJECT_ROOT / "plans" / "handoff.md"
DECISIONS_DIR = PROJECT_ROOT / "plans" / "decisions" / "projects"

# ---------------------------------------------------------------------------
# Evidence Ledger scan
# ---------------------------------------------------------------------------


def get_recent_failures(days: int = 7) -> list[dict[str, Any]]:
    """Scan Evidence Ledger for recent failures and partial runs.

    Returns list of dicts with keys:
        run_id, pipeline, scenario, status, error_summary, timestamp
    """
    results: list[dict[str, Any]] = []

    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from tools.common.evidence_ledger import EvidenceLedger  # type: ignore[import]

        ledger = EvidenceLedger(str(EVIDENCE_DIR))
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        for status in ("error", "partial"):
            records = ledger.query(status=status, date_from=date_from, limit=20)
            for rec in records:
                error_summary = ""
                if rec.errors:
                    first_err = rec.errors[0]
                    error_summary = first_err.get("message", "")[:120]
                results.append({
                    "run_id": rec.run_id,
                    "pipeline": rec.pipeline,
                    "scenario": rec.scenario or "-",
                    "status": rec.status,
                    "error_summary": error_summary,
                    "timestamp": rec.timestamp[:19],
                })
    except Exception:
        pass

    return results


def get_recent_runs_summary(days: int = 7) -> dict[str, Any]:
    """Return pipeline-level summary of recent runs."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from tools.common.evidence_ledger import EvidenceLedger  # type: ignore[import]

        ledger = EvidenceLedger(str(EVIDENCE_DIR))
        return ledger.summary(days=days)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Wiki health (wiki_lint)
# ---------------------------------------------------------------------------


def get_wiki_health() -> dict[str, Any]:
    """Run wiki_lint and extract critical/warning items.

    Returns:
        critical: list of {path, trust_score, issues}
        warnings: list of {path, trust_score, issues}
        avg_trust_score: float
        total_files: int
    """
    result: dict[str, Any] = {
        "critical": [],
        "warnings": [],
        "avg_trust_score": None,
        "total_files": 0,
    }

    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from tools.wiki_lint import lint_all  # type: ignore[import]

        lint_results, _contradictions, _broken_links = lint_all()
        if not lint_results:
            return result

        result["total_files"] = len(lint_results)
        scores = [r.trust_score for r in lint_results]
        result["avg_trust_score"] = round(sum(scores) / len(scores), 1)

        for r in sorted(lint_results, key=lambda x: x.trust_score):
            entry = {
                "path": r.display_path,
                "trust_score": r.trust_score,
                "age_days": r.age_days,
                "issues": [i.code for i in r.issues],
            }
            if r.severity == "CRITICAL":
                result["critical"].append(entry)
            elif r.severity == "WARNING":
                result["warnings"].append(entry)

    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Git status
# ---------------------------------------------------------------------------


def get_git_status() -> dict[str, Any]:
    """Get current git state.

    Returns:
        branch: str
        modified_files: list[str]
        untracked_files: list[str]
        recent_commits: list[str]
    """
    result: dict[str, Any] = {
        "branch": "unknown",
        "modified_files": [],
        "untracked_files": [],
        "recent_commits": [],
    }

    cwd = str(PROJECT_ROOT)

    # Branch name
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=cwd, timeout=10,
        )
        result["branch"] = r.stdout.strip() or "HEAD (detached)"
    except Exception:
        pass

    # Modified / untracked files (use bytes to avoid CP932 issues on Windows)
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, cwd=cwd, timeout=10,
        )
        raw_text = r.stdout.decode("utf-8", errors="replace")
        for line in raw_text.splitlines():
            if len(line) < 3:
                continue
            xy = line[:2]
            fname = line[3:].strip()
            if xy.startswith("??"):
                result["untracked_files"].append(fname)
            else:
                result["modified_files"].append(fname)
    except Exception:
        pass

    # Recent commits (last 5)
    try:
        r = subprocess.run(
            ["git", "log", "-5", "--oneline", "--format=%h %s (%cr)"],
            capture_output=True, cwd=cwd, timeout=10,
        )
        raw_text = r.stdout.decode("utf-8", errors="replace")
        result["recent_commits"] = [
            line.strip() for line in raw_text.splitlines() if line.strip()
        ]
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Handoff.md parser
# ---------------------------------------------------------------------------


def get_handoff_summary() -> dict[str, Any]:
    """Parse handoff.md for pending tasks.

    Returns:
        pending_high: list[str]
        pending_mid: list[str]
        last_updated: str
        found: bool
    """
    result: dict[str, Any] = {
        "pending_high": [],
        "pending_mid": [],
        "last_updated": "",
        "found": False,
    }

    if not HANDOFF_PATH.exists():
        return result

    result["found"] = True

    try:
        text = HANDOFF_PATH.read_text(encoding="utf-8", errors="replace")

        # Extract last_updated from first heading line "# Handoff — YYYY-MM-DD"
        m = re.search(r"#\s*Handoff\s*[—\-]+\s*(\d{4}-\d{2}-\d{2})", text)
        if m:
            result["last_updated"] = m.group(1)

        # Find "未完了・次回タスク" section
        section_match = re.search(
            r"##\s*未完了[・]?次回タスク(.*?)(?=^##\s|\Z)",
            text, re.DOTALL | re.MULTILINE,
        )
        if not section_match:
            return result

        section_text = section_match.group(1)

        # Parse 優先度高 and 優先度中 sub-sections
        high_match = re.search(
            r"###\s*優先度高(.*?)(?=^###\s|\Z)",
            section_text, re.DOTALL | re.MULTILINE,
        )
        mid_match = re.search(
            r"###\s*優先度中(.*?)(?=^###\s|\Z)",
            section_text, re.DOTALL | re.MULTILINE,
        )

        def _parse_items(block: str) -> list[str]:
            items: list[str] = []
            for line in block.splitlines():
                line = line.strip()
                # Match numbered list: "1. **title** — detail"
                m2 = re.match(r"^\d+\.\s+(?:\*\*(.+?)\*\*\s*[—\-]+\s*)?(.+)", line)
                if m2:
                    title = m2.group(1) or ""
                    detail = m2.group(2).strip()
                    if title:
                        items.append(f"{title} — {detail}")
                    else:
                        items.append(detail)
            return items

        if high_match:
            result["pending_high"] = _parse_items(high_match.group(1))
        if mid_match:
            result["pending_mid"] = _parse_items(mid_match.group(1))

    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Stale decisions
# ---------------------------------------------------------------------------


def get_stale_decisions(days_threshold: int = 90) -> list[dict[str, Any]]:
    """Find decision files not updated recently.

    Returns list of {file, last_modified_days_ago}
    """
    stale: list[dict[str, Any]] = []
    if not DECISIONS_DIR.exists():
        return stale

    for md_file in sorted(DECISIONS_DIR.glob("*.md")):
        try:
            r = subprocess.run(
                ["git", "log", "-1", "--format=%ci", "--", str(md_file)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=str(PROJECT_ROOT), timeout=10,
            )
            raw = r.stdout.strip()
            if not raw:
                # Fallback to mtime
                mtime = md_file.stat().st_mtime
                dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
            else:
                dt = datetime.fromisoformat(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)

            now = datetime.now(tz=timezone.utc)
            days_ago = (now - dt).days
            if days_ago >= days_threshold:
                stale.append({
                    "file": md_file.name,
                    "last_modified_days_ago": days_ago,
                })
        except Exception:
            pass

    return sorted(stale, key=lambda x: -x["last_modified_days_ago"])


# ---------------------------------------------------------------------------
# Briefing generator
# ---------------------------------------------------------------------------

_BORDER = "═" * 51


def generate_briefing(compact: bool = False) -> str:
    """Generate full or compact session briefing."""

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # --- Collect data ---
    failures = get_recent_failures(days=7)
    wiki = get_wiki_health()
    git = get_git_status()
    handoff = get_handoff_summary()
    stale_dec = get_stale_decisions(days_threshold=90)
    run_summary = get_recent_runs_summary(days=7)

    lines: list[str] = []

    lines.append(_BORDER)
    lines.append(f"SESSION BRIEFING — {now_str}")
    lines.append(_BORDER)
    lines.append("")

    # ■ URGENT
    urgent_items: list[str] = []

    for f in failures:
        msg = f"[{f['status'].upper()}] {f['run_id']}: {f['pipeline']}"
        if f["error_summary"]:
            msg += f" — {f['error_summary'][:80]}"
        urgent_items.append(msg)

    for c in wiki.get("critical", [])[:3]:
        age_str = f", {c['age_days']}d未更新" if c["age_days"] else ""
        urgent_items.append(f"[STALE] {c['path']}: Trust={c['trust_score']}{age_str}")

    lines.append("■ URGENT (要対応)")
    if urgent_items:
        for item in urgent_items:
            lines.append(f"  • {item}")
    else:
        lines.append("  (なし)")
    lines.append("")

    # ■ PENDING
    lines.append("■ PENDING (handoffより)")
    if handoff["found"]:
        last_upd = handoff["last_updated"] or "不明"
        lines.append(f"  [最終更新: {last_upd}]")
        if handoff["pending_high"]:
            lines.append("  優先度高:")
            for item in handoff["pending_high"]:
                lines.append(f"    • {item}")
        if not compact and handoff["pending_mid"]:
            lines.append("  優先度中:")
            for item in handoff["pending_mid"][:3]:
                lines.append(f"    • {item}")
    else:
        lines.append("  handoff.mdが見つかりません")
    lines.append("")

    # ■ KNOWLEDGE HEALTH
    lines.append("■ KNOWLEDGE HEALTH")
    if wiki["avg_trust_score"] is not None:
        n_crit = len(wiki.get("critical", []))
        n_warn = len(wiki.get("warnings", []))
        lines.append(
            f"  Wiki Trust: avg {wiki['avg_trust_score']} "
            f"({n_crit} critical, {n_warn} warning)"
        )
    else:
        lines.append("  Wiki Lint スキップ（wiki_lint未インストール）")

    if stale_dec and not compact:
        for sd in stale_dec[:3]:
            lines.append(f"  Stale decision: {sd['file']} ({sd['last_modified_days_ago']}日前)")
    lines.append("")

    # ■ GIT STATE
    lines.append("■ GIT STATE")
    lines.append(f"  Branch: {git['branch']}")
    n_mod = len(git["modified_files"])
    n_untr = len(git["untracked_files"])
    lines.append(f"  Modified: {n_mod} files, Untracked: {n_untr} files")
    if git["recent_commits"]:
        lines.append(f"  Last commit: {git['recent_commits'][0]}")
    lines.append("")

    # ■ RECENT RUNS
    if not compact:
        lines.append("■ RECENT RUNS (7日間)")
        if run_summary:
            by_pipeline = run_summary.get("by_pipeline", {})
            if by_pipeline:
                for pipeline, counts in sorted(by_pipeline.items()):
                    s = counts.get("success", 0)
                    e = counts.get("error", 0)
                    p = counts.get("partial", 0)
                    lines.append(
                        f"  • {pipeline}: {s+e+p} runs "
                        f"({s} success, {e} error, {p} partial)"
                    )
            else:
                lines.append("  (記録なし)")
        else:
            lines.append("  (Evidence Ledger スキップ)")
        lines.append("")

    lines.append(_BORDER)

    result = "\n".join(lines)

    # Compact: trim to 20 lines max
    if compact:
        compact_lines = result.splitlines()
        if len(compact_lines) > 20:
            compact_lines = compact_lines[:19] + ["  [... --compact で省略 ...]"]
        result = "\n".join(compact_lines)

    return result


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def generate_json() -> str:
    """Collect all data and return as JSON string."""
    data = {
        "generated_at": datetime.now().isoformat(),
        "recent_failures": get_recent_failures(days=7),
        "run_summary": get_recent_runs_summary(days=7),
        "wiki_health": get_wiki_health(),
        "git_status": get_git_status(),
        "handoff": get_handoff_summary(),
        "stale_decisions": get_stale_decisions(days_threshold=90),
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Session Briefing Generator (Open-Loop Resurfacer)"
    )
    parser.add_argument(
        "--compact", action="store_true", help="One-screen summary (max 20 lines)"
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.json:
        print(generate_json())
    else:
        print(generate_briefing(compact=args.compact))


if __name__ == "__main__":
    main()
