"""Generate a read-only RK10 goal status snapshot.

The snapshot consolidates current scenario evidence into one Markdown/JSON
artifact. It does not run RK10, Outlook, Rakuraku, Azure, printing, mail, or
payment actions.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from check_hold_release_gates_20260620 import (
    S44_SPOT_CHECK,
    S70_CHECKLIST,
    S71_CHECKLIST,
    check_s12_13,
    check_s44,
    check_s70,
    check_s71,
)


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
SUPPLEMENTAL_EVIDENCE = {
    "44": ROOT
    / "plans"
    / "reports"
    / "s44_sample_ok_shadow_20260620"
    / "s44_sample_ok_shadow.md.numbered",
    "70": ROOT
    / "plans"
    / "reports"
    / "s70_sample_confirm_preview_20260620"
    / "s70_sample_confirm_preview.md.numbered",
    "71": ROOT
    / "plans"
    / "reports"
    / "s71_sample_mock_ocr_apply_20260620"
    / "s71_sample_mock_ocr_apply_validation.md.numbered",
}


@dataclass(frozen=True)
class ScenarioSnapshot:
    scenario: str
    current_scope: str
    current_status: str
    remaining_gate: str
    next_action: str
    source: str
    source_exists: bool
    supplemental_evidence: str = ""
    supplemental_evidence_exists: bool = False


def scenario(
    scenario_id: str,
    current_scope: str,
    current_status: str,
    remaining_gate: str,
    next_action: str,
    source: str,
) -> ScenarioSnapshot:
    source_path = Path(source)
    return ScenarioSnapshot(
        scenario=scenario_id,
        current_scope=current_scope,
        current_status=current_status,
        remaining_gate=remaining_gate,
        next_action=next_action,
        source=source,
        source_exists=source_path.exists(),
    )


def build_static_scenarios() -> list[ScenarioSnapshot]:
    return [
        scenario(
            "37",
            "safe sample / safe-stop scope",
            "PYTHON_SAMPLE_OK_RKS_SAFE_STOP_SCOPE_ONLY",
            "実在対象者・RecoRu登録・latest clean log",
            "対象日と実在対象者を決め、登録前停止または有人確認で再検証する。",
            r"C:\ProgramData\RK10\Robots\migration\reports\s37_current_safe_recheck_20260619_0035\s37_current_safe_recheck_report.md.numbered",
        ),
        scenario(
            "38",
            "Python LOCAL SAFE",
            "PYTHON_LOCAL_SAFE_READY_RKS_EDITOR_OPEN_NG",
            "RKS要否判断 / Save As再生成",
            "RKSが必要ならRK10 Editor Save Asで別名再生成。不要ならPython/BAT入口に固定する。",
            r"C:\ProgramData\RK10\Robots\migration\reports\s38_migration_kit_payload_update_20260619_1115\s38_migration_kit_payload_update.md.numbered",
        ),
        scenario(
            "42",
            "registry-confirmed exact production file exists",
            "CONFIRMED_FILE_EXISTS_SCOPE_SEPARATE",
            "customer entry selection / rerun safety",
            "既存CONFIRMED RKSを使うかcurrent fixed-nameを使うか決め、再メール・上書きを避ける。",
            r"C:\ProgramData\RK10\Robots\migration\reports\all_scenario_prod_file_certainty_map_20260618_152452\all_scenario_prod_file_certainty_map.md.numbered",
        ),
        scenario(
            "43",
            "confirmed pipeline entry after feedback",
            "SCOPED_CONFIRMED_AFTER_FEEDBACK",
            "latest real data regeneration / final click boundary",
            "必要時は現データでPDF/XLSXを再生成し、最終クリックは人が判断する。",
            r"C:\ProgramData\RK10\Robots\migration\reports\prod_files_after_feedback_final_reconfirm_20260618_161709\prod_files_after_feedback_final_reconfirm.md.numbered",
        ),
        scenario(
            "47",
            "safe dry-run / mail dry-run",
            "CONFIRMED_FILE_EXISTS_BUT_LIVE_FLAGS_UNPROVEN",
            "flagあり日 / mail evidence / latest clean log",
            "flagあり日にdry-run、TEST/PROD送信証跡、latest clean logを確認する。",
            r"C:\ProgramData\RK10\Robots\migration\reports\s47_current_safe_recheck_20260618_2310\s47_current_safe_recheck_report.md.numbered",
        ),
        scenario(
            "51/52",
            "Excel save scope",
            "EXCEL_SAVE_SCOPE_SELECTED_AFTER_FEEDBACK",
            "Rakuraku registration remains intentionally stopped",
            "Excel保存範囲を維持し、楽楽登録へ進める場合は別承認を取る。",
            r"C:\ProgramData\RK10\Robots\migration\reports\prod_files_after_feedback_final_reconfirm_20260618_161709\prod_files_after_feedback_final_reconfirm.md.numbered",
        ),
        scenario(
            "55",
            "v2 dry-run / source-copy row insertion",
            "V2_DRYRUN_ERRORS_0_OVERFLOW_0",
            "production payment-day execution remains separate",
            "本番実行前に支払日・原本コピー・処理済みログ更新範囲を確認する。",
            r"C:\ProgramData\RK10\Robots\migration\reports\s55_matsujitsu_v2_long_timeout_recheck_20260619_101651\stdout.txt.numbered",
        ),
        scenario(
            "56",
            "historical prod evidence / current RKS not deployable",
            "CURRENT_DEPLOYABLE_RKS_NOT_CONFIRMED",
            "current workbook copy / no-write proof / Save As if RKS needed",
            "本番PCで2 workbook copyを開き、PROD dry-run no-writeを確認する。",
            r"C:\ProgramData\RK10\Robots\migration\reports\scenario56_prod_history_current_state_followup_20260618_0118.md.numbered",
        ),
        scenario(
            "57",
            "canonical Python dry-run / RKS open-build",
            "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
            "safe-stop clean log",
            "no-mail/no-upload/no-writeでsafe-stop再実行し、clean logを取り直す。",
            r"C:\ProgramData\RK10\Robots\migration\reports\s57_canonical_python_safe_dryrun_20260618_110309\summary.json.numbered",
        ),
        scenario(
            "58",
            "LOCAL dry-run/no-mail sample suite",
            "SAFE_SAMPLE_OK_RKS_UNCONFIRMED",
            "operator-select / real date-category / output evidence",
            "支払日と対象区分を決め、no-mail/no-writeで停止位置を確認する。",
            r"C:\ProgramData\RK10\Robots\migration\reports\s58_current_safe_sample_recheck_20260618_173202\s58_current_safe_sample_recheck_report.md.numbered",
        ),
        scenario(
            "63",
            "safe gate / dry-run scope",
            "SAFE_STOP_SCOPE_ONLY",
            "active master rows / duplicate guard / permission",
            "有効マスタ8件と重複/権限を確認し、executeなし全件dry-runへ進める。",
            r"C:\ProgramData\RK10\Robots\migration\reports\s63_current_safe_gate_recheck_20260618_181644\s63_current_safe_gate_recheck_report.md.numbered",
        ),
    ]


def build_gate_scenarios(s12_exit_code: int | None) -> list[ScenarioSnapshot]:
    gate_results = [
        check_s44(S44_SPOT_CHECK),
        check_s70(S70_CHECKLIST),
        check_s71(S71_CHECKLIST),
        check_s12_13(s12_exit_code),
    ]
    return [
        ScenarioSnapshot(
            scenario=result.scenario,
            current_scope="HOLD gate read-only check",
            current_status=result.status,
            remaining_gate=result.reason,
            next_action=result.next_action,
            source=result.source,
            source_exists=Path(result.source).exists(),
            supplemental_evidence=str(SUPPLEMENTAL_EVIDENCE.get(result.scenario, "")),
            supplemental_evidence_exists=SUPPLEMENTAL_EVIDENCE.get(result.scenario, Path()).exists()
            if result.scenario in SUPPLEMENTAL_EVIDENCE
            else False,
        )
        for result in gate_results
    ]


def build_payload(s12_exit_code: int | None) -> dict[str, object]:
    generated_at = datetime.now().isoformat(timespec="seconds")
    scenarios = build_gate_scenarios(s12_exit_code) + build_static_scenarios()
    blocked_or_hold = [
        item
        for item in scenarios
        if "HOLD" in item.current_status
        or "UNCONFIRMED" in item.current_status
        or "NOT_CONFIRMED" in item.current_status
        or "NG" in item.current_status
        or "MISSING" in item.current_status
    ]
    missing_sources = [item for item in scenarios if not item.source_exists]
    supplemental_evidence = [
        item for item in scenarios if item.supplemental_evidence_exists
    ]
    return {
        "generated_at": generated_at,
        "overall_goal_complete": False,
        "safety": "read-only evidence snapshot only",
        "scenario_count": len(scenarios),
        "hold_or_unconfirmed_count": len(blocked_or_hold),
        "missing_source_count": len(missing_sources),
        "supplemental_evidence_count": len(supplemental_evidence),
        "scenarios": [asdict(item) for item in scenarios],
    }


def build_markdown(payload: dict[str, object]) -> str:
    scenarios = payload["scenarios"]
    assert isinstance(scenarios, list)
    lines = [
        "# 全シナリオ現況スナップショット 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- hold_or_unconfirmed_count: `{payload['hold_or_unconfirmed_count']}`",
        f"- missing_source_count: `{payload['missing_source_count']}`",
        f"- supplemental_evidence_count: `{payload['supplemental_evidence_count']}`",
        "",
        "## Scenario Matrix",
        "",
        "| Scenario | Current Status | Remaining Gate | Next Action | Source Exists | Supplemental Evidence Exists |",
        "|---|---|---|---|---:|---:|",
    ]
    for item in scenarios:
        assert isinstance(item, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["scenario"]),
                    str(item["current_status"]).replace("|", "/"),
                    str(item["remaining_gate"]).replace("|", "/"),
                    str(item["next_action"]).replace("|", "/"),
                    "YES" if item["source_exists"] else "NO",
                    "YES" if item.get("supplemental_evidence_exists") else "NO",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Sources", ""])
    for item in scenarios:
        assert isinstance(item, dict)
        lines.append(f"- {item['scenario']}: `{item['source']}`")
    lines.extend(["", "## Supplemental Evidence", ""])
    for item in scenarios:
        assert isinstance(item, dict)
        if item.get("supplemental_evidence"):
            lines.append(f"- {item['scenario']}: `{item['supplemental_evidence']}`")
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RK10 goal status snapshot.")
    parser.add_argument(
        "--s12-exit-code",
        type=int,
        default=None,
        help="Latest 12/13 --check-outlook-com exit code. Use 0 only when just verified.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "plans" / "reports" / "goal_status_snapshot_20260620",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.s12_exit_code)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "goal_status_snapshot.json"
    md_path = args.out_dir / "goal_status_snapshot.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
