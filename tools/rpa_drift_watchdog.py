"""RPA Drift Watchdog: Detect SaaS UI changes before they break automation.

Two modes:
1. Baseline mode: Save current DOM structure as baseline
2. Check mode: Compare current DOM against baseline, flag changes

Focus areas:
- Table headers (column order/naming changes)
- Button labels (action elements)
- Form inputs (login/search fields)
- Navigation structure (menu items)

Storage: .rpa_baselines/{target_name}/
  ├── baseline.json          (structured DOM snapshot)
  ├── baseline_screenshot.png (visual reference, optional)
  └── history/
      ├── 20260406_check.json (diff results)
      └── ...

Usage:
    # Save baseline
    python tools/rpa_drift_watchdog.py baseline --target rakuraku --url "https://..."

    # Check against baseline (no browser needed if baseline exists)
    python tools/rpa_drift_watchdog.py check --target rakuraku

    # Compare two snapshots
    python tools/rpa_drift_watchdog.py diff --old baseline.json --new current.json

    # List registered targets
    python tools/rpa_drift_watchdog.py list
"""
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = PROJECT_ROOT / ".rpa_baselines"


# === Data Structures ===

@dataclass
class DOMSnapshot:
    """Structured page snapshot for drift detection."""
    target: str                 # "rakuraku", "recoru", etc.
    url: str
    timestamp: str
    title: str = ""

    # Key UI elements
    table_headers: list[list[str]] = field(default_factory=list)  # [[header1, header2, ...]]
    buttons: list[str] = field(default_factory=list)               # ["ログイン", "検索", ...]
    form_inputs: list[dict] = field(default_factory=list)          # [{name, type, label}]
    nav_items: list[str] = field(default_factory=list)             # ["ホーム", "経費申請", ...]

    # Raw element list (for detailed comparison)
    elements: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DOMSnapshot":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class DriftReport:
    """Report of detected UI changes."""
    target: str
    checked_at: str
    baseline_at: str

    # Changes by category
    header_changes: list[dict] = field(default_factory=list)   # [{table_idx, action, details}]
    button_changes: list[dict] = field(default_factory=list)   # [{action, old, new}]
    input_changes: list[dict] = field(default_factory=list)    # [{action, details}]
    nav_changes: list[dict] = field(default_factory=list)      # [{action, old, new}]

    # Impact assessment
    affected_scripts: list[str] = field(default_factory=list)  # ["rakuraku_scraper.py:L45"]
    severity: str = "info"  # "info", "warning", "critical"

    @property
    def has_changes(self) -> bool:
        return bool(
            self.header_changes or self.button_changes
            or self.input_changes or self.nav_changes
        )

    def summary(self) -> str:
        """One-line summary."""
        total = (
            len(self.header_changes) + len(self.button_changes)
            + len(self.input_changes) + len(self.nav_changes)
        )
        if total == 0:
            return f"[{self.target}] No drift detected"
        return f"[{self.target}] {total} changes detected (severity: {self.severity})"


# === Core Engine ===

