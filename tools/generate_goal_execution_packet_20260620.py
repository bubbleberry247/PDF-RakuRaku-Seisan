"""Generate bundle execution packets for the active RK10 validation goal.

This tool only writes repository reports. It does not open Outlook, RK10,
Rakuraku, Azure, printers, mail, payment systems, MainSV, or production files.
The packet turns the remaining HOLD board into operator-ready CSV checklists so
approvals can be requested by bundle instead of by individual command.
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

from generate_goal_unblock_board_20260620 import build_payload as build_board_payload


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "goal_execution_packet_20260620"
OPERATOR_FIELDS = ["operator_result", "evidence_path", "reviewer", "reviewed_at"]
CLEANUP_FIELDS = [
    "rakuraku_customer_login_used",
    "temporary_save_created",
    "created_data_cleanup_status",
    "created_data_cleanup_evidence_path",
    "cleanup_reviewer",
    "cleanup_reviewed_at",
]
RAKURAKU_TEMP_SAVE_CLEANUP_RULE = (
    "客先担当者名ログイン・一時保存データ作成の有無と後続処置は任意記録欄として残す。"
    "削除証跡は承認ゲートの必須条件にしない"
)
S44_REPORT_DIR = ROOT / "plans" / "reports" / "s44_spot_check_handoff_candidates_20260620"
S70_PAYMENT_PREFILL_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s70_payment_approval_evidence_collect_20260620"
    / "s70_payment_confirmation_gate_checklist_prefill.csv"
)
S71_PAID_SMOKE_TEMPLATE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "s71_paid_azure_ocr_evidence_collect_20260620"
    / "s71_paid_azure_one_pdf_smoke_summary_template.json"
)
S71_ENVIRONMENT_PRESENCE_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s71_paid_azure_ocr_evidence_collect_20260620"
    / "s71_azure_ocr_environment_presence.csv"
)
BUSINESS_DATA_APPROVAL_CHECKLIST_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "business_data_approval_bundle"
    / "business_data_approval_checklist.csv"
)
RKS_RUNTIME_OPERATOR_INTAKE_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "rk10_editor_runtime_bundle"
    / "rks_runtime_operator_intake.csv"
)
RK10_RECOVERY_CHECKLIST_MD = (
    ROOT
    / "plans"
    / "reports"
    / "external_approval_runbook_20260620"
    / "rk10_editor_recovery_checklist.md.numbered"
)
OUTLOOK_BUNDLE_DRYRUN_PS1 = (
    ROOT
    / "plans"
    / "reports"
    / "external_approval_runbook_20260620"
    / "outlook_com_bundle_dryrun.ps1"
)
OUTLOOK_RECOVERY_CHECKLIST_MD = (
    ROOT
    / "plans"
    / "reports"
    / "external_approval_runbook_20260620"
    / "outlook_com_recovery_checklist.md"
)
SUPPORTING_INPUT_PATHS_BY_BUNDLE: dict[str, tuple[Path, ...]] = {
    "BUSINESS_REVIEW_BUNDLE": (
        S44_REPORT_DIR / "s44_business_review_single_entry_input.csv",
        S44_REPORT_DIR / "s44_business_review_next_steps.md",
        S44_REPORT_DIR / "s44_business_review_decision_input.csv",
        S44_REPORT_DIR / "s44_business_review_bucket_decision_input.csv",
        S44_REPORT_DIR / "s44_business_review_priority_queue.csv",
        S44_REPORT_DIR / "s44_review_01_amount_zero_review.csv",
        S44_REPORT_DIR / "s44_review_02_amount_mismatch_review.csv",
        S44_REPORT_DIR / "s44_review_03_amount_match_quick_review.csv",
        S44_REPORT_DIR / "s44_business_review_aid.csv",
    ),
    "BUSINESS_DATA_APPROVAL_BUNDLE": (BUSINESS_DATA_APPROVAL_CHECKLIST_CSV,),
    "PAYMENT_APPROVAL_BUNDLE": (S70_PAYMENT_PREFILL_CSV,),
    "PAID_AZURE_OCR_BUNDLE": (
        S71_ENVIRONMENT_PRESENCE_CSV,
        S71_PAID_SMOKE_TEMPLATE_JSON,
    ),
    "RK10_EDITOR_RUNTIME_BUNDLE": (
        RKS_RUNTIME_OPERATOR_INTAKE_CSV,
        RK10_RECOVERY_CHECKLIST_MD,
    ),
    "OUTLOOK_COM_BUNDLE": (
        OUTLOOK_BUNDLE_DRYRUN_PS1,
        OUTLOOK_RECOVERY_CHECKLIST_MD,
    ),
}


@dataclass(frozen=True)
class ExecutionPacket:
    bundle: str
    owner: str
    scenarios: str
    approval_scope: str
    preconditions: str
    allowed_operations: str
    evidence_to_capture: str
    cleanup_rule: str
    hard_stops: str
    supporting_input_paths: str
    csv_path: str


PACKET_RULES = {
    "BUSINESS_DATA_APPROVAL_BUNDLE": {
        "preconditions": "対象日・対象者/対象データ・停止条件・承認者を記録する",
        "allowed_operations": "no-mail/no-submit/no-write/dry-runまたは登録前停止まで",
        "evidence_to_capture": "対象データ、dry-runログ、停止位置、件数/金額、latest clean log",
        "hard_stops": "本番登録、実メール、本番Excel/サーバ確定書込、支払処理",
    },
    "BUSINESS_REVIEW_BUNDLE": {
        "preconditions": "44 spot check CSVにOK/NGを記入し、OK行だけ対象にする",
        "allowed_operations": "OK行のshadow handoff再生成とlive handoff候補確認まで",
        "evidence_to_capture": "OK/NG入力済みCSV、候補件数/金額、validation結果、PDF存在確認",
        "hard_stops": "review未了の登録、Rakuraku操作、PDF processed移動、メール送信",
    },
    "OUTLOOK_COM_BUNDLE": {
        "preconditions": "Outlookを閉じてよい状態、Classic Outlook COM復旧許可",
        "allowed_operations": "--check-outlook-com、成功後dry-run/no-print/no-mailまで",
        "evidence_to_capture": "COM check exit 0、dry-runログ、保存対象件数、印刷/送信未実行ログ",
        "hard_stops": "実印刷、実送信、メール状態変更、未読/既読変更",
    },
    "PAID_AZURE_OCR_BUNDLE": {
        "preconditions": "endpoint/key、費用上限、承認者、1件PDFを記録する",
        "allowed_operations": "1件PDFのpaid OCR smoke testとコピーExcel照合まで",
        "evidence_to_capture": "環境変数存在確認、サンプルPDF名、費用上限、OCR結果、コピーExcel照合",
        "hard_stops": "複数PDF送信、秘密値出力、原本Excel直書き、上限超過",
    },
    "PAYMENT_APPROVAL_BUNDLE": {
        "preconditions": "expected_count、expected_total_amount_yen、銀行確認、承認者を記録する",
        "allowed_operations": "confirm-previewのみ",
        "evidence_to_capture": "入力済み承認表、preview件数/金額、差異0、execute未実行ログ",
        "hard_stops": "--execute、支払確定、支払実行、RK10 ButtonRun",
    },
    "RK10_EDITOR_RUNTIME_BUNDLE": {
        "preconditions": "対象RKS、確認範囲、保存先別名、停止条件、操作者を記録する",
        "allowed_operations": "RK10 Editor open/build、safe-stop/runtime、latest clean log取得まで",
        "evidence_to_capture": "metadata guard、open/build結果、safe-stopログ、latest clean log、別名保存パス",
        "hard_stops": "ButtonRun、本番書込、実メール、実印刷、最終申請、ZIP直接RKS改変",
    },
}


def slugify(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return text or "bundle"


def split_scenarios(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def display_supporting_path(path: Path) -> Path:
    locked_copy_path = Path(str(path) + ".locked_copy")
    if locked_copy_path.exists():
        return locked_copy_path
    return path


def supporting_input_paths_for_bundle(bundle: str) -> str:
    return " / ".join(
        str(display_supporting_path(path))
        for path in SUPPORTING_INPUT_PATHS_BY_BUNDLE.get(bundle, ())
    )


def build_source_map(board_payload: dict[str, Any]) -> dict[str, str]:
    return {
        str(row["scenario"]): str(row["source"])
        for row in board_payload["rows"]
    }


def build_current_evidence_map(board_payload: dict[str, Any]) -> dict[str, str]:
    evidence_map: dict[str, str] = {}
    for row in board_payload["rows"]:
        scenario = str(row["scenario"])
        supplemental = str(row.get("supplemental_evidence") or "").strip()
        evidence_map[scenario] = supplemental or str(row["source"])
    return evidence_map


def read_existing_operator_fields(csv_path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not csv_path.exists():
        return {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            (str(row.get("scenario", "")).strip(), str(row.get("bundle", "")).strip()): {
                field: str(row.get(field, ""))
                for field in [*OPERATOR_FIELDS, *CLEANUP_FIELDS]
            }
            for row in csv.DictReader(handle)
            if str(row.get("scenario", "")).strip()
            and str(row.get("bundle", "")).strip()
        }


def build_packets(board_payload: dict[str, Any], out_dir: Path) -> list[ExecutionPacket]:
    packets = []
    for bundle in board_payload["approval_bundles"]:
        bundle_name = str(bundle["bundle"])
        rule = PACKET_RULES[bundle_name]
        csv_path = out_dir / f"{slugify(bundle_name)}.csv"
        packets.append(
            ExecutionPacket(
                bundle=bundle_name,
                owner=str(bundle["owner"]),
                scenarios=str(bundle["scenarios"]),
                approval_scope=str(bundle["approval_scope"]),
                preconditions=rule["preconditions"],
                allowed_operations=rule["allowed_operations"],
                evidence_to_capture=rule["evidence_to_capture"],
                cleanup_rule=RAKURAKU_TEMP_SAVE_CLEANUP_RULE,
                hard_stops=rule["hard_stops"],
                supporting_input_paths=supporting_input_paths_for_bundle(bundle_name),
                csv_path=str(csv_path),
            )
        )
    return packets


def write_packet_csvs(
    packets: list[ExecutionPacket],
    source_map: dict[str, str],
    current_evidence_map: dict[str, str] | None = None,
) -> None:
    fieldnames = [
        "scenario",
        "bundle",
        "owner",
        "approval_scope",
        "preconditions",
        "allowed_operations",
        "evidence_to_capture",
        "cleanup_rule",
        "hard_stops",
        "supporting_input_paths",
        "source",
        "current_safe_evidence",
        "current_safe_evidence_scope",
        "operator_result",
        "evidence_path",
        "reviewer",
        "reviewed_at",
        "rakuraku_customer_login_used",
        "temporary_save_created",
        "created_data_cleanup_status",
        "created_data_cleanup_evidence_path",
        "cleanup_reviewer",
        "cleanup_reviewed_at",
    ]
    for packet in packets:
        csv_path = Path(packet.csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        existing_operator_fields = read_existing_operator_fields(csv_path)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for scenario in split_scenarios(packet.scenarios):
                preserved_fields = existing_operator_fields.get((scenario, packet.bundle), {})
                writer.writerow(
                    {
                        "scenario": scenario,
                        "bundle": packet.bundle,
                        "owner": packet.owner,
                        "approval_scope": packet.approval_scope,
                        "preconditions": packet.preconditions,
                        "allowed_operations": packet.allowed_operations,
                        "evidence_to_capture": packet.evidence_to_capture,
                        "cleanup_rule": packet.cleanup_rule,
                        "hard_stops": packet.hard_stops,
                        "supporting_input_paths": packet.supporting_input_paths,
                        "source": source_map.get(scenario, ""),
                        "current_safe_evidence": (current_evidence_map or {}).get(scenario, ""),
                        "current_safe_evidence_scope": (
                            "reference_only_not_operator_approval"
                            if (current_evidence_map or {}).get(scenario)
                            else ""
                        ),
                        **{
                            field: preserved_fields.get(field, "")
                            for field in [*OPERATOR_FIELDS, *CLEANUP_FIELDS]
                        },
                    }
                )


def build_payload(s12_exit_code: int | None, out_dir: Path) -> dict[str, Any]:
    board_payload = build_board_payload(s12_exit_code)
    packets = build_packets(board_payload, out_dir)
    source_map = build_source_map(board_payload)
    current_evidence_map = build_current_evidence_map(board_payload)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": "read-only execution packet generation only; no external operation",
        "source_board_generated_at": board_payload["generated_at"],
        "scenario_count": board_payload["scenario_count"],
        "approval_bundle_count": len(packets),
        "packet_csv_count": len(packets),
        "fixed_safe_runner": board_payload["fixed_safe_runner"],
        "packets": [asdict(packet) for packet in packets],
        "source_map": source_map,
        "current_evidence_map": current_evidence_map,
    }


def build_markdown(payload: dict[str, Any]) -> str:
    packets = payload["packets"]
    assert isinstance(packets, list)
    lines = [
        "# 目標実行パケット 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- approval_bundle_count: `{payload['approval_bundle_count']}`",
        f"- packet_csv_count: `{payload['packet_csv_count']}`",
        "",
        "## Use Order",
        "",
        "1. 固定ランナーで最新HOLDを再確認する。",
        "2. 下表のBundle単位で承認する。",
        "3. 該当CSVの `operator_result` / `evidence_path` / `reviewer` / `reviewed_at` を埋める。",
        "4. `rakuraku_customer_login_used` / `temporary_save_created` / cleanup系列は任意記録欄。削除証跡は承認ゲートの必須条件にしない。",
        "5. 実行後に固定ランナーを再実行し、HOLD解除または残理由を更新する。",
        "",
        "## Fixed Safe Runner",
        "",
        f"`{payload['fixed_safe_runner']}`",
        "",
        "## Packet Matrix",
        "",
        "| Bundle | Owner | Scenarios | Allowed Operations | Evidence To Capture | Supporting Inputs | Cleanup Rule | Hard Stops | CSV |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for packet in packets:
        assert isinstance(packet, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(packet["bundle"]),
                    str(packet["owner"]),
                    str(packet["scenarios"]).replace("|", "/"),
                    str(packet["allowed_operations"]).replace("|", "/"),
                    str(packet["evidence_to_capture"]).replace("|", "/"),
                    str(packet["supporting_input_paths"]).replace("|", "/"),
                    str(packet["cleanup_rule"]).replace("|", "/"),
                    str(packet["hard_stops"]).replace("|", "/"),
                    f"`{packet['csv_path']}`",
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
    parser = argparse.ArgumentParser(description="Generate RK10 goal execution packet.")
    parser.add_argument(
        "--s12-exit-code",
        type=int,
        default=2,
        help="Latest known 12/13 Outlook COM probe exit code.",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.s12_exit_code, args.out_dir)
    packets = [
        ExecutionPacket(**packet)
        for packet in payload["packets"]
    ]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_packet_csvs(
        packets,
        dict(payload["source_map"]),
        dict(payload["current_evidence_map"]),
    )
    json_path = args.out_dir / "goal_execution_packet.json"
    md_path = args.out_dir / "goal_execution_packet.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
