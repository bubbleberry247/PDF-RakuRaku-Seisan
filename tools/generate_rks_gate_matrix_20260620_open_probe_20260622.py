"""Generate a read-only RKS gate matrix for RK10 migration readiness.

This tool does not open RK10, run RKS files, press ButtonRun, write production
data, send mail, print, submit, execute payment confirmation, or call Azure.
It only consolidates existing evidence paths into a current gate matrix.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "rks_gate_matrix_20260620"
RKS_STATIC_GUARD_AUDIT = (
    ROOT
    / "plans"
    / "reports"
    / "rks_static_guard_audit_20260620"
    / "rks_static_guard_audit.md.numbered"
)
RKS_RUNTIME_INTAKE_VALIDATION = (
    ROOT
    / "plans"
    / "reports"
    / "rks_runtime_operator_intake_validation_20260620"
    / "rks_runtime_operator_intake_validation.json"
)
OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "outlook_bundle_evidence_collect_20260620"
    / "outlook_bundle_evidence_collect.json"
)
RKS_EDITOR_OPEN_PROBE_REPORTS_ROOT = Path(
    r"C:\ProgramData\RK10\Robots\migration\reports"
)
RKS_EDITOR_OPEN_PROBE_REPORT_GLOB = "rks_editor_open_build_probe_20260620_*"
DEFERRED_RUNTIME_STATUS = "RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION"


@dataclass(frozen=True)
class RksGateRow:
    scenario: str
    operational_entry: str
    current_rks_status: str
    strongest_confirmed_scope: str
    missing_gate: str
    next_safe_action: str
    blocked_operation: str
    primary_source: str
    source_exists: bool
    existing_evidence_search_result: str = "not_applicable"
    runtime_intake_status: str = "RUNTIME_INTAKE_VALIDATION_NOT_APPLIED"
    runtime_intake_approved_count: int = 0
    runtime_intake_required_count: int = 0
    runtime_intake_source: str = ""
    editor_open_probe_status: str = "RK10_EDITOR_OPEN_PROBE_NOT_APPLIED"
    editor_open_probe_source: str = ""
    editor_open_probe_build_artifact_found: bool = False
    editor_open_probe_button_run_clicked: bool = False


def row(
    scenario: str,
    operational_entry: str,
    current_rks_status: str,
    strongest_confirmed_scope: str,
    missing_gate: str,
    next_safe_action: str,
    blocked_operation: str,
    primary_source: str,
    existing_evidence_search_result: str = "not_applicable",
) -> RksGateRow:
    return RksGateRow(
        scenario=scenario,
        operational_entry=operational_entry,
        current_rks_status=current_rks_status,
        strongest_confirmed_scope=strongest_confirmed_scope,
        missing_gate=missing_gate,
        next_safe_action=next_safe_action,
        blocked_operation=blocked_operation,
        primary_source=primary_source,
        source_exists=Path(primary_source).exists(),
        existing_evidence_search_result=existing_evidence_search_result,
    )


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_editor_open_probe_rows(
    reports_root: Path | None = None,
) -> dict[str, dict[str, Any]]:
    root = reports_root or RKS_EDITOR_OPEN_PROBE_REPORTS_ROOT
    if not root.exists():
        return {}
    latest_rows: dict[str, dict[str, Any]] = {}
    for json_path in sorted(
        root.glob(f"{RKS_EDITOR_OPEN_PROBE_REPORT_GLOB}/rks_editor_open_build_probe.json")
    ):
        payload = load_json(json_path)
        rows = payload.get("rows", [])
        if not isinstance(rows, list):
            continue
        generated_at = str(payload.get("generated_at", json_path.parent.name))
        for item in rows:
            if not isinstance(item, dict):
                continue
            scenario = str(item.get("scenario", ""))
            if not scenario:
                continue
            if item.get("editor_open_status") != "RK10_EDITOR_OPEN_CONFIRMED":
                continue
            if item.get("executed") is not True:
                continue
            if int(item.get("metadata_guard_returncode", -1)) != 0:
                continue
            if item.get("button_run_clicked") is True:
                continue
            candidate = {
                **item,
                "probe_generated_at": generated_at,
                "probe_source": str(json_path),
            }
            current = latest_rows.get(scenario)
            if current is None or generated_at >= str(current.get("probe_generated_at", "")):
                latest_rows[scenario] = candidate
    return latest_rows


def is_outlook_com_bundle_safe_evidence_ready(
    path: Path | None = None,
) -> bool:
    payload = load_json(path or OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON)
    log_status = payload.get("log_status", {})
    if not isinstance(log_status, dict):
        return False
    return (
        payload.get("status") == "READY_FOR_FINAL_EVIDENCE_INTAKE"
        and payload.get("ready_for_intake") is True
        and str(log_status.get("check_exit")) == "0"
        and str(log_status.get("scan_exit")) == "0"
    )


def outlook_12_13_row() -> RksGateRow:
    if is_outlook_com_bundle_safe_evidence_ready():
        evidence_path = str(
            load_json(OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON).get(
                "evidence_path",
                OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON,
            )
        )
        return row(
            "12/13",
            "Python/Outlook COM flow; no primary RKS",
            "N_A_NO_PRIMARY_RKS",
            "Outlook COM check + scan-only dry-run/no-print/no-mail confirmed; RKS not required",
            "final operator approval and real print/send/mail-state-change gates",
            "最終入力欄を埋める。実印刷・実送信・メール状態変更は別承認のまま維持する。",
            "実印刷, 実送信, メール状態変更",
            evidence_path,
        )
    return row(
        "12/13",
        "Python/Outlook COM flow; no primary RKS",
        "N_A_NO_PRIMARY_RKS",
        "PDF extraction subpath OK; Outlook COM still HOLD",
        "Outlook COM exit 0 then dry-run/no-print/no-mail",
        "Outlook COM復旧後に--check-outlook-comから再開する。",
        "実印刷, 実送信, メール状態変更",
        r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\s12_13_outlook_com_recheck_20260620\s12_13_outlook_com_recheck_20260620.md.numbered",
    )


def build_rows() -> list[RksGateRow]:
    return [
        row(
            "38",
            "TBD: Python/BAT入口 or regenerated RKS",
            "PRIMARY_RKS_EDITOR_OPEN_NG",
            "Python LOCAL SAFE",
            "RKS要否判断 / RK10 Editor Save As再生成 / open/build/runtime/latest clean log",
            "RKSが必要ならprimaryを直接直さずRK10 Editor Save Asで別名再生成する。",
            "NG primary RKS execution, ZIP-level RKS patching, RK10 ButtonRun",
            r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\s38_rks_regeneration_decision_sheet_20260620.md.numbered",
        ),
        row(
            "57",
            "current RKS + canonical Python flow",
            "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
            "RK10 editor open/build + Python dry-run",
            "runtime safe-stop latest clean log",
            "no-mail/no-upload/no-write safe-stopでlatest clean logを取り直す。",
            "MainSV確定書込, メール実送信, 本番TXT確定出力",
            r"C:\ProgramData\RK10\Robots\migration\reports\s57_current_rks_editor_open_build_probe_20260618_103111\summary.tsv.numbered",
            (
                "not_promotable: editor/open/build probe explicitly lacks runtime/safe-stop/latest clean log; "
                r"C:\ProgramData\RK10\Robots\migration\reports\s57_current_rks_editor_open_build_probe_20260618_103111\status_gate.stdout.txt.numbered:1. "
                "canonical Python dry-run is also non-promotable because it says no RKS execution/UI side effects; "
                r"C:\ProgramData\RK10\Robots\migration\reports\s57_canonical_python_safe_dryrun_20260618_110309\summary.json.numbered:4"
            ),
        ),
        row(
            "42",
            "confirmed production file or current fixed-name RKS",
            "ENTRY_SELECTION_REQUIRED",
            "registry-confirmed exact production file exists",
            "customer entry selection / same-candidate open-build-runtime evidence",
            "既存CONFIRMED RKSを使うかcurrent fixed-nameを新候補にするか決める。",
            "既存本番RKS上書き, 再メール送信",
            r"C:\ProgramData\RK10\Robots\migration\reports\all_scenario_prod_file_certainty_map_20260618_152452\all_scenario_prod_file_certainty_map.md.numbered",
        ),
        row(
            "51/52",
            "Excel保存までRKS",
            "RKS_STATUS_GATE_UNCONFIRMED",
            "Excel save scope selected after feedback",
            "RK10 open/build/safe-stop for selected customer entry",
            "RKS入口で運用する場合だけopen/build/safe-stopを取り直す。",
            "allow-rakuraku-application, 一時保存, 最終申請",
            r"C:\ProgramData\RK10\Robots\migration\reports\prod_files_after_feedback_final_reconfirm_20260618_161709\prod_files_after_feedback_final_reconfirm.md.numbered",
        ),
        row(
            "56",
            "current deployable RKS not fixed",
            "CURRENT_DEPLOYABLE_RKS_NOT_CONFIRMED",
            "historical production evidence only",
            "current workbook copy / no-write proof / Save As if RKS needed",
            "必要なら現行候補をRK10 Editor Save Asで再生成し、2 workbook copyでno-write確認。",
            "disabled archive RKS昇格, 原本Excel直書き",
            r"C:\ProgramData\RK10\Robots\migration\reports\scenario56_prod_history_current_state_followup_20260618_0118.md.numbered",
        ),
        row(
            "58",
            "RKS or Python operator-select flow",
            "RKS_RUNTIME_UNCONFIRMED",
            "LOCAL sample/test-suite OK",
            "operator-select / real date-category / no-mail runtime evidence",
            "支払日/対象区分を決め、no-mail/no-writeで停止位置を確認する。",
            "MainSV本番TXT書込, 保存通知メール送信",
            r"C:\ProgramData\RK10\Robots\migration\reports\s58_current_safe_sample_recheck_20260618_173202\s58_current_safe_sample_recheck_report.md.numbered",
            (
                "not_promotable: sample generation/py_compile/LOCAL dry-run test-suite are OK, "
                "but the same report keeps RKS editor open/build/runtime/latest clean log UNCONFIRMED; "
                r"C:\ProgramData\RK10\Robots\migration\reports\s58_current_safe_sample_recheck_20260618_173202\s58_current_safe_sample_recheck_report.md.numbered:4,37,38,132"
            ),
        ),
        row(
            "37/47/55/63",
            "representative RKS candidates",
            "SAFE_STOP_SCOPE_ONLY",
            "open/build/safe-stop scope for representative candidates",
            "business data / approval / latest clean log per scenario",
            "RKS再確認より先に実対象データ・停止条件・業務承認を揃える。",
            "RecoRu登録, Outlook実送信, 本番Excel/支払処理, 楽楽最終申請",
            r"C:\ProgramData\RK10\Robots\migration\reports\rk10_open_build_safe_stop_status_gate_20260618_1019\summary.tsv.numbered",
        ),
        row(
            "44",
            "handoff/latest_ready.json then RKS",
            "BUSINESS_REVIEW_HOLD_BEFORE_RKS",
            "HandoffService shadow contract OK; latest spot check has no OK rows",
            "business spot check OK rows / live handoff generation / processed-move evidence",
            "26件spot checkのOK行だけshadow→live handoff候補へ進める。",
            "review未了のままRakuraku登録, PDF processed移動",
            r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\s44_spot_check_handoff_candidates_20260620\s44_spot_check_handoff_candidates.md.numbered",
        ),
        row(
            "70",
            "payment confirmation RKS",
            "PAYMENT_APPROVAL_HOLD_BEFORE_RKS",
            "parameter review only",
            "expected count/amount, bank evidence, approver, confirm-preview",
            "支払件数・金額・銀行確認・承認者を記録し、confirm-previewだけ確認する。",
            "--execute, RK10 ButtonRun",
            r"C:\ProgramData\RK10\Robots\migration\reports\s70_payment_confirmation_gate_pack_20260619_1218\s70_payment_confirmation_gate_pack.md.numbered",
        ),
        row(
            "71",
            "OCR/apply RKS or Python flow",
            "AZURE_OCR_GATE_HOLD_BEFORE_RKS",
            "real PDF + mock OCR + workbook copy apply verified",
            "endpoint/key, sample PDF, budget approval, paid OCR smoke",
            "1件サンプル・費用上限・承認者を記録してからpaid OCR smoke test。",
            "Azure/API課金, 原本Excel直書き",
            r"C:\ProgramData\RK10\Robots\migration\reports\s71_azure_ocr_gate_pack_20260619_1220\s71_azure_ocr_gate_pack.md.numbered",
        ),
        outlook_12_13_row(),
    ]


def load_runtime_intake_validation(path: Path | None = None) -> dict[str, Any] | None:
    target_path = path or RKS_RUNTIME_INTAKE_VALIDATION
    if not target_path.exists():
        return None
    return json.loads(target_path.read_text(encoding="utf-8"))


def scenario_keys(value: str) -> list[str]:
    if value == "37/47/55/63":
        return ["37", "47", "55", "63"]
    return [value]


def runtime_rows_by_scenario(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("scenario", "")): row
        for row in rows
        if isinstance(row, dict)
    }


def build_runtime_status(
    matrix_row: RksGateRow,
    validation_payload: dict[str, Any] | None,
) -> tuple[str, int, int, str]:
    source = str(RKS_RUNTIME_INTAKE_VALIDATION)
    if matrix_row.current_rks_status == "N_A_NO_PRIMARY_RKS":
        return "N_A_NO_PRIMARY_RKS", 0, 0, source
    if validation_payload is None:
        return "RUNTIME_INTAKE_VALIDATION_MISSING", 0, 0, source
    validation_rows = runtime_rows_by_scenario(validation_payload)
    matching_all_rows = [
        validation_rows[key]
        for key in scenario_keys(matrix_row.scenario)
        if key in validation_rows
    ]
    matching_rows = [
        row
        for row in matching_all_rows
        if bool(row.get("requires_rk10_evidence"))
    ]
    deferred_rows = [
        row
        for row in matching_all_rows
        if not bool(row.get("requires_rk10_evidence"))
    ]
    required_count = len(matching_rows)
    approved_count = sum(1 for row in matching_rows if row.get("approved") is True)
    hard_error_count = sum(
        1 for row in matching_rows if row.get("latest_log_has_hard_errors") is True
    )
    if required_count == 0:
        if deferred_rows:
            return DEFERRED_RUNTIME_STATUS, 0, 0, source
        return "RUNTIME_INTAKE_ROW_MISSING", approved_count, required_count, source
    if hard_error_count > 0:
        return "LATEST_RUN_ERROR_NG", approved_count, required_count, source
    if approved_count == required_count:
        return "RKS_RUNTIME_EVIDENCE_CONFIRMED", approved_count, required_count, source
    return "RKS_RUNTIME_EVIDENCE_PENDING", approved_count, required_count, source


def append_open_probe_scope(scope: str) -> str:
    addition = "RK10 editor open confirmed only; build/runtime not confirmed by this probe"
    if addition in scope:
        return scope
    return f"{scope}; {addition}"


def with_runtime_status(
    rows: list[RksGateRow],
    validation_payload: dict[str, Any] | None,
) -> list[RksGateRow]:
    updated = []
    for item in rows:
        status, approved_count, required_count, source = build_runtime_status(item, validation_payload)
        updated.append(
            RksGateRow(
                scenario=item.scenario,
                operational_entry=item.operational_entry,
                current_rks_status=item.current_rks_status,
                strongest_confirmed_scope=item.strongest_confirmed_scope,
                missing_gate=item.missing_gate,
                next_safe_action=item.next_safe_action,
                blocked_operation=item.blocked_operation,
                primary_source=item.primary_source,
                source_exists=item.source_exists,
                existing_evidence_search_result=item.existing_evidence_search_result,
                runtime_intake_status=status,
                runtime_intake_approved_count=approved_count,
                runtime_intake_required_count=required_count,
                runtime_intake_source=source,
                editor_open_probe_status=item.editor_open_probe_status,
                editor_open_probe_source=item.editor_open_probe_source,
                editor_open_probe_build_artifact_found=item.editor_open_probe_build_artifact_found,
                editor_open_probe_button_run_clicked=item.editor_open_probe_button_run_clicked,
            )
        )
    return updated


def with_editor_open_probe_status(
    rows: list[RksGateRow],
    probe_rows: dict[str, dict[str, Any]],
) -> list[RksGateRow]:
    updated = []
    for item in rows:
        matching_probe = next(
            (probe_rows[key] for key in scenario_keys(item.scenario) if key in probe_rows),
            None,
        )
        if matching_probe is None:
            updated.append(item)
            continue
        build_artifact_found = bool(matching_probe.get("build_artifact_found"))
        button_run_clicked = bool(matching_probe.get("button_run_clicked"))
        updated.append(
            RksGateRow(
                scenario=item.scenario,
                operational_entry=item.operational_entry,
                current_rks_status=item.current_rks_status,
                strongest_confirmed_scope=append_open_probe_scope(item.strongest_confirmed_scope),
                missing_gate=item.missing_gate,
                next_safe_action=item.next_safe_action,
                blocked_operation=item.blocked_operation,
                primary_source=item.primary_source,
                source_exists=item.source_exists,
                existing_evidence_search_result=item.existing_evidence_search_result,
                runtime_intake_status=item.runtime_intake_status,
                runtime_intake_approved_count=item.runtime_intake_approved_count,
                runtime_intake_required_count=item.runtime_intake_required_count,
                runtime_intake_source=item.runtime_intake_source,
                editor_open_probe_status="RK10_EDITOR_OPEN_CONFIRMED",
                editor_open_probe_source=str(matching_probe.get("probe_source", "")),
                editor_open_probe_build_artifact_found=build_artifact_found,
                editor_open_probe_button_run_clicked=button_run_clicked,
            )
        )
    return updated


def rks_row_resolved(item: RksGateRow) -> bool:
    return item.current_rks_status == "N_A_NO_PRIMARY_RKS" or item.runtime_intake_status == "RKS_RUNTIME_EVIDENCE_CONFIRMED"


def rks_row_deferred(item: RksGateRow) -> bool:
    return item.runtime_intake_status == DEFERRED_RUNTIME_STATUS


def rks_row_technical_unresolved(item: RksGateRow) -> bool:
    return not rks_row_resolved(item) and not rks_row_deferred(item)


def build_payload() -> dict[str, object]:
    generated_at = datetime.now().isoformat(timespec="seconds")
    runtime_validation = load_runtime_intake_validation()
    editor_open_probe_rows = load_editor_open_probe_rows()
    rows = with_editor_open_probe_status(
        with_runtime_status(build_rows(), runtime_validation),
        editor_open_probe_rows,
    )
    unresolved = [item for item in rows if not rks_row_resolved(item)]
    deferred = [item for item in rows if rks_row_deferred(item)]
    technical_unresolved = [item for item in rows if rks_row_technical_unresolved(item)]
    missing_sources = [item for item in rows if not item.source_exists]
    runtime_validation_complete = (
        runtime_validation is not None
        and runtime_validation.get("overall_rks_runtime_evidence_complete") is True
    )
    rks_technical_gate_complete = (
        bool(rows)
        and runtime_validation_complete
        and len(technical_unresolved) == 0
        and len(missing_sources) == 0
    )
    return {
        "generated_at": generated_at,
        "overall_rks_production_ready": (
            bool(rows)
            and runtime_validation_complete
            and len(unresolved) == 0
            and len(missing_sources) == 0
        ),
        "safety": "read-only existing-evidence matrix only; no RK10/RKS execution",
        "row_count": len(rows),
        "unresolved_rks_gate_count": len(unresolved),
        "technical_unresolved_rks_gate_count": len(technical_unresolved),
        "deferred_rks_gate_count": len(deferred),
        "rks_technical_gate_complete": rks_technical_gate_complete,
        "missing_source_count": len(missing_sources),
        "supplemental_static_guard_audit": str(RKS_STATIC_GUARD_AUDIT),
        "supplemental_static_guard_audit_exists": RKS_STATIC_GUARD_AUDIT.exists(),
        "runtime_intake_validation": str(RKS_RUNTIME_INTAKE_VALIDATION),
        "runtime_intake_validation_exists": RKS_RUNTIME_INTAKE_VALIDATION.exists(),
        "runtime_intake_validation_complete": runtime_validation_complete,
        "editor_open_probe_reports_root": str(RKS_EDITOR_OPEN_PROBE_REPORTS_ROOT),
        "editor_open_probe_confirmed_count": sum(
            1 for item in rows if item.editor_open_probe_status == "RK10_EDITOR_OPEN_CONFIRMED"
        ),
        "rows": [asdict(item) for item in rows],
    }


def build_markdown(payload: dict[str, object]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# RKS Gate Evidence Matrix 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_rks_production_ready: `{payload['overall_rks_production_ready']}`",
        f"- safety: `{payload['safety']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- unresolved_rks_gate_count: `{payload['unresolved_rks_gate_count']}`",
        f"- technical_unresolved_rks_gate_count: `{payload['technical_unresolved_rks_gate_count']}`",
        f"- deferred_rks_gate_count: `{payload['deferred_rks_gate_count']}`",
        f"- rks_technical_gate_complete: `{payload['rks_technical_gate_complete']}`",
        f"- missing_source_count: `{payload['missing_source_count']}`",
        f"- supplemental_static_guard_audit_exists: `{payload['supplemental_static_guard_audit_exists']}`",
        f"- runtime_intake_validation_exists: `{payload['runtime_intake_validation_exists']}`",
        f"- runtime_intake_validation_complete: `{payload['runtime_intake_validation_complete']}`",
        f"- editor_open_probe_confirmed_count: `{payload['editor_open_probe_confirmed_count']}`",
        "",
        "## Matrix",
        "",
        "| Scenario | Current RKS Status | Runtime Intake Status | Runtime Approved | Editor Open Probe | Strongest Confirmed Scope | Missing Gate | Next Safe Action | Source Exists |",
        "|---|---|---|---:|---|---|---|---|---:|",
    ]
    for item in rows:
        assert isinstance(item, dict)
        required_count = int(item["runtime_intake_required_count"])
        approved_text = (
            "n/a"
            if required_count == 0
            else f"{item['runtime_intake_approved_count']}/{required_count}"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["scenario"]),
                    str(item["current_rks_status"]).replace("|", "/"),
                    str(item["runtime_intake_status"]).replace("|", "/"),
                    approved_text,
                    str(item.get("editor_open_probe_status", "RK10_EDITOR_OPEN_PROBE_NOT_APPLIED")).replace("|", "/"),
                    str(item["strongest_confirmed_scope"]).replace("|", "/"),
                    str(item["missing_gate"]).replace("|", "/"),
                    str(item["next_safe_action"]).replace("|", "/"),
                    "YES" if item["source_exists"] else "NO",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Blocked Operations", ""])
    for item in rows:
        assert isinstance(item, dict)
        lines.append(f"- {item['scenario']}: {item['blocked_operation']}")
    evidence_search_rows = [
        item
        for item in rows
        if isinstance(item, dict)
        and str(item.get("existing_evidence_search_result", "not_applicable"))
        != "not_applicable"
    ]
    if evidence_search_rows:
        lines.extend(["", "## Existing Evidence Search Results", ""])
        for item in evidence_search_rows:
            assert isinstance(item, dict)
            lines.append(
                f"- {item['scenario']}: {item['existing_evidence_search_result']}"
            )
    open_probe_rows = [
        item
        for item in rows
        if isinstance(item, dict)
        and item.get("editor_open_probe_status") == "RK10_EDITOR_OPEN_CONFIRMED"
    ]
    if open_probe_rows:
        lines.extend(["", "## RK10 Editor Open Probe Evidence", ""])
        lines.append(
            "- scope: editor open only; build/runtime/ButtonRun are not promoted by this evidence."
        )
        for item in open_probe_rows:
            assert isinstance(item, dict)
            lines.append(
                f"- {item['scenario']}: `{item.get('editor_open_probe_source', '')}`; "
                f"build_artifact_found={item.get('editor_open_probe_build_artifact_found')}; "
                f"button_run_clicked={item.get('editor_open_probe_button_run_clicked')}"
            )
    lines.extend(["", "## Primary Sources", ""])
    for item in rows:
        assert isinstance(item, dict)
        lines.append(f"- {item['scenario']}: `{item['primary_source']}`")
    lines.extend(
        [
            "",
            "## Supplemental Static Guard Audit",
            "",
            f"- source: `{payload['supplemental_static_guard_audit']}`",
            "- scope: RKS package structure guard only; not RK10 Editor open/build/runtime proof.",
            "",
            "## Supplemental Runtime Intake Validation",
            "",
            f"- source: `{payload['runtime_intake_validation']}`",
            "- scope: operator-provided RK10 editor open/build/runtime/latest clean log evidence; no RK10 execution by this generator.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate read-only RKS gate evidence matrix.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "rks_gate_matrix.json"
    md_path = args.out_dir / "rks_gate_matrix.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