class DriftWatchdog:
    """RPA Drift detection engine."""

    # Known targets with their expected selectors and affected scripts
    KNOWN_TARGETS: dict[str, dict] = {
        "rakuraku": {
            "description": "楽楽精算（経費精算SaaS）",
            "expected_headers": ["No.", "申請者", "件名", "状態", "金額"],
            "affected_scripts": [
                "tools/scenario55/rakuraku_scraper.py",
            ],
            "login_url": "https://app.rakurakuseisan.jp/",
        },
        "recoru": {
            "description": "レコル（勤怠管理SaaS）",
            "expected_headers": [],
            "affected_scripts": [],
            "login_url": "https://app.recoru.in/",
        },
    }

    def __init__(self, baseline_dir: str | Path = BASELINE_DIR) -> None:
        self.baseline_dir = Path(baseline_dir)

    # -- Target Registry --

    def save_baseline(self, snapshot: DOMSnapshot) -> str:
        """Save snapshot as baseline for a target."""
        target_dir = self.baseline_dir / snapshot.target
        target_dir.mkdir(parents=True, exist_ok=True)

        path = target_dir / "baseline.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)
        return str(path)

    def load_baseline(self, target: str) -> DOMSnapshot | None:
        """Load saved baseline for a target."""
        path = self.baseline_dir / target / "baseline.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return DOMSnapshot.from_dict(json.load(f))

    def compare(self, baseline: DOMSnapshot, current: DOMSnapshot) -> DriftReport:
        """Compare two snapshots and generate drift report."""
        report = DriftReport(
            target=baseline.target,
            checked_at=current.timestamp,
            baseline_at=baseline.timestamp,
        )

        # 1. Table headers comparison
        self._compare_headers(baseline.table_headers, current.table_headers, report)

        # 2. Buttons comparison
        self._compare_lists(baseline.buttons, current.buttons, "button", report.button_changes)

        # 3. Form inputs comparison
        self._compare_inputs(baseline.form_inputs, current.form_inputs, report)

        # 4. Navigation comparison
        self._compare_lists(baseline.nav_items, current.nav_items, "nav", report.nav_changes)

        # 5. Determine severity
        report.severity = self._assess_severity(report)

        # 6. Map affected scripts
        target_info = self.KNOWN_TARGETS.get(baseline.target, {})
        if report.has_changes:
            report.affected_scripts = target_info.get("affected_scripts", [])

        return report

    def _compare_headers(
        self,
        old_headers: list[list[str]],
        new_headers: list[list[str]],
        report: DriftReport,
    ) -> None:
        """Compare table headers between snapshots."""
        max_tables = max(len(old_headers), len(new_headers), 1)
        for i in range(max_tables):
            old = old_headers[i] if i < len(old_headers) else []
            new = new_headers[i] if i < len(new_headers) else []

            if old == new:
                continue

            if len(old) != len(new):
                report.header_changes.append({
                    "table_idx": i,
                    "action": "column_count_changed",
                    "old_count": len(old),
                    "new_count": len(new),
                    "old": old,
                    "new": new,
                })
            else:
                for j, (o, n) in enumerate(zip(old, new)):
                    if o != n:
                        report.header_changes.append({
                            "table_idx": i,
                            "column_idx": j,
                            "action": "header_renamed",
                            "old": o,
                            "new": n,
                        })

    def _compare_lists(
        self,
        old_items: list[str],
        new_items: list[str],
        item_type: str,
        changes_list: list[dict],
    ) -> None:
        """Compare two lists of strings, report additions/removals."""
        old_set = set(old_items)
        new_set = set(new_items)

        for item in sorted(old_set - new_set):
            changes_list.append({"action": "removed", "value": item, "type": item_type})
        for item in sorted(new_set - old_set):
            changes_list.append({"action": "added", "value": item, "type": item_type})

    def _compare_inputs(
        self,
        old_inputs: list[dict],
        new_inputs: list[dict],
        report: DriftReport,
    ) -> None:
        """Compare form inputs."""
        old_by_name = {inp.get("name", ""): inp for inp in old_inputs}
        new_by_name = {inp.get("name", ""): inp for inp in new_inputs}

        for name in sorted(set(old_by_name) - set(new_by_name)):
            report.input_changes.append({"action": "removed", "name": name, "details": old_by_name[name]})
        for name in sorted(set(new_by_name) - set(old_by_name)):
            report.input_changes.append({"action": "added", "name": name, "details": new_by_name[name]})
        for name in sorted(set(old_by_name) & set(new_by_name)):
            if old_by_name[name] != new_by_name[name]:
                report.input_changes.append({
                    "action": "modified",
                    "name": name,
                    "old": old_by_name[name],
                    "new": new_by_name[name],
                })

    def _assess_severity(self, report: DriftReport) -> str:
        """Determine severity based on change types."""
        if report.header_changes:
            return "critical"   # Table structure changes break scrapers
        if report.input_changes:
            return "warning"    # Form changes may break login/search
        if report.button_changes or report.nav_changes:
            return "info"       # Label changes are usually cosmetic
        return "info"

    def save_check_result(self, report: DriftReport) -> str:
        """Save check result to history."""
        target_dir = self.baseline_dir / report.target / "history"
        target_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = target_dir / f"{ts}_check.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, ensure_ascii=False, indent=2)
        return str(path)

    def list_targets(self) -> list[dict]:
        """List all registered targets with baseline info."""
        targets = []
        for name, info in self.KNOWN_TARGETS.items():
            baseline = self.load_baseline(name)
            targets.append({
                "name": name,
                "description": info["description"],
                "has_baseline": baseline is not None,
                "baseline_date": baseline.timestamp if baseline else None,
                "affected_scripts": info.get("affected_scripts", []),
            })
        return targets


# === Playwright Integration (optional) ===

