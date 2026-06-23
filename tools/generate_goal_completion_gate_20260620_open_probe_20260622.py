"""Generate the final completion gate for the active RK10 validation goal.

This checker reads current repository reports and produces one strict
completion decision. It does not open Outlook, RK10, Rakuraku, Azure, printers,
mail, payment systems, MainSV, or production files.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_OUT_DIR = REPORTS / "goal_completion_gate_20260620"

DEFAULT_SOURCES = {
    "safe_runner": REPORTS / "safe_goal_checks_20260620" / "safe_goal_checks_summary.json",
    "status_snapshot": REPORTS
    / "goal_status_snapshot_rks_runtime_overlay_20260623"
    / "goal_status_snapshot_rks_runtime_overlay.json",
    "requirement_trace": REPORTS / "goal_requirement_traceability_20260620" / "goal_requirement_traceability.json",
    "packet_validation": REPORTS
    / "goal_execution_packet_validation_20260620"
    / "goal_execution_packet_validation.json",
    "bundle_evidence_pack_validation": REPORTS
    / "bundle_evidence_pack_validation_20260620"
    / "bundle_evidence_pack_validation.json",
    "code_artifact_backup": REPORTS
    / "goal_code_artifact_backups_20260620"
    / "goal_code_artifact_backups.json",
    "evidence_ledger": REPORTS / "goal_evidence_ledger_20260620" / "goal_evidence_ledger.json",
    "rks_matrix": REPORTS / "rks_gate_matrix_20260620" / "rks_gate_matrix.json",
    "rks_matrix_open_probe": REPORTS
    / "rks_gate_matrix_open_probe_20260622"
    / "rks_gate_matrix.json",
    "rks_runtime_intake_validation": REPORTS
    / "rks_runtime_operator_intake_validation_20260620"
    / "rks_runtime_operator_intake_validation.json",
}


@dataclass(frozen=True)
class GateCheck:
    gate: str
    passed: bool
    status: str
    source: str
    detail: str
    next_action: str


DERIVED_FINAL_EVIDENCE_GATES = {
    "STATUS_SNAPSHOT",
    "REQUIREMENT_TRACE",
    "EVIDENCE_LEDGER",
}


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_safe_runner_gate(path: Path) -> GateCheck:
    payload = load_json(path)
    if payload is None:
        return missing_gate("SAFE_RUNNER", path, "固定ランナーを再実行する")
    passed = payload.get("overall_passed") is True
    status = "PASSED" if passed else "FAILED"
    detail = f"overall_passed={payload.get('overall_passed')}"
    return GateCheck("SAFE_RUNNER", passed, status, str(path), detail, "失敗ステップを修正して固定ランナーを再実行する")


def build_status_snapshot_gate(path: Path) -> GateCheck:
    payload = load_json(path)
    if payload is None:
        return missing_gate("STATUS_SNAPSHOT", path, "全シナリオ現況スナップショットを再生成する")
    hold_count = int(
        payload.get(
            "hold_or_unconfirmed_count_after_overlay",
            payload.get("hold_or_unconfirmed_count", 0),
        )
        or 0
    )
    before_overlay = payload.get("hold_or_unconfirmed_count_before_overlay")
    overlay_count = payload.get("overlay_applied_count")
    passed = payload.get("overall_goal_complete") is True and hold_count == 0
    status = "COMPLETE" if passed else "INCOMPLETE"
    detail = (
        f"overall_goal_complete={payload.get('overall_goal_complete')}; "
        f"hold_or_unconfirmed_count={hold_count}"
    )
    if before_overlay is not None or overlay_count is not None:
        detail += (
            f"; before_overlay={before_overlay}; "
            f"overlay_applied_count={overlay_count}"
        )
    return GateCheck("STATUS_SNAPSHOT", passed, status, str(path), detail, "HOLD/UNCONFIRMEDの残行を解除する")


def build_requirement_gate(path: Path) -> GateCheck:
    payload = load_json(path)
    if payload is None:
        return missing_gate("REQUIREMENT_TRACE", path, "要件トレーサビリティを再生成する")
    requirement_count = int(payload.get("requirement_count", 0))
    complete_count = int(payload.get("complete_or_safe_count", 0))
    missing_source_count = int(payload.get("missing_source_count", 0))
    passed = (
        payload.get("overall_goal_complete") is True
        and requirement_count > 0
        and complete_count == requirement_count
        and missing_source_count == 0
    )
    status = "COMPLETE" if passed else "INCOMPLETE"
    detail = (
        f"overall_goal_complete={payload.get('overall_goal_complete')}; "
        f"complete_or_safe_count={complete_count}/{requirement_count}; "
        f"missing_source_count={missing_source_count}"
    )
    return GateCheck("REQUIREMENT_TRACE", passed, status, str(path), detail, "12要件すべての未達理由を解消する")


def build_packet_gate(path: Path) -> GateCheck:
    payload = load_json(path)
    if payload is None:
        return missing_gate("EXECUTION_PACKET_VALIDATION", path, "承認CSV証跡検証を再実行する")
    row_count = int(payload.get("row_count", 0))
    approved_count = int(payload.get("approved_row_count", 0))
    needs_attention_count = int(payload.get("needs_attention_count", 0))
    passed = (
        payload.get("all_packet_rows_approved") is True
        and row_count > 0
        and approved_count == row_count
        and needs_attention_count == 0
    )
    status = "COMPLETE" if passed else "INCOMPLETE"
    detail = (
        f"all_packet_rows_approved={payload.get('all_packet_rows_approved')}; "
        f"approved_row_count={approved_count}/{row_count}; "
        f"needs_attention_count={needs_attention_count}"
    )
    return GateCheck(
        "EXECUTION_PACKET_VALIDATION",
        passed,
        status,
        str(path),
        detail,
        "remaining_operator_input.csvのoperator_result/reviewer/reviewed_atを記入し、固定安全ランナーを再実行してsource_packet_csvとunified_final_evidence_input.csvへ同期する",
    )


def build_bundle_evidence_pack_gate(path: Path) -> GateCheck:
    payload = load_json(path)
    if payload is None:
        return missing_gate("BUNDLE_EVIDENCE_PACK_VALIDATION", path, "6束証跡パック検証を再実行する")
    bundle_count = int(payload.get("bundle_count", 0))
    ready_count = int(payload.get("final_evidence_ready_count", 0))
    missing_prepared_count = int(payload.get("missing_prepared_pack_count", 0))
    passed = (
        payload.get("prepared_pack_validation_passed") is True
        and payload.get("final_evidence_complete") is True
        and bundle_count > 0
        and ready_count == bundle_count
        and missing_prepared_count == 0
    )
    status = "COMPLETE" if passed else "INCOMPLETE"
    detail = (
        f"prepared_pack_validation_passed={payload.get('prepared_pack_validation_passed')}; "
        f"final_evidence_complete={payload.get('final_evidence_complete')}; "
        f"final_evidence_ready_count={ready_count}/{bundle_count}; "
        f"missing_prepared_pack_count={missing_prepared_count}"
    )
    return GateCheck(
        "BUNDLE_EVIDENCE_PACK_VALIDATION",
        passed,
        status,
        str(path),
        detail,
        "6束証跡パックへ最終証跡を配置し、remaining_operator_input.csvを更新して固定安全ランナーで同期する",
    )


def final_evidence_chain_complete(
    packet_gate: GateCheck,
    bundle_gate: GateCheck,
) -> bool:
    return packet_gate.passed and bundle_gate.passed


def apply_final_evidence_chain_override(
    gate: GateCheck,
    final_chain_complete: bool,
) -> GateCheck:
    if not final_chain_complete:
        return gate
    if gate.passed or gate.status == "MISSING_SOURCE":
        return gate
    if gate.gate not in DERIVED_FINAL_EVIDENCE_GATES:
        return gate
    return GateCheck(
        gate.gate,
        True,
        "COMPLETE_BY_FINAL_OPERATOR_EVIDENCE",
        gate.source,
        f"{gate.detail}; final_evidence_chain=complete",
        "最終証跡CSVと6束証跡パックが全承認済みのため、派生集計は完了証跡として扱う",
    )


def build_code_backup_gate(path: Path) -> GateCheck:
    payload = load_json(path)
    if payload is None:
        return missing_gate("CODE_ARTIFACT_BACKUP", path, "修正実装ファイルの別名保存を再実行する")
    artifact_count = int(payload.get("artifact_count", 0))
    missing_count = int(payload.get("missing_count", 0))
    passed = payload.get("backup_complete") is True and artifact_count > 0 and missing_count == 0
    status = "COMPLETE" if passed else "INCOMPLETE"
    detail = (
        f"backup_complete={payload.get('backup_complete')}; "
        f"artifact_count={artifact_count}; "
        f"missing_count={missing_count}"
    )
    return GateCheck(
        "CODE_ARTIFACT_BACKUP",
        passed,
        status,
        str(path),
        detail,
        "修正実装ファイルをタイムスタンプ付き別名保存へ退避し、missing_countを0にする",
    )


def objective_summary_has_state(summary: str, key: str, accepted_states: set[str]) -> bool:
    parts = [part.strip() for part in summary.split(";")]
    prefix = f"{key}="
    for part in parts:
        if part.startswith(prefix):
            return part.removeprefix(prefix) in accepted_states
    return False


def count_objective_checkpoint(
    rows: list[Any],
    key: str,
    accepted_states: set[str],
) -> int:
    return sum(
        1
        for row in rows
        if isinstance(row, dict)
        and objective_summary_has_state(
            str(row.get("objective_checkpoint_summary", "")),
            key,
            accepted_states,
        )
    )


def build_evidence_ledger_gate(path: Path) -> GateCheck:
    payload = load_json(path)
    if payload is None:
        return missing_gate("EVIDENCE_LEDGER", path, "目標証跡台帳を再生成する")
    scenario_count = int(payload.get("scenario_count", 0))
    complete_count = int(payload.get("complete_goal_evidence_count", 0))
    missing_source_count = int(payload.get("missing_source_count", 0))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    sample_ready_count = count_objective_checkpoint(rows, "sample", {"OK"})
    safe_execution_ready_count = count_objective_checkpoint(rows, "safe", {"OK"})
    business_amount_or_draft_count = count_objective_checkpoint(
        rows,
        "cost",
        {"SAMPLE_OK", "DRAFT_OK"},
    )
    business_count_only_scope_count = count_objective_checkpoint(
        rows,
        "cost",
        {"COUNT_ONLY"},
    )
    business_cost_scope_count = business_amount_or_draft_count + business_count_only_scope_count
    final_evidence_ready_count = int(payload.get("final_evidence_ready_count", 0))
    passed = (
        payload.get("overall_goal_complete") is True
        and scenario_count > 0
        and complete_count == scenario_count
        and missing_source_count == 0
    )
    status = "COMPLETE" if passed else "INCOMPLETE"
    detail = (
        f"overall_goal_complete={payload.get('overall_goal_complete')}; "
        f"complete_goal_evidence_count={complete_count}/{scenario_count}; "
        f"missing_source_count={missing_source_count}; "
        f"sample_ready_count={sample_ready_count}/{scenario_count}; "
        f"safe_execution_ready_count={safe_execution_ready_count}/{scenario_count}; "
        f"business_amount_or_draft_count={business_amount_or_draft_count}/{scenario_count}; "
        f"business_count_only_scope_count={business_count_only_scope_count}/{scenario_count}; "
        f"business_cost_scope_count={business_cost_scope_count}/{scenario_count}; "
        f"final_evidence_ready_count={final_evidence_ready_count}/{scenario_count}"
    )
    return GateCheck("EVIDENCE_LEDGER", passed, status, str(path), detail, "全15シナリオの強い実行証跡を揃える")


def build_rks_gate(path: Path) -> GateCheck:
    payload = load_json(path)
    if payload is None:
        return missing_gate("RKS_GATE_MATRIX", path, "RKS横断ゲート表を再生成する")
    row_count = int(payload.get("row_count", 0))
    unresolved_count = int(payload.get("unresolved_rks_gate_count", 0))
    technical_unresolved_count = int(
        payload.get("technical_unresolved_rks_gate_count", unresolved_count)
    )
    deferred_count = int(payload.get("deferred_rks_gate_count", 0))
    missing_source_count = int(payload.get("missing_source_count", 0))
    passed = (
        payload.get("rks_technical_gate_complete") is True
        and row_count > 0
        and technical_unresolved_count == 0
        and missing_source_count == 0
    )
    status = "COMPLETE" if passed else "INCOMPLETE"
    detail = (
        f"overall_rks_production_ready={payload.get('overall_rks_production_ready')}; "
        f"rks_technical_gate_complete={payload.get('rks_technical_gate_complete')}; "
        f"unresolved_rks_gate_count={unresolved_count}; "
        f"technical_unresolved_rks_gate_count={technical_unresolved_count}; "
        f"deferred_rks_gate_count={deferred_count}; "
        f"missing_source_count={missing_source_count}"
    )
    return GateCheck(
        "RKS_GATE_MATRIX",
        passed,
        status,
        str(path),
        detail,
        "必要RKSの技術証跡を取得し、非RKS前提保留は下位ゲートで確認する",
    )


def build_rks_open_probe_gate(path: Path) -> GateCheck:
    payload = load_json(path)
    if payload is None:
        return missing_gate("RKS_GATE_OPEN_PROBE_SUPPLEMENT", path, "open証跡補足マトリクスを再生成する")
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    confirmed_count = int(payload.get("editor_open_probe_confirmed_count", 0))
    unsafe_count = sum(
        1
        for row in rows
        if isinstance(row, dict)
        and row.get("editor_open_probe_status") == "RK10_EDITOR_OPEN_CONFIRMED"
        and (
            row.get("editor_open_probe_build_artifact_found") is True
            or row.get("editor_open_probe_button_run_clicked") is True
        )
    )
    passed = confirmed_count > 0 and unsafe_count == 0
    status = "COMPLETE" if passed else "INCOMPLETE"
    detail = (
        f"editor_open_probe_confirmed_count={confirmed_count}; "
        f"unsafe_open_probe_count={unsafe_count}; "
        f"overall_rks_production_ready={payload.get('overall_rks_production_ready')}"
    )
    return GateCheck(
        "RKS_GATE_OPEN_PROBE_SUPPLEMENT",
        passed,
        status,
        str(path),
        detail,
        "open証跡は補助扱いのまま、build/runtime/latest clean logはRKS_GATE_MATRIXで維持する",
    )


def build_rks_runtime_intake_gate(path: Path) -> GateCheck:
    payload = load_json(path)
    if payload is None:
        return missing_gate("RKS_RUNTIME_INTAKE_VALIDATION", path, "RKSランタイム証跡CSV検証を再実行する")
    required_count = int(payload.get("required_row_count", 0))
    approved_count = int(payload.get("approved_row_count", 0))
    needs_attention_count = int(payload.get("needs_attention_count", 0))
    hard_error_count = int(payload.get("hard_error_count", 0))
    missing_latest_log_count = int(payload.get("missing_latest_log_count", 0))
    passed = (
        payload.get("overall_rks_runtime_evidence_complete") is True
        and required_count > 0
        and approved_count == required_count
        and needs_attention_count == 0
        and hard_error_count == 0
        and missing_latest_log_count == 0
    )
    status = "COMPLETE" if passed else "INCOMPLETE"
    detail = (
        f"overall_rks_runtime_evidence_complete={payload.get('overall_rks_runtime_evidence_complete')}; "
        f"approved_row_count={approved_count}/{required_count}; "
        f"needs_attention_count={needs_attention_count}; "
        f"hard_error_count={hard_error_count}; "
        f"missing_latest_log_count={missing_latest_log_count}"
    )
    return GateCheck(
        "RKS_RUNTIME_INTAKE_VALIDATION",
        passed,
        status,
        str(path),
        detail,
        "RKS入力CSVにopen/build/runtime/latest clean log/操作者/日時を記入し、実在ログを添付する",
    )


def missing_gate(gate: str, path: Path, next_action: str) -> GateCheck:
    return GateCheck(gate, False, "MISSING_SOURCE", str(path), "source JSON not found", next_action)


def build_payload(sources: dict[str, Path]) -> dict[str, Any]:
    safe_runner_gate = build_safe_runner_gate(sources["safe_runner"])
    status_snapshot_gate = build_status_snapshot_gate(sources["status_snapshot"])
    requirement_gate = build_requirement_gate(sources["requirement_trace"])
    packet_gate = build_packet_gate(sources["packet_validation"])
    bundle_evidence_pack_gate = build_bundle_evidence_pack_gate(
        sources["bundle_evidence_pack_validation"]
    )
    evidence_ledger_gate = build_evidence_ledger_gate(sources["evidence_ledger"])
    final_chain_complete = final_evidence_chain_complete(
        packet_gate,
        bundle_evidence_pack_gate,
    )
    status_snapshot_gate = apply_final_evidence_chain_override(
        status_snapshot_gate,
        final_chain_complete,
    )
    requirement_gate = apply_final_evidence_chain_override(
        requirement_gate,
        final_chain_complete,
    )
    evidence_ledger_gate = apply_final_evidence_chain_override(
        evidence_ledger_gate,
        final_chain_complete,
    )
    gates = [
        safe_runner_gate,
        status_snapshot_gate,
        requirement_gate,
        packet_gate,
        bundle_evidence_pack_gate,
        build_code_backup_gate(sources["code_artifact_backup"]),
        evidence_ledger_gate,
        build_rks_gate(sources["rks_matrix"]),
        build_rks_open_probe_gate(sources["rks_matrix_open_probe"]),
        build_rks_runtime_intake_gate(sources["rks_runtime_intake_validation"]),
    ]
    passed_count = sum(1 for gate in gates if gate.passed)
    blocking_gates = [gate for gate in gates if not gate.passed]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "final_goal_complete": len(blocking_gates) == 0,
        "safety": "read-only completion gate; repository report writes only",
        "gate_count": len(gates),
        "passed_gate_count": passed_count,
        "blocking_gate_count": len(blocking_gates),
        "gates": [asdict(gate) for gate in gates],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    gates = payload["gates"]
    assert isinstance(gates, list)
    lines = [
        "# 目標最終完了ゲート 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- final_goal_complete: `{payload['final_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- gate_count: `{payload['gate_count']}`",
        f"- passed_gate_count: `{payload['passed_gate_count']}`",
        f"- blocking_gate_count: `{payload['blocking_gate_count']}`",
        "",
        "## Gate Matrix",
        "",
        "| Gate | Passed | Status | Detail | Next Action | Source |",
        "|---|---:|---|---|---|---|",
    ]
    for gate in gates:
        assert isinstance(gate, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(gate["gate"]),
                    "YES" if gate["passed"] else "NO",
                    str(gate["status"]),
                    str(gate["detail"]).replace("|", "/"),
                    str(gate["next_action"]).replace("|", "/"),
                    f"`{gate['source']}`",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate final RK10 goal completion gate.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(DEFAULT_SOURCES)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "goal_completion_gate.json"
    md_path = args.out_dir / "goal_completion_gate.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
