"""Generate a decision brief for the remaining operator review rows.

This tool is intentionally non-approving. It reads the current minimum
operator-review pack and produces a compact brief that explains what a human
reviewer must decide, why the row cannot be auto-approved, and which evidence
signals should be inspected first.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_MINIMUM_PACK_JSON = (
    REPORTS
    / "minimum_operator_review_input_20260623"
    / "minimum_operator_review_pack.json"
)
DEFAULT_VALIDATION_JSON = (
    REPORTS
    / "remaining_operator_input_ready_validation_20260623"
    / "remaining_operator_input_ready_validation.json"
)
DEFAULT_OBJECTIVE_AUDIT_JSON = (
    REPORTS
    / "objective_completion_audit_20260623"
    / "objective_completion_audit.json"
)
DEFAULT_OUT_DIR = REPORTS / "remaining_operator_decision_brief_20260623"

OPERATOR_FIELDS = ("operator_result", "reviewer", "reviewed_at")

SCENARIO_DECISION_OVERRIDES: dict[str, tuple[str, str]] = {
    "47": (
        "BUSINESS_DATA_REVIEW_REQUIRED",
        "RecoRu dry-run/no-upload、メールdry-run、deprecated mail fail-closed、RKS gateの未確認範囲を確認する",
    ),
    "55": (
        "FURIKOMI_RECONCILIATION_REVIEW_REQUIRED",
        "振込Excelの件数・合計・unknown supplier・no-mail・overflow 0の証跡を確認する",
    ),
    "63": (
        "BUSINESS_DATA_AND_RKS_SAFE_STOP_REVIEW_REQUIRED",
        "LOCAL/dry-run、submitted=false、最終申請なし、RKS open/build/runtime未確認範囲を確認する",
    ),
    "44": (
        "BUSINESS_REVIEW_GATE_REQUIRED",
        "レビューDB/金額確認、handoff生成、楽楽登録なし、processed moveなしの安全範囲を確認する",
    ),
    "71": (
        "PAID_AZURE_OCR_REVIEW_REQUIRED",
        "Azure有償OCR・PDF送信・Outlook送信を実行していない安全証跡と、残す外部入力判断を確認する",
    ),
    "70": (
        "PAYMENT_APPROVAL_REVIEW_REQUIRED",
        "支払実行・銀行アップロード・メール送信なしの安全証跡と、支払承認境界を確認する",
    ),
    "51/52": (
        "SOFTBANK_MANUAL_SUBMISSION_POLICY_REVIEW_REQUIRED",
        "資料作成までを確認し、楽楽精算は資料＋郵送請求を担当者が手動合算申請する方針を確認する",
    ),
}

BUNDLE_DECISION_DEFAULTS: dict[str, tuple[str, str]] = {
    "BUSINESS_DATA_APPROVAL_BUNDLE": (
        "BUSINESS_DATA_REVIEW_REQUIRED",
        "サンプル業務データ・金額・安全停止範囲が業務要件を満たすか確認する",
    ),
    "BUSINESS_REVIEW_BUNDLE": (
        "BUSINESS_REVIEW_GATE_REQUIRED",
        "レビュー済み/未レビュー、handoff、移動処理、楽楽登録なしの境界を確認する",
    ),
    "PAID_AZURE_OCR_BUNDLE": (
        "PAID_EXTERNAL_SERVICE_REVIEW_REQUIRED",
        "有償外部サービスを実行していないため、人が証跡と残リスクを確認する",
    ),
    "PAYMENT_APPROVAL_BUNDLE": (
        "PAYMENT_APPROVAL_REVIEW_REQUIRED",
        "支払実行を止めた安全確認であり、人の承認境界を確認する",
    ),
    "RK10_EDITOR_RUNTIME_BUNDLE": (
        "RK10_RUNTIME_GATE_REVIEW_REQUIRED",
        "RK10 editor open/build/runtime/latest-log 証跡不足または安全停止範囲を確認する",
    ),
}


@dataclass(frozen=True)
class DecisionBriefRow:
    row_number: int
    bundle: str
    scenario: str
    status: str
    operator_fields_state: str
    operator_result: str
    reviewer: str
    reviewed_at: str
    allowed_operator_result: str
    decision_boundary: str
    review_focus: str
    why_not_auto_approved: str
    recommended_operator_action: str
    latest_evidence_file: str
    latest_evidence_exists: str
    latest_evidence_uri: str
    evidence_success_signals: str
    evidence_attention_signals: str
    evidence_safety_signals: str
    validation_blockers: str
    validation_missing_operator_fields: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def entry_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("bundle", "")), str(row.get("scenario", ""))


def rows_by_key(rows: Sequence[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {entry_key(row): row for row in rows if isinstance(row, dict)}


def path_exists_text(path_text: str) -> str:
    if not path_text.strip():
        return "NO"
    return "YES" if Path(path_text).exists() else "NO"


def file_uri(path_text: str) -> str:
    if not path_text.strip():
        return ""
    return Path(path_text).absolute().as_uri()


def operator_fields_state(row: dict[str, Any]) -> str:
    values = [str(row.get(field, "")).strip() for field in OPERATOR_FIELDS]
    filled_count = sum(1 for value in values if value)
    if filled_count == 0:
        return "blank"
    if filled_count == len(OPERATOR_FIELDS):
        return "complete"
    return "partial"


def decision_details(row: dict[str, Any]) -> tuple[str, str]:
    scenario = str(row.get("scenario", ""))
    if scenario in SCENARIO_DECISION_OVERRIDES:
        return SCENARIO_DECISION_OVERRIDES[scenario]
    bundle = str(row.get("bundle", ""))
    return BUNDLE_DECISION_DEFAULTS.get(
        bundle,
        (
            "HUMAN_OPERATOR_REVIEW_REQUIRED",
            "latest evidenceを開き、残る人手判断と安全境界を確認する",
        ),
    )


def why_not_auto_approved(
    row: dict[str, Any],
    validation_row: dict[str, Any],
    decision_boundary: str,
) -> str:
    state = operator_fields_state(row)
    reasons: list[str] = []
    if state != "complete":
        reasons.append("operator_result/reviewer/reviewed_at が未完了")
    if str(row.get("latest_evidence_exists", "")) != "YES":
        reasons.append("latest evidence file が未確認または不存在")
    blockers = str(validation_row.get("blockers", "")).strip()
    if blockers:
        reasons.append(f"validation blocker: {blockers}")
    if "RK10" in decision_boundary:
        reasons.append("RKSはopen/build/runtime/latest-log証跡を人が分けて判定する必要がある")
    if "PAYMENT" in decision_boundary:
        reasons.append("支払実行は不可逆操作のため自動承認しない")
    if "PAID_AZURE" in decision_boundary or "PAID_EXTERNAL" in decision_boundary:
        reasons.append("有償OCR/外部送信はこの安全確認では実行していない")
    if "SOFTBANK" in decision_boundary:
        reasons.append("SoftBankは楽楽精算へ自動申請せず、担当者の手動合算申請方針を確認する")
    if not reasons:
        reasons.append("業務承認は人の署名付き判断として残す")
    return " / ".join(dict.fromkeys(reasons))


def recommended_action(row: dict[str, Any], decision_boundary: str) -> str:
    allowed = str(row.get("allowed_operator_result", "")).strip() or "OK / NG / HOLD"
    if "SOFTBANK" in decision_boundary:
        return (
            "latest evidenceと手動申請方針を確認し、"
            f"`{allowed}` のいずれか、reviewer、reviewed_atを人が記入する"
        )
    if "RK10" in decision_boundary:
        return (
            "RKS open/build/runtime/latest-logの不足を許容するか追加確認するか判断し、"
            f"`{allowed}` のいずれか、reviewer、reviewed_atを人が記入する"
        )
    return (
        "latest evidenceの成功/注意/安全シグナルを確認し、"
        f"`{allowed}` のいずれか、reviewer、reviewed_atを人が記入する"
    )


def build_rows(
    minimum_payload: dict[str, Any],
    validation_payload: dict[str, Any],
) -> list[DecisionBriefRow]:
    validation_rows = rows_by_key(validation_payload.get("rows", []))
    rows: list[DecisionBriefRow] = []
    for index, row in enumerate(minimum_payload.get("rows", []), 1):
        if not isinstance(row, dict):
            continue
        validation_row = validation_rows.get(entry_key(row), {})
        decision_boundary, review_focus = decision_details(row)
        latest_evidence_file = str(row.get("latest_evidence_file", ""))
        latest_evidence_exists = str(
            row.get("latest_evidence_exists", path_exists_text(latest_evidence_file))
        )
        output_row = DecisionBriefRow(
            row_number=index,
            bundle=str(row.get("bundle", "")),
            scenario=str(row.get("scenario", "")),
            status=str(row.get("status", "")),
            operator_fields_state=operator_fields_state(row),
            operator_result=str(row.get("operator_result", "")),
            reviewer=str(row.get("reviewer", "")),
            reviewed_at=str(row.get("reviewed_at", "")),
            allowed_operator_result=str(row.get("allowed_operator_result", "OK / NG / HOLD")),
            decision_boundary=decision_boundary,
            review_focus=review_focus,
            why_not_auto_approved=why_not_auto_approved(
                {**row, "latest_evidence_exists": latest_evidence_exists},
                validation_row,
                decision_boundary,
            ),
            recommended_operator_action=recommended_action(row, decision_boundary),
            latest_evidence_file=latest_evidence_file,
            latest_evidence_exists=latest_evidence_exists,
            latest_evidence_uri=str(row.get("latest_evidence_uri", "")) or file_uri(latest_evidence_file),
            evidence_success_signals=str(row.get("evidence_success_signals", "")),
            evidence_attention_signals=str(row.get("evidence_attention_signals", "")),
            evidence_safety_signals=str(row.get("evidence_safety_signals", "")),
            validation_blockers=str(validation_row.get("blockers", "")),
            validation_missing_operator_fields=str(
                validation_row.get("missing_operator_fields", "")
            ),
        )
        rows.append(output_row)
    return rows


def boundary_counts(rows: Sequence[DecisionBriefRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.decision_boundary] = counts.get(row.decision_boundary, 0) + 1
    return dict(sorted(counts.items()))


def build_payload(
    minimum_pack_json: Path = DEFAULT_MINIMUM_PACK_JSON,
    validation_json: Path = DEFAULT_VALIDATION_JSON,
    objective_audit_json: Path = DEFAULT_OBJECTIVE_AUDIT_JSON,
) -> dict[str, Any]:
    minimum_payload = read_json(minimum_pack_json)
    validation_payload = read_json(validation_json)
    objective_payload = read_json(objective_audit_json)
    rows = build_rows(minimum_payload, validation_payload)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": (
            "decision brief only; no auto approval; no operator field writes; "
            "no RK10 ButtonRun; no production write; no mail; no print; "
            "no submit; no payment; no paid Azure OCR"
        ),
        "minimum_pack_json": str(minimum_pack_json),
        "minimum_pack_json_exists": minimum_pack_json.exists(),
        "validation_json": str(validation_json),
        "validation_json_exists": validation_json.exists(),
        "objective_audit_json": str(objective_audit_json),
        "objective_audit_json_exists": objective_audit_json.exists(),
        "row_count": len(rows),
        "blank_operator_row_count": sum(
            row.operator_fields_state == "blank" for row in rows
        ),
        "partial_operator_row_count": sum(
            row.operator_fields_state == "partial" for row in rows
        ),
        "complete_operator_row_count": sum(
            row.operator_fields_state == "complete" for row in rows
        ),
        "latest_evidence_file_exists_count": sum(
            row.latest_evidence_exists == "YES" for row in rows
        ),
        "scope_exclusion_count": minimum_payload.get(
            "scope_exclusion_count",
            validation_payload.get("scope_exclusion_count", 0),
        ),
        "packet_scope_excluded_scenarios": minimum_payload.get(
            "packet_scope_excluded_scenarios",
            validation_payload.get("scope_exclusions", []),
        ),
        "objective_overall_goal_complete": objective_payload.get(
            "overall_goal_complete", False
        ),
        "objective_remaining_operator_not_ready_count": objective_payload.get(
            "remaining_operator_not_ready_count", None
        ),
        "decision_boundary_counts": boundary_counts(rows),
        "rows": [asdict(row) for row in rows],
    }


def csv_row_from_brief(row: dict[str, Any]) -> dict[str, Any]:
    fieldnames = [field.name for field in fields(DecisionBriefRow)]
    return {fieldname: row.get(fieldname, "") for fieldname in fieldnames}


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(DecisionBriefRow)]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_row_from_brief(row) for row in rows)


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " / ")


def build_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Remaining Operator Decision Brief Summary 2026-06-23",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- blank_operator_row_count: `{payload['blank_operator_row_count']}`",
        f"- partial_operator_row_count: `{payload['partial_operator_row_count']}`",
        f"- complete_operator_row_count: `{payload['complete_operator_row_count']}`",
        f"- latest_evidence_file_exists_count: `{payload['latest_evidence_file_exists_count']}`",
        f"- scope_exclusion_count: `{payload['scope_exclusion_count']}`",
        f"- packet_scope_excluded_scenarios: `{', '.join(payload['packet_scope_excluded_scenarios'])}`",
        f"- objective_overall_goal_complete: `{payload['objective_overall_goal_complete']}`",
        f"- objective_remaining_operator_not_ready_count: `{payload['objective_remaining_operator_not_ready_count']}`",
        f"- safety: `{payload['safety']}`",
        "",
        "## Decision Boundary Counts",
        "",
    ]
    for boundary, count in payload["decision_boundary_counts"].items():
        lines.append(f"- {boundary}: `{count}`")
    return "\n".join(lines) + "\n"


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Remaining Operator Decision Brief 2026-06-23",
        "",
        "このファイルは、人が確認する判断境界を短く示すためのブリーフです。",
        "承認欄は自動入力しません。",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- safety: `{payload['safety']}`",
        "",
        "| # | Scenario | Boundary | Operator Fields | Review Focus | Why Not Auto Approved |",
        "|---:|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["row_number"]),
                    markdown_cell(row["scenario"]),
                    markdown_cell(row["decision_boundary"]),
                    markdown_cell(row["operator_fields_state"]),
                    markdown_cell(row["review_focus"]),
                    markdown_cell(row["why_not_auto_approved"]),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def build_html(payload: dict[str, Any]) -> str:
    lines = [
        "<!doctype html>",
        '<html lang="ja">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Remaining Operator Decision Brief</title>",
        "<style>",
        "body{font-family:Meiryo,Segoe UI,sans-serif;margin:24px;line-height:1.5}",
        "table{border-collapse:collapse;width:100%;font-size:12px}",
        "th,td{border:1px solid #ccc;padding:6px;vertical-align:top}",
        "th{background:#f4f6f8}",
        ".warn{color:#8a4b00;font-weight:bold}",
        ".mono{font-family:Consolas,monospace}",
        "</style>",
        "</head>",
        "<body>",
        "<h1>Remaining Operator Decision Brief</h1>",
        f"<p>generated_at: <code>{html.escape(str(payload['generated_at']))}</code></p>",
        (
            f"<p>row_count: <strong>{payload['row_count']}</strong> / "
            f"blank_operator_row_count: <strong>{payload['blank_operator_row_count']}</strong> / "
            f"scope_exclusion_count: <strong>{payload['scope_exclusion_count']}</strong></p>"
        ),
        '<p class="warn">This is a decision brief only. It does not auto-approve, write operator fields, submit, print, send mail, pay, call paid OCR, or run RK10 ButtonRun.</p>',
        "<table>",
        "<thead><tr><th>#</th><th>Bundle</th><th>Scenario</th><th>Decision Boundary</th><th>Operator Fields</th><th>Review Focus</th><th>Why Not Auto Approved</th><th>Recommended Action</th><th>Latest Evidence</th><th>Signals</th></tr></thead>",
        "<tbody>",
    ]
    for row in payload["rows"]:
        latest = str(row.get("latest_evidence_file", ""))
        latest_link = (
            f'<a href="{html.escape(str(row.get("latest_evidence_uri", "")))}">{html.escape(latest)}</a>'
            if latest
            else ""
        )
        signals = "<br>".join(
            html.escape(str(row.get(key, "")))
            for key in (
                "evidence_success_signals",
                "evidence_attention_signals",
                "evidence_safety_signals",
            )
            if str(row.get(key, "")).strip()
        )
        lines.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('row_number', '')))}</td>"
            f"<td>{html.escape(str(row.get('bundle', '')))}</td>"
            f"<td>{html.escape(str(row.get('scenario', '')))}</td>"
            f"<td class=\"mono\">{html.escape(str(row.get('decision_boundary', '')))}</td>"
            f"<td>{html.escape(str(row.get('operator_fields_state', '')))}</td>"
            f"<td>{html.escape(str(row.get('review_focus', '')))}</td>"
            f"<td>{html.escape(str(row.get('why_not_auto_approved', '')))}</td>"
            f"<td>{html.escape(str(row.get('recommended_operator_action', '')))}</td>"
            f"<td>{latest_link}<br>{html.escape(str(row.get('latest_evidence_exists', '')))}</td>"
            f"<td>{signals}</td>"
            "</tr>"
        )
    lines.extend(["</tbody>", "</table>", "</body>", "</html>"])
    return "\n".join(lines) + "\n"


def build_start_here(payload: dict[str, Any], out_dir: Path) -> str:
    return "\n".join(
        [
            "# START HERE - Remaining Operator Decision Brief",
            "",
            "1. `remaining_operator_decision_brief.html` を開く。",
            "2. 各行の `decision_boundary` と `why_not_auto_approved` を確認する。",
            "3. `latest_evidence_file` を開き、成功/注意/安全シグナルを照合する。",
            "4. 承認できる場合のみ、既存の operator 入力CSVへ人が `operator_result/reviewer/reviewed_at` を記入する。",
            "",
            "## Files",
            "",
            f"- html: `{out_dir / 'remaining_operator_decision_brief.html'}`",
            f"- csv: `{out_dir / 'remaining_operator_decision_brief.csv'}`",
            f"- json: `{out_dir / 'remaining_operator_decision_brief.json'}`",
            f"- summary: `{out_dir / 'remaining_operator_decision_brief_summary.md'}`",
            f"- minimum_pack_json: `{payload['minimum_pack_json']}`",
            f"- validation_json: `{payload['validation_json']}`",
            f"- objective_audit_json: `{payload['objective_audit_json']}`",
        ]
    ) + "\n"


def build_opener_bat(out_dir: Path) -> str:
    return "\r\n".join(
        [
            "@echo off",
            "setlocal",
            f'start "" "{out_dir / "remaining_operator_decision_brief.html"}"',
            f'start "" "{out_dir / "remaining_operator_decision_brief.csv"}"',
            "exit /b 0",
            "",
        ]
    )


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "remaining_operator_decision_brief.json"
    csv_path = out_dir / "remaining_operator_decision_brief.csv"
    md_path = out_dir / "remaining_operator_decision_brief.md"
    html_path = out_dir / "remaining_operator_decision_brief.html"
    summary_path = out_dir / "remaining_operator_decision_brief_summary.md"
    start_here_path = out_dir / "START_HERE_remaining_operator_decision_brief.md"
    opener_path = out_dir / "OPEN_remaining_operator_decision_brief.bat"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, payload["rows"])
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    html_path.write_text(build_html(payload), encoding="utf-8")
    summary_path.write_text(build_summary_markdown(payload), encoding="utf-8")
    start_here_path.write_text(build_start_here(payload, out_dir), encoding="utf-8")
    opener_path.write_text(build_opener_bat(out_dir), encoding="utf-8")
    for path in (json_path, csv_path, md_path, summary_path, start_here_path):
        write_numbered_copy(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a non-approving decision brief for remaining operator rows."
    )
    parser.add_argument("--minimum-pack-json", type=Path, default=DEFAULT_MINIMUM_PACK_JSON)
    parser.add_argument("--validation-json", type=Path, default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--objective-audit-json", type=Path, default=DEFAULT_OBJECTIVE_AUDIT_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        args.minimum_pack_json,
        args.validation_json,
        args.objective_audit_json,
    )
    write_outputs(payload, args.out_dir)
    print(
        json.dumps(
            {key: value for key, value in payload.items() if key != "rows"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
