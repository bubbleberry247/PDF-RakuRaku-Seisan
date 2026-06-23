"""Generate an RKS-runtime-aware overlay for the goal status snapshot.

This does not edit the original status snapshot inputs. It reads the current
snapshot and the operator-confirmed RKS runtime intake validation, then writes
an overlay report that prevents stale RKS-missing labels from hiding newer
open/build/safe-stop evidence.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_STATUS_JSON = (
    ROOT / "plans" / "reports" / "goal_status_snapshot_20260620" / "goal_status_snapshot.json"
)
DEFAULT_RKS_RUNTIME_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "rks_runtime_operator_intake_validation_20260620"
    / "rks_runtime_operator_intake_validation.json"
)
DEFAULT_RKS_RUNTIME_REPORT = (
    ROOT
    / "plans"
    / "reports"
    / "rks_runtime_operator_intake_validation_20260620"
    / "rks_runtime_operator_intake_validation.md.numbered"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "goal_status_snapshot_rks_runtime_overlay_20260623"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def is_confirmed_runtime_row(row: dict[str, Any]) -> bool:
    return (
        row.get("approved") is True
        and row.get("rk10_editor_open") == "CONFIRMED"
        and row.get("rk10_build") == "CONFIRMED"
        and row.get("runtime_or_safe_stop") == "CONFIRMED"
        and row.get("latest_log_clean") == "YES"
        and row.get("latest_log_path_exists") is True
        and row.get("latest_log_has_hard_errors") is False
    )


def confirmed_runtime_rows(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = read_json(path)
    rows: dict[str, dict[str, Any]] = {}
    for row in payload.get("rows", []):
        if isinstance(row, dict) and is_confirmed_runtime_row(row):
            rows[str(row.get("scenario", ""))] = row
    return rows


def is_stale_rks_status(status: str) -> bool:
    upper_status = status.upper()
    return "RKS" in upper_status and (
        "UNCONFIRMED" in upper_status
        or "MISSING" in upper_status
        or "NOT_CONFIRMED" in upper_status
    )


def overlay_scenario(
    row: dict[str, Any],
    runtime_rows: dict[str, dict[str, Any]],
    runtime_report: Path,
) -> dict[str, Any]:
    scenario = str(row.get("scenario", ""))
    runtime_row = runtime_rows.get(scenario)
    if runtime_row is None or not is_stale_rks_status(str(row.get("current_status", ""))):
        return {**row, "overlay_applied": False, "overlay_reason": ""}
    return {
        **row,
        "current_scope": "RK10 editor open/build + safe-stop confirmed",
        "current_status": "RKS_SAFE_STOP_CONFIRMED_SCOPE_ONLY",
        "remaining_gate": "operator final evidence and business approval record",
        "next_action": (
            "最終証跡パケットへoperator_result/reviewer/reviewed_atを記入し、"
            "本番不可逆操作は別承認で実施する。"
        ),
        "source": str(runtime_report),
        "source_exists": runtime_report.exists(),
        "supplemental_evidence": str(row.get("source", "")),
        "supplemental_evidence_exists": bool(row.get("source_exists")),
        "overlay_applied": True,
        "overlay_reason": "confirmed_rks_open_build_safe_stop_latest_clean_log",
        "runtime_latest_log_path": str(runtime_row.get("latest_log_path", "")),
        "runtime_operator_name": str(runtime_row.get("operator_name", "")),
        "runtime_checked_at": str(runtime_row.get("checked_at", "")),
    }


def build_payload(
    status_json: Path = DEFAULT_STATUS_JSON,
    rks_runtime_json: Path = DEFAULT_RKS_RUNTIME_JSON,
    rks_runtime_report: Path = DEFAULT_RKS_RUNTIME_REPORT,
) -> dict[str, Any]:
    status_payload = read_json(status_json)
    runtime_rows = confirmed_runtime_rows(rks_runtime_json)
    scenarios = [
        overlay_scenario(row, runtime_rows, rks_runtime_report)
        for row in status_payload.get("scenarios", [])
        if isinstance(row, dict)
    ]
    blocked_or_hold = [
        item
        for item in scenarios
        if "HOLD" in str(item.get("current_status", ""))
        or "UNCONFIRMED" in str(item.get("current_status", ""))
        or "NOT_CONFIRMED" in str(item.get("current_status", ""))
        or "NG" in str(item.get("current_status", ""))
        or "MISSING" in str(item.get("current_status", ""))
    ]
    missing_sources = [item for item in scenarios if not item.get("source_exists")]
    overlay_rows = [item for item in scenarios if item.get("overlay_applied") is True]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": "read-only overlay only; no RK10 ButtonRun or production action",
        "source_status_json": str(status_json),
        "rks_runtime_json": str(rks_runtime_json),
        "rks_runtime_report": str(rks_runtime_report),
        "scenario_count": len(scenarios),
        "hold_or_unconfirmed_count_before_overlay": int(
            status_payload.get("hold_or_unconfirmed_count", 0) or 0
        ),
        "hold_or_unconfirmed_count_after_overlay": len(blocked_or_hold),
        "overlay_applied_count": len(overlay_rows),
        "overlay_scenarios": [str(item.get("scenario", "")) for item in overlay_rows],
        "missing_source_count": len(missing_sources),
        "scenarios": scenarios,
    }


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goal Status Snapshot RKS Runtime Overlay 2026-06-23",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- hold_or_unconfirmed_count_before_overlay: `{payload['hold_or_unconfirmed_count_before_overlay']}`",
        f"- hold_or_unconfirmed_count_after_overlay: `{payload['hold_or_unconfirmed_count_after_overlay']}`",
        f"- overlay_applied_count: `{payload['overlay_applied_count']}`",
        f"- overlay_scenarios: `{', '.join(payload['overlay_scenarios'])}`",
        "",
        "## Scenario Matrix",
        "",
        "| Scenario | Overlay | Current Status | Remaining Gate | Source Exists |",
        "|---|---:|---|---|---:|",
    ]
    for item in payload["scenarios"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("scenario", "")),
                    "YES" if item.get("overlay_applied") else "NO",
                    str(item.get("current_status", "")).replace("|", "/"),
                    str(item.get("remaining_gate", "")).replace("|", "/"),
                    "YES" if item.get("source_exists") else "NO",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Sources", ""])
    lines.append(f"- source_status_json: `{payload['source_status_json']}`")
    lines.append(f"- rks_runtime_json: `{payload['rks_runtime_json']}`")
    lines.append(f"- rks_runtime_report: `{payload['rks_runtime_report']}`")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "goal_status_snapshot_rks_runtime_overlay.json"
    md_path = out_dir / "goal_status_snapshot_rks_runtime_overlay.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an RKS runtime overlay for the status snapshot.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
