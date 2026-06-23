"""Split final completion blockers by actionability and safety boundary.

This report is read-only. It does not approve evidence, open RK10, run RKS,
send mail, print, submit, pay, call Azure, or write production files.
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
DEFAULT_COMPLETION_GATE_JSON = (
    ROOT / "plans" / "reports" / "goal_completion_gate_20260620" / "goal_completion_gate.json"
)
DEFAULT_FINAL_QUEUE_JSON = (
    ROOT / "plans" / "reports" / "final_evidence_fill_queue_20260621" / "final_evidence_fill_queue.json"
)
DEFAULT_FINAL_BOUNDARY_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "final_input_autonomous_boundary_20260622"
    / "final_input_autonomous_boundary.json"
)
DEFAULT_EXECUTION_VALIDATION_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "goal_execution_packet_validation_20260620"
    / "goal_execution_packet_validation.json"
)
DEFAULT_RKS_OPEN_PROBE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "rks_gate_matrix_open_probe_20260622"
    / "rks_gate_matrix.json"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "completion_blocker_split_20260622"

AGGREGATE_BLOCKED_BY_DOWNSTREAM_GATES = "AGGREGATE_BLOCKED_BY_DOWNSTREAM_GATES"
EXTERNAL_HUMAN_APPROVAL_REQUIRED = "EXTERNAL_HUMAN_APPROVAL_REQUIRED"
FINAL_OPERATOR_FIELDS_REQUIRED = "FINAL_OPERATOR_FIELDS_REQUIRED"
TECHNICAL_EVIDENCE_COLLECTED_OPEN_ONLY = "TECHNICAL_EVIDENCE_COLLECTED_OPEN_ONLY"
TRUE_TECHNICAL_RUNTIME_GAP = "TRUE_TECHNICAL_RUNTIME_GAP"
RKS_NON_BLOCKING_RUNTIME_STATUSES = {
    "N_A_NO_PRIMARY_RKS",
    "RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION",
    "RKS_RUNTIME_EVIDENCE_CONFIRMED",
}


@dataclass(frozen=True)
class BlockerRow:
    rank: int
    source_kind: str
    gate_or_bundle: str
    scenarios: str
    category: str
    blocker: str
    codex_can_continue_with: str
    human_or_external_input_needed: str
    forbidden_scope: str
    next_action: str
    source_path: str


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def category_for_gate(gate: str) -> str:
    if gate in {"STATUS_SNAPSHOT", "REQUIREMENT_TRACE", "EVIDENCE_LEDGER"}:
        return AGGREGATE_BLOCKED_BY_DOWNSTREAM_GATES
    if gate in {"EXECUTION_PACKET_VALIDATION", "BUNDLE_EVIDENCE_PACK_VALIDATION"}:
        return FINAL_OPERATOR_FIELDS_REQUIRED
    if gate == "RKS_GATE_MATRIX":
        return TRUE_TECHNICAL_RUNTIME_GAP
    return AGGREGATE_BLOCKED_BY_DOWNSTREAM_GATES


def build_gate_rows(completion_gate: dict[str, Any]) -> list[BlockerRow]:
    rows: list[BlockerRow] = []
    for gate in completion_gate.get("gates", []):
        if not isinstance(gate, dict) or bool(gate.get("passed")):
            continue
        gate_name = str(gate.get("gate", "")).strip()
        category = category_for_gate(gate_name)
        rows.append(
            BlockerRow(
                rank=len(rows) + 1,
                source_kind="COMPLETION_GATE",
                gate_or_bundle=gate_name,
                scenarios="",
                category=category,
                blocker=str(gate.get("detail", "")).strip(),
                codex_can_continue_with=(
                    "下位レポート再生成と証跡案内"
                    if category == AGGREGATE_BLOCKED_BY_DOWNSTREAM_GATES
                    else "不足項目の一覧化と入力先案内"
                ),
                human_or_external_input_needed=(
                    "下位の人手承認・外部実行・技術証跡が揃うこと"
                ),
                forbidden_scope="自動承認、実メール、実印刷、支払実行、本番登録、RK10 ButtonRun",
                next_action=str(gate.get("next_action", "")).strip(),
                source_path=str(gate.get("source", "")).strip(),
            )
        )
    return rows


def build_final_queue_rows(final_queue: dict[str, Any], start_rank: int) -> list[BlockerRow]:
    rows: list[BlockerRow] = []
    for queue_row in final_queue.get("rows", []):
        if not isinstance(queue_row, dict):
            continue
        if str(queue_row.get("action_status", "")).strip() != "NEEDS_OPERATOR_INPUT":
            continue
        rows.append(
            BlockerRow(
                rank=start_rank + len(rows),
                source_kind="FINAL_EVIDENCE_FILL_QUEUE",
                gate_or_bundle=str(queue_row.get("bundle", "")).strip(),
                scenarios=str(queue_row.get("scenarios", "")).strip(),
                category=FINAL_OPERATOR_FIELDS_REQUIRED,
                blocker=str(queue_row.get("missing_operator_fields", "")).strip()
                or str(queue_row.get("final_evidence_gap", "")).strip(),
                codex_can_continue_with="入力CSV、START_HERE、証跡置き場の案内",
                human_or_external_input_needed=str(queue_row.get("fill_only_fields", "")).strip(),
                forbidden_scope=str(queue_row.get("forbidden", "")).strip(),
                next_action=str(queue_row.get("next_action", "")).strip(),
                source_path=str(queue_row.get("target_intake_path", "")).strip()
                or str(queue_row.get("unified_input_csv", "")).strip(),
            )
        )
    return rows


def category_for_boundary(boundary_class: str) -> str:
    if boundary_class == "HUMAN_OR_EXTERNAL_APPROVAL_REQUIRED_NO_AUTO_APPROVAL":
        return EXTERNAL_HUMAN_APPROVAL_REQUIRED
    if boundary_class == "SAFE_TECHNICAL_EVIDENCE_CAN_CONTINUE_NO_AUTO_APPROVAL":
        return TECHNICAL_EVIDENCE_COLLECTED_OPEN_ONLY
    return AGGREGATE_BLOCKED_BY_DOWNSTREAM_GATES


def build_boundary_rows(final_boundary: dict[str, Any], start_rank: int) -> list[BlockerRow]:
    rows: list[BlockerRow] = []
    for boundary_row in final_boundary.get("rows", []):
        if not isinstance(boundary_row, dict):
            continue
        if str(boundary_row.get("current_status", "")).strip() != "MISSING_FINAL_INPUT":
            continue
        boundary_class = str(boundary_row.get("boundary_class", "")).strip()
        category = category_for_boundary(boundary_class)
        rows.append(
            BlockerRow(
                rank=start_rank + len(rows),
                source_kind="FINAL_INPUT_AUTONOMOUS_BOUNDARY",
                gate_or_bundle=str(boundary_row.get("bundle", "")).strip(),
                scenarios=str(boundary_row.get("scenario", "")).strip(),
                category=category,
                blocker=str(boundary_row.get("missing_fields", "")).strip(),
                codex_can_continue_with=str(boundary_row.get("codex_can_continue_with", "")).strip(),
                human_or_external_input_needed=str(
                    boundary_row.get("human_or_external_input_needed", "")
                ).strip(),
                forbidden_scope=str(boundary_row.get("forbidden_scope", "")).strip(),
                next_action="該当final_evidence_intake.csvへ最小項目のみ記入する",
                source_path=str(boundary_row.get("source_intake_path", "")).strip(),
            )
        )
    return rows


def build_rks_open_only_rows(rks_open_probe: dict[str, Any], start_rank: int) -> list[BlockerRow]:
    rows: list[BlockerRow] = []
    for rks_row in rks_open_probe.get("rows", []):
        if not isinstance(rks_row, dict):
            continue
        editor_status = str(rks_row.get("editor_open_probe_status", "")).strip()
        if editor_status != "RK10_EDITOR_OPEN_CONFIRMED":
            continue
        if bool(rks_row.get("editor_open_probe_build_artifact_found")):
            continue
        runtime_status = str(rks_row.get("runtime_intake_status", "")).strip()
        if runtime_status in RKS_NON_BLOCKING_RUNTIME_STATUSES:
            continue
        scenario = str(rks_row.get("scenario", "")).strip()
        rows.append(
            BlockerRow(
                rank=start_rank + len(rows),
                source_kind="RKS_OPEN_PROBE_SUPPLEMENT",
                gate_or_bundle="RKS_GATE_MATRIX",
                scenarios=scenario,
                category=TECHNICAL_EVIDENCE_COLLECTED_OPEN_ONLY,
                blocker=(
                    f"editor_open={editor_status}; build_artifact=NO; "
                    f"status={str(rks_row.get('current_rks_status', '')).strip()}; "
                    f"runtime_intake_status={runtime_status or 'UNKNOWN'}"
                ),
                codex_can_continue_with="証跡整理、必要ならRK10 Editor open確認まで",
                human_or_external_input_needed="RK10 build、runtime/safe-stop、latest clean log",
                forbidden_scope=str(rks_row.get("blocked_operation", "")).strip(),
                next_action=str(rks_row.get("missing_gate", "")).strip(),
                source_path=str(rks_row.get("editor_open_probe_source", "")).strip()
                or str(rks_row.get("primary_source", "")).strip(),
            )
        )
    return rows


def category_counts(rows: list[BlockerRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.category] = counts.get(row.category, 0) + 1
    return dict(sorted(counts.items()))


def build_operator_gap_summary(execution_validation: dict[str, Any]) -> dict[str, Any]:
    validation_rows = [
        row for row in execution_validation.get("rows", []) if isinstance(row, dict)
    ]
    evidence_path_set_count = sum(1 for row in validation_rows if row.get("evidence_path"))
    evidence_exists_count = sum(
        1 for row in validation_rows if row.get("evidence_exists") is True
    )
    approved_row_count = sum(1 for row in validation_rows if row.get("approved") is True)
    missing_operator_rows = [
        row
        for row in validation_rows
        if str(row.get("status", "")).strip() == "MISSING_OPERATOR_FIELDS"
    ]
    operator_field_only_rows = [
        row
        for row in missing_operator_rows
        if row.get("evidence_exists") is True and str(row.get("missing_fields", "")).strip()
    ]
    missing_evidence_rows = [
        row for row in validation_rows if row.get("evidence_exists") is not True
    ]
    missing_field_counts: dict[str, int] = {}
    for row in missing_operator_rows:
        for field_name in str(row.get("missing_fields", "")).split(","):
            normalized_field = field_name.strip()
            if not normalized_field:
                continue
            missing_field_counts[normalized_field] = (
                missing_field_counts.get(normalized_field, 0) + 1
            )
    return {
        "row_count": len(validation_rows),
        "approved_row_count": approved_row_count,
        "needs_attention_count": int(
            execution_validation.get("needs_attention_count", 0) or 0
        ),
        "evidence_path_set_count": evidence_path_set_count,
        "evidence_exists_count": evidence_exists_count,
        "missing_evidence_row_count": len(missing_evidence_rows),
        "operator_field_only_pending_count": len(operator_field_only_rows),
        "missing_operator_field_counts": dict(sorted(missing_field_counts.items())),
        "operator_field_only_pending_rows": [
            {
                "bundle": str(row.get("bundle", "")),
                "scenario": str(row.get("scenario", "")),
                "missing_fields": str(row.get("missing_fields", "")),
                "evidence_path": str(row.get("evidence_path", "")),
            }
            for row in operator_field_only_rows
        ],
        "source_status": str(execution_validation.get("all_packet_rows_approved", "")),
    }


def build_payload(
    completion_gate_json: Path,
    final_queue_json: Path,
    final_boundary_json: Path,
    execution_validation_json: Path,
    rks_open_probe_json: Path,
) -> dict[str, Any]:
    completion_gate = read_json(completion_gate_json)
    final_queue = read_json(final_queue_json)
    final_boundary = read_json(final_boundary_json)
    execution_validation = read_json(execution_validation_json)
    rks_open_probe = read_json(rks_open_probe_json)

    rows = build_gate_rows(completion_gate)
    rows.extend(build_final_queue_rows(final_queue, len(rows) + 1))
    rows.extend(build_boundary_rows(final_boundary, len(rows) + 1))
    rows.extend(build_rks_open_only_rows(rks_open_probe, len(rows) + 1))

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "final_goal_complete": bool(completion_gate.get("final_goal_complete")),
        "safety": (
            "read-only classification; no auto approval; no RK10 ButtonRun; "
            "no mail/print/payment/final submit/production write"
        ),
        "row_count": len(rows),
        "category_counts": category_counts(rows),
        "operator_gap_summary": build_operator_gap_summary(execution_validation),
        "source_files": {
            "completion_gate_json": str(completion_gate_json),
            "final_queue_json": str(final_queue_json),
            "final_boundary_json": str(final_boundary_json),
            "execution_validation_json": str(execution_validation_json),
            "rks_open_probe_json": str(rks_open_probe_json),
        },
        "rows": [asdict(row) for row in rows],
    }


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[field.name for field in fields(BlockerRow)],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def format_path(value: str) -> str:
    return f"`{value}`" if value else "-"


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 完了ブロッカー分解 2026-06-22",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- final_goal_complete: `{payload['final_goal_complete']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- category_counts: `{json.dumps(payload['category_counts'], ensure_ascii=False)}`",
        f"- safety: `{payload['safety']}`",
        "",
        "## Meaning",
        "",
        "- `EXTERNAL_HUMAN_APPROVAL_REQUIRED`: Codex cannot auto-approve; operator/customer confirmation is required.",
        "- `FINAL_OPERATOR_FIELDS_REQUIRED`: final intake fields or evidence paths are blank.",
        "- `TECHNICAL_EVIDENCE_COLLECTED_OPEN_ONLY`: RK10 Editor open evidence exists, and runtime-intake still shows a technical evidence gap.",
        "- `TRUE_TECHNICAL_RUNTIME_GAP`: the RKS gate itself remains incomplete.",
        "- `AGGREGATE_BLOCKED_BY_DOWNSTREAM_GATES`: summary gate only; clear the specific rows first.",
        "",
        "## Operator Gap Summary",
        "",
        f"- row_count: `{payload['operator_gap_summary']['row_count']}`",
        f"- approved_row_count: `{payload['operator_gap_summary']['approved_row_count']}`",
        f"- needs_attention_count: `{payload['operator_gap_summary']['needs_attention_count']}`",
        f"- evidence_path_set_count: `{payload['operator_gap_summary']['evidence_path_set_count']}`",
        f"- evidence_exists_count: `{payload['operator_gap_summary']['evidence_exists_count']}`",
        f"- missing_evidence_row_count: `{payload['operator_gap_summary']['missing_evidence_row_count']}`",
        f"- operator_field_only_pending_count: `{payload['operator_gap_summary']['operator_field_only_pending_count']}`",
        f"- missing_operator_field_counts: `{json.dumps(payload['operator_gap_summary']['missing_operator_field_counts'], ensure_ascii=False)}`",
        "- This summary does not approve rows; it only proves whether remaining rows are evidence-path gaps or human/operator field gaps.",
        "",
        "## Rows",
        "",
        "| Rank | Source | Gate/Bundle | Scenarios | Category | Blocker | Codex Can Continue | Human/External Needed | Forbidden | Next Action | Source |",
        "|---:|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["rank"]),
                    str(row["source_kind"]),
                    str(row["gate_or_bundle"]),
                    str(row["scenarios"]) or "-",
                    str(row["category"]),
                    str(row["blocker"]).replace("|", "/") or "-",
                    str(row["codex_can_continue_with"]).replace("|", "/") or "-",
                    str(row["human_or_external_input_needed"]).replace("|", "/") or "-",
                    str(row["forbidden_scope"]).replace("|", "/") or "-",
                    str(row["next_action"]).replace("|", "/") or "-",
                    format_path(str(row["source_path"])),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Sources", ""])
    for key, value in payload["source_files"].items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "completion_blocker_split.json"
    csv_path = out_dir / "completion_blocker_split.csv"
    md_path = out_dir / "completion_blocker_split.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, payload["rows"])
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(csv_path)
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate completion blocker split.")
    parser.add_argument("--completion-gate-json", type=Path, default=DEFAULT_COMPLETION_GATE_JSON)
    parser.add_argument("--final-queue-json", type=Path, default=DEFAULT_FINAL_QUEUE_JSON)
    parser.add_argument("--final-boundary-json", type=Path, default=DEFAULT_FINAL_BOUNDARY_JSON)
    parser.add_argument(
        "--execution-validation-json",
        type=Path,
        default=DEFAULT_EXECUTION_VALIDATION_JSON,
    )
    parser.add_argument("--rks-open-probe-json", type=Path, default=DEFAULT_RKS_OPEN_PROBE_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        args.completion_gate_json,
        args.final_queue_json,
        args.final_boundary_json,
        args.execution_validation_json,
        args.rks_open_probe_json,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
