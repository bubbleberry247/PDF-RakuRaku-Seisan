"""Generate an operator fill queue for remaining final evidence gaps.

This tool reads existing validation reports and writes a repository-local
queue. It does not approve rows, copy evidence, open external applications,
submit, print, pay, run RK10, call Azure, or write production files.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_BUNDLE_VALIDATION_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_pack_validation_20260620"
    / "bundle_evidence_pack_validation.json"
)
DEFAULT_EXECUTION_VALIDATION_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "goal_execution_packet_validation_20260620"
    / "goal_execution_packet_validation.json"
)
DEFAULT_REMAINING_NEXT_STEPS_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "remaining_approval_next_steps_20260621"
    / "remaining_approval_next_steps.json"
)
DEFAULT_RK10_COLLECT_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "rk10_runtime_bundle_evidence_collect_20260620"
    / "rk10_runtime_bundle_evidence_collect.json"
)
DEFAULT_RKS_GATE_MATRIX_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "rks_gate_matrix_open_probe_20260622"
    / "rks_gate_matrix.json"
)
DEFAULT_BUNDLE_SYNC_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_intake_sync_20260620"
    / "bundle_evidence_intake_sync.json"
)
DEFAULT_UNIFIED_INPUT_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "unified_final_evidence_intake_20260621"
    / "unified_final_evidence_input.csv"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "final_evidence_fill_queue_20260621"
PATH_SEPARATOR = " / "
RK10_BUNDLE = "RK10_EDITOR_RUNTIME_BUNDLE"
FILL_ONLY_FIELDS = "operator_result, reviewer, reviewed_at"


@dataclass(frozen=True)
class FillQueueRow:
    rank: int | None
    bundle: str
    scenarios: str
    owner: str
    active: bool
    final_evidence_ready: bool
    action_status: str
    missing_operator_fields: str
    operator_attention_count: int
    final_evidence_gap: str
    final_evidence_item_count: int
    start_here_path: str
    unified_input_csv: str
    unified_entry_keys: str
    fill_only_fields: str
    supporting_input_paths: str
    suggested_final_evidence_path: str
    target_intake_path: str
    attention_target_csvs: str
    filename_examples: str
    forbidden: str
    next_action: str
    after_action_command: str
    supplemental_evidence_status: str
    remaining_runtime_evidence: str
    supplemental_evidence_source: str
    validation_source: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional_json(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {}
    return read_json(Path(path_text))


def parse_rank(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def split_paths(value: object) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.split(PATH_SEPARATOR) if part.strip()]


def split_csv_values(value: object) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def join_unique(values: list[str]) -> str:
    unique_values = []
    for value in values:
        text = value.strip()
        if text and text not in unique_values:
            unique_values.append(text)
    return PATH_SEPARATOR.join(unique_values)


def bundle_checks_by_bundle(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return {}
    return {
        str(check.get("bundle", "")).strip(): check
        for check in checks
        if isinstance(check, dict) and str(check.get("bundle", "")).strip()
    }


def remaining_rows_by_bundle(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("bundle", "")).strip(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("bundle", "")).strip()
    }


def is_unapproved(row: dict[str, Any]) -> bool:
    if bool(row.get("approved")):
        return False
    return str(row.get("status", "")).strip() not in {
        "APPROVED_WITH_EVIDENCE",
        "APPROVED_BY_BUNDLE_WITH_EVIDENCE",
    }


def attention_rows_by_bundle(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    rows_by_bundle: dict[str, list[dict[str, str]]] = {}
    bundle_sheet_path = str(payload.get("bundle_sheet_path", "")).strip()
    bundle_approvals = payload.get("bundle_approvals", [])
    if isinstance(bundle_approvals, list):
        for approval in bundle_approvals:
            if not isinstance(approval, dict) or not is_unapproved(approval):
                continue
            bundle = str(approval.get("bundle", "")).strip()
            if not bundle:
                continue
            rows_by_bundle.setdefault(bundle, []).append(
                {
                    "level": "bundle",
                    "scenario": "*",
                    "status": str(approval.get("status", "")).strip(),
                    "missing_fields": str(approval.get("missing_fields", "")).strip(),
                    "target_csv": bundle_sheet_path,
                }
            )
    scenario_rows = payload.get("rows", [])
    if isinstance(scenario_rows, list):
        for row in scenario_rows:
            if not isinstance(row, dict) or not is_unapproved(row):
                continue
            bundle = str(row.get("bundle", "")).strip()
            if not bundle:
                continue
            rows_by_bundle.setdefault(bundle, []).append(
                {
                    "level": "scenario",
                    "scenario": str(row.get("scenario", "")).strip(),
                    "status": str(row.get("status", "")).strip(),
                    "missing_fields": str(row.get("missing_fields", "")).strip(),
                    "target_csv": str(row.get("csv_path", "")).strip(),
                }
            )
    return rows_by_bundle


def missing_operator_summary(attention_rows: list[dict[str, str]]) -> str:
    parts = []
    for row in attention_rows:
        level = row.get("level", "")
        scenario = row.get("scenario", "")
        status = row.get("status", "")
        missing_fields = row.get("missing_fields", "")
        detail = missing_fields or status
        target = f"{level}:{scenario}" if scenario else level
        parts.append(f"{target}={detail}")
    return "; ".join(parts)


def bundle_sync_results_by_bundle(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = payload.get("results", [])
    if not isinstance(results, list):
        return {}
    return {
        str(result.get("bundle", "")).strip(): result
        for result in results
        if isinstance(result, dict) and str(result.get("bundle", "")).strip()
    }


def bundle_sync_attention_rows(sync_result: dict[str, Any]) -> list[dict[str, str]]:
    if not sync_result:
        return []
    target_csv = str(sync_result.get("intake_path", "")).strip()
    rows = []
    bundle_blockers = str(sync_result.get("blockers", "")).strip()
    if bundle_blockers and not bool(sync_result.get("ready_to_sync")):
        rows.append(
            {
                "level": "bundle",
                "scenario": "*",
                "status": "BUNDLE_INTAKE_NOT_READY",
                "missing_fields": bundle_blockers,
                "target_csv": target_csv,
            }
        )
    for row in sync_result.get("rows", []):
        if not isinstance(row, dict):
            continue
        if str(row.get("status", "")).strip() == "READY":
            continue
        scenario = str(row.get("scenario", "")).strip()
        blockers = str(row.get("blockers", "")).strip()
        if not scenario or not blockers:
            continue
        rows.append(
            {
                "level": "scenario",
                "scenario": scenario,
                "status": str(row.get("status", "")).strip(),
                "missing_fields": blockers,
                "target_csv": target_csv,
            }
        )
    return rows


def bundle_sync_attention_rows_by_bundle(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    return {
        bundle: bundle_sync_attention_rows(result)
        for bundle, result in bundle_sync_results_by_bundle(payload).items()
    }


def attention_target_csvs(attention_rows: list[dict[str, str]]) -> str:
    return join_unique([row.get("target_csv", "") for row in attention_rows])


def synced_final_evidence_item_count(sync_result: dict[str, Any]) -> int:
    count = 0
    for row in sync_result.get("rows", []):
        if not isinstance(row, dict):
            continue
        value = row.get("final_evidence_filename_match_count", 0)
        count += int(value) if isinstance(value, int) else 0
    return count


def sync_has_final_evidence_content(sync_result: dict[str, Any]) -> bool:
    rows = sync_result.get("rows", [])
    if not isinstance(rows, list):
        return False
    return any(
        isinstance(row, dict)
        and bool(row.get("final_evidence_exists"))
        and bool(row.get("final_evidence_has_content"))
        for row in rows
    )


def sync_filename_gaps(sync_result: dict[str, Any]) -> list[str]:
    gaps = []
    rows = sync_result.get("rows", [])
    if not isinstance(rows, list):
        return gaps
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not bool(row.get("final_evidence_exists")) or not bool(row.get("final_evidence_has_content")):
            continue
        if bool(row.get("final_evidence_filenames_match")):
            continue
        for key in ("final_evidence_filename_issue", "final_evidence_filename_mismatches"):
            value = str(row.get(key, "")).strip()
            if value:
                gaps.append(value)
    return gaps


def final_evidence_gap(
    check: dict[str, Any],
    sync_result: dict[str, Any] | None = None,
) -> str:
    if bool(check.get("final_evidence_ready")):
        return "READY"
    gaps = []
    if not bool(check.get("operator_fields_complete")):
        gaps.append("OPERATOR_FIELDS_INCOMPLETE")
    if sync_result and sync_has_final_evidence_content(sync_result):
        gaps.extend(sync_filename_gaps(sync_result))
    else:
        for key in (
            "final_evidence_path_issue",
            "final_evidence_filename_issue",
            "final_evidence_filename_mismatches",
        ):
            value = str(check.get(key, "")).strip()
            if value:
                gaps.append(value)
        if not bool(check.get("final_evidence_has_content")):
            gaps.append("NO_FINAL_EVIDENCE_CONTENT")
    return "; ".join(dict.fromkeys(gaps)) or "FINAL_EVIDENCE_NOT_READY"


def final_evidence_item_count(
    check: dict[str, Any],
    sync_result: dict[str, Any] | None = None,
) -> int:
    count = int(check.get("final_evidence_item_count", 0) or 0)
    if not sync_result:
        return count
    return max(count, synced_final_evidence_item_count(sync_result))


def rk10_collected_scenarios(rk10_collect: dict[str, Any]) -> str:
    scenarios = rk10_collect.get("scenarios", [])
    if not isinstance(scenarios, list):
        return ""
    return ", ".join(
        str(row.get("scenario", "")).strip()
        for row in scenarios
        if isinstance(row, dict)
        and str(row.get("scenario", "")).strip()
        and str(row.get("status", "")).strip() == "READY_FOR_REVIEWER_TIMESTAMP"
    )


def rk10_remaining_runtime_evidence(rks_validation: dict[str, Any]) -> str:
    rows = rks_validation.get("rows", [])
    if not isinstance(rows, list):
        return ""
    remaining = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not bool(row.get("requires_rk10_evidence")) or bool(row.get("approved")):
            continue
        scenario = str(row.get("scenario", "")).strip()
        issue_codes = str(row.get("issue_codes", "")).strip()
        if scenario and issue_codes:
            remaining.append(f"{scenario}={issue_codes}")
    return "; ".join(remaining)


def rks_runtime_intake_complete(rks_validation: dict[str, Any]) -> bool:
    if bool(rks_validation.get("overall_rks_runtime_evidence_complete")):
        return True
    required_count = int(rks_validation.get("required_row_count", 0) or 0)
    needs_attention_count = int(rks_validation.get("needs_attention_count", 0) or 0)
    hard_error_count = int(rks_validation.get("hard_error_count", 0) or 0)
    missing_log_count = int(rks_validation.get("missing_latest_log_count", 0) or 0)
    return (
        required_count > 0
        and needs_attention_count == 0
        and hard_error_count == 0
        and missing_log_count == 0
    )


def rk10_active_scenarios(remaining_next_steps: dict[str, Any]) -> set[str]:
    rk10_row = remaining_rows_by_bundle(remaining_next_steps).get(RK10_BUNDLE, {})
    return set(split_csv_values(rk10_row.get("scenarios", "")))


def rk10_gate_matrix_remaining(
    rks_gate_matrix: dict[str, Any],
    active_scenarios: set[str],
) -> str:
    rows = rks_gate_matrix.get("rows", [])
    if not isinstance(rows, list):
        return ""
    remaining = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        scenario = str(row.get("scenario", "")).strip()
        if not scenario or scenario not in active_scenarios:
            continue
        current_status = str(row.get("current_rks_status", "")).strip()
        missing_gate = str(row.get("missing_gate", "")).strip()
        editor_open_probe = str(row.get("editor_open_probe_status", "")).strip()
        build_artifact = row.get("editor_open_probe_build_artifact_found")
        if not current_status and not missing_gate:
            continue
        if editor_open_probe:
            build_status = "YES" if bool(build_artifact) else "NO"
            remaining.append(
                f"{scenario}=open_probe:{editor_open_probe}, "
                f"build_artifact={build_status}, status={current_status}: {missing_gate}"
            )
            continue
        if missing_gate:
            remaining.append(f"{scenario}={current_status}: {missing_gate}")
        else:
            remaining.append(f"{scenario}={current_status}")
    return "; ".join(remaining)


def combine_rk10_remaining(
    runtime_remaining: str,
    gate_remaining: str,
) -> str:
    parts = []
    if runtime_remaining:
        parts.append(f"runtime_intake_pending: {runtime_remaining}")
    if gate_remaining:
        parts.append(f"rks_gate_matrix_pending: {gate_remaining}")
    return " | ".join(parts)


def unified_entry_keys(bundle: str, scenarios: str) -> str:
    return PATH_SEPARATOR.join(
        f"{bundle}::{scenario.strip()}"
        for scenario in split_csv_values(scenarios)
    )


def rk10_supplemental_by_bundle(
    rk10_collect_json: Path,
    rk10_collect: dict[str, Any],
    rks_gate_matrix_json: Path,
    rks_gate_matrix: dict[str, Any],
    remaining_next_steps: dict[str, Any],
) -> dict[str, dict[str, str]]:
    if not rk10_collect:
        return {}
    rks_validation = read_optional_json(str(rk10_collect.get("validation_json", "")).strip())
    active_scenarios = rk10_active_scenarios(remaining_next_steps)
    runtime_remaining = rk10_remaining_runtime_evidence(rks_validation)
    runtime_complete = rks_runtime_intake_complete(rks_validation)
    gate_remaining = ""
    if not runtime_complete:
        gate_remaining = rk10_gate_matrix_remaining(rks_gate_matrix, active_scenarios)
    collected_scenarios = rk10_collected_scenarios(rk10_collect)
    status = str(rk10_collect.get("status", "")).strip()
    approved_count = int(rk10_collect.get("approved_validator_count", 0) or 0)
    collected_count = int(rk10_collect.get("collected_count", 0) or 0)
    appended_count = int(rk10_collect.get("appended_intake_row_count", 0) or 0)
    skipped_count = int(rk10_collect.get("skipped_count", 0) or 0)
    status_parts = [
        f"collector_status={status or 'UNKNOWN'}",
        f"collected={collected_count}/{approved_count}",
        f"auto_appended_intake_rows={appended_count}",
        f"skipped={skipped_count}",
    ]
    if runtime_complete:
        status_parts.append("rks_runtime_intake=COMPLETE")
    if collected_scenarios:
        status_parts.append(f"collected_scenarios={collected_scenarios}")
    return {
        RK10_BUNDLE: {
            "supplemental_evidence_status": "; ".join(status_parts),
            "remaining_runtime_evidence": combine_rk10_remaining(
                runtime_remaining,
                gate_remaining,
            ),
            "supplemental_evidence_source": join_unique(
                [
                    str(rk10_collect_json),
                    str(rk10_collect.get("validation_json", "")).strip(),
                    str(rks_gate_matrix_json),
                ]
            ),
        }
    }


def action_status(
    active: bool,
    final_ready: bool,
    attention_count: int,
) -> str:
    if final_ready and attention_count == 0:
        return "READY_OR_COMPLETED"
    if active:
        return "NEEDS_OPERATOR_INPUT"
    return "NOT_READY_BUT_NOT_ACTIVE"


def build_row(
    bundle: str,
    remaining_row: dict[str, Any],
    check: dict[str, Any],
    attention_rows: list[dict[str, str]],
    sync_result: dict[str, Any],
    supplemental: dict[str, str],
    validation_source: str,
    unified_input_csv: Path = DEFAULT_UNIFIED_INPUT_CSV,
) -> FillQueueRow:
    active = bool(remaining_row.get("active"))
    final_ready = bool(check.get("final_evidence_ready"))
    attention_count = len(attention_rows)
    scenarios = str(remaining_row.get("scenarios") or check.get("scenarios") or "").strip()
    return FillQueueRow(
        rank=parse_rank(remaining_row.get("rank")),
        bundle=bundle,
        scenarios=scenarios,
        owner=str(remaining_row.get("owner", "")).strip(),
        active=active,
        final_evidence_ready=final_ready,
        action_status=action_status(active, final_ready, attention_count),
        missing_operator_fields=missing_operator_summary(attention_rows),
        operator_attention_count=attention_count,
        final_evidence_gap=final_evidence_gap(check, sync_result),
        final_evidence_item_count=final_evidence_item_count(check, sync_result),
        start_here_path=str(remaining_row.get("start_here_path", "")).strip(),
        unified_input_csv=str(unified_input_csv),
        unified_entry_keys=unified_entry_keys(bundle, scenarios),
        fill_only_fields=FILL_ONLY_FIELDS,
        supporting_input_paths=str(remaining_row.get("all_input_paths", "")).strip(),
        suggested_final_evidence_path=str(
            remaining_row.get("final_evidence_dir")
            or check.get("final_evidence_dir")
            or ""
        ).strip(),
        target_intake_path=str(remaining_row.get("target_intake_path") or check.get("intake_path") or "").strip(),
        attention_target_csvs=attention_target_csvs(attention_rows),
        filename_examples=str(remaining_row.get("filename_examples", "")).strip(),
        forbidden=str(remaining_row.get("forbidden", "")).strip(),
        next_action=str(remaining_row.get("next_action", "")).strip(),
        after_action_command=str(remaining_row.get("after_action_command", "")).strip(),
        supplemental_evidence_status=str(supplemental.get("supplemental_evidence_status", "")).strip(),
        remaining_runtime_evidence=str(supplemental.get("remaining_runtime_evidence", "")).strip(),
        supplemental_evidence_source=str(supplemental.get("supplemental_evidence_source", "")).strip(),
        validation_source=validation_source,
    )


def build_rows(
    bundle_validation: dict[str, Any],
    execution_validation: dict[str, Any],
    remaining_next_steps: dict[str, Any],
    bundle_sync: dict[str, Any],
    supplemental_by_bundle: dict[str, dict[str, str]] | None = None,
    unified_input_csv: Path = DEFAULT_UNIFIED_INPUT_CSV,
) -> list[FillQueueRow]:
    checks_by_bundle = bundle_checks_by_bundle(bundle_validation)
    remaining_by_bundle = remaining_rows_by_bundle(remaining_next_steps)
    attention_by_bundle = attention_rows_by_bundle(execution_validation)
    sync_attention_by_bundle = bundle_sync_attention_rows_by_bundle(bundle_sync)
    sync_results_by_bundle = bundle_sync_results_by_bundle(bundle_sync)
    supplemental_lookup = supplemental_by_bundle or {}
    bundles = list(remaining_by_bundle)
    for bundle in checks_by_bundle:
        if bundle not in bundles:
            bundles.append(bundle)
    validation_source = join_unique(
        [
            str(bundle_validation.get("pack_json", "")).strip(),
            str(bundle_validation.get("operator_sheet", "")).strip(),
            str(execution_validation.get("packet_dir", "")).strip(),
            str(remaining_next_steps.get("operator_prefill_json", "")).strip(),
        ]
    )
    rows = [
        build_row(
            bundle,
            remaining_by_bundle.get(bundle, {"bundle": bundle}),
            checks_by_bundle.get(bundle, {"bundle": bundle}),
            sync_attention_by_bundle.get(bundle) or attention_by_bundle.get(bundle, []),
            sync_results_by_bundle.get(bundle, {}),
            supplemental_lookup.get(bundle, {}),
            validation_source,
            unified_input_csv,
        )
        for bundle in bundles
    ]
    return sorted(rows, key=lambda row: (row.rank is None, row.rank or 999, row.bundle))


def build_payload(
    bundle_validation_json: Path,
    execution_validation_json: Path,
    remaining_next_steps_json: Path,
    rk10_collect_json: Path = DEFAULT_RK10_COLLECT_JSON,
    rks_gate_matrix_json: Path = DEFAULT_RKS_GATE_MATRIX_JSON,
    bundle_sync_json: Path = DEFAULT_BUNDLE_SYNC_JSON,
    unified_input_csv: Path = DEFAULT_UNIFIED_INPUT_CSV,
) -> dict[str, Any]:
    bundle_validation = read_json(bundle_validation_json)
    execution_validation = read_json(execution_validation_json)
    remaining_next_steps = read_json(remaining_next_steps_json)
    rk10_collect = read_json(rk10_collect_json)
    rks_gate_matrix = read_json(rks_gate_matrix_json)
    bundle_sync = read_json(bundle_sync_json)
    rows = build_rows(
        bundle_validation,
        execution_validation,
        remaining_next_steps,
        bundle_sync,
        rk10_supplemental_by_bundle(
            rk10_collect_json,
            rk10_collect,
            rks_gate_matrix_json,
            rks_gate_matrix,
            remaining_next_steps,
        ),
        unified_input_csv,
    )
    active_rows = [row for row in rows if row.action_status == "NEEDS_OPERATOR_INPUT"]
    ready_rows = [row for row in rows if row.action_status == "READY_OR_COMPLETED"]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": (
            "read-only queue generation only; no approval, no evidence copy, "
            "no external operation"
        ),
        "bundle_validation_json": str(bundle_validation_json),
        "execution_validation_json": str(execution_validation_json),
        "remaining_next_steps_json": str(remaining_next_steps_json),
        "rk10_collect_json": str(rk10_collect_json),
        "rks_gate_matrix_json": str(rks_gate_matrix_json),
        "bundle_sync_json": str(bundle_sync_json),
        "unified_input_csv": str(unified_input_csv),
        "row_count": len(rows),
        "active_queue_count": len(active_rows),
        "ready_or_completed_count": len(ready_rows),
        "operator_attention_row_count": sum(row.operator_attention_count for row in rows),
        "next_active_bundle": active_rows[0].bundle if active_rows else "",
        "after_action_command": active_rows[0].after_action_command if active_rows else "",
        "rows": [asdict(row) for row in rows],
    }


def format_path(value: str) -> str:
    return f"`{value}`" if value else "-"


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    active_rows = [row for row in rows if row["action_status"] == "NEEDS_OPERATOR_INPUT"]
    completed_rows = [row for row in rows if row["action_status"] == "READY_OR_COMPLETED"]
    lines = [
        "# Final evidence fill queue 2026-06-21",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- active_queue_count: `{payload['active_queue_count']}`",
        f"- ready_or_completed_count: `{payload['ready_or_completed_count']}`",
        f"- operator_attention_row_count: `{payload['operator_attention_row_count']}`",
        f"- next_active_bundle: `{payload['next_active_bundle']}`",
        f"- safety: `{payload['safety']}`",
        "",
        "## Read This First",
        "",
        "- This queue shows exactly which operator fields and final evidence paths still block the goal.",
        "- To reduce hunting, fill the shown `Unified Input` row and only the shown `Fill Only` fields unless the evidence folder changed.",
        "- It does not approve completion and does not copy reference evidence into final evidence.",
        "- Keep hard stops in force: no production registration, real mail, real print, payment execution, Azure paid OCR, RK10 ButtonRun, or production writes unless explicitly approved.",
        "",
        "## Active Fill Queue",
        "",
        "| Rank | Bundle | Scenarios | Missing Operator Fields | Unified Input | Entry Key | Fill Only | Final Evidence Gap | Evidence Progress | Remaining Runtime Evidence | START_HERE | Target Intake | Attention CSVs | Put Evidence Here | Hard Stop |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    if active_rows:
        for row in active_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["rank"] or ""),
                        str(row["bundle"]),
                        str(row["scenarios"]),
                        str(row["missing_operator_fields"]) or "-",
                        format_path(str(row["unified_input_csv"])),
                        str(row["unified_entry_keys"]) or "-",
                        str(row["fill_only_fields"]) or "-",
                        str(row["final_evidence_gap"]) or "-",
                        str(row.get("supplemental_evidence_status", "")) or "-",
                        str(row.get("remaining_runtime_evidence", "")) or "-",
                        format_path(str(row["start_here_path"])),
                        format_path(str(row["target_intake_path"])),
                        format_path(str(row["attention_target_csvs"])),
                        format_path(str(row["suggested_final_evidence_path"])),
                        str(row["forbidden"]) or "-",
                    ]
                )
                + " |"
            )
    else:
        lines.append("|  | - | - | - | - | - | - | - | - | - | - | - | - | - | - |")
    if completed_rows:
        lines.extend(
            [
                "",
                "## Ready / Completed Bundles",
                "",
                "| Bundle | Scenarios | Final Evidence Items | Evidence Status |",
                "|---|---|---:|---|",
            ]
        )
        for row in completed_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["bundle"]),
                        str(row["scenarios"]),
                        str(row["final_evidence_item_count"]),
                        str(row["final_evidence_gap"]),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## After Action",
            "",
            f"- fixed_safe_runner: `{payload['after_action_command']}`",
            f"- bundle_validation_json: `{payload['bundle_validation_json']}`",
            f"- execution_validation_json: `{payload['execution_validation_json']}`",
            f"- remaining_next_steps_json: `{payload['remaining_next_steps_json']}`",
            f"- rk10_collect_json: `{payload['rk10_collect_json']}`",
            f"- rks_gate_matrix_json: `{payload['rks_gate_matrix_json']}`",
            f"- bundle_sync_json: `{payload['bundle_sync_json']}`",
            f"- unified_input_csv: `{payload['unified_input_csv']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(FillQueueRow)]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "final_evidence_fill_queue.json"
    csv_path = out_dir / "final_evidence_fill_queue.csv"
    md_path = out_dir / "final_evidence_fill_queue.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, payload["rows"])
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)
    write_numbered_copy(csv_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate final evidence fill queue.")
    parser.add_argument("--bundle-validation-json", type=Path, default=DEFAULT_BUNDLE_VALIDATION_JSON)
    parser.add_argument("--execution-validation-json", type=Path, default=DEFAULT_EXECUTION_VALIDATION_JSON)
    parser.add_argument("--remaining-next-steps-json", type=Path, default=DEFAULT_REMAINING_NEXT_STEPS_JSON)
    parser.add_argument("--rk10-collect-json", type=Path, default=DEFAULT_RK10_COLLECT_JSON)
    parser.add_argument("--rks-gate-matrix-json", type=Path, default=DEFAULT_RKS_GATE_MATRIX_JSON)
    parser.add_argument("--bundle-sync-json", type=Path, default=DEFAULT_BUNDLE_SYNC_JSON)
    parser.add_argument("--unified-input-csv", type=Path, default=DEFAULT_UNIFIED_INPUT_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        args.bundle_validation_json,
        args.execution_validation_json,
        args.remaining_next_steps_json,
        args.rk10_collect_json,
        args.rks_gate_matrix_json,
        args.bundle_sync_json,
        args.unified_input_csv,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
