"""Generate the next approval queue for the active RK10 validation goal.

This report ranks the remaining approval bundles. It does not open Outlook,
RK10, Rakuraku, Azure, printers, mail, payment systems, MainSV, or production
files. It only reads current repository evidence and writes reports.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from generate_goal_unblock_board_20260620 import build_payload as build_unblock_payload


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "next_approval_queue_20260620"
EXTERNAL_RUNBOOK = (
    ROOT
    / "plans"
    / "reports"
    / "external_approval_runbook_20260620"
    / "external_approval_runbook.md.numbered"
)
EXTERNAL_RUNBOOK_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "external_approval_runbook_20260620"
    / "external_approval_runbook.json"
)
OUTLOOK_COM_DIAGNOSIS = (
    ROOT
    / "plans"
    / "reports"
    / "outlook_com_environment_diagnosis_20260620"
    / "outlook_com_environment_diagnosis.json"
)
OUTLOOK_COM_DIAGNOSIS_REPORT = (
    ROOT
    / "plans"
    / "reports"
    / "outlook_com_environment_diagnosis_20260620"
    / "outlook_com_environment_diagnosis.md.numbered"
)
BUNDLE_SHEET = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_operator_sheet_20260620"
    / "bundle_operator_sheet.csv"
)
RKS_RUNTIME_VALIDATION = (
    ROOT
    / "plans"
    / "reports"
    / "rks_runtime_operator_intake_validation_20260620"
    / "rks_runtime_operator_intake_validation.json"
)
BUNDLE_EVIDENCE_VALIDATION = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_pack_validation_20260620"
    / "bundle_evidence_pack_validation.json"
)
BUNDLE_EVIDENCE_INTAKE_SYNC_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_intake_sync_20260620"
    / "bundle_evidence_intake_sync.json"
)
RKS_RUNTIME_FINAL_EVIDENCE_DIR = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "rk10_editor_runtime_bundle"
    / "final_evidence"
    / "rks_runtime"
)
RK10_RECOVERY_CHECKLIST = (
    ROOT
    / "plans"
    / "reports"
    / "external_approval_runbook_20260620"
    / "rk10_editor_recovery_checklist.md.numbered"
)
FIXED_RUNNER = ROOT / "tools" / "run_safe_goal_checks_20260620.py"


PRIORITY_RULES = {
    "OUTLOOK_COM_BUNDLE": {
        "rank": 1,
        "why_next": "12/13のサンプルrefreshとメールPDF dry-run確認がOutlook COMで止まっている",
        "operator_action": "Classic Outlookを通常画面で復旧し、OUTLOOK_COM_BUNDLE dry-runだけ確認する",
        "approval_boundary": "Outlook COM preflightとscan-only dry-run/no-print/no-mailのみ",
    },
    "BUSINESS_REVIEW_BUNDLE": {
        "rank": 2,
        "why_next": "44はOK/NG未記入でlive handoff候補へ進めない",
        "operator_action": "spot check CSVにOK/NGを記入し、OK行だけを証跡パックへ入れる",
        "approval_boundary": "Rakuraku登録、PDF processed移動、メール送信はまだ禁止",
    },
    "PAYMENT_APPROVAL_BUNDLE": {
        "rank": 3,
        "why_next": "70は件数・金額・銀行確認・承認者の証跡が未記録",
        "operator_action": "expected_count/amount、銀行確認、承認者を記録しconfirm-previewのみ実施する",
        "approval_boundary": "--execute、支払確定、支払実行、RK10 ButtonRunは禁止",
    },
    "PAID_AZURE_OCR_BUNDLE": {
        "rank": 4,
        "why_next": "71はendpoint/key、費用上限、1件サンプルが未確定",
        "operator_action": "費用上限と1件PDFを確定し、必要ならpaid smokeの証跡だけ取る",
        "approval_boundary": "複数PDF送信、秘密値出力、原本Excel直書きは禁止",
    },
    "BUSINESS_DATA_APPROVAL_BUNDLE": {
        "rank": 5,
        "why_next": "43/47/55/63は実対象データ・停止条件・業務承認が未確定",
        "operator_action": "実対象データ、支払日/対象日、停止条件、承認者を束で決める",
        "approval_boundary": "本番登録、実メール、本番Excel/サーバ確定書込は禁止",
    },
    "RK10_EDITOR_RUNTIME_BUNDLE": {
        "rank": 6,
        "why_next": "37/38/42/51/52/56/57/58はRK10 Editor open/build/runtime証跡が不足",
        "operator_action": "必要RKSだけRK10 Editor open/build/safe-stop/latest clean logをまとめて取る",
        "approval_boundary": "ButtonRun、本番書込、実メール、実印刷、最終申請、ZIP直接RKS改変は禁止",
    },
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class QueueRow:
    rank: int
    bundle: str
    owner: str
    scenarios: str
    scenario_count: int
    why_next: str
    operator_action: str
    approval_boundary: str
    forbidden: str
    evidence_pack_path: str
    bundle_sheet_path: str
    after_action_command: str


@dataclass(frozen=True)
class RksRuntimeFocusRow:
    scenario: str
    source_status: str
    rks_path: str
    issue_codes: str
    confirmed_evidence: str
    remaining_inputs: str
    latest_log_path: str
    evidence_folder: str
    rk10_cold_status: str
    rk10_recovery_checklist: str
    next_safe_action: str
    blocked_operation: str


@dataclass(frozen=True)
class Rk10ColdEvidence:
    status: str
    checklist_path: str


@dataclass(frozen=True)
class OutlookComEvidence:
    status: str
    diagnosis: str
    next_action: str
    report_path: str


def split_scenarios(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def safe_folder_name(value: str) -> str:
    return (
        value.replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_completed_bundles(validation_path: Path = BUNDLE_EVIDENCE_VALIDATION) -> set[str]:
    sync_path = BUNDLE_EVIDENCE_INTAKE_SYNC_JSON
    if validation_path != BUNDLE_EVIDENCE_VALIDATION:
        sync_path = validation_path
    payload = load_json(sync_path)
    results = payload.get("results", [])
    if not isinstance(results, list):
        return set()
    return {
        str(result.get("bundle", "")).strip()
        for result in results
        if isinstance(result, dict) and result.get("ready_to_sync") is True
    } - {""}


def detect_rk10_cold_evidence(
    checklist_path: Path = RK10_RECOVERY_CHECKLIST,
) -> Rk10ColdEvidence:
    if not checklist_path.exists():
        return Rk10ColdEvidence(
            status="NO_CURRENT_RK10_COLD_EVIDENCE",
            checklist_path="",
        )
    text = checklist_path.read_text(encoding="utf-8", errors="replace")
    has_cold_marker = "現在のRK10 Editor環境がcold" in text
    has_license_marker = "RK10ライセンス有効期限警告" in text
    if has_cold_marker or has_license_marker:
        return Rk10ColdEvidence(
            status="RK10_EDITOR_ENV_COLD_LICENSE_PROMPT",
            checklist_path=str(checklist_path),
        )
    if "RK10_EDITOR_OPEN_TIMEOUT" in text:
        return Rk10ColdEvidence(
            status="RK10_EDITOR_OPEN_TIMEOUT_REPORTED",
            checklist_path=str(checklist_path),
        )
    return Rk10ColdEvidence(
        status="RK10_RECOVERY_CHECKLIST_PRESENT_NO_COLD_MARKER",
        checklist_path=str(checklist_path),
    )


def is_rk10_editor_cold(cold_evidence: Rk10ColdEvidence | None) -> bool:
    return bool(
        cold_evidence
        and cold_evidence.status
        in {
            "RK10_EDITOR_ENV_COLD_LICENSE_PROMPT",
            "RK10_EDITOR_OPEN_TIMEOUT_REPORTED",
        }
    )


def detect_outlook_com_evidence(
    diagnosis_path: Path = OUTLOOK_COM_DIAGNOSIS,
    report_path: Path = OUTLOOK_COM_DIAGNOSIS_REPORT,
) -> OutlookComEvidence:
    if not diagnosis_path.exists():
        return OutlookComEvidence(
            status="NO_CURRENT_OUTLOOK_COM_DIAGNOSIS",
            diagnosis="",
            next_action="",
            report_path="",
        )
    payload = load_json(diagnosis_path)
    return OutlookComEvidence(
        status=str(payload.get("status", "OUTLOOK_COM_DIAGNOSIS_STATUS_MISSING")),
        diagnosis=str(payload.get("diagnosis", "")),
        next_action=str(payload.get("next_action", "")),
        report_path=str(report_path) if report_path.exists() else str(diagnosis_path),
    )


def outlook_operator_action(
    default_action: str,
    outlook_evidence: OutlookComEvidence | None,
) -> str:
    if not outlook_evidence or not outlook_evidence.next_action:
        return default_action
    if outlook_evidence.status in {
        "NO_CURRENT_OUTLOOK_COM_DIAGNOSIS",
        "OUTLOOK_COM_READY",
    }:
        return default_action
    return outlook_evidence.next_action


def outlook_priority_rule(
    default_rule: dict[str, object],
    outlook_evidence: OutlookComEvidence | None,
) -> dict[str, object]:
    if not outlook_evidence or outlook_evidence.status != "OUTLOOK_COM_READY":
        return dict(default_rule)
    return {
        **default_rule,
        "rank": 7,
        "why_next": "12/13はOutlook COM/dry-run証跡配置済みだが、最終承認フィールドが未記入",
        "operator_action": "final_evidenceへ証跡を置き、intake CSVへoperator_result/reviewer/reviewed_atを記入する",
        "approval_boundary": "実印刷・実送信は別ゲート。ここでは証跡配置と担当者確認のみ",
    }


def rk10_runtime_operator_action(
    default_action: str,
    cold_evidence: Rk10ColdEvidence | None,
) -> str:
    if not is_rk10_editor_cold(cold_evidence):
        return default_action
    return "RK10ライセンス復旧→63対照open確認→必要RKSのopen/build/safe-stop/latest clean logを取得する"


def rks_next_safe_action(
    scenario: str,
    cold_evidence: Rk10ColdEvidence | None = None,
) -> str:
    actions = {
        "57": "no-mail/no-upload/no-write safe-stopでlatest clean logを取得する",
        "58": "支払日/対象区分を選び、no-mail/no-write safe-stopでlatest clean logを取得する",
    }
    action = actions.get(
        scenario,
        "RK10 Editor open/build/runtime/safe-stop/latest clean logを取得する",
    )
    if not is_rk10_editor_cold(cold_evidence):
        return action
    return f"先にRK10ライセンス復旧→63対照open確認後に、{action}"


def rks_blocked_operation(scenario: str) -> str:
    blocked = {
        "57": "MainSV確定書込, メール実送信, 本番TXT確定出力, RK10 ButtonRun",
        "58": "MainSV本番TXT書込, 保存通知メール送信, RK10 ButtonRun",
    }
    return blocked.get(scenario, "本番書込, 実メール, 実印刷, 最終申請, RK10 ButtonRun")


def summarize_confirmed_rks_evidence(row: dict[str, Any]) -> str:
    confirmed = []
    if str(row.get("rk10_editor_open", "")) == "CONFIRMED":
        confirmed.append("RK10 editor open")
    if str(row.get("rk10_build", "")) == "CONFIRMED":
        confirmed.append("RK10 build")
    if str(row.get("runtime_or_safe_stop", "")) == "CONFIRMED":
        confirmed.append("runtime/safe-stop")
    if str(row.get("latest_log_clean", "")) == "YES" and str(row.get("latest_log_path", "")):
        confirmed.append("latest clean log")
    return ", ".join(confirmed) or "none"


def summarize_remaining_rks_inputs(row: dict[str, Any]) -> str:
    remaining = []
    if str(row.get("operator_decision", "")) not in {
        "OPEN_BUILD_ONLY",
        "SAFE_STOP_ONLY",
        "REGENERATE_SAVE_AS_REQUIRED",
    }:
        remaining.append("operator_decision")
    if str(row.get("rk10_editor_open", "")) != "CONFIRMED":
        remaining.append("rk10_editor_open")
    if str(row.get("rk10_build", "")) != "CONFIRMED":
        remaining.append("rk10_build")
    if str(row.get("runtime_or_safe_stop", "")) != "CONFIRMED":
        remaining.append("runtime_or_safe_stop")
    if str(row.get("latest_log_clean", "")) != "YES":
        remaining.append("latest_log_clean")
    if not str(row.get("latest_log_path", "")):
        remaining.append("latest_log_path")
    if not str(row.get("operator_name", "")):
        remaining.append("operator_name")
    if not str(row.get("checked_at", "")):
        remaining.append("checked_at")
    return ", ".join(remaining) or "none"


def build_rks_runtime_focus_rows(
    validation_path: Path = RKS_RUNTIME_VALIDATION,
    checklist_path: Path = RK10_RECOVERY_CHECKLIST,
    cold_evidence: Rk10ColdEvidence | None = None,
) -> list[RksRuntimeFocusRow]:
    payload = load_json(validation_path)
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return []
    resolved_cold_evidence = cold_evidence or detect_rk10_cold_evidence(checklist_path)
    focus_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("requires_rk10_evidence") is not True or row.get("approved") is True:
            continue
        scenario = str(row.get("scenario", ""))
        focus_rows.append(
            RksRuntimeFocusRow(
                scenario=scenario,
                source_status=str(row.get("source_status", "")),
                rks_path=str(row.get("rks_path", "")),
                issue_codes=str(row.get("issue_codes", "")),
                confirmed_evidence=summarize_confirmed_rks_evidence(row),
                remaining_inputs=summarize_remaining_rks_inputs(row),
                latest_log_path=str(row.get("latest_log_path", "")),
                evidence_folder=str(RKS_RUNTIME_FINAL_EVIDENCE_DIR / safe_folder_name(scenario)),
                rk10_cold_status=resolved_cold_evidence.status,
                rk10_recovery_checklist=resolved_cold_evidence.checklist_path,
                next_safe_action=rks_next_safe_action(scenario, resolved_cold_evidence),
                blocked_operation=rks_blocked_operation(scenario),
            )
        )
    return focus_rows


def build_rows(
    unblock_payload: dict[str, Any],
    cold_evidence: Rk10ColdEvidence | None = None,
    outlook_evidence: OutlookComEvidence | None = None,
    completed_bundles: set[str] | None = None,
    s12_exit_code: int = 2,
) -> list[QueueRow]:
    rows = []
    resolved_cold_evidence = cold_evidence or detect_rk10_cold_evidence()
    resolved_outlook_evidence = outlook_evidence or detect_outlook_com_evidence()
    resolved_completed_bundles = completed_bundles or set()
    for bundle in unblock_payload.get("approval_bundles", []):
        bundle_name = str(bundle["bundle"])
        if bundle_name in resolved_completed_bundles:
            continue
        rule = PRIORITY_RULES[bundle_name]
        if bundle_name == "OUTLOOK_COM_BUNDLE":
            rule = outlook_priority_rule(rule, resolved_outlook_evidence)
        scenarios = str(bundle["scenarios"])
        operator_action = str(rule["operator_action"])
        if bundle_name == "OUTLOOK_COM_BUNDLE":
            operator_action = outlook_operator_action(
                operator_action,
                resolved_outlook_evidence,
            )
        if bundle_name == "RK10_EDITOR_RUNTIME_BUNDLE":
            operator_action = rk10_runtime_operator_action(
                operator_action,
                resolved_cold_evidence,
            )
        evidence_pack = (
            ROOT
            / "plans"
            / "reports"
            / "bundle_evidence_packs_20260620"
            / bundle_name.lower()
        )
        rows.append(
            QueueRow(
                rank=int(rule["rank"]),
                bundle=bundle_name,
                owner=str(bundle["owner"]),
                scenarios=scenarios,
                scenario_count=len(split_scenarios(scenarios)),
                why_next=str(rule["why_next"]),
                operator_action=operator_action,
                approval_boundary=str(rule["approval_boundary"]),
                forbidden=str(bundle["still_forbidden"]),
                evidence_pack_path=str(evidence_pack),
                bundle_sheet_path=str(BUNDLE_SHEET),
                after_action_command=(
                    f"C:\\Users\\masam\\AppData\\Local\\Programs\\Python\\Python313\\python.exe "
                    f"-X utf8 {FIXED_RUNNER} --s12-exit-code {s12_exit_code}"
                ),
            )
        )
    return sorted(rows, key=lambda row: row.rank)


def build_payload(s12_exit_code: int | None) -> dict[str, Any]:
    unblock_payload = build_unblock_payload(s12_exit_code)
    external_runbook_payload = read_json(EXTERNAL_RUNBOOK_JSON)
    rk10_cold_evidence = detect_rk10_cold_evidence()
    outlook_evidence = detect_outlook_com_evidence()
    completed_bundles = load_completed_bundles()
    rows = build_rows(
        unblock_payload,
        rk10_cold_evidence,
        outlook_evidence,
        completed_bundles,
        2 if s12_exit_code is None else s12_exit_code,
    )
    rks_runtime_focus_rows = build_rks_runtime_focus_rows(
        cold_evidence=rk10_cold_evidence,
    )
    next_row = rows[0] if rows else None
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": "read-only approval queue; no external operation",
        "source_unblock_board_generated_at": unblock_payload["generated_at"],
        "external_runbook": str(EXTERNAL_RUNBOOK),
        "external_runbook_json": str(EXTERNAL_RUNBOOK_JSON),
        "outlook_bundle_script": str(
            external_runbook_payload.get("outlook_bundle_script", "")
        ),
        "outlook_recovery_checklist": str(
            external_runbook_payload.get("outlook_recovery_checklist", "")
        ),
        "queue_count": len(rows),
        "next_bundle": next_row.bundle if next_row else "",
        "next_operator_action": next_row.operator_action if next_row else "",
        "outlook_com_status": outlook_evidence.status,
        "outlook_com_diagnosis": outlook_evidence.diagnosis,
        "outlook_com_next_action": outlook_evidence.next_action,
        "outlook_com_diagnosis_report": outlook_evidence.report_path,
        "rk10_editor_cold_status": rk10_cold_evidence.status,
        "rk10_recovery_checklist": rk10_cold_evidence.checklist_path,
        "rks_runtime_focus_source": str(RKS_RUNTIME_VALIDATION),
        "rks_runtime_focus_count": len(rks_runtime_focus_rows),
        "rks_runtime_focus_rows": [asdict(row) for row in rks_runtime_focus_rows],
        "completed_bundles_excluded": sorted(completed_bundles),
        "rows": [asdict(row) for row in rows],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# 次承認キュー 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- queue_count: `{payload['queue_count']}`",
        f"- completed_bundles_excluded: `{', '.join(payload.get('completed_bundles_excluded', []))}`",
        f"- next_bundle: `{payload['next_bundle']}`",
        f"- next_operator_action: `{payload['next_operator_action']}`",
        f"- outlook_com_status: `{payload.get('outlook_com_status', '')}`",
        f"- outlook_com_diagnosis_report: `{payload.get('outlook_com_diagnosis_report', '')}`",
        f"- outlook_bundle_script: `{payload.get('outlook_bundle_script', '')}`",
        f"- outlook_recovery_checklist: `{payload.get('outlook_recovery_checklist', '')}`",
        f"- rk10_editor_cold_status: `{payload.get('rk10_editor_cold_status', '')}`",
        f"- rk10_recovery_checklist: `{payload.get('rk10_recovery_checklist', '')}`",
        f"- rks_runtime_focus_count: `{payload['rks_runtime_focus_count']}`",
        f"- external_runbook: `{payload['external_runbook']}`",
        f"- external_runbook_json: `{payload.get('external_runbook_json', '')}`",
        "",
        "## Queue",
        "",
        "| Rank | Bundle | Owner | Scenarios | Count | Why Next | Operator Action | Approval Boundary | Forbidden | Evidence Pack |",
        "|---:|---|---|---|---:|---|---|---|---|---|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["rank"]),
                    str(row["bundle"]),
                    str(row["owner"]),
                    str(row["scenarios"]).replace("|", "/"),
                    str(row["scenario_count"]),
                    str(row["why_next"]).replace("|", "/"),
                    str(row["operator_action"]).replace("|", "/"),
                    str(row["approval_boundary"]).replace("|", "/"),
                    str(row["forbidden"]).replace("|", "/"),
                    f"`{row['evidence_pack_path']}`",
                ]
            )
            + " |"
        )
    focus_rows = payload.get("rks_runtime_focus_rows", [])
    assert isinstance(focus_rows, list)
    lines.extend(
        [
            "",
            "## Focused RKS Runtime Rows",
            "",
            f"- source: `{payload['rks_runtime_focus_source']}`",
            "- この表は現時点でRK10 runtime証跡が直接必要な行だけを表示する。前提条件待ち・入口選定待ちは含めない。",
            "- この表はRKS実行OK判定ではない。実在latest clean logが揃うまで未完了のままにする。",
            "",
            "| Scenario | Source Status | Confirmed Evidence | Remaining Inputs | RK10 Cold Status | Next Safe Action | Blocked Operation | Evidence Folder | Recovery Checklist | Issues |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    if focus_rows:
        for row in focus_rows:
            assert isinstance(row, dict)
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["scenario"]),
                        str(row["source_status"]).replace("|", "/"),
                        str(row.get("confirmed_evidence", "")).replace("|", "/"),
                        str(row.get("remaining_inputs", "")).replace("|", "/"),
                        str(row.get("rk10_cold_status", "")).replace("|", "/"),
                        str(row["next_safe_action"]).replace("|", "/"),
                        str(row["blocked_operation"]).replace("|", "/"),
                        f"`{row['evidence_folder']}`",
                        f"`{row.get('rk10_recovery_checklist', '')}`",
                        str(row["issue_codes"]).replace("|", "/"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| - | - | - | - | - | - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## After Action",
            "",
            "- 実行後は6束入力シートへ結果・証跡パス・担当者・日時を記入する。",
            "- 客先担当者名ログイン・一時保存データ作成・cleanup系列は任意記録欄。削除証跡は承認ゲートの必須条件にしない。",
            "- 記入後は固定ランナーを再実行してHOLD解除または残理由を更新する。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate next RK10 approval queue.")
    parser.add_argument("--s12-exit-code", type=int, default=2)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.s12_exit_code)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "next_approval_queue.json"
    md_path = args.out_dir / "next_approval_queue.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
