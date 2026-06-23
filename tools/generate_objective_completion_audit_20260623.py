"""Generate a current-state audit against the user's full objective.

This report is read-only. It summarizes existing repository evidence and does
not run RK10, send mail, print, submit, pay, call Azure, or write production
systems.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_OUT_DIR = REPORTS / "objective_completion_audit_20260623"
GOAL_EVIDENCE_LEDGER_JSON = (
    REPORTS / "goal_evidence_ledger_20260620" / "goal_evidence_ledger.json"
)
GOAL_COMPLETION_GATE_JSON = (
    REPORTS / "goal_completion_gate_20260620" / "goal_completion_gate.json"
)
SAFE_GOAL_CHECKS_JSON = REPORTS / "safe_goal_checks_20260620" / "safe_goal_checks_summary.json"
REMAINING_OPERATOR_READY_JSON = (
    REPORTS
    / "remaining_operator_input_ready_validation_20260623"
    / "remaining_operator_input_ready_validation.json"
)
GOAL_CODE_BACKUP_JSON = (
    REPORTS / "goal_code_artifact_backups_20260620" / "goal_code_artifact_backups.json"
)
SYNC_MANIFEST_JSON = (
    REPORTS
    / "sync_manifest_remaining_operator_input_precheck_20260623_verification"
    / "sync_manifest_remaining_operator_input_precheck_20260623_verification.json"
)
FINAL_FRONT_DOOR_SYNC_MANIFEST_JSON = (
    REPORTS
    / "final_operator_front_door_20260623"
    / "sync_manifest_final_operator_front_door_20260623.json"
)
FINAL_FRONT_DOOR_DISTRIBUTION_CHECK_JSON = (
    REPORTS
    / "final_operator_front_door_20260623"
    / "final_operator_front_door_distribution_check.json"
)
SCOPE_EXCLUSIONS_JSON = (
    REPORTS / "objective_scope_exclusions_20260623" / "objective_scope_exclusions.json"
)

SAMPLE_READY_STATUSES = {
    "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT",
    "OUTLOOK_COM_BUNDLE_DRYRUN_SAMPLE_REFRESH_READY",
}
SAFE_EXECUTION_READY_STATUSES = {
    "SAFE_SUITE_EXIT0_STDERR0",
    "OUTLOOK_COM_BUNDLE_DRYRUN_NO_PRINT_NO_MAIL_EXIT0",
}
RKS_TECHNICAL_COMPLETE_STATUSES = {
    "RKS_TECHNICAL_GATE_COMPLETE",
    "NON_RKS_OR_DEFERRED_OK",
    "RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION",
    "RKS_RUNTIME_EVIDENCE_CONFIRMED",
    "N_A_NO_PRIMARY_RKS",
}
BUSINESS_COST_NOT_READY_STATUSES = {
    "",
    "INVALID_COST_EVIDENCE",
    "MISSING_COST_EVIDENCE",
    "PENDING",
}


@dataclass(frozen=True)
class ObjectiveAuditRow:
    requirement_id: str
    requirement: str
    status: str
    evidence: str
    current_value: str
    remaining_gap: str
    next_action: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def count_rows(rows: list[dict[str, Any]], predicate: Any) -> int:
    return sum(1 for row in rows if predicate(row))


def scenario_tokens(value: str) -> set[str]:
    tokens = {value.strip()} if value.strip() else set()
    for chunk in value.replace("、", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            tokens.add(chunk)
            if "/" in chunk and all(part.strip().isdigit() for part in chunk.split("/")):
                tokens.update(part.strip() for part in chunk.split("/") if part.strip())
    return tokens


def load_scope_exclusions(path: Path = SCOPE_EXCLUSIONS_JSON) -> list[dict[str, str]]:
    payload = read_json(path)
    raw_rows = payload.get("exclusions", [])
    if not isinstance(raw_rows, list):
        raw_rows = []
    rows: list[dict[str, str]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        active = row.get("active", True)
        if active is False or str(active).strip().lower() in {"false", "0", "no"}:
            continue
        scenario = str(row.get("scenario", "")).strip()
        if not scenario:
            continue
        rows.append(
            {
                "scenario": scenario,
                "reason": str(row.get("reason", "")).strip(),
                "requested_by": str(row.get("requested_by", "")).strip(),
                "requested_at": str(row.get("requested_at", "")).strip(),
                "evidence": str(row.get("evidence", "")).strip(),
            }
        )
    return rows


def excluded_scenario_tokens(exclusions: list[dict[str, str]]) -> set[str]:
    tokens: set[str] = set()
    for row in exclusions:
        tokens.update(scenario_tokens(row.get("scenario", "")))
    return tokens


def row_is_excluded(row: dict[str, Any], excluded_tokens: set[str]) -> bool:
    if not excluded_tokens:
        return False
    value = str(row.get("scenario") or row.get("scenarios") or "")
    return bool(scenario_tokens(value) & excluded_tokens)


def is_sample_ready(row: dict[str, Any]) -> bool:
    return str(row.get("sample_data_status", "")) in SAMPLE_READY_STATUSES


def is_safe_execution_ready(row: dict[str, Any]) -> bool:
    return str(row.get("safe_execution_status", "")) in SAFE_EXECUTION_READY_STATUSES


def is_business_cost_ready(row: dict[str, Any]) -> bool:
    status = str(row.get("business_cost_status", ""))
    checkpoint_summary = str(row.get("objective_checkpoint_summary", ""))
    if status in BUSINESS_COST_NOT_READY_STATUSES:
        return False
    if "cost=PENDING" in checkpoint_summary:
        return False
    return bool(row.get("business_cost_evidence_exists", True))


def is_rks_runtime_resolved(row: dict[str, Any]) -> bool:
    status = str(row.get("rks_runtime_intake_status", ""))
    rks_status = str(row.get("rks_status", ""))
    return status in RKS_TECHNICAL_COMPLETE_STATUSES or rks_status in RKS_TECHNICAL_COMPLETE_STATUSES


def status_from_condition(condition: bool, partial: bool = False) -> str:
    if condition:
        return "PROVED"
    if partial:
        return "PARTIAL"
    return "NOT_PROVED"


def build_sync_evidence() -> dict[str, Any]:
    final_manifest = read_json(FINAL_FRONT_DOOR_SYNC_MANIFEST_JSON)
    distribution_check = read_json(FINAL_FRONT_DOOR_DISTRIBUTION_CHECK_JSON)
    if final_manifest:
        manifest_ok = bool(final_manifest.get("all_hashes_match"))
        distribution_ok = bool(distribution_check.get("all_distribution_checks_pass"))
        relative_inner_apply_fix = bool(final_manifest.get("relative_inner_apply_fix"))
        return {
            "ok": manifest_ok and distribution_ok and relative_inner_apply_fix,
            "evidence": (
                f"{FINAL_FRONT_DOOR_SYNC_MANIFEST_JSON}; "
                f"{FINAL_FRONT_DOOR_DISTRIBUTION_CHECK_JSON}"
            ),
            "current_value": (
                f"source_count={final_manifest.get('source_count')}; "
                f"copy_result_count={final_manifest.get('copy_result_count')}; "
                f"all_hashes_match={final_manifest.get('all_hashes_match')}; "
                "all_distribution_checks_pass="
                f"{distribution_check.get('all_distribution_checks_pass')}; "
                f"relative_inner_apply_fix={final_manifest.get('relative_inner_apply_fix')}"
            ),
            "remaining_gap": "" if manifest_ok and distribution_ok else "sync or distribution check failed",
        }

    legacy_manifest = read_json(SYNC_MANIFEST_JSON)
    legacy_ok = bool(legacy_manifest.get("all_requested_destinations_available")) and bool(
        legacy_manifest.get("all_available_copy_hashes_match")
    )
    return {
        "ok": legacy_ok,
        "evidence": str(SYNC_MANIFEST_JSON),
        "current_value": (
            f"copy_result_count={legacy_manifest.get('copy_result_count')}; "
            "all_available_copy_hashes_match="
            f"{legacy_manifest.get('all_available_copy_hashes_match')}"
        ),
        "remaining_gap": ""
        if legacy_manifest.get("all_available_copy_hashes_match")
        else "sync hash mismatch",
    }


def build_payload() -> dict[str, Any]:
    ledger = read_json(GOAL_EVIDENCE_LEDGER_JSON)
    gate = read_json(GOAL_COMPLETION_GATE_JSON)
    safe_runner = read_json(SAFE_GOAL_CHECKS_JSON)
    remaining_ready = read_json(REMAINING_OPERATOR_READY_JSON)
    backup = read_json(GOAL_CODE_BACKUP_JSON)
    sync_evidence = build_sync_evidence()
    scope_exclusions = load_scope_exclusions()
    excluded_tokens = excluded_scenario_tokens(scope_exclusions)
    ledger_rows = [dict(row) for row in ledger.get("rows", [])]
    active_ledger_rows = [row for row in ledger_rows if not row_is_excluded(row, excluded_tokens)]
    excluded_ledger_rows = [row for row in ledger_rows if row_is_excluded(row, excluded_tokens)]
    total_scenario_count = int(ledger.get("scenario_count", len(ledger_rows)))
    scenario_count = len(active_ledger_rows)
    sample_ready_count = count_rows(active_ledger_rows, is_sample_ready)
    safe_execution_ready_count = count_rows(active_ledger_rows, is_safe_execution_ready)
    business_cost_ready_count = count_rows(active_ledger_rows, is_business_cost_ready)
    rks_runtime_resolved_count = count_rows(active_ledger_rows, is_rks_runtime_resolved)
    final_evidence_ready_count = count_rows(
        active_ledger_rows,
        lambda row: bool(row.get("final_evidence_ready")),
    )
    remaining_rows = [
        dict(row) for row in remaining_ready.get("rows", []) if isinstance(row, dict)
    ]
    active_remaining_rows = [
        row for row in remaining_rows if not row_is_excluded(row, excluded_tokens)
    ]
    if remaining_rows:
        remaining_operator_count = len(active_remaining_rows)
        remaining_operator_not_ready_count = sum(
            1
            for row in active_remaining_rows
            if str(row.get("status", "")) != "READY_FOR_SYNC" or bool(row.get("blockers"))
        )
    else:
        remaining_operator_count = int(remaining_ready.get("row_count", 0))
        remaining_operator_not_ready_count = int(remaining_ready.get("not_ready_row_count", 0))
    raw_remaining_operator_count = int(
        remaining_ready.get("raw_row_count", remaining_ready.get("row_count", 0))
    )
    raw_remaining_operator_not_ready_count = int(
        remaining_ready.get(
            "raw_not_ready_row_count",
            remaining_ready.get("not_ready_row_count", 0),
        )
    )
    rows = [
        ObjectiveAuditRow(
            requirement_id="REQ-01",
            requirement="全シナリオのサンプルデータを用意する",
            status=status_from_condition(sample_ready_count == scenario_count and scenario_count > 0),
            evidence=str(GOAL_EVIDENCE_LEDGER_JSON),
            current_value=(
                f"sample_ready_count={sample_ready_count}/{scenario_count}; "
                f"excluded_scope_count={len(excluded_ledger_rows)}"
            ),
            remaining_gap="" if sample_ready_count == scenario_count else "sample data evidence missing",
            next_action="不足シナリオのsample_data_evidenceを追加する",
        ),
        ObjectiveAuditRow(
            requirement_id="REQ-02",
            requirement="PY/Pythonツールを安全スコープで実行し、エラーなく終了する",
            status=status_from_condition(bool(safe_runner.get("overall_passed"))),
            evidence=str(SAFE_GOAL_CHECKS_JSON),
            current_value=f"overall_passed={safe_runner.get('overall_passed')}",
            remaining_gap="" if safe_runner.get("overall_passed") else "safe runner failed or missing",
            next_action="失敗ステップを修正し、固定安全ランナーを再実行する",
        ),
        ObjectiveAuditRow(
            requirement_id="REQ-03",
            requirement="RKSファイルのopen/build/runtime/safe-stop証跡をスコープ付きで確認する",
            status=status_from_condition(
                rks_runtime_resolved_count == scenario_count and scenario_count > 0,
                partial=rks_runtime_resolved_count > 0,
            ),
            evidence=str(GOAL_EVIDENCE_LEDGER_JSON),
            current_value=(
                f"rks_runtime_resolved_count={rks_runtime_resolved_count}/{scenario_count}; "
                f"excluded_scope_count={len(excluded_ledger_rows)}"
            ),
            remaining_gap=(
                ""
                if rks_runtime_resolved_count == scenario_count
                else "RKS technical evidence or prerequisite/entry decision remains incomplete"
            ),
            next_action="RKS要否判断、RK10 open/build/runtime/latest clean log、または前提保留の承認を記録する",
        ),
        ObjectiveAuditRow(
            requirement_id="REQ-04",
            requirement="実際の業務費用・件数・金額スコープを証跡化する",
            status=status_from_condition(
                business_cost_ready_count == scenario_count and scenario_count > 0,
                partial=business_cost_ready_count > 0,
            ),
            evidence=str(GOAL_EVIDENCE_LEDGER_JSON),
            current_value=(
                f"business_cost_ready_count={business_cost_ready_count}/{scenario_count}; "
                f"excluded_scope_count={len(excluded_ledger_rows)}"
            ),
            remaining_gap="" if business_cost_ready_count == scenario_count else "business cost proof missing",
            next_action="不足シナリオの件数/金額/安全dry-run証跡を追加する",
        ),
        ObjectiveAuditRow(
            requirement_id="REQ-05",
            requirement="全シナリオの安全実行証跡を揃える",
            status=status_from_condition(
                safe_execution_ready_count == scenario_count and scenario_count > 0,
                partial=safe_execution_ready_count > 0,
            ),
            evidence=str(GOAL_EVIDENCE_LEDGER_JSON),
            current_value=(
                f"safe_execution_ready_count={safe_execution_ready_count}/{scenario_count}; "
                f"excluded_scope_count={len(excluded_ledger_rows)}"
            ),
            remaining_gap="" if safe_execution_ready_count == scenario_count else "safe execution proof missing",
            next_action="不足シナリオの安全実行またはsafe-stop証跡を追加する",
        ),
        ObjectiveAuditRow(
            requirement_id="REQ-06",
            requirement="エラー発生時は原因究明と対策を実装する",
            status=status_from_condition(bool(gate.get("final_goal_complete")), partial=bool(safe_runner.get("overall_passed"))),
            evidence=str(GOAL_COMPLETION_GATE_JSON),
            current_value=(
                f"final_goal_complete={gate.get('final_goal_complete')}; "
                f"blocking_gate_count={gate.get('blocking_gate_count')}"
            ),
            remaining_gap=(
                "" if gate.get("final_goal_complete") else "final completion gates remain incomplete"
            ),
            next_action=(
                "追加対応なし。固定安全ランナーと完了ゲートは通過済み。"
                if gate.get("final_goal_complete")
                else "残ゲートの未達理由を解除してから完了判定する"
            ),
        ),
        ObjectiveAuditRow(
            requirement_id="REQ-07",
            requirement="修正実装ファイルを別名保存でバックアップする",
            status=status_from_condition(bool(backup.get("backup_complete")) and int(backup.get("missing_count", 1)) == 0),
            evidence=str(GOAL_CODE_BACKUP_JSON),
            current_value=(
                f"backup_complete={backup.get('backup_complete')}; "
                f"missing_count={backup.get('missing_count')}; "
                f"snapshot_id={backup.get('snapshot_id')}"
            ),
            remaining_gap="" if backup.get("backup_complete") else "backup incomplete",
            next_action="コード成果物バックアップを再実行する",
        ),
        ObjectiveAuditRow(
            requirement_id="REQ-08",
            requirement="最終ログ・報告を出し、移行先へ同期する",
            status=status_from_condition(bool(sync_evidence["ok"])),
            evidence=str(sync_evidence["evidence"]),
            current_value=str(sync_evidence["current_value"]),
            remaining_gap=str(sync_evidence["remaining_gap"]),
            next_action="同期manifestを再生成し、C/E配布先のhash一致を確認する",
        ),
        ObjectiveAuditRow(
            requirement_id="REQ-09",
            requirement="本番移行OK状態を最終確定する",
            status=status_from_condition(bool(gate.get("final_goal_complete"))),
            evidence=str(GOAL_COMPLETION_GATE_JSON),
            current_value=(
                f"final_goal_complete={gate.get('final_goal_complete')}; "
                f"passed_gate_count={gate.get('passed_gate_count')}/{gate.get('gate_count')}; "
                f"active_remaining_operator_not_ready_count={remaining_operator_not_ready_count}/{remaining_operator_count}; "
                f"raw_remaining_operator_not_ready_count={raw_remaining_operator_not_ready_count}/{raw_remaining_operator_count}; "
                f"excluded_scope_count={len(excluded_ledger_rows)}"
            ),
            remaining_gap=(
                ""
                if gate.get("final_goal_complete")
                else (
                    "operator_result/reviewer/reviewed_at remain blank for final operator rows"
                    if remaining_operator_not_ready_count
                    else "completion gate incomplete"
                )
            ),
            next_action=(
                "追加対応なし。Codex自動証跡確認、最終証跡同期、固定安全ランナーは通過済み。"
                if gate.get("final_goal_complete")
                else (
                    f"残{remaining_operator_not_ready_count}行をCodex自動証跡確認またはレビュー入力し、"
                    "RUN_AFTER_FILLで同期と安全ランナーを実行する"
                )
            ),
        ),
    ]
    passed_count = sum(1 for row in rows if row.status == "PROVED")
    partial_count = sum(1 for row in rows if row.status == "PARTIAL")
    not_proved_count = sum(1 for row in rows if row.status == "NOT_PROVED")
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": bool(gate.get("final_goal_complete")),
        "safety": (
            "read-only objective audit; no RK10 ButtonRun, no production write, "
            "no real mail, no real print, no final submit, no payment, no paid Azure OCR"
        ),
        "requirement_count": len(rows),
        "proved_count": passed_count,
        "partial_count": partial_count,
        "not_proved_count": not_proved_count,
        "total_scenario_count": total_scenario_count,
        "scenario_count": scenario_count,
        "scope_exclusion_count": len(scope_exclusions),
        "scope_exclusions_path": str(SCOPE_EXCLUSIONS_JSON),
        "scope_exclusions": scope_exclusions,
        "sample_ready_count": sample_ready_count,
        "safe_execution_ready_count": safe_execution_ready_count,
        "business_cost_ready_count": business_cost_ready_count,
        "rks_runtime_resolved_count": rks_runtime_resolved_count,
        "final_evidence_ready_count": final_evidence_ready_count,
        "raw_remaining_operator_not_ready_count": raw_remaining_operator_not_ready_count,
        "remaining_operator_not_ready_count": remaining_operator_not_ready_count,
        "rows": [asdict(row) for row in rows],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Objective Completion Audit 2026-06-23",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- requirement_count: `{payload['requirement_count']}`",
        f"- proved_count: `{payload['proved_count']}`",
        f"- partial_count: `{payload['partial_count']}`",
        f"- not_proved_count: `{payload['not_proved_count']}`",
        f"- total_scenario_count: `{payload.get('total_scenario_count', payload['scenario_count'])}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- scope_exclusion_count: `{payload.get('scope_exclusion_count', 0)}`",
        f"- scope_exclusions_path: `{payload.get('scope_exclusions_path', '')}`",
        f"- sample_ready_count: `{payload['sample_ready_count']}`",
        f"- safe_execution_ready_count: `{payload['safe_execution_ready_count']}`",
        f"- business_cost_ready_count: `{payload['business_cost_ready_count']}`",
        f"- rks_runtime_resolved_count: `{payload['rks_runtime_resolved_count']}`",
        f"- final_evidence_ready_count: `{payload['final_evidence_ready_count']}`",
        f"- remaining_operator_not_ready_count: `{payload['remaining_operator_not_ready_count']}`",
        f"- safety: `{payload['safety']}`",
        "",
    ]
    if payload.get("scope_exclusions"):
        lines.extend(
            [
                "## Scope Exclusions",
                "",
                "| Scenario | Reason | Requested By | Requested At | Evidence |",
                "|---|---|---|---|---|",
            ]
        )
        for exclusion in payload["scope_exclusions"]:
            lines.append(
                "| "
                + " | ".join(
                    str(exclusion.get(key, "")).replace("|", "/")
                    for key in ["scenario", "reason", "requested_by", "requested_at", "evidence"]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Requirement Results",
            "",
            "| ID | Requirement | Status | Current Value | Remaining Gap | Next Action | Evidence |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                str(row.get(key, "")).replace("|", "/")
                for key in [
                    "requirement_id",
                    "requirement",
                    "status",
                    "current_value",
                    "remaining_gap",
                    "next_action",
                    "evidence",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in ObjectiveAuditRow.__dataclass_fields__.values()]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "objective_completion_audit.json"
    md_path = out_dir / "objective_completion_audit.md"
    csv_path = out_dir / "objective_completion_audit.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_csv(csv_path, payload["rows"])
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    write_numbered_copy(csv_path)


def main() -> int:
    payload = build_payload()
    write_outputs(payload)
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
