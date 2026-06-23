"""Generate a read-only unblock board for the active RK10 validation goal.

The board is intentionally evidence-only. It does not run Outlook, RK10,
Rakuraku, Azure, printing, mail, payment confirmation, or production writes.
Its purpose is to reduce approval prompts by grouping remaining work into
approval bundles instead of one command at a time.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from generate_goal_status_snapshot_20260620 import build_payload as build_snapshot_payload
from generate_rks_gate_matrix_20260620 import build_payload as build_rks_payload


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "goal_unblock_board_20260620"
FIXED_SAFE_RUNNER = ROOT / "tools" / "run_safe_goal_checks_20260620.py"
BUNDLE_EVIDENCE_INTAKE_SYNC_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_intake_sync_20260620"
    / "bundle_evidence_intake_sync.json"
)
BUNDLE_EVIDENCE_PACKS_DIR = ROOT / "plans" / "reports" / "bundle_evidence_packs_20260620"
LEGACY_OUTLOOK_AUTO_REVIEWER = "OUTLOOK_COM_BUNDLE_AUTO_COLLECTOR"


@dataclass(frozen=True)
class UnblockRow:
    scenario: str
    current_status: str
    rks_status: str
    approval_bundle: str
    owner: str
    can_codex_complete_next_gate_without_approval: bool
    blocked_until: str
    next_action: str
    resolution_lane: str
    codex_safe_next_action: str
    approval_reduction_hint: str
    source: str
    supplemental_evidence: str
    supplemental_evidence_exists: bool


@dataclass(frozen=True)
class ApprovalBundle:
    bundle: str
    owner: str
    scenarios: str
    approval_scope: str
    still_forbidden: str


def split_grouped_scenarios(value: str) -> set[str]:
    return {part.strip() for part in value.split("/") if part.strip()}


def find_rks_status(scenario: str, rks_rows: list[dict[str, Any]]) -> str:
    for row in rks_rows:
        row_scenario = str(row["scenario"])
        if scenario == row_scenario:
            return str(row["current_rks_status"])
        if scenario in split_grouped_scenarios(row_scenario):
            return str(row["current_rks_status"])
    return "NO_RKS_MATRIX_ROW"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def non_empty_evidence_files(value: str) -> list[Path]:
    if not value.strip():
        return []
    path = Path(value)
    if path.is_file():
        return [path] if path.stat().st_size > 0 else []
    if not path.is_dir():
        return []
    return sorted(
        item
        for item in path.rglob("*")
        if item.is_file() and item.stat().st_size > 0
    )


def intake_row_completed(row: dict[str, str]) -> bool:
    bundle = str(row.get("bundle", "")).strip()
    reviewer = str(row.get("reviewer", "")).strip()
    if bundle == "OUTLOOK_COM_BUNDLE" and reviewer == LEGACY_OUTLOOK_AUTO_REVIEWER:
        return False
    if str(row.get("operator_result", "")).strip().upper() != "OK":
        return False
    evidence_path = str(row.get("evidence_path") or row.get("final_evidence_path") or "").strip()
    if not evidence_path:
        return False
    if not reviewer or not str(row.get("reviewed_at", "")).strip():
        return False
    return bool(non_empty_evidence_files(evidence_path))


def load_completed_bundles_from_intake(root: Path | None = None) -> set[str]:
    resolved_root = root or BUNDLE_EVIDENCE_PACKS_DIR
    if not resolved_root.exists():
        return set()
    completed: set[str] = set()
    for intake_path in resolved_root.glob("*/final_evidence_intake.csv"):
        with intake_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if intake_row_completed({str(key): str(value) for key, value in row.items()}):
                    completed.add(str(row.get("bundle", "")).strip())
    return {bundle for bundle in completed if bundle}


def load_completed_bundles_from_sync(path: Path) -> set[str]:
    payload = load_json(path)
    results = payload.get("results", [])
    if not isinstance(results, list):
        return set()
    return {
        str(result.get("bundle", "")).strip()
        for result in results
        if isinstance(result, dict) and result.get("ready_to_sync") is True
    } - {""}


def load_completed_bundles(path: Path | None = None) -> set[str]:
    sync_path = path or BUNDLE_EVIDENCE_INTAKE_SYNC_JSON
    if sync_path.exists():
        return load_completed_bundles_from_sync(sync_path)
    return load_completed_bundles_from_intake()


def classify_bundle(scenario: str, status: str, rks_status: str) -> tuple[str, str, str]:
    if scenario == "44":
        return (
            "BUSINESS_REVIEW_BUNDLE",
            "業務担当者",
            "spot check OK/NG未記入のため自動でlive handoffへ進めない",
        )
    if scenario == "70":
        return (
            "PAYMENT_APPROVAL_BUNDLE",
            "支払承認者",
            "件数・金額・銀行確認・承認者が未記録のため支払確定へ進めない",
        )
    if scenario == "71":
        return (
            "PAID_AZURE_OCR_BUNDLE",
            "Azure/費用承認者",
            "endpoint/key・費用承認・1件サンプルが未設定のため課金OCRへ進めない",
        )
    if scenario == "12/13":
        if status == "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL":
            return (
                "OUTLOOK_COM_BUNDLE",
                "PC/Outlook管理者",
                "Outlook dry-run/no-print/no-mail証跡は配置済み。operator_result/reviewer/reviewed_at未記入のため最終取込は未完",
            )
        return (
            "OUTLOOK_COM_BUNDLE",
            "PC/Outlook管理者",
            "Outlook COM exit 0が未確認のためメール保存・印刷フローへ進めない",
        )
    has_real_rks_matrix_status = rks_status != "NO_RKS_MATRIX_ROW" and "RKS" in rks_status
    if "RKS" in status or has_real_rks_matrix_status or scenario in {"38", "42", "51/52", "56", "57", "58"}:
        return (
            "RK10_EDITOR_RUNTIME_BUNDLE",
            "RK10操作担当者",
            "RK10 Editor open/build/runtime/latest logの不足はGUI操作なしに解消できない",
        )
    return (
        "BUSINESS_DATA_APPROVAL_BUNDLE",
        "業務担当者",
        "実対象データ・停止条件・業務承認が未確定のため本番業務費用へ進めない",
    )


def classify_resolution_lane(
    scenario: str,
    status: str,
    rks_status: str,
    bundle: str,
) -> tuple[str, str, str]:
    if bundle == "RK10_EDITOR_RUNTIME_BUNDLE":
        return (
            "NEEDS_RK10_GUI_EVIDENCE",
            "RK10担当者がopen/build/runtime/latest logを取得後、Codexは固定runnerで検証する",
            "対象RKSを1回のRK10確認枠にまとめ、ButtonRunと本番書込は別承認のままにする",
        )
    if bundle == "OUTLOOK_COM_BUNDLE" and status == "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL":
        return (
            "NEEDS_FINAL_INTAKE_ONLY",
            "operator_result/reviewer/reviewed_at記入後、Codexは証跡同期と固定runnerを再実行する",
            "unified_final_evidence_input.csvの該当entry_keyだけ埋めれば、実印刷・実送信承認は不要",
        )
    if bundle == "OUTLOOK_COM_BUNDLE":
        return (
            "NEEDS_LOCAL_OUTLOOK_DRYRUN",
            "PC担当者がno-print/no-mailのCOM dry-run証跡を取得後、Codexは取込検証する",
            "Outlook確認を1回のdry-run承認にまとめ、実印刷・実送信は別承認のままにする",
        )
    if bundle == "PAID_AZURE_OCR_BUNDLE":
        return (
            "NEEDS_PAID_SERVICE_APPROVAL",
            "費用上限・endpoint/key・1件PDFが確定後、Codexはpaid smoke証跡だけ検証する",
            "課金OCRは1件PDFのsmoke承認に限定し、複数PDF送信は別承認に残す",
        )
    if bundle == "PAYMENT_APPROVAL_BUNDLE":
        return (
            "NEEDS_PAYMENT_APPROVER_INPUT",
            "支払承認者の件数・金額・銀行確認記入後、Codexはconfirm-preview証跡を検証する",
            "支払実行ではなくconfirm-previewまでを1束にして、--executeは別承認に残す",
        )
    if bundle == "BUSINESS_REVIEW_BUNDLE":
        return (
            "NEEDS_BUSINESS_REVIEW_INPUT",
            "OK/NG記入後、CodexはOK行だけhandoff候補へ進められるか検証する",
            "spot check記入を1つのSTART_HEREに集約し、Rakuraku登録とprocessed移動は別承認に残す",
        )
    if bundle == "BUSINESS_DATA_APPROVAL_BUNDLE":
        return (
            "NEEDS_BUSINESS_DATA_APPROVAL",
            "実対象データ・停止条件・承認者記入後、Codexはno-mail/no-submit/no-writeで再検証する",
            "43/47/55/63を1束で承認し、本番登録・実送信・本番Excel書込は別承認に残す",
        )
    return (
        "NEEDS_OPERATOR_DECISION",
        "担当者の入力後、Codexは固定runnerで再検証する",
        f"{scenario}の残ゲートを1束にまとめ、不可逆操作は別承認に残す: {rks_status}",
    )


def completed_bundle_row(row: UnblockRow) -> UnblockRow:
    return replace(
        row,
        owner="証跡済み",
        can_codex_complete_next_gate_without_approval=True,
        blocked_until="final evidence ready; no additional approval required for this evidence bundle",
        next_action="不可逆操作は別承認のまま、完了済み証跡束として次承認キューから除外する。",
        resolution_lane="FINAL_EVIDENCE_READY",
        codex_safe_next_action="固定runnerで完了済み束として除外されることを再確認する",
        approval_reduction_hint="この束の追加承認は不要。不可逆操作だけ別承認のまま維持する",
    )


def build_rows(
    snapshot_payload: dict[str, Any],
    rks_payload: dict[str, Any],
    completed_bundles: set[str] | None = None,
) -> list[UnblockRow]:
    rks_rows = list(rks_payload["rows"])
    completed_bundle_names = completed_bundles or set()
    rows = []
    for item in snapshot_payload["scenarios"]:
        scenario = str(item["scenario"])
        status = str(item["current_status"])
        rks_status = find_rks_status(scenario, rks_rows)
        bundle, owner, blocked_until = classify_bundle(scenario, status, rks_status)
        resolution_lane, codex_safe_next_action, approval_reduction_hint = classify_resolution_lane(
            scenario,
            status,
            rks_status,
            bundle,
        )
        row = UnblockRow(
            scenario=scenario,
            current_status=status,
            rks_status=rks_status,
            approval_bundle=bundle,
            owner=owner,
            can_codex_complete_next_gate_without_approval=False,
            blocked_until=blocked_until,
            next_action=str(item["next_action"]),
            resolution_lane=resolution_lane,
            codex_safe_next_action=codex_safe_next_action,
            approval_reduction_hint=approval_reduction_hint,
            source=str(item["source"]),
            supplemental_evidence=str(item.get("supplemental_evidence", "")),
            supplemental_evidence_exists=bool(item.get("supplemental_evidence_exists")),
        )
        if bundle in completed_bundle_names:
            row = completed_bundle_row(row)
        rows.append(row)
    return rows


def build_bundles(rows: list[UnblockRow]) -> list[ApprovalBundle]:
    grouped: dict[str, list[UnblockRow]] = {}
    for row in rows:
        grouped.setdefault(row.approval_bundle, []).append(row)
    bundle_rules = {
        "BUSINESS_REVIEW_BUNDLE": (
            "業務担当者",
            "44 spot checkで行単位または安全なbucket単位のOK/NGを記入し、OK行だけhandoff候補へ進める",
            "review未了のままRakuraku登録・PDF processed移動",
        ),
        "PAYMENT_APPROVAL_BUNDLE": (
            "支払承認者",
            "70の件数・金額・銀行確認・承認者を記録し、confirm-previewのみ確認する",
            "--execute・支払実行・RK10 ButtonRun",
        ),
        "PAID_AZURE_OCR_BUNDLE": (
            "Azure/費用承認者",
            "71のendpoint/key・費用上限・承認者・1件PDFを確定してpaid smokeだけ許可する",
            "複数PDF送信・原本Excel直書き・秘密値出力",
        ),
        "OUTLOOK_COM_BUNDLE": (
            "PC/Outlook管理者",
            "12/13はCOM check/scan-only dry-run/no-print/no-mail証跡を確認し、最終入力欄を埋める",
            "実印刷・実送信・メール状態変更",
        ),
        "RK10_EDITOR_RUNTIME_BUNDLE": (
            "RK10操作担当者",
            "必要RKSだけRK10 Editor open/build/runtime/safe-stop/latest logをまとめて確認する",
            "ButtonRun・本番書込・実メール・最終申請",
        ),
        "BUSINESS_DATA_APPROVAL_BUNDLE": (
            "業務担当者",
            "実対象データ・停止条件・承認者を決め、no-mail/no-submit/no-writeで再検証する",
            "本番登録・実送信・本番Excel/サーバ確定書込",
        ),
    }
    bundles = []
    for bundle in sorted(grouped):
        owner, approval_scope, still_forbidden = bundle_rules[bundle]
        scenarios = ", ".join(row.scenario for row in grouped[bundle])
        bundles.append(
            ApprovalBundle(
                bundle=bundle,
                owner=owner,
                scenarios=scenarios,
                approval_scope=approval_scope,
                still_forbidden=still_forbidden,
            )
        )
    return bundles


def count_resolution_lanes(rows: list[UnblockRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.resolution_lane] = counts.get(row.resolution_lane, 0) + 1
    return dict(sorted(counts.items()))


def format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return ""
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def build_payload(s12_exit_code: int | None) -> dict[str, Any]:
    snapshot_payload = build_snapshot_payload(s12_exit_code)
    rks_payload = build_rks_payload()
    completed_bundles = load_completed_bundles()
    rows = build_rows(snapshot_payload, rks_payload, completed_bundles)
    bundles = build_bundles(rows)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": "read-only evidence board only; no external operation",
        "safe_refresh_available_without_new_approval": True,
        "fixed_safe_runner": (
            f"C:\\Users\\masam\\AppData\\Local\\Programs\\Python\\Python313\\python.exe -X utf8 "
            f"{FIXED_SAFE_RUNNER} --s12-exit-code {s12_exit_code if s12_exit_code is not None else 2}"
        ),
        "scenario_count": len(rows),
        "approval_required_count": len(
            [row for row in rows if not row.can_codex_complete_next_gate_without_approval]
        ),
        "approval_bundle_count": len(bundles),
        "completed_bundles_excluded": sorted(completed_bundles),
        "resolution_lane_counts": count_resolution_lanes(rows),
        "rows": [asdict(row) for row in rows],
        "approval_bundles": [asdict(bundle) for bundle in bundles],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    bundles = payload["approval_bundles"]
    assert isinstance(rows, list)
    assert isinstance(bundles, list)
    lines = [
        "# 目標HOLD解除ボード 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- safe_refresh_available_without_new_approval: `{payload['safe_refresh_available_without_new_approval']}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- approval_required_count: `{payload['approval_required_count']}`",
        f"- approval_bundle_count: `{payload['approval_bundle_count']}`",
        f"- completed_bundles_excluded: `{', '.join(payload.get('completed_bundles_excluded', []))}`",
        f"- resolution_lane_counts: `{format_counts(payload.get('resolution_lane_counts', {}))}`",
        "",
        "## Safe Refresh",
        "",
        "- 追加承認を減らす通常再確認は、固定ランナー1本で実行する。",
        f"- fixed_safe_runner: `{payload['fixed_safe_runner']}`",
        "- ただし、GUI/Outlook/RK10/実送信/実印刷/支払実行/本番書込/Azure課金は別承認にする。",
        "",
        "## Approval Bundles",
        "",
        "| Bundle | Owner | Scenarios | Approval Scope | Still Forbidden |",
        "|---|---|---|---|---|",
    ]
    for item in bundles:
        assert isinstance(item, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["bundle"]),
                    str(item["owner"]),
                    str(item["scenarios"]).replace("|", "/"),
                    str(item["approval_scope"]).replace("|", "/"),
                    str(item["still_forbidden"]).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Approval Reduction Lanes",
            "",
            "| Lane | Count | What Codex Can Still Do Without New Approval | How This Reduces Approval Prompts |",
            "|---|---:|---|---|",
        ]
    )
    lane_examples: dict[str, dict[str, str]] = {}
    for item in rows:
        assert isinstance(item, dict)
        lane = str(item.get("resolution_lane", "NEEDS_OPERATOR_DECISION"))
        lane_examples.setdefault(
            lane,
            {
                "codex_safe_next_action": str(item.get("codex_safe_next_action", "")),
                "approval_reduction_hint": str(item.get("approval_reduction_hint", "")),
            },
        )
    lane_counts = payload.get("resolution_lane_counts", {})
    assert isinstance(lane_counts, dict)
    for lane, count in sorted(lane_counts.items()):
        example = lane_examples.get(str(lane), {})
        lines.append(
            "| "
            + " | ".join(
                [
                    str(lane),
                    str(count),
                    str(example.get("codex_safe_next_action", "")).replace("|", "/"),
                    str(example.get("approval_reduction_hint", "")).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Scenario Board",
            "",
            "| Scenario | Current Status | RKS Status | Bundle | Owner | Can Codex Complete Next Gate Without Approval | Blocked Until | Next Action | Resolution Lane | Approval Reduction Hint |",
            "|---|---|---|---|---|---:|---|---|---|---|",
        ]
    )
    for item in rows:
        assert isinstance(item, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["scenario"]),
                    str(item["current_status"]).replace("|", "/"),
                    str(item["rks_status"]).replace("|", "/"),
                    str(item["approval_bundle"]),
                    str(item["owner"]),
                    "YES" if item["can_codex_complete_next_gate_without_approval"] else "NO",
                    str(item["blocked_until"]).replace("|", "/"),
                    str(item["next_action"]).replace("|", "/"),
                    str(item.get("resolution_lane", "")).replace("|", "/"),
                    str(item.get("approval_reduction_hint", "")).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Sources", ""])
    for item in rows:
        assert isinstance(item, dict)
        lines.append(f"- {item['scenario']}: `{item['source']}`")
    lines.extend(["", "## Supplemental Evidence", ""])
    for item in rows:
        assert isinstance(item, dict)
        if item.get("supplemental_evidence"):
            lines.append(f"- {item['scenario']}: `{item['supplemental_evidence']}`")
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RK10 goal unblock board.")
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
    payload = build_payload(args.s12_exit_code)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "goal_unblock_board.json"
    md_path = args.out_dir / "goal_unblock_board.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
