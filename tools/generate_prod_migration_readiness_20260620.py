"""Generate a production-migration readiness gate separate from final execution.

This report answers whether each scenario is ready to be moved into the
customer production-migration set. It intentionally does not mark the final
business execution complete and does not open Outlook, RK10, Rakuraku, Azure,
printers, mail, payment systems, MainSV, or production files.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_OUT_DIR = REPORTS / "prod_migration_readiness_20260620"

DEFAULT_SOURCES = {
    "safe_runner": REPORTS / "safe_goal_checks_20260620" / "safe_goal_checks_summary.json",
    "code_artifact_backup": REPORTS
    / "goal_code_artifact_backups_20260620"
    / "goal_code_artifact_backups.json",
    "status_snapshot": REPORTS / "goal_status_snapshot_20260620" / "goal_status_snapshot.json",
    "sample_data_map": REPORTS
    / "sample_data_evidence_map_20260620"
    / "sample_data_evidence_map.json",
    "safe_execution_map": REPORTS
    / "safe_execution_evidence_map_20260620"
    / "safe_execution_evidence_map.json",
    "business_cost_map": REPORTS
    / "business_cost_evidence_map_20260620"
    / "business_cost_evidence_map.json",
    "rks_matrix": REPORTS / "rks_gate_matrix_20260620" / "rks_gate_matrix.json",
    "bundle_evidence_validation": REPORTS
    / "bundle_evidence_pack_validation_20260620"
    / "bundle_evidence_pack_validation.json",
    "outlook_bundle_evidence_collect": REPORTS
    / "outlook_bundle_evidence_collect_20260620"
    / "outlook_bundle_evidence_collect.json",
}

SAMPLE_READY_STATUS = "SAFE_SUITE_SAMPLE_OR_DRYRUN_ARTIFACTS_PRESENT"
SAFE_EXECUTION_READY_STATUS = "SAFE_SUITE_EXIT0_STDERR0"
OUTLOOK_COM_BUNDLE_NAME = "OUTLOOK_COM_BUNDLE"
OUTLOOK_COM_SCENARIO = "12/13"
OUTLOOK_COM_SAMPLE_READY_STATUS = "OUTLOOK_COM_BUNDLE_DRYRUN_SAMPLE_REFRESH_READY"
OUTLOOK_COM_SAFE_READY_STATUS = "OUTLOOK_COM_BUNDLE_DRYRUN_NO_PRINT_NO_MAIL_EXIT0"
RKS_SAFE_STOP_STATUS = "SAFE_STOP_SCOPE_ONLY"
RKS_RUNTIME_CONFIRMED_STATUS = "RKS_RUNTIME_EVIDENCE_CONFIRMED"
NO_RKS_REQUIRED_SCENARIOS = {"12/13", "43"}
BLOCKING_STATUS_TOKENS = (
    "HOLD",
    "UNCONFIRMED",
    "NOT_CONFIRMED",
    "OPEN_NG",
    "MISSING",
    "UNPROVEN",
)
STATUS_NEXT_ACTIONS_JA = {
    "HOLD_OUTLOOK_COM_NOT_READY": "Classic Outlook COMを復旧し、--check-outlook-com exit0後にdry-run/no-print/no-mailを実行する。",
    "HOLD_NO_CONFIRMED_ROWS": "44 spot checkで業務担当者がOK/NGを記入し、OK行だけhandoff候補へ進める。",
    "HOLD_PAYMENT_EXECUTE_NOT_ALLOWED": "70の件数・金額・銀行確認・承認者を記入し、confirm-previewのみ実行する。",
    "HOLD_AZURE_OCR_GATE_MISSING": "71のendpoint/key・費用承認・1件PDFを確定してpaid smoke可否を判断する。",
}
READY_CANDIDATE_FIELDNAMES = [
    "scenario",
    "migration_ready",
    "safe_scope",
    "current_status",
    "sample_gate",
    "safe_execution_gate",
    "rks_gate",
    "cost_scope",
    "no_irreversible_operations",
    "next_action",
    "source",
    "evidence_paths",
]
BLOCKER_FIELDNAMES = [
    "scenario",
    "migration_ready",
    "current_status",
    "blockers",
    "sample_gate",
    "safe_execution_gate",
    "rks_gate",
    "cost_scope",
    "required_before_migration",
    "source",
    "evidence_paths",
]
DISPOSITION_FIELDNAMES = [
    "scenario",
    "kit_inclusion_status",
    "executable_in_customer_kit",
    "migration_ready",
    "current_status",
    "allowed_scope",
    "prohibited_operations",
    "blockers",
    "next_action",
    "source",
    "evidence_paths",
]
SAFE_SCOPE_LABEL = "safe dry-run/no-mail/no-submit/no-print/no-payment only"
NO_IRREVERSIBLE_OPERATIONS_LABEL = "YES"
HOLD_SCOPE_LABEL = "review/repair/evidence collection only"
PROHIBITED_OPERATIONS_LABEL = (
    "real mail; real print; final submit; payment execute; production write; "
    "RK10 ButtonRun unless separately approved"
)


@dataclass(frozen=True)
class MigrationReadinessRow:
    scenario: str
    migration_ready: bool
    current_status: str
    sample_gate: str
    safe_execution_gate: str
    rks_gate: str
    cost_scope: str
    source: str
    evidence_paths: str
    blockers: str
    next_action: str


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rows_by_scenario(payload: dict[str, Any], key: str = "rows") -> dict[str, dict[str, Any]]:
    rows = payload.get(key, [])
    if not isinstance(rows, list):
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        scenario = str(row.get("scenario", ""))
        if scenario:
            indexed[scenario] = row
    return indexed


def split_grouped_scenarios(value: str) -> set[str]:
    return {part.strip() for part in value.split("/") if part.strip()}


def split_bundle_scenarios(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def find_rks_row(scenario: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        row_scenario = str(row.get("scenario", ""))
        if row_scenario == scenario:
            return row
        if scenario in split_grouped_scenarios(row_scenario):
            return row
    return None


def status_is_blocking(status: str) -> bool:
    return any(token in status for token in BLOCKING_STATUS_TOKENS)


def sample_gate_ready(status: str) -> bool:
    return status in {SAMPLE_READY_STATUS, OUTLOOK_COM_SAMPLE_READY_STATUS}


def safe_execution_gate_ready(status: str) -> bool:
    return status in {SAFE_EXECUTION_READY_STATUS, OUTLOOK_COM_SAFE_READY_STATUS}


def global_safe_runner_ready(payload: dict[str, Any]) -> bool:
    return payload.get("overall_passed") is True


def code_backup_ready(payload: dict[str, Any]) -> bool:
    return (
        payload.get("backup_complete") is True
        and int(payload.get("artifact_count", 0)) > 0
        and int(payload.get("missing_count", 0)) == 0
    )


def classify_rks_gate(scenario: str, rks_row: dict[str, Any] | None) -> tuple[str, str]:
    if scenario in NO_RKS_REQUIRED_SCENARIOS and rks_row is None:
        return "RKS_NOT_REQUIRED", ""
    if rks_row is None:
        return "RKS_ROW_MISSING", "RKS_GATE_NOT_READY"
    rks_status = str(rks_row.get("current_rks_status", ""))
    runtime_status = str(rks_row.get("runtime_intake_status", ""))
    if rks_status == "N_A_NO_PRIMARY_RKS":
        return "RKS_NOT_REQUIRED", ""
    if rks_status == RKS_SAFE_STOP_STATUS and runtime_status == RKS_RUNTIME_CONFIRMED_STATUS:
        return "RKS_SAFE_STOP_CONFIRMED_SCOPE_ONLY", ""
    return rks_status or "RKS_STATUS_UNKNOWN", "RKS_GATE_NOT_READY"


def first_non_empty(values: list[str]) -> str:
    for value in values:
        if value:
            return value
    return ""


def find_outlook_com_final_evidence_path(payload: dict[str, Any]) -> str:
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return ""
    for item in checks:
        if not isinstance(item, dict):
            continue
        if item.get("bundle") != OUTLOOK_COM_BUNDLE_NAME:
            continue
        if item.get("final_evidence_ready") is not True:
            continue
        scenarios = split_bundle_scenarios(str(item.get("scenarios", "")))
        if OUTLOOK_COM_SCENARIO in scenarios:
            return str(item.get("final_evidence_path", ""))
    return ""


def find_outlook_com_safe_evidence_path(payload: dict[str, Any]) -> str:
    log_status = payload.get("log_status", {})
    if not isinstance(log_status, dict):
        log_status = {}
    if payload.get("status") != "READY_FOR_FINAL_EVIDENCE_INTAKE":
        return ""
    if payload.get("ready_for_intake") is not True:
        return ""
    if str(log_status.get("check_exit", "")).strip() != "0":
        return ""
    if str(log_status.get("scan_exit", "")).strip() != "0":
        return ""
    return first_non_empty(
        [
            str(payload.get("evidence_path", "")).strip(),
            str(payload.get("evidence_file", "")).strip(),
        ]
    )


def apply_outlook_com_bundle_override(
    sample_rows: dict[str, dict[str, Any]],
    safe_rows: dict[str, dict[str, Any]],
    final_evidence_path: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if not final_evidence_path:
        return sample_rows, safe_rows
    sample_row = sample_rows.get(OUTLOOK_COM_SCENARIO, {})
    safe_row = safe_rows.get(OUTLOOK_COM_SCENARIO, {})
    return (
        {
            **sample_rows,
            OUTLOOK_COM_SCENARIO: {
                **sample_row,
                "sample_data_status": OUTLOOK_COM_SAMPLE_READY_STATUS,
                "artifact_paths": final_evidence_path,
            },
        },
        {
            **safe_rows,
            OUTLOOK_COM_SCENARIO: {
                **safe_row,
                "safe_suite_status": OUTLOOK_COM_SAFE_READY_STATUS,
                "stdout_paths": final_evidence_path,
            },
        },
    )


def next_action_for(blockers: list[str], status_row: dict[str, Any], rks_row: dict[str, Any] | None) -> str:
    if not blockers:
        return "本番移行候補。最終実行・不可逆操作は実行パケット承認後に進める。"
    if "GLOBAL_SAFE_RUNNER_NOT_PASSED" in blockers:
        return "固定ランナーを再実行し、失敗ステップを修正する。"
    if "CODE_BACKUP_INCOMPLETE" in blockers:
        return "修正実装ファイルの別名保存とhash台帳を更新する。"
    if any(blocker.startswith("SCENARIO_STATUS_GATE") for blocker in blockers):
        current_status = str(status_row.get("current_status", ""))
        if current_status in STATUS_NEXT_ACTIONS_JA:
            return STATUS_NEXT_ACTIONS_JA[current_status]
        return str(status_row.get("next_action", "シナリオの残ゲートを解除する。"))
    if any(blocker.startswith("SAMPLE_OR_DRYRUN") for blocker in blockers):
        return "サンプルデータまたはdry-run証跡を再生成する。"
    if any(blocker.startswith("SAFE_EXECUTION") for blocker in blockers):
        return "safe suiteの該当シナリオを再実行し、exit0/stderr0を確認する。"
    if "RKS_GATE_NOT_READY" in blockers and rks_row is not None:
        return str(rks_row.get("next_safe_action", "RKS open/build/runtime/latest clean logを取得する。"))
    return "残ブロッカーを上から順に解除する。"


def build_row(
    scenario: str,
    global_ready: bool,
    backup_ready: bool,
    status_row: dict[str, Any],
    sample_row: dict[str, Any],
    safe_row: dict[str, Any],
    cost_row: dict[str, Any],
    rks_row: dict[str, Any] | None,
) -> MigrationReadinessRow:
    current_status = str(status_row.get("current_status", "STATUS_ROW_MISSING"))
    sample_gate = str(sample_row.get("sample_data_status", "SAMPLE_ROW_MISSING"))
    safe_gate = str(safe_row.get("safe_suite_status", "SAFE_EXECUTION_ROW_MISSING"))
    cost_scope = str(cost_row.get("cost_evidence_status", "COST_ROW_MISSING"))
    rks_gate, rks_blocker = classify_rks_gate(scenario, rks_row)
    blockers: list[str] = []
    if not global_ready:
        blockers.append("GLOBAL_SAFE_RUNNER_NOT_PASSED")
    if not backup_ready:
        blockers.append("CODE_BACKUP_INCOMPLETE")
    if status_is_blocking(current_status):
        blockers.append(f"SCENARIO_STATUS_GATE:{current_status}")
    if not sample_gate_ready(sample_gate):
        blockers.append(f"SAMPLE_OR_DRYRUN_EVIDENCE_NOT_READY:{sample_gate}")
    if not safe_execution_gate_ready(safe_gate):
        blockers.append(f"SAFE_EXECUTION_EVIDENCE_NOT_READY:{safe_gate}")
    if rks_blocker:
        blockers.append(rks_blocker)
    evidence_paths = "; ".join(
        path
        for path in [
            str(sample_row.get("artifact_paths", "")),
            str(safe_row.get("stdout_paths", "")),
            str(cost_row.get("source", "")),
            str(rks_row.get("primary_source", "")) if rks_row else "",
        ]
        if path
    )
    return MigrationReadinessRow(
        scenario=scenario,
        migration_ready=not blockers,
        current_status=current_status,
        sample_gate=sample_gate,
        safe_execution_gate=safe_gate,
        rks_gate=rks_gate,
        cost_scope=cost_scope,
        source=str(status_row.get("source", "")),
        evidence_paths=evidence_paths,
        blockers=", ".join(blockers),
        next_action=next_action_for(blockers, status_row, rks_row),
    )


def build_payload(sources: dict[str, Path]) -> dict[str, Any]:
    safe_runner = load_json(sources["safe_runner"])
    code_backup = load_json(sources["code_artifact_backup"])
    status_payload = load_json(sources["status_snapshot"])
    sample_payload = load_json(sources["sample_data_map"])
    safe_payload = load_json(sources["safe_execution_map"])
    cost_payload = load_json(sources["business_cost_map"])
    rks_payload = load_json(sources["rks_matrix"])
    bundle_payload = load_json(sources["bundle_evidence_validation"])
    outlook_collect_payload = load_json(
        sources.get(
            "outlook_bundle_evidence_collect",
            Path("__missing_outlook_bundle_evidence_collect.json"),
        )
    )
    status_rows = rows_by_scenario(status_payload, "scenarios")
    sample_rows = rows_by_scenario(sample_payload)
    safe_rows = rows_by_scenario(safe_payload)
    cost_rows = rows_by_scenario(cost_payload)
    sample_rows, safe_rows = apply_outlook_com_bundle_override(
        sample_rows,
        safe_rows,
        first_non_empty(
            [
                find_outlook_com_safe_evidence_path(outlook_collect_payload),
                find_outlook_com_final_evidence_path(bundle_payload),
            ]
        ),
    )
    rks_rows = rks_payload.get("rows", [])
    if not isinstance(rks_rows, list):
        rks_rows = []
    scenarios = sorted(status_rows, key=lambda value: (value.replace("/", "~")))
    global_ready = global_safe_runner_ready(safe_runner)
    backup_ready = code_backup_ready(code_backup)
    rows = [
        build_row(
            scenario,
            global_ready,
            backup_ready,
            status_rows.get(scenario, {}),
            sample_rows.get(scenario, {}),
            safe_rows.get(scenario, {}),
            cost_rows.get(scenario, {}),
            find_rks_row(scenario, rks_rows),
        )
        for scenario in scenarios
    ]
    missing_source_keys = [
        name for name, path in sources.items() if not path.exists()
    ]
    migration_ready_count = sum(1 for row in rows if row.migration_ready)
    blocked_count = len(rows) - migration_ready_count
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "prod_migration_ok": bool(rows) and blocked_count == 0 and not missing_source_keys,
        "final_execution_complete": False,
        "safety": "read-only migration readiness gate; no external or irreversible operation",
        "scenario_count": len(rows),
        "migration_ready_count": migration_ready_count,
        "blocked_scenario_count": blocked_count,
        "missing_source_keys": missing_source_keys,
        "global_safe_runner_ready": global_ready,
        "code_backup_ready": backup_ready,
        "rows": [asdict(row) for row in rows],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# 本番移行OK判定ゲート 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- prod_migration_ok: `{payload['prod_migration_ok']}`",
        f"- final_execution_complete: `{payload['final_execution_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- migration_ready_count: `{payload['migration_ready_count']}`",
        f"- blocked_scenario_count: `{payload['blocked_scenario_count']}`",
        f"- global_safe_runner_ready: `{payload['global_safe_runner_ready']}`",
        f"- code_backup_ready: `{payload['code_backup_ready']}`",
        f"- missing_source_keys: `{', '.join(payload['missing_source_keys'])}`",
        "",
        "## Meaning",
        "",
        "- これは本番移行OK判定であり、最終実行完了ではない。",
        "- 実メール、実印刷、支払実行、本番書込、最終申請は別承認が揃うまで未実行扱い。",
        "- RKSはopen/build/runtime/latest clean logの証跡範囲を明記し、静的OKだけでは本番OKにしない。",
        "",
        "## Scenario Readiness Matrix",
        "",
        "| Scenario | Ready | Current Status | Sample Gate | Safe Execution | RKS Gate | Cost Scope | Blockers | Next Action | Source |",
        "|---|---:|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    "YES" if row["migration_ready"] else "NO",
                    str(row["current_status"]).replace("|", "/"),
                    str(row["sample_gate"]).replace("|", "/"),
                    str(row["safe_execution_gate"]).replace("|", "/"),
                    str(row["rks_gate"]).replace("|", "/"),
                    str(row["cost_scope"]).replace("|", "/"),
                    str(row["blockers"]).replace("|", "/") if row["blockers"] else "-",
                    str(row["next_action"]).replace("|", "/"),
                    f"`{row['source']}`" if row["source"] else "-",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def build_ready_candidate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload["rows"]
    assert isinstance(rows, list)
    return [
        {
            **row,
            "safe_scope": SAFE_SCOPE_LABEL,
            "no_irreversible_operations": NO_IRREVERSIBLE_OPERATIONS_LABEL,
        }
        for row in rows
        if isinstance(row, dict) and row.get("migration_ready") is True
    ]


def build_blocker_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload["rows"]
    assert isinstance(rows, list)
    return [
        {
            **row,
            "required_before_migration": row.get("next_action", ""),
        }
        for row in rows
        if isinstance(row, dict) and row.get("migration_ready") is not True
    ]


def build_disposition_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload["rows"]
    assert isinstance(rows, list)
    disposition_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        migration_ready = row.get("migration_ready") is True
        disposition_rows.append(
            {
                **row,
                "kit_inclusion_status": (
                    "INCLUDE_AS_SAFE_SCOPE_CANDIDATE"
                    if migration_ready
                    else "INCLUDE_AS_HOLD_OR_REVIEW_ONLY"
                ),
                "executable_in_customer_kit": "YES_WITH_SAFE_SCOPE_ONLY" if migration_ready else "NO",
                "allowed_scope": SAFE_SCOPE_LABEL if migration_ready else HOLD_SCOPE_LABEL,
                "prohibited_operations": PROHIBITED_OPERATIONS_LABEL,
            }
        )
    return disposition_rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({fieldname: row.get(fieldname, "") for fieldname in fieldnames})


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate production migration readiness gate.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(DEFAULT_SOURCES)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "prod_migration_readiness.json"
    md_path = args.out_dir / "prod_migration_readiness.md"
    ready_csv_path = args.out_dir / "prod_migration_ready_candidates.csv"
    blockers_csv_path = args.out_dir / "prod_migration_blockers.csv"
    disposition_csv_path = args.out_dir / "prod_migration_disposition.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_csv(ready_csv_path, build_ready_candidate_rows(payload), READY_CANDIDATE_FIELDNAMES)
    write_csv(blockers_csv_path, build_blocker_rows(payload), BLOCKER_FIELDNAMES)
    write_csv(disposition_csv_path, build_disposition_rows(payload), DISPOSITION_FIELDNAMES)
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
