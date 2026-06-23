"""Generate an operator runbook for approval-minimized external checks.

This report turns the six remaining approval bundles into one operator-facing
runbook. It does not execute Outlook, RK10, Rakuraku, Azure, printers, mail,
payment systems, MainSV, or production files.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_OUT_DIR = REPORTS / "external_approval_runbook_20260620"
EXECUTION_PACKET_JSON = (
    REPORTS / "goal_execution_packet_20260620" / "goal_execution_packet.json"
)
PYTHON_EXE = Path(r"C:\Users\masam\AppData\Local\Programs\Python\Python313\python.exe")
S12_TOOL = Path(
    r"C:\ProgramData\RK10\Robots"
    r"\12・13受信メールのPDFを保存・一括印刷"
    r"\tools\outlook_save_pdf_and_batch_print.py"
)
S12_PROD_CONFIG = Path(
    r"C:\ProgramData\RK10\Robots"
    r"\12・13受信メールのPDFを保存・一括印刷"
    r"\config\tool_config_prod.json"
)
SAFE_RUNNER = ROOT / "tools" / "run_safe_goal_checks_20260620_ai_default_probe_20260622.py"
RKS_EDITOR_PROBE = ROOT / "tools" / "run_rks_editor_open_build_probe_20260620_safe_exe_default_20260622.py"
S44_HANDOFF_CANDIDATES = ROOT / "tools" / "build_s44_spot_check_handoff_candidates_20260620.py"
S70_SAMPLE_CONFIRM = ROOT / "tools" / "run_s70_sample_confirm_preview_20260620.py"
S71_MOCK_OCR = ROOT / "tools" / "validate_s71_sample_mock_ocr_apply_20260620.py"
RKS_STATIC_GUARD = ROOT / "tools" / "generate_rks_static_guard_audit_20260620.py"


@dataclass(frozen=True)
class ExternalStep:
    bundle: str
    step_id: str
    approval_unit: str
    operation: str
    command: str
    manual_instruction: str
    expected_evidence: str
    requires_external_approval: bool
    forbidden_operations: str


def command_text(parts: list[str | Path]) -> str:
    return " ".join(f'"{part}"' if " " in str(part) else str(part) for part in parts)


def ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def load_execution_packet(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"execution packet not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def fixed_safe_runner_command() -> str:
    return command_text([PYTHON_EXE, "-X", "utf8", SAFE_RUNNER, "--s12-exit-code", "2"])


def build_known_steps(out_dir: Path) -> list[ExternalStep]:
    outlook_log_dir = out_dir / "outlook_com_bundle_logs"
    return [
        ExternalStep(
            bundle="SAFE_REFRESH_LOCAL",
            step_id="LOCAL-01",
            approval_unit="承認不要",
            operation="固定ランナー再実行",
            command=fixed_safe_runner_command(),
            manual_instruction="Codexが承認なしで再実行できる安全チェック。",
            expected_evidence=str(REPORTS / "safe_goal_checks_20260620"),
            requires_external_approval=False,
            forbidden_operations="GUI起動、実送信、実印刷、本番書込、支払実行",
        ),
        ExternalStep(
            bundle="OUTLOOK_COM_BUNDLE",
            step_id="OUTLOOK-01",
            approval_unit="1回承認: OUTLOOK_COM_BUNDLE",
            operation="Outlook COM preflight",
            command=command_text([PYTHON_EXE, "-X", "utf8", S12_TOOL, "--check-outlook-com"]),
            manual_instruction="Classic Outlook COMの疎通確認だけ。保存・印刷・送信はしない。",
            expected_evidence=str(outlook_log_dir / "01_check_outlook_com.log"),
            requires_external_approval=True,
            forbidden_operations="実印刷、実送信、メール状態変更、未読/既読変更",
        ),
        ExternalStep(
            bundle="OUTLOOK_COM_BUNDLE",
            step_id="OUTLOOK-02",
            approval_unit="1回承認: OUTLOOK_COM_BUNDLE",
            operation="scan-only dry-run/no-mail/no-print",
            command=command_text(
                [
                    PYTHON_EXE,
                    "-X",
                    "utf8",
                    S12_TOOL,
                    "--config",
                    S12_PROD_CONFIG,
                    "--scan-only",
                    "--dry-run",
                    "--dry-run-mail",
                    "--max-messages",
                    "10",
                ]
            ),
            manual_instruction="OUTLOOK-01がexit 0の時だけ実行。候補確認のみで保存・印刷・送信はしない。",
            expected_evidence=str(outlook_log_dir / "02_scan_only_dryrun.log"),
            requires_external_approval=True,
            forbidden_operations="--execute、--print、実送信、メール状態変更",
        ),
        ExternalStep(
            bundle="BUSINESS_REVIEW_BUNDLE",
            step_id="S44-01",
            approval_unit="業務OK/NG入力後に1回",
            operation="44 OK行handoff候補再生成",
            command=command_text([PYTHON_EXE, "-X", "utf8", S44_HANDOFF_CANDIDATES]),
            manual_instruction="spot check CSVへOK/NG記入後に実行。review未了行は進めない。",
            expected_evidence=str(REPORTS / "s44_spot_check_handoff_candidates_20260620"),
            requires_external_approval=False,
            forbidden_operations="Rakuraku登録、PDF processed移動、メール送信",
        ),
        ExternalStep(
            bundle="PAYMENT_APPROVAL_BUNDLE",
            step_id="S70-01",
            approval_unit="支払承認情報入力後に1回",
            operation="70 confirm-preview sample refresh",
            command=command_text([PYTHON_EXE, "-X", "utf8", S70_SAMPLE_CONFIRM]),
            manual_instruction="承認表の件数・金額・銀行確認が揃った後、previewのみ確認する。",
            expected_evidence=str(REPORTS / "s70_sample_confirm_preview_20260620"),
            requires_external_approval=False,
            forbidden_operations="--execute、支払確定、支払実行、RK10 ButtonRun",
        ),
        ExternalStep(
            bundle="PAID_AZURE_OCR_BUNDLE",
            step_id="S71-01",
            approval_unit="費用承認後に1回",
            operation="71 mock OCR apply evidence refresh",
            command=command_text([PYTHON_EXE, "-X", "utf8", S71_MOCK_OCR]),
            manual_instruction="課金OCR前の安全なmock再確認。paid OCRは別途1件だけ承認する。",
            expected_evidence=str(REPORTS / "s71_sample_mock_ocr_apply_20260620"),
            requires_external_approval=False,
            forbidden_operations="複数PDF送信、秘密値出力、原本Excel直書き、上限超過",
        ),
        ExternalStep(
            bundle="RK10_EDITOR_RUNTIME_BUNDLE",
            step_id="RK10-01",
            approval_unit="1回承認: RK10_EDITOR_RUNTIME_BUNDLE",
            operation="RKS static guard refresh before RK10 GUI",
            command=command_text([PYTHON_EXE, "-X", "utf8", RKS_STATIC_GUARD]),
            manual_instruction="GUI操作前の構造監査。RK10 Editor open/build/runtimeは手動証跡で記録する。",
            expected_evidence=str(REPORTS / "rks_static_guard_audit_20260620"),
            requires_external_approval=False,
            forbidden_operations="ButtonRun、本番書込、実メール、実印刷、ZIP直接RKS改変",
        ),
        ExternalStep(
            bundle="BUSINESS_DATA_APPROVAL_BUNDLE",
            step_id="BUSINESS-01",
            approval_unit="業務対象確定後に1回",
            operation="business data dry-run evidence refresh",
            command=fixed_safe_runner_command(),
            manual_instruction="対象日・対象者・停止条件が決まった後、no-mail/no-submit/no-write範囲で再検証する。",
            expected_evidence=str(REPORTS / "safe_goal_checks_20260620"),
            requires_external_approval=False,
            forbidden_operations="本番登録、実メール、本番Excel/サーバ確定書込、支払処理",
        ),
    ]


def build_bundle_summary(packet_payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for packet in packet_payload.get("packets", []):
        rows.append(
            {
                "bundle": str(packet["bundle"]),
                "owner": str(packet["owner"]),
                "scenarios": str(packet["scenarios"]),
                "allowed_operations": str(packet["allowed_operations"]),
                "hard_stops": str(packet["hard_stops"]),
                "csv_path": str(packet["csv_path"]),
            }
        )
    return rows


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    if raw.count(b"\x00") > max(0, len(raw) // 10):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")


def parse_summary_value(summary_text: str, key: str) -> str:
    for line in summary_text.splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def extract_hresult_codes(log_text: str) -> list[str]:
    return sorted(set(re.findall(r"com_error\((-?\d+),", log_text)))


def classify_outlook_result(summary_text: str, check_log_text: str) -> tuple[str, str]:
    if not summary_text:
        return "NOT_RUN", "OUTLOOK_COM_BUNDLE has not been executed yet."
    check_exit = parse_summary_value(summary_text, "check_outlook_com_exit")
    scan_exit = parse_summary_value(summary_text, "scan_only_dryrun_exit")
    if check_exit == "0" and scan_exit == "0":
        return "OUTLOOK_SCAN_ONLY_DRYRUN_OK", "COM check and scan-only dry-run both exited 0."
    if "can't open file" in check_log_text or "No such file or directory" in check_log_text:
        return (
            "SCRIPT_PATH_ENCODING_ERROR_FIXED_BY_UTF8_BOM",
            "PowerShell read the Japanese path with the wrong encoding; regenerate the PS1 with UTF-8 BOM.",
        )
    hresults = set(extract_hresult_codes(check_log_text))
    if "-2147221021" in hresults and "-2146959355" in hresults:
        return (
            "OUTLOOK_COM_NOT_ATTACHABLE_OR_STARTABLE",
            "Outlook COM could not attach to a running instance and Dispatch could not start the COM server.",
        )
    if hresults:
        return (
            "OUTLOOK_COM_CHECK_FAILED",
            f"Outlook COM probe failed with HRESULT(s): {', '.join(sorted(hresults))}.",
        )
    return "OUTLOOK_COM_CHECK_FAILED", "COM check did not exit 0; scan-only dry-run was skipped."


def build_last_outlook_result(out_dir: Path) -> dict[str, Any]:
    log_dir = out_dir / "outlook_com_bundle_logs"
    summary_path = log_dir / "summary.txt"
    check_log_path = log_dir / "01_check_outlook_com.log"
    scan_log_path = log_dir / "02_scan_only_dryrun.log"
    summary_text = read_text_if_exists(summary_path)
    check_log_text = read_text_if_exists(check_log_path)
    status, diagnosis = classify_outlook_result(summary_text, check_log_text)
    return {
        "status": status,
        "diagnosis": diagnosis,
        "summary_path": str(summary_path),
        "check_log_path": str(check_log_path),
        "scan_log_path": str(scan_log_path),
        "summary_exists": summary_path.exists(),
        "check_log_exists": check_log_path.exists(),
        "scan_log_exists": scan_log_path.exists(),
        "check_outlook_com_exit": parse_summary_value(summary_text, "check_outlook_com_exit"),
        "scan_only_dryrun_exit": parse_summary_value(summary_text, "scan_only_dryrun_exit"),
        "hresult_codes": extract_hresult_codes(check_log_text),
    }


def outlook_scan_only_dryrun_ok(last_outlook_result: dict[str, Any]) -> bool:
    return str(last_outlook_result.get("status", "")) == "OUTLOOK_SCAN_ONLY_DRYRUN_OK"


def external_steps_pending(steps: list[ExternalStep], last_outlook_result: dict[str, Any]) -> list[ExternalStep]:
    outlook_done = outlook_scan_only_dryrun_ok(last_outlook_result)
    return [
        step
        for step in steps
        if step.requires_external_approval
        and not (outlook_done and step.bundle == "OUTLOOK_COM_BUNDLE")
    ]


def next_single_approval(last_outlook_result: dict[str, Any]) -> str:
    if outlook_scan_only_dryrun_ok(last_outlook_result):
        return "BUSINESS_REVIEW_BUNDLE"
    return "OUTLOOK_COM_BUNDLE"


def build_payload(packet_payload: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    steps = build_known_steps(out_dir)
    last_outlook_result = build_last_outlook_result(out_dir)
    external_steps = external_steps_pending(steps, last_outlook_result)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": (
            "report/script generation only; no Outlook/RK10/Azure/mail/print/payment "
            "or production operation is executed"
        ),
        "approval_bundle_count": packet_payload.get("approval_bundle_count", 0),
        "external_approval_step_count": len(external_steps),
        "next_single_approval": next_single_approval(last_outlook_result),
        "outlook_bundle_script": str(out_dir / "outlook_com_bundle_dryrun.ps1"),
        "outlook_recovery_checklist": str(out_dir / "outlook_com_recovery_checklist.md"),
        "last_outlook_result": last_outlook_result,
        "bundle_summary": build_bundle_summary(packet_payload),
        "steps": [asdict(step) for step in steps],
    }


def build_outlook_script(out_dir: Path) -> str:
    log_dir = out_dir / "outlook_com_bundle_logs"
    summary_path = log_dir / "summary.txt"
    check_log = log_dir / "01_check_outlook_com.log"
    scan_log = log_dir / "02_scan_only_dryrun.log"
    return "\n".join(
        [
            "$ErrorActionPreference = 'Continue'",
            f"$LogDir = {ps_quote(log_dir)}",
            f"$Python = {ps_quote(PYTHON_EXE)}",
            f"$Tool = {ps_quote(S12_TOOL)}",
            f"$Config = {ps_quote(S12_PROD_CONFIG)}",
            f"$SummaryPath = {ps_quote(summary_path)}",
            "New-Item -ItemType Directory -Force -Path $LogDir | Out-Null",
            "'OUTLOOK_COM_BUNDLE safety: no --execute, no --print, no mail send, no state change' | Set-Content -LiteralPath $SummaryPath -Encoding UTF8",
            f"& $Python -X utf8 $Tool --check-outlook-com *> {ps_quote(check_log)}",
            "$CheckExit = $LASTEXITCODE",
            "'check_outlook_com_exit=' + $CheckExit | Add-Content -LiteralPath $SummaryPath -Encoding UTF8",
            "if ($CheckExit -eq 0) {",
            f"  & $Python -X utf8 $Tool --config $Config --scan-only --dry-run --dry-run-mail --max-messages 10 *> {ps_quote(scan_log)}",
            "  $ScanExit = $LASTEXITCODE",
            "} else {",
            "  $ScanExit = 'SKIPPED'",
            "  'scan_only_dryrun=SKIPPED because COM check failed' | Add-Content -LiteralPath $SummaryPath -Encoding UTF8",
            "}",
            "'scan_only_dryrun_exit=' + $ScanExit | Add-Content -LiteralPath $SummaryPath -Encoding UTF8",
            "Get-Content -LiteralPath $SummaryPath",
            "if ($CheckExit -ne 0) { exit $CheckExit }",
            "if ($ScanExit -is [int] -and $ScanExit -ne 0) { exit $ScanExit }",
            "exit 0",
            "",
        ]
    )


def build_markdown(payload: dict[str, Any]) -> str:
    steps = payload["steps"]
    bundles = payload["bundle_summary"]
    assert isinstance(steps, list)
    assert isinstance(bundles, list)
    lines = [
        "# 外部承認束 実行ランブック 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- approval_bundle_count: `{payload['approval_bundle_count']}`",
        f"- external_approval_step_count: `{payload['external_approval_step_count']}`",
        f"- next_single_approval: `{payload['next_single_approval']}`",
        f"- outlook_bundle_script: `{payload['outlook_bundle_script']}`",
        f"- outlook_recovery_checklist: `{payload['outlook_recovery_checklist']}`",
        "",
        "## Last OUTLOOK_COM_BUNDLE Result",
        "",
    ]
    last_outlook = payload["last_outlook_result"]
    assert isinstance(last_outlook, dict)
    lines.extend(
        [
            f"- status: `{last_outlook['status']}`",
            f"- diagnosis: {last_outlook['diagnosis']}",
            f"- check_outlook_com_exit: `{last_outlook['check_outlook_com_exit']}`",
            f"- scan_only_dryrun_exit: `{last_outlook['scan_only_dryrun_exit']}`",
            f"- hresult_codes: `{', '.join(last_outlook['hresult_codes'])}`",
            f"- summary: `{last_outlook['summary_path']}`",
            f"- check_log: `{last_outlook['check_log_path']}`",
            "",
        ]
    )
    lines.extend(
        [
        "## 使い方",
        "",
        "1. 承認なしで固定ランナーを再実行する。",
        "2. 外部操作が必要なものはBundle単位で1回だけ承認する。",
        "3. 実行後、該当CSVの `operator_result` / `evidence_path` / `reviewer` / `reviewed_at` を埋める。",
        "4. 固定ランナーを再実行し、HOLD解除または残理由を更新する。",
        "",
        "## 最初に承認するなら",
        "",
        (
            "- `BUSINESS_REVIEW_BUNDLE` が次。OUTLOOK_COM_BUNDLEはCOM check/scan-only dry-runが成功済みなので、実行承認ではなくintake CSVの担当者確認欄を埋める。"
            if payload["next_single_approval"] == "BUSINESS_REVIEW_BUNDLE"
            else "- `OUTLOOK_COM_BUNDLE` を1回だけ承認するのが最短。12/13のCOM HOLDを解除できる可能性がある。"
        ),
        (
            "- Outlookの実印刷・実送信は引き続き禁止。12/13は `operator_result` / `reviewer` / `reviewed_at` の最終入力待ち。"
            if payload["next_single_approval"] == "BUSINESS_REVIEW_BUNDLE"
            else "- 実行スクリプトは `--execute` / `--print` を含まず、保存・印刷・送信・メール状態変更を禁止している。"
        ),
        "",
        "## Step Matrix",
        "",
        "| Step | Bundle | Approval Unit | External Approval | Operation | Command | Evidence | Forbidden |",
        "|---|---|---|---:|---|---|---|---|",
        ]
    )
    for step in steps:
        assert isinstance(step, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(step["step_id"]),
                    str(step["bundle"]),
                    str(step["approval_unit"]).replace("|", "/"),
                    "YES" if step["requires_external_approval"] else "NO",
                    str(step["operation"]).replace("|", "/"),
                    f"`{step['command']}`" if step["command"] else "-",
                    f"`{step['expected_evidence']}`",
                    str(step["forbidden_operations"]).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Bundle Summary",
            "",
            "| Bundle | Owner | Scenarios | Allowed Operations | Hard Stops | CSV |",
            "|---|---|---|---|---|---|",
        ]
    )
    for bundle in bundles:
        assert isinstance(bundle, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(bundle["bundle"]),
                    str(bundle["owner"]),
                    str(bundle["scenarios"]).replace("|", "/"),
                    str(bundle["allowed_operations"]).replace("|", "/"),
                    str(bundle["hard_stops"]).replace("|", "/"),
                    f"`{bundle['csv_path']}`",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def build_outlook_recovery_checklist(payload: dict[str, Any]) -> str:
    last_outlook = payload["last_outlook_result"]
    assert isinstance(last_outlook, dict)
    return "\n".join(
        [
            "# OUTLOOK_COM_BUNDLE 復旧チェックリスト 2026-06-20",
            "",
            f"- generated_at: `{payload['generated_at']}`",
            "- safety: `manual recovery guide only; no process close, no Outlook launch, no mail/print/save`",
            f"- latest_status: `{last_outlook['status']}`",
            f"- check_outlook_com_exit: `{last_outlook['check_outlook_com_exit']}`",
            f"- scan_only_dryrun_exit: `{last_outlook['scan_only_dryrun_exit']}`",
            f"- hresult_codes: `{', '.join(last_outlook['hresult_codes'])}`",
            f"- retry_script: `{payload['outlook_bundle_script']}`",
            f"- summary_log: `{last_outlook['summary_path']}`",
            f"- check_log: `{last_outlook['check_log_path']}`",
            f"- scan_log: `{last_outlook['scan_log_path']}`",
            "",
            "## 手順",
            "",
            "1. Outlookの未保存メール、下書き、開きっぱなしの編集画面を保存または閉じる。",
            "2. Classic Outlookの全ウィンドウを通常操作で閉じる。",
            "3. サインイン、プロファイル選択、アドイン警告、更新通知などのモーダルが残っていないことを確認する。",
            "4. 同じWindowsユーザーの通常デスクトップ画面でClassic Outlookを再起動する。",
            "5. 受信トレイが表示され、追加のダイアログが出ていないことを確認する。",
            "6. `outlook_com_bundle_dryrun.ps1` を実行し、`check_outlook_com_exit=0` と `scan_only_dryrun_exit=0` を確認する。",
            "7. 成功後、固定ランナーを再実行して `outlook_bundle_evidence_collect` が `ready_for_intake=True` になることを確認する。",
            "",
            "## 禁止",
            "",
            "- このチェックリストだけではOutlookプロセスを強制終了しない。",
            "- `--execute`、`--print`、実印刷、実送信、メール状態変更、未読/既読変更はしない。",
            "- scan-only dry-runが成功するまで、12/13を完了扱いにしない。",
            "",
            "## 成功時に置く証跡",
            "",
            "- `summary.txt` に `check_outlook_com_exit=0` と `scan_only_dryrun_exit=0` があること。",
            "- `01_check_outlook_com.log` と `02_scan_only_dryrun.log` が存在すること。",
            "- `C:\\ProgramData\\Generative AI\\Github\\PDF-RakuRaku-Seisan\\plans\\reports\\outlook_bundle_evidence_collect_20260620\\outlook_bundle_evidence_collect.md.numbered` が `updated_intake=True` になること。",
            "",
        ]
    )


def build_rk10_recovery_checklist(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# RK10_EDITOR_RUNTIME_BUNDLE 復旧チェックリスト 2026-06-20",
            "",
            f"- generated_at: `{payload['generated_at']}`",
            "- safety: `manual recovery guide only; no ButtonRun, no RunScenario, no production write, no mail/print/payment/final submit`",
            f"- probe_tool: `{RKS_EDITOR_PROBE}`",
            "- latest_s58_original_report: `C:\\ProgramData\\RK10\\Robots\\migration\\reports\\rks_editor_open_build_probe_20260620_20260620_184738\\rks_editor_open_build_probe.md.numbered`",
            "- latest_s58_ascii_copy_report: `C:\\ProgramData\\RK10\\Robots\\migration\\reports\\rks_editor_open_build_probe_20260620_20260620_185152\\rks_editor_open_build_probe.md.numbered`",
            "- latest_s63_control_report: `C:\\ProgramData\\RK10\\Robots\\migration\\reports\\rks_editor_open_build_probe_20260620_20260620_185538\\rks_editor_open_build_probe.md.numbered`",
            "",
            "## 現在の判定",
            "",
            "- 58原本、58 ASCII別名コピー、過去成功済み63の全てが `RK10_EDITOR_OPEN_TIMEOUT`。",
            "- 58固有ではなく、現在のRK10 Editor環境がcold。画面証跡ではRK10ライセンス有効期限警告が出ている。",
            "",
            "## 手順",
            "",
            "1. RK10のライセンス登録/更新を行い、有効期限警告が出ない状態にする。",
            "2. RK10を通常起動し、ライセンス選択後にホーム画面で警告やモーダルが残っていないことを確認する。",
            "3. 先に63を対照としてRK10 Editorで開き、ウィンドウタイトルに対象 `.rks` 名が入ることを確認する。",
            "4. 63で開けた後に58を同じ手順で開き、Debugger build artifactが生成されることを確認する。",
            "5. 成功後、RKS runtime operator CSVへ operator_result / rk10_editor_open / rk10_build / latest_log_path / operator_name / checked_at を記入する。",
            "6. 固定ランナーを再実行して `RKS_RUNTIME_INTAKE_VALIDATION` が更新されることを確認する。",
            "",
            "## 禁止",
            "",
            "- ButtonRun、RunScenario、本番TXT/Excel/サーバ書込、実メール、実印刷、支払実行、最終申請はしない。",
            "- ZIP直接編集したRKSを合格扱いにしない。",
            "- 63対照が開けない状態で58だけを不良扱いしない。",
            "",
            "## 成功時に置く証跡",
            "",
            "- 63と58それぞれのRK10 Editorタイトルに対象 `.rks` 名が含まれる画面証跡。",
            "- Debugger `Temp\\Program.cs` と build artifactの照合結果。",
            "- no-mail/no-write/safe-stop範囲のlatest clean log。",
            "",
        ]
    )


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "external_approval_runbook.json"
    md_path = out_dir / "external_approval_runbook.md"
    csv_path = out_dir / "external_approval_steps.csv"
    ps1_path = out_dir / "outlook_com_bundle_dryrun.ps1"
    recovery_path = out_dir / "outlook_com_recovery_checklist.md"
    rk10_recovery_path = out_dir / "rk10_editor_recovery_checklist.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    recovery_path.write_text(build_outlook_recovery_checklist(payload), encoding="utf-8")
    rk10_recovery_path.write_text(build_rk10_recovery_checklist(payload), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "step_id",
            "bundle",
            "approval_unit",
            "requires_external_approval",
            "operation",
            "command",
            "expected_evidence",
            "forbidden_operations",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for step in payload["steps"]:
            writer.writerow({field: step[field] for field in fieldnames})
    ps1_path.write_text(build_outlook_script(out_dir), encoding="utf-8-sig")
    write_numbered_copy(md_path)
    write_numbered_copy(recovery_path)
    write_numbered_copy(rk10_recovery_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate external approval runbook.")
    parser.add_argument("--packet-json", type=Path, default=EXECUTION_PACKET_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet_payload = load_execution_packet(args.packet_json)
    payload = build_payload(packet_payload, args.out_dir)
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