def capture_snapshot_playwright(url: str, target: str) -> DOMSnapshot:
    """Capture DOM snapshot using Playwright (requires playwright installed).

    Uses msedge as browser (Chrome 146 EULA issue workaround).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && playwright install msedge"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)

        title = page.title()

        # Extract table headers (works through iframes too)
        table_headers: list[list[str]] = []
        for frame in page.frames:
            tables = frame.query_selector_all("table")
            for table in tables:
                ths = table.query_selector_all("th")
                headers = [th.inner_text().strip() for th in ths if th.inner_text().strip()]
                if headers:
                    table_headers.append(headers)

        # Extract buttons
        buttons: list[str] = []
        for frame in page.frames:
            btns = frame.query_selector_all(
                "button, input[type='submit'], a.btn, [role='button']"
            )
            for b in btns:
                text = b.inner_text().strip()
                if text:
                    buttons.append(text)

        # Extract form inputs
        form_inputs: list[dict] = []
        for frame in page.frames:
            inputs = frame.query_selector_all("input, select, textarea")
            for inp in inputs:
                form_inputs.append({
                    "name": inp.get_attribute("name") or "",
                    "type": inp.get_attribute("type") or "text",
                    "label": (
                        inp.get_attribute("aria-label")
                        or inp.get_attribute("placeholder")
                        or ""
                    ),
                })

        # Extract navigation items
        nav_items: list[str] = []
        for frame in page.frames:
            nav_els = frame.query_selector_all(
                "nav a, [role='navigation'] a, .nav-item, .menu-item"
            )
            for n in nav_els:
                text = n.inner_text().strip()
                if text:
                    nav_items.append(text)

        browser.close()

        return DOMSnapshot(
            target=target,
            url=url,
            timestamp=datetime.now().isoformat(),
            title=title,
            table_headers=table_headers,
            buttons=buttons,
            form_inputs=form_inputs,
            nav_items=nav_items,
        )


# === Manual Snapshot (no browser required) ===

def create_manual_snapshot(
    target: str,
    url: str,
    table_headers: list[list[str]] | None = None,
    buttons: list[str] | None = None,
    form_inputs: list[dict] | None = None,
    nav_items: list[str] | None = None,
) -> DOMSnapshot:
    """Create snapshot manually (for targets that can't be auto-captured)."""
    return DOMSnapshot(
        target=target,
        url=url,
        timestamp=datetime.now().isoformat(),
        table_headers=table_headers or [],
        buttons=buttons or [],
        form_inputs=form_inputs or [],
        nav_items=nav_items or [],
    )


# === CLI ===

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="RPA Drift Watchdog")
    sub = parser.add_subparsers(dest="command")

    # baseline
    bp = sub.add_parser("baseline", help="Save current state as baseline")
    bp.add_argument("--target", required=True, help="Target name (e.g. rakuraku)")
    bp.add_argument("--url", help="URL to capture (requires Playwright + msedge)")
    bp.add_argument(
        "--manual-headers", nargs="+",
        help="Manual table headers (space-separated, for single-table snapshot)",
    )

    # check
    cp = sub.add_parser("check", help="Check current state against baseline")
    cp.add_argument("--target", required=True)
    cp.add_argument("--url", required=True, help="URL to capture and compare")

    # diff
    dp = sub.add_parser("diff", help="Compare two snapshot JSON files")
    dp.add_argument("--old", required=True, help="Path to old snapshot JSON")
    dp.add_argument("--new", required=True, help="Path to new snapshot JSON")

    # list
    sub.add_parser("list", help="List registered targets and baseline status")

    args = parser.parse_args()
    watchdog = DriftWatchdog()

    if args.command == "list":
        for t in watchdog.list_targets():
            status = "baseline OK" if t["has_baseline"] else "no baseline"
            date_str = f"  ({t['baseline_date'][:10]})" if t["baseline_date"] else ""
            print(f"  {t['name']}: {t['description']} [{status}]{date_str}")

    elif args.command == "baseline":
        if args.url:
            snapshot = capture_snapshot_playwright(args.url, args.target)
        elif args.manual_headers:
            snapshot = create_manual_snapshot(
                args.target, "", table_headers=[args.manual_headers]
            )
        else:
            print("ERROR: --url or --manual-headers required for baseline command")
            sys.exit(1)
        path = watchdog.save_baseline(snapshot)
        print(f"Baseline saved: {path}")
        print(f"  Tables: {len(snapshot.table_headers)}, Buttons: {len(snapshot.buttons)}")

    elif args.command == "check":
        baseline = watchdog.load_baseline(args.target)
        if not baseline:
            print(f"ERROR: No baseline for '{args.target}'. Run 'baseline' command first.")
            sys.exit(1)
        current = capture_snapshot_playwright(args.url, args.target)
        report = watchdog.compare(baseline, current)
        result_path = watchdog.save_check_result(report)
        print(report.summary())
        if report.has_changes:
            if report.header_changes:
                print(f"  Header changes: {len(report.header_changes)}")
            if report.button_changes:
                print(f"  Button changes: {len(report.button_changes)}")
            if report.input_changes:
                print(f"  Input changes: {len(report.input_changes)}")
            if report.nav_changes:
                print(f"  Nav changes: {len(report.nav_changes)}")
            if report.affected_scripts:
                print(f"  Affected: {', '.join(report.affected_scripts)}")
        print(f"  Result saved: {result_path}")

    elif args.command == "diff":
        with open(args.old, "r", encoding="utf-8") as f:
            old_snap = DOMSnapshot.from_dict(json.load(f))
        with open(args.new, "r", encoding="utf-8") as f:
            new_snap = DOMSnapshot.from_dict(json.load(f))
        report = watchdog.compare(old_snap, new_snap)
        print(report.summary())
        if report.has_changes:
            print(json.dumps(asdict(report), ensure_ascii=False, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
