"""Generate a durable remaining-work breakdown for production readiness.

The report is read-only. It classifies existing final-evidence queue rows into
what Codex can continue doing automatically and what still needs human or
external approval before the full production-migration goal can be claimed.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_FILL_QUEUE_CSV = (
    REPORTS / "final_evidence_fill_queue_20260621" / "final_evidence_fill_queue.csv"
)
DEFAULT_BUSINESS_COST_CSV = (
    REPORTS / "business_cost_evidence_map_20260620" / "business_cost_evidence_map.csv"
)
DEFAULT_RKS_INTAKE_CSV = (
    REPORTS
    / "rks_runtime_operator_pack_20260620"
    / "rks_runtime_operator_intake.csv"
)
DEFAULT_RKS_VALIDATION_MD = (
    REPORTS
    / "rks_runtime_operator_intake_validation_20260620"
    / "rks_runtime_operator_intake_validation.md.numbered"
)
DEFAULT_RKS_OPEN_PROBE_MATRIX_JSON = (
    REPORTS
    / "rks_gate_matrix_open_probe_20260622"
    / "rks_gate_matrix.json"
)
DEFAULT_GOAL_GATE_MD = (
    REPORTS / "goal_completion_gate_20260620" / "goal_completion_gate.md.numbered"
)
DEFAULT_GOAL_FINAL_MD = (
    REPORTS / "goal_final_report_20260620" / "goal_final_report.md.numbered"
)
DEFAULT_SAFE_RUNNER_MD = (
    REPORTS / "safe_goal_checks_20260620" / "safe_goal_checks_summary.md.numbered"
)
DEFAULT_OUT_DIR = REPORTS / "prod_readiness_remaining_work_breakdown_20260622"


@dataclass(frozen=True)
class BundleWorkRow:
    bundle: str
    scenarios: str
    owner: str
    active_queue: str
    action_status: str
    category: str
    final_evidence_folder_exists: str
    missing_operator_fields: str
    remaining_runtime_evidence: str
    codex_can_continue_with: str
    human_or_external_input_needed: str
    hard_stop: str
    start_here_path: str
    target_intake_path: str
    suggested_final_evidence_path: str


@dataclass(frozen=True)
class ScenarioWorkRow:
    scenario: str
    bundle: str
    cost_status: str
    item_count: str
    total_amount_yen: str
    cost_validation: str
    cost_scope: str
    rks_operator_decision: str
    rks_editor_open: str
    rks_build: str
    rks_runtime_or_safe_stop: str
    rks_latest_log_clean: str
    next_action: str


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def first_matching_line(path: Path, fragments: list[str]) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if all(fragment in line for fragment in fragments):
            return line.strip()
    return ""


def path_exists_text(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    return "YES" if Path(text).exists() else "NO"


def split_scenarios(value: str) -> list[str]:
    return [scenario.strip() for scenario in value.split(",") if scenario.strip()]


def split_rks_matrix_scenario(value: str) -> list[str]:
    if value in {"12/13", "51/52"}:
        return [value]
    if "/" in value:
        return [scenario.strip() for scenario in value.split("/") if scenario.strip()]
    return [value]


def build_open_probe_rows(open_probe_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    payload_rows = open_probe_payload.get("rows", [])
    if not isinstance(payload_rows, list):
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for payload_row in payload_rows:
        if not isinstance(payload_row, dict):
            continue
        if payload_row.get("editor_open_probe_status") != "RK10_EDITOR_OPEN_CONFIRMED":
            continue
        if payload_row.get("editor_open_probe_build_artifact_found") is True:
            continue
        if payload_row.get("editor_open_probe_button_run_clicked") is True:
            continue
        for scenario in split_rks_matrix_scenario(str(payload_row.get("scenario", ""))):
            rows[scenario] = payload_row
    return rows


def classify_bundle(row: dict[str, str]) -> tuple[str, str, str]:
    missing_fields = row.get("missing_operator_fields", "")
    remaining_runtime = row.get("remaining_runtime_evidence", "")
    final_ready = row.get("final_evidence_ready") == "True"
    if final_ready:
        category = "COMPLETE_OR_READY"
        codex_next = "固定ランナー再実行と配布先同期のみ"
        human_needed = "なし"
    elif "OPERATOR_RESULT_BLANK" in missing_fields or "REVIEWER_BLANK" in missing_fields:
        category = "HUMAN_FINAL_EVIDENCE_INPUT_REQUIRED"
        codex_next = "証跡整理、入力箇所案内、固定ランナー再実行"
        human_needed = "operator_result/reviewer/reviewed_at の記入"
    else:
        category = "TECHNICAL_REVIEW_REQUIRED"
        codex_next = "ログ再収集と差異調査"
        human_needed = "必要に応じて運用判断"
    if remaining_runtime:
        category = f"{category}+RKS_OR_ENTRY_DECISION_PENDING"
    return category, codex_next, human_needed


def build_bundle_rows(fill_rows: list[dict[str, str]]) -> list[BundleWorkRow]:
    rows: list[BundleWorkRow] = []
    for row in fill_rows:
        category, codex_next, human_needed = classify_bundle(row)
        suggested_path = row.get("suggested_final_evidence_path", "")
        rows.append(
            BundleWorkRow(
                bundle=row.get("bundle", ""),
                scenarios=row.get("scenarios", ""),
                owner=row.get("owner", ""),
                active_queue="YES" if row.get("active") == "True" else "NO",
                action_status=row.get("action_status", ""),
                category=category,
                final_evidence_folder_exists=path_exists_text(suggested_path),
                missing_operator_fields=row.get("missing_operator_fields", ""),
                remaining_runtime_evidence=row.get("remaining_runtime_evidence", ""),
                codex_can_continue_with=codex_next,
                human_or_external_input_needed=human_needed,
                hard_stop=row.get("forbidden", ""),
                start_here_path=row.get("start_here_path", ""),
                target_intake_path=row.get("target_intake_path", ""),
                suggested_final_evidence_path=suggested_path,
            )
        )
    return rows


def build_scenario_rows(
    fill_rows: list[dict[str, str]],
    cost_rows: dict[str, dict[str, str]],
    rks_rows: dict[str, dict[str, str]],
    open_probe_rows: dict[str, dict[str, Any]],
) -> list[ScenarioWorkRow]:
    rows: list[ScenarioWorkRow] = []
    seen: set[str] = set()
    for fill_row in fill_rows:
        for scenario in split_scenarios(fill_row.get("scenarios", "")):
            seen.add(scenario)
            rows.append(
                build_scenario_row(
                    scenario,
                    fill_row.get("bundle", ""),
                    fill_row.get("next_action", ""),
                    cost_rows.get(scenario, {}),
                    rks_rows.get(scenario, {}),
                    open_probe_rows.get(scenario, {}),
                )
            )
    for scenario in sorted(cost_rows):
        if scenario in seen:
            continue
        rows.append(
            build_scenario_row(
                scenario,
                "READY_OR_NOT_IN_ACTIVE_QUEUE",
                "final evidence ready or separate queue",
                cost_rows.get(scenario, {}),
                rks_rows.get(scenario, {}),
                open_probe_rows.get(scenario, {}),
            )
        )
    return rows


def build_scenario_row(
    scenario: str,
    bundle: str,
    next_action: str,
    cost_row: dict[str, str],
    rks_row: dict[str, str],
    open_probe_row: dict[str, Any],
) -> ScenarioWorkRow:
    rks_editor_open = rks_row.get("rk10_editor_open", "")
    if not rks_editor_open and open_probe_row:
        rks_editor_open = "RK10_EDITOR_OPEN_CONFIRMED_ONLY"
    return ScenarioWorkRow(
        scenario=scenario,
        bundle=bundle,
        cost_status=cost_row.get("cost_evidence_status", ""),
        item_count=cost_row.get("item_count", ""),
        total_amount_yen=cost_row.get("total_amount_yen", ""),
        cost_validation=cost_row.get("validation_result", ""),
        cost_scope=cost_row.get("safety_scope", ""),
        rks_operator_decision=rks_row.get("operator_decision", ""),
        rks_editor_open=rks_editor_open,
        rks_build=rks_row.get("rk10_build", ""),
        rks_runtime_or_safe_stop=rks_row.get("runtime_or_safe_stop", ""),
        rks_latest_log_clean=rks_row.get("latest_log_clean", ""),
        next_action=next_action,
    )


def build_payload(
    fill_queue_csv: Path,
    business_cost_csv: Path,
    rks_intake_csv: Path,
    rks_validation_md: Path,
    goal_gate_md: Path,
    goal_final_md: Path,
    safe_runner_md: Path,
    rks_open_probe_matrix_json: Path = DEFAULT_RKS_OPEN_PROBE_MATRIX_JSON,
) -> dict[str, Any]:
    fill_rows = read_csv_dicts(fill_queue_csv)
    cost_rows = {row.get("scenario", ""): row for row in read_csv_dicts(business_cost_csv)}
    rks_rows = {row.get("scenario", ""): row for row in read_csv_dicts(rks_intake_csv)}
    open_probe_payload = read_json_dict(rks_open_probe_matrix_json)
    open_probe_rows = build_open_probe_rows(open_probe_payload)
    bundle_rows = build_bundle_rows(fill_rows)
    scenario_rows = build_scenario_rows(fill_rows, cost_rows, rks_rows, open_probe_rows)
    return {
        "summary": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "goal_complete_line": first_matching_line(goal_final_md, ["final_goal_complete"]),
            "safe_runner_generated_at": first_matching_line(safe_runner_md, ["generated_at"]),
            "safe_runner_line": first_matching_line(safe_runner_md, ["overall_passed"]),
            "blocking_gate_line": first_matching_line(goal_gate_md, ["blocking_gate_count"]),
            "rks_validation_line": first_matching_line(
                rks_validation_md,
                ["overall_rks_runtime_evidence_complete"],
            ),
            "active_bundle_count": sum(
                1 for row in bundle_rows if row.active_queue == "YES"
            ),
            "human_input_bundle_count": sum(
                1
                for row in bundle_rows
                if "HUMAN_FINAL_EVIDENCE_INPUT_REQUIRED" in row.category
            ),
            "scenario_count": len(scenario_rows),
            "open_probe_confirmed_scenario_count": sum(
                1
                for row in scenario_rows
                if row.rks_editor_open == "RK10_EDITOR_OPEN_CONFIRMED_ONLY"
            ),
            "safety": (
                "no production registration, no mail, no print, no payment, "
                "no RK10 ButtonRun, no paid Azure OCR"
            ),
            "sources": {
                "fill_queue_csv": str(fill_queue_csv),
                "business_cost_csv": str(business_cost_csv),
                "rks_intake_csv": str(rks_intake_csv),
                "rks_validation_md": str(rks_validation_md),
                "rks_open_probe_matrix_json": str(rks_open_probe_matrix_json),
                "goal_gate_md": str(goal_gate_md),
                "goal_final_md": str(goal_final_md),
                "safe_runner_md": str(safe_runner_md),
            },
        },
        "bundles": [asdict(row) for row in bundle_rows],
        "scenarios": [asdict(row) for row in scenario_rows],
    }


def write_csv(path: Path, rows: list[dict[str, Any]], dataclass_type: type) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(dataclass_type)]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def markdown_cell(value: object) -> str:
    text = str(value or "").replace("|", "/")
    return text if text else "-"


def final_goal_complete_from_line(value: str) -> bool:
    return "`True`" in value or value.strip().endswith(": True")


def build_markdown(payload: dict[str, Any], out_dir: Path) -> str:
    summary = payload["summary"]
    final_goal_complete = final_goal_complete_from_line(summary["goal_complete_line"])
    if final_goal_complete:
        conclusion_lines = [
            "- 固定ランナーと最終ゲートは通過しており、本番移行OK状態として扱えます。",
            "- この分類は残作業ではなく、実送信・実印刷・支払実行などを追加で行う場合の安全境界です。",
            "- Codex側で自動継続できるのは、証跡整理、固定ランナー再実行、C/E同期までです。",
            "- Open欄の `RK10_EDITOR_OPEN_CONFIRMED_ONLY` はRK10エディタで開けた補助証跡であり、Build/Runtime/Clean Logは昇格していません。",
            "- 支払実行、実送信、実印刷、Rakuraku本番登録、RK10 ButtonRun、paid Azure OCRは別承認なしで実施しません。",
        ]
    else:
        conclusion_lines = [
            "- 固定ランナーは通過していますが、最終ゴールは未完了です。",
            "- 残りは主に `operator_result` / `reviewer` / `reviewed_at` の人間の最終入力と、外部環境・業務承認が必要なゲートです。",
            "- Codex側で自動継続できるのは、証跡整理、入力箇所案内、固定ランナー再実行、C/E同期までです。",
            "- Open欄の `RK10_EDITOR_OPEN_CONFIRMED_ONLY` はRK10エディタで開けた補助証跡であり、Build/Runtime/Clean Logは昇格していません。",
            "- 支払実行、実送信、実印刷、Rakuraku本番登録、RK10 ButtonRun、paid Azure OCRは別承認なしで実施しません。",
        ]
    lines = [
        "# 本番移行OKまでの残作業分類 2026-06-22",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- goal_complete_source: `{summary['goal_complete_line']}`",
        f"- safe_runner_generated_at_source: `{summary['safe_runner_generated_at']}`",
        f"- safe_runner_source: `{summary['safe_runner_line']}`",
        f"- blocking_gate_source: `{summary['blocking_gate_line']}`",
        f"- rks_validation_source: `{summary['rks_validation_line']}`",
        f"- active_bundle_count: `{summary['active_bundle_count']}`",
        f"- human_input_bundle_count: `{summary['human_input_bundle_count']}`",
        f"- scenario_count: `{summary['scenario_count']}`",
        f"- open_probe_confirmed_scenario_count: `{summary['open_probe_confirmed_scenario_count']}`",
        f"- safety: `{summary['safety']}`",
        "",
        "## 結論",
        "",
        *conclusion_lines,
        "",
        "## Bundle Classification",
        "",
        "| Bundle | Scenarios | Category | Codex Can Continue With | Human/External Needed | Final Evidence Folder | Hard Stop |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in payload["bundles"]:
        lines.append(
            "| "
            + " | ".join(
                markdown_cell(row[key])
                for key in [
                    "bundle",
                    "scenarios",
                    "category",
                    "codex_can_continue_with",
                    "human_or_external_input_needed",
                    "final_evidence_folder_exists",
                    "hard_stop",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Scenario Cost/RKS Snapshot",
            "",
            "| Scenario | Bundle | Cost Status | Count | Amount | Cost Validation | RKS Decision | Open | Build | Runtime | Clean Log |",
            "|---|---|---|---:|---:|---|---|---|---|---|---|",
        ]
    )
    for row in payload["scenarios"]:
        lines.append(
            "| "
            + " | ".join(
                markdown_cell(row[key])
                for key in [
                    "scenario",
                    "bundle",
                    "cost_status",
                    "item_count",
                    "total_amount_yen",
                    "cost_validation",
                    "rks_operator_decision",
                    "rks_editor_open",
                    "rks_build",
                    "rks_runtime_or_safe_stop",
                    "rks_latest_log_clean",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Files", ""])
    for key, value in summary["sources"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- bundle_csv: `{out_dir / 'remaining_bundle_work.csv'}`",
            f"- scenario_csv: `{out_dir / 'remaining_scenario_work.csv'}`",
            f"- json: `{out_dir / 'prod_readiness_remaining_work_breakdown.json'}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "prod_readiness_remaining_work_breakdown.json"
    bundle_csv = out_dir / "remaining_bundle_work.csv"
    scenario_csv = out_dir / "remaining_scenario_work.csv"
    md_path = out_dir / "prod_readiness_remaining_work_breakdown.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(bundle_csv, payload["bundles"], BundleWorkRow)
    write_csv(scenario_csv, payload["scenarios"], ScenarioWorkRow)
    md_path.write_text(build_markdown(payload, out_dir), encoding="utf-8")
    write_numbered_copy(md_path)
    write_numbered_copy(bundle_csv)
    write_numbered_copy(scenario_csv)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate production readiness remaining-work breakdown."
    )
    parser.add_argument("--fill-queue-csv", type=Path, default=DEFAULT_FILL_QUEUE_CSV)
    parser.add_argument("--business-cost-csv", type=Path, default=DEFAULT_BUSINESS_COST_CSV)
    parser.add_argument("--rks-intake-csv", type=Path, default=DEFAULT_RKS_INTAKE_CSV)
    parser.add_argument("--rks-validation-md", type=Path, default=DEFAULT_RKS_VALIDATION_MD)
    parser.add_argument(
        "--rks-open-probe-matrix-json",
        type=Path,
        default=DEFAULT_RKS_OPEN_PROBE_MATRIX_JSON,
    )
    parser.add_argument("--goal-gate-md", type=Path, default=DEFAULT_GOAL_GATE_MD)
    parser.add_argument("--goal-final-md", type=Path, default=DEFAULT_GOAL_FINAL_MD)
    parser.add_argument("--safe-runner-md", type=Path, default=DEFAULT_SAFE_RUNNER_MD)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        args.fill_queue_csv,
        args.business_cost_csv,
        args.rks_intake_csv,
        args.rks_validation_md,
        args.goal_gate_md,
        args.goal_final_md,
        args.safe_runner_md,
        args.rks_open_probe_matrix_json,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
