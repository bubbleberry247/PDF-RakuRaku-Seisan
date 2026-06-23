"""Generate requirement traceability for the active RK10 validation goal.

The traceability report maps the user's full objective to current authoritative
evidence and remaining proof gaps. It is read-only and does not open or operate
Outlook, RK10, Rakuraku, Azure, printers, mail, payment systems, MainSV, or
production files.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "goal_requirement_traceability_20260620"

SAFE_RUNNER_SUMMARY = ROOT / "plans" / "reports" / "safe_goal_checks_20260620" / "safe_goal_checks_summary.md.numbered"
SAFE_SUITE_REPORT = ROOT / "plans" / "reports" / "other_scenarios_safe_suite_recheck_20260620.md.numbered"
SAMPLE_DATA_MAP = ROOT / "plans" / "reports" / "sample_data_evidence_map_20260620" / "sample_data_evidence_map.md.numbered"
BUSINESS_COST_MAP = ROOT / "plans" / "reports" / "business_cost_evidence_map_20260620" / "business_cost_evidence_map.md.numbered"
BUSINESS_COST_MAP_JSON = ROOT / "plans" / "reports" / "business_cost_evidence_map_20260620" / "business_cost_evidence_map.json"
GOAL_STATUS_SNAPSHOT = ROOT / "plans" / "reports" / "goal_status_snapshot_20260620" / "goal_status_snapshot.md.numbered"
RKS_GATE_MATRIX = ROOT / "plans" / "reports" / "rks_gate_matrix_20260620" / "rks_gate_matrix.md.numbered"
RKS_GATE_MATRIX_JSON = ROOT / "plans" / "reports" / "rks_gate_matrix_20260620" / "rks_gate_matrix.json"
GOAL_UNBLOCK_BOARD = ROOT / "plans" / "reports" / "goal_unblock_board_20260620" / "goal_unblock_board.md.numbered"
GOAL_EXECUTION_PACKET = ROOT / "plans" / "reports" / "goal_execution_packet_20260620" / "goal_execution_packet.md.numbered"
BUNDLE_OPERATOR_SHEET = ROOT / "plans" / "reports" / "bundle_operator_sheet_20260620" / "bundle_operator_sheet.md.numbered"
BUNDLE_EVIDENCE_INTAKE_SYNC = ROOT / "plans" / "reports" / "bundle_evidence_intake_sync_20260620" / "bundle_evidence_intake_sync.md.numbered"
BUNDLE_EVIDENCE_INTAKE_SYNC_JSON = ROOT / "plans" / "reports" / "bundle_evidence_intake_sync_20260620" / "bundle_evidence_intake_sync.json"
EXTERNAL_APPROVAL_RUNBOOK = ROOT / "plans" / "reports" / "external_approval_runbook_20260620" / "external_approval_runbook.md.numbered"
GOAL_EVIDENCE_LEDGER = ROOT / "plans" / "reports" / "goal_evidence_ledger_20260620" / "goal_evidence_ledger.md.numbered"
GOAL_EVIDENCE_ACTUAL_TRACE_OVERLAY = (
    ROOT
    / "plans"
    / "reports"
    / "goal_evidence_actual_trace_overlay_20260623"
    / "goal_evidence_actual_trace_overlay.md.numbered"
)
GOAL_EVIDENCE_ACTUAL_TRACE_OVERLAY_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "goal_evidence_actual_trace_overlay_20260623"
    / "goal_evidence_actual_trace_overlay.json"
)
GOAL_COMPLETION_AUDIT = (
    ROOT
    / "plans"
    / "reports"
    / "goal_completion_audit_20260620"
    / "goal_completion_audit.md.numbered"
)
APPROVAL_MINIMIZATION = ROOT / "plans" / "reports" / "approval_minimization_20260620.md.numbered"
CODE_ARTIFACT_BACKUPS = ROOT / "plans" / "reports" / "goal_code_artifact_backups_20260620" / "goal_code_artifact_backups.md.numbered"
BUNDLE_EVIDENCE_VALIDATION_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_pack_validation_20260620"
    / "bundle_evidence_pack_validation.json"
)
OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "outlook_bundle_evidence_collect_20260620"
    / "outlook_bundle_evidence_collect.json"
)
OBJECTIVE_COMPLETION_AUDIT_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "objective_completion_audit_20260623"
    / "objective_completion_audit.json"
)


@dataclass(frozen=True)
class RequirementTraceRow:
    requirement_id: str
    requirement: str
    current_status: str
    authoritative_evidence: str
    remaining_gap: str
    next_evidence_needed: str
    source_exists: bool


def source_exists(path: Path) -> bool:
    return path.exists()


def evidence_sources_exist(evidence_text: str) -> bool:
    paths = [chunk.strip() for chunk in evidence_text.split(";") if chunk.strip()]
    if not paths:
        return False
    return all(Path(path).exists() for path in paths)


def row(
    requirement_id: str,
    requirement: str,
    current_status: str,
    authoritative_evidence: Path,
    remaining_gap: str,
    next_evidence_needed: str,
) -> RequirementTraceRow:
    return RequirementTraceRow(
        requirement_id=requirement_id,
        requirement=requirement,
        current_status=current_status,
        authoritative_evidence=str(authoritative_evidence),
        remaining_gap=remaining_gap,
        next_evidence_needed=next_evidence_needed,
        source_exists=source_exists(authoritative_evidence),
    )


def summarize_business_cost_amount_evidence(path: Path = BUSINESS_COST_MAP_JSON) -> str:
    if not path.exists():
        return "sample/dry-run/mock-apply金額は未集約"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return "sample/dry-run/mock-apply金額は未集約"
    scenarios = [
        str(item.get("scenario", ""))
        for item in rows
        if isinstance(item, dict)
        and item.get("validation_result") == "PASS"
        and isinstance(item.get("total_amount_yen"), int)
        and str(item.get("scenario", ""))
    ]
    if not scenarios:
        return "sample/dry-run/mock-apply金額は未集約"
    return f"{'/'.join(scenarios)}のsample/dry-run/mock-apply金額は再計算済み"


def summarize_goal_actual_trace_overlay(
    path: Path = GOAL_EVIDENCE_ACTUAL_TRACE_OVERLAY_JSON,
) -> str:
    if not path.exists():
        return "客先安全入口のBAT→PowerShell→PY/tool実行トレースoverlayは未集約"
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenario_count = int(payload.get("scenario_count", 0) or 0)
    trace_ready_count = int(payload.get("trace_ready_scenario_count", 0) or 0)
    trace_missing_count = int(payload.get("trace_missing_scenario_count", 0) or 0)
    script_missing_count = int(payload.get("trace_script_missing_count", 0) or 0)
    return (
        "客先安全入口のBAT→PowerShell→PY/tool実行トレースは"
        f"{trace_ready_count}/{scenario_count}シナリオ接続済み、"
        f"trace_missing_scenario_count={trace_missing_count}、"
        f"trace_script_missing_count={script_missing_count}"
    )


def summarize_rks_gate_matrix(path: Path = RKS_GATE_MATRIX_JSON) -> str:
    if not path.exists():
        return "RKSゲートJSONは未集約で、open/build/runtime/latest clean logの現況は未確認"
    payload = json.loads(path.read_text(encoding="utf-8"))
    technical_complete = payload.get("rks_technical_gate_complete") is True
    technical_unresolved_count = int(payload.get("technical_unresolved_rks_gate_count", 0) or 0)
    deferred_count = int(payload.get("deferred_rks_gate_count", 0) or 0)
    production_ready = payload.get("overall_rks_production_ready") is True
    return (
        "RKS open/build/runtime/latest clean logの技術ゲートは"
        f"rks_technical_gate_complete={technical_complete}、"
        f"technical_unresolved_rks_gate_count={technical_unresolved_count}まで集約済み。"
        f"ただしoverall_rks_production_ready={production_ready}、"
        f"deferred_rks_gate_count={deferred_count}で、"
        "本番業務費用・外部HOLD・入口選定・operator final evidenceは未完"
    )


def is_outlook_com_bundle_final_evidence_ready(path: Path | None = None) -> bool:
    target_path = path or BUNDLE_EVIDENCE_VALIDATION_JSON
    if not target_path.exists():
        return False
    payload = json.loads(target_path.read_text(encoding="utf-8"))
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return False
    return any(
        isinstance(item, dict)
        and item.get("bundle") == "OUTLOOK_COM_BUNDLE"
        and item.get("final_evidence_ready") is True
        for item in checks
    )


def is_outlook_com_bundle_ready_to_sync(path: Path | None = None) -> bool:
    target_path = path or BUNDLE_EVIDENCE_INTAKE_SYNC_JSON
    if not target_path.exists():
        return False
    payload = json.loads(target_path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    if not isinstance(results, list):
        return False
    return any(
        isinstance(item, dict)
        and item.get("bundle") == "OUTLOOK_COM_BUNDLE"
        and item.get("ready_to_sync") is True
        for item in results
    )


def is_outlook_com_bundle_safe_evidence_ready(path: Path | None = None) -> bool:
    target_path = path or OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON
    if not target_path.exists():
        return False
    payload = json.loads(target_path.read_text(encoding="utf-8"))
    log_status = payload.get("log_status", {})
    if not isinstance(log_status, dict):
        log_status = {}
    return (
        payload.get("status") == "READY_FOR_FINAL_EVIDENCE_INTAKE"
        and payload.get("ready_for_intake") is True
        and str(log_status.get("check_exit", "")).strip() == "0"
        and str(log_status.get("scan_exit", "")).strip() == "0"
    )


def build_rows() -> list[RequirementTraceRow]:
    business_cost_amount_summary = summarize_business_cost_amount_evidence()
    actual_trace_summary = summarize_goal_actual_trace_overlay()
    rks_gate_summary = summarize_rks_gate_matrix()
    outlook_evidence_ready = is_outlook_com_bundle_final_evidence_ready()
    outlook_safe_evidence_ready = is_outlook_com_bundle_safe_evidence_ready()
    outlook_ready_to_sync = is_outlook_com_bundle_ready_to_sync()
    if outlook_ready_to_sync:
        req01_gap = "15シナリオのサンプル/テスト/dry-run証跡は集約済み。12/13はOutlook COMのdry-run/no-print/no-mail証跡取込済み"
        req01_next = "残バンドルの最終証跡、業務金額差異0、RKS runtime証跡を揃える。実印刷・実送信は別ゲート"
        req11_gap = "6束入力シートと最終証跡取り込み同期は追加済み。OUTLOOK_COM_BUNDLEはfinal evidence取込済みで、残5バンドルの証跡入力が未完"
        req11_next = "残5バンドルのfinal_evidence_intake.csvへ証跡・担当者・日時を記入し、固定ランナーで6束入力シートへ自動反映"
        req12_gap = "6バンドルへ集約済み。OUTLOOK_COM_BUNDLEはfinal evidence取込済みだが、残5バンドルのHOLD解除入力・外部環境復旧は未完"
        req12_next = "44/70/71/RK10/業務データ各バンドルの承認と実行証跡"
    elif outlook_safe_evidence_ready or outlook_evidence_ready:
        req01_gap = "15シナリオのサンプル/テスト/dry-run証跡は集約済み。12/13はOutlook COMのdry-run/no-print/no-mail証跡配置済みだが、operator_result/reviewer/reviewed_at未記入で最終取込は未完"
        req01_next = "残バンドルの最終承認フィールド、業務金額差異0、RKS runtime証跡を揃える。実印刷・実送信は別ゲート"
        req11_gap = "6束入力シートと最終証跡取り込み同期は追加済みだが、final_evidence_path/operator_result/reviewer/reviewed_atは未記入"
        req11_next = "現場実行後に各Bundleのfinal_evidence_intake.csvへ証跡を記入し、固定ランナーで6束入力シートへ自動反映"
        req12_gap = "6バンドルへ集約済み。OUTLOOK_COM_BUNDLEは安全証跡配置済みで、operator_result/reviewer/reviewed_atの最終記入のみ未完。残5バンドルはHOLD解除入力・外部環境復旧が未完"
        req12_next = "44/70/71/RK10/業務データ各バンドルの承認と実行証跡。12-13はoperator_result/reviewer/reviewed_atのみ"
    else:
        req01_gap = "15シナリオのサンプル/テスト/dry-run証跡は集約済みだが、12/13はOutlook COM別HOLDで最新refresh待ち"
        req01_next = "12/13 Outlook COM exit 0後のdry-run/no-print/no-mail証跡と最新サンプルマップ"
        req11_gap = "6束入力シートと最終証跡取り込み同期は追加済みだが、final_evidence_path/operator_result/reviewer/reviewed_atは未記入"
        req11_next = "現場実行後に各Bundleのfinal_evidence_intake.csvへ証跡を記入し、固定ランナーで6束入力シートへ自動反映"
        req12_gap = "6バンドルへ集約済みだが、HOLD解除入力・外部環境復旧は未完"
        req12_next = "44/70/71/12-13/RK10/業務データ各バンドルの承認と実行証跡"
    return [
        row(
            "REQ-01",
            "全シナリオサンプルデータを用意する",
            "PARTIAL_OK",
            SAMPLE_DATA_MAP,
            req01_gap,
            req01_next,
        ),
        row(
            "REQ-02",
            "PYファイル・Pythonツールを実行してエラーなしを確認する",
            "PARTIAL_OK",
            GOAL_EVIDENCE_ACTUAL_TRACE_OVERLAY,
            f"{actual_trace_summary}。固定ランナー範囲も通過しているが、実業務費用の全量・外部操作は未実行",
            "各バンドル実行後の固定ランナー再実行ログと該当ツールの実行ログ",
        ),
        row(
            "REQ-03",
            "RKSファイルを実際に実行して確認する",
            "NOT_PROVEN",
            RKS_GATE_MATRIX,
            f"{rks_gate_summary}。full production scopeのRKS実行確認は未証明",
            "deferred行のHOLD解除/入口選定後、必要RKSだけmetadata guard、RK10 open/build、safe-stop/runtime、latest clean logを取り直す",
        ),
        row(
            "REQ-04",
            "実際の業務費用を稼働させる",
            "NOT_PROVEN",
            BUSINESS_COST_MAP,
            f"{business_cost_amount_summary}だが、本番業務費用の全量・不可逆操作は未実行",
            "実対象データ、件数/金額、停止条件、承認者、実行後ログ、差異0証跡",
        ),
        row(
            "REQ-05",
            "エラーなく終了することを確認する",
            "PARTIAL_OK",
            GOAL_EVIDENCE_ACTUAL_TRACE_OVERLAY,
            f"{actual_trace_summary}。safe suiteや固定ランナーは成功。ただし本番業務費用・RKS runtime・外部操作は未完",
            "HOLD解除後の各バンドル実行ログ、stderr/キーワード監査、latest clean log",
        ),
        row(
            "REQ-06",
            "エラー発生時は原因を究明する",
            "PARTIAL_OK",
            GOAL_COMPLETION_AUDIT,
            "既知原因は分類済みだが、未解除HOLDや今後の実行エラーは未解決",
            "新規エラーごとの再現ログ、原因分類、対策、再実行成功ログ",
        ),
        row(
            "REQ-07",
            "対策・修正実装を行う",
            "PARTIAL_OK",
            GOAL_COMPLETION_AUDIT,
            "55/38/12-13など代表対策はあるが、全シナリオ・全HOLD解除までは未完",
            "修正差分、py_compile/pytest/dry-run、移行キット反映、再発防止証跡",
        ),
        row(
            "REQ-08",
            "修正実装したファイルは別名保存する",
            "PARTIAL_OK",
            CODE_ARTIFACT_BACKUPS,
            "固定ランナー対象のhelper code/testは別名保存対象へ入れたが、本番側ファイルや今後の修正分は継続記録が必要",
            "本番側を修正するたびにbefore/after、別名バックアップ、manifest/hash、反映レポートを追加する",
        ),
        row(
            "REQ-09",
            "最終ログ報告を出す",
            "PARTIAL_OK",
            GOAL_EVIDENCE_LEDGER,
            "現時点の台帳・パケット・監査はあるが、全HOLD解除後の最終報告は未作成",
            "complete_goal_evidence_countがscenario_countに一致する最終証跡台帳と完了報告",
        ),
        row(
            "REQ-10",
            "承認回数を減らして進める",
            "OK_FOR_BUNDLE_RUNBOOK_ONLY",
            EXTERNAL_APPROVAL_RUNBOOK,
            "安全チェックと外部承認束runbookは一括化済み。ただしGUI/Outlook/RK10/本番操作はBundle単位の別承認が必要",
            "OUTLOOK_COM_BUNDLEなど、必要Bundleだけ1回承認して実行パケットCSVへ証跡記録",
        ),
        row(
            "REQ-11",
            "現場実行後の証跡を回収できる状態にする",
            "PARTIAL_OK",
            BUNDLE_EVIDENCE_INTAKE_SYNC,
            req11_gap,
            req11_next,
        ),
        row(
            "REQ-12",
            "残HOLDをバンドル単位で管理する",
            "PARTIAL_OK",
            GOAL_UNBLOCK_BOARD,
            req12_gap,
            req12_next,
        ),
    ]


def load_objective_audit_rows(path: Path = OBJECTIVE_COMPLETION_AUDIT_JSON) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(item.get("requirement_id", "")): item
        for item in rows
        if isinstance(item, dict) and str(item.get("requirement_id", ""))
    }


def apply_objective_audit_overlay(
    rows: list[RequirementTraceRow],
    audit_path: Path = OBJECTIVE_COMPLETION_AUDIT_JSON,
) -> list[RequirementTraceRow]:
    audit_rows = load_objective_audit_rows(audit_path)
    if not audit_rows:
        return rows

    aligned_rows: list[RequirementTraceRow] = []
    for item in rows:
        audit_row = audit_rows.get(item.requirement_id)
        if not audit_row:
            aligned_rows.append(item)
            continue

        evidence_text = str(audit_row.get("evidence") or item.authoritative_evidence)
        current_value = str(audit_row.get("current_value") or "").strip()
        remaining_gap = str(audit_row.get("remaining_gap") or "").strip()
        if current_value and remaining_gap:
            gap_text = f"{current_value}; {remaining_gap}"
        elif current_value:
            gap_text = current_value
        elif remaining_gap:
            gap_text = remaining_gap
        else:
            gap_text = "objective_completion_auditで証明済み"

        aligned_rows.append(
            RequirementTraceRow(
                requirement_id=item.requirement_id,
                requirement=str(audit_row.get("requirement") or item.requirement),
                current_status=str(audit_row.get("status") or item.current_status),
                authoritative_evidence=evidence_text,
                remaining_gap=gap_text,
                next_evidence_needed=str(audit_row.get("next_action") or item.next_evidence_needed),
                source_exists=evidence_sources_exist(evidence_text),
            )
        )
    return aligned_rows


def build_payload() -> dict[str, object]:
    rows = apply_objective_audit_overlay(build_rows())
    complete_rows = [
        item for item in rows
        if item.current_status in {
            "PROVED",
            "COMPLETE",
            "OK_FOR_SAFE_CHECKS_ONLY",
            "OK_FOR_BUNDLE_RUNBOOK_ONLY",
        }
    ]
    missing_sources = [item for item in rows if not item.source_exists]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": all(
            item.current_status
            in {
                "PROVED",
                "COMPLETE",
                "OK_FOR_SAFE_CHECKS_ONLY",
                "OK_FOR_BUNDLE_RUNBOOK_ONLY",
            }
            for item in rows
        ),
        "safety": "read-only requirement traceability only; no external operation",
        "requirement_count": len(rows),
        "complete_or_safe_count": len(complete_rows),
        "missing_source_count": len(missing_sources),
        "rows": [asdict(item) for item in rows],
    }


def build_markdown(payload: dict[str, object]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# 目標要件トレーサビリティ 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- requirement_count: `{payload['requirement_count']}`",
        f"- complete_or_safe_count: `{payload['complete_or_safe_count']}`",
        f"- missing_source_count: `{payload['missing_source_count']}`",
        "",
        "## Requirement Traceability",
        "",
        "| ID | Requirement | Current Status | Remaining Gap | Next Evidence Needed | Source Exists | Evidence |",
        "|---|---|---|---|---|---:|---|",
    ]
    for item in rows:
        assert isinstance(item, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["requirement_id"]),
                    str(item["requirement"]).replace("|", "/"),
                    str(item["current_status"]).replace("|", "/"),
                    str(item["remaining_gap"]).replace("|", "/"),
                    str(item["next_evidence_needed"]).replace("|", "/"),
                    "YES" if item["source_exists"] else "NO",
                    f"`{item['authoritative_evidence']}`",
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
    parser = argparse.ArgumentParser(description="Generate RK10 goal requirement traceability.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "goal_requirement_traceability.json"
    md_path = args.out_dir / "goal_requirement_traceability.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
