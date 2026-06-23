"""Generate a one-page next-step guide for remaining approval bundles.

This tool only reads existing bundle queue/prefill reports and writes a
repository report. It does not approve, execute, submit, print, mail, pay,
open RK10, call Azure, or write production files.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OPERATOR_PREFILL_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "operator_evidence_prefill_20260620"
    / "operator_evidence_prefill.json"
)
DEFAULT_NEXT_QUEUE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "next_approval_queue_20260620"
    / "next_approval_queue.json"
)
DEFAULT_COMPLETION_GATE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "goal_completion_gate_20260620"
    / "goal_completion_gate.json"
)
DEFAULT_BUNDLE_SYNC_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_intake_sync_20260620"
    / "bundle_evidence_intake_sync.json"
)
DEFAULT_UNIFIED_INPUT_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "unified_final_evidence_intake_20260621"
    / "unified_final_evidence_input.csv"
)
DEFAULT_MINIMUM_INPUT_INDEX = (
    ROOT
    / "plans"
    / "reports"
    / "next_bundle_minimum_input_packet_20260622"
    / "next_bundle_minimum_input_packet_index.md.numbered"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "remaining_approval_next_steps_20260621"
DEFAULT_BUNDLE_PACK_ROOT = ROOT / "plans" / "reports" / "bundle_evidence_packs_20260620"
PATH_SEPARATOR = " / "
COMPLETED_STATUSES = {"OUTLOOK_COM_READY"}


@dataclass(frozen=True)
class NextStepRow:
    rank: int | None
    bundle: str
    owner: str
    scenarios: str
    current_status: str
    next_action: str
    first_input_path: str
    additional_input_count: int
    all_input_paths: str
    supporting_material_paths: str
    final_evidence_dir: str
    target_intake_path: str
    filename_examples: str
    forbidden: str
    after_action_command: str
    start_here_path: str
    unified_input_csv: str
    unified_entry_keys: str
    active: bool


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def split_paths(value: object) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.split(PATH_SEPARATOR) if part.strip()]


def parse_rank(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def queue_rows_by_bundle(queue_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = queue_payload.get("rows", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("bundle", "")).strip(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("bundle", "")).strip()
    }


def bundle_sync_by_bundle(sync_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = sync_payload.get("results", [])
    if not isinstance(results, list):
        return {}
    return {
        str(row.get("bundle", "")).strip(): row
        for row in results
        if isinstance(row, dict) and str(row.get("bundle", "")).strip()
    }


def input_paths_for_row(prefill_row: dict[str, Any], status: str) -> list[str]:
    supporting_paths = split_paths(prefill_row.get("supporting_input_paths"))
    if status not in COMPLETED_STATUSES:
        return supporting_paths

    final_intake_paths = [
        str(prefill_row.get("target_intake_path") or "").strip(),
        str(prefill_row.get("suggested_scenario_folders") or "").strip(),
    ]
    return [path for path in final_intake_paths if path] or supporting_paths


def build_row(
    prefill_row: dict[str, Any],
    queue_row: dict[str, Any],
    fallback_after_action: str,
    unified_input_csv: Path,
    sync_row: dict[str, Any] | None = None,
) -> NextStepRow:
    rank = parse_rank(prefill_row.get("current_queue_rank") or queue_row.get("rank"))
    status = str(prefill_row.get("current_status", "")).strip()
    supporting_paths = input_paths_for_row(prefill_row, status)
    bundle = str(prefill_row.get("bundle", "")).strip()
    active = status not in COMPLETED_STATUSES
    if status in COMPLETED_STATUSES and sync_row is not None:
        active = not bool(sync_row.get("ready_to_sync"))
    return NextStepRow(
        rank=rank,
        bundle=bundle,
        owner=str(prefill_row.get("owner", "")).strip(),
        scenarios=str(prefill_row.get("scenarios", "")).strip(),
        current_status=status,
        next_action=str(prefill_row.get("next_action") or queue_row.get("operator_action") or "").strip(),
        first_input_path=supporting_paths[0] if supporting_paths else "",
        additional_input_count=max(len(supporting_paths) - 1, 0),
        all_input_paths=PATH_SEPARATOR.join(supporting_paths),
        supporting_material_paths=PATH_SEPARATOR.join(discover_supporting_material_paths(bundle)),
        final_evidence_dir=str(prefill_row.get("suggested_scenario_folders") or "").strip(),
        target_intake_path=str(prefill_row.get("target_intake_path") or "").strip(),
        filename_examples=str(prefill_row.get("filename_examples") or "").strip(),
        forbidden=str(queue_row.get("forbidden") or queue_row.get("approval_boundary") or "").strip(),
        after_action_command=str(queue_row.get("after_action_command") or fallback_after_action).strip(),
        start_here_path="",
        unified_input_csv=str(unified_input_csv),
        unified_entry_keys=PATH_SEPARATOR.join(
            f"{bundle}::{scenario.strip()}"
            for scenario in str(prefill_row.get("scenarios", "")).split(",")
            if scenario.strip()
        ),
        active=active,
    )


def build_rows(
    operator_prefill: dict[str, Any],
    next_queue: dict[str, Any],
    bundle_sync: dict[str, Any] | None = None,
    unified_input_csv: Path = DEFAULT_UNIFIED_INPUT_CSV,
) -> list[NextStepRow]:
    queue_by_bundle = queue_rows_by_bundle(next_queue)
    sync_by_bundle = bundle_sync_by_bundle(bundle_sync or {})
    prefill_rows = operator_prefill.get("rows", [])
    if not isinstance(prefill_rows, list):
        return []
    queue_rows = next_queue.get("rows", [])
    first_queue_row = queue_rows[0] if isinstance(queue_rows, list) and queue_rows else {}
    fallback_after_action = str(first_queue_row.get("after_action_command", "")).strip()
    rows = [
        build_row(
            row,
            queue_by_bundle.get(str(row.get("bundle", "")).strip(), {}),
            fallback_after_action,
            unified_input_csv,
            sync_by_bundle.get(str(row.get("bundle", "")).strip()),
        )
        for row in prefill_rows
        if isinstance(row, dict) and str(row.get("bundle", "")).strip()
    ]
    return sorted(rows, key=lambda row: (row.rank is None, row.rank or 99, row.bundle))


def build_payload(
    operator_prefill_json: Path,
    next_queue_json: Path,
    completion_gate_json: Path,
    bundle_sync_json: Path = DEFAULT_BUNDLE_SYNC_JSON,
    unified_input_csv: Path = DEFAULT_UNIFIED_INPUT_CSV,
) -> dict[str, Any]:
    operator_prefill = read_json(operator_prefill_json)
    next_queue = read_json(next_queue_json)
    completion_gate = read_json(completion_gate_json)
    bundle_sync = read_json(bundle_sync_json)
    rows = build_rows(operator_prefill, next_queue, bundle_sync, unified_input_csv)
    active_rows = [row for row in rows if row.active]
    completed_rows = [row for row in rows if not row.active]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": bool(completion_gate.get("final_goal_complete")),
        "safety": (
            "read-only guide generation only; no approval, no external operation, "
            "no evidence copy"
        ),
        "operator_prefill_json": str(operator_prefill_json),
        "next_queue_json": str(next_queue_json),
        "completion_gate_json": str(completion_gate_json),
        "bundle_sync_json": str(bundle_sync_json),
        "unified_input_csv": str(unified_input_csv),
        "minimum_input_index": str(DEFAULT_MINIMUM_INPUT_INDEX),
        "active_bundle_count": len(active_rows),
        "completed_bundle_count": len(completed_rows),
        "next_active_bundle": active_rows[0].bundle if active_rows else "",
        "after_action_command": active_rows[0].after_action_command if active_rows else "",
        "rows": [asdict(row) for row in rows],
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(NextStepRow.__dataclass_fields__.keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def format_path(value: str) -> str:
    return f"`{value}`" if value else "-"


def safe_filename(value: str) -> str:
    safe = "".join(
        character.lower() if character.isalnum() else "_"
        for character in value.strip()
    )
    return "_".join(part for part in safe.split("_") if part) or "bundle"


def discover_supporting_material_paths(
    bundle: str,
    bundle_pack_root: Path | None = None,
) -> list[str]:
    root = bundle_pack_root or DEFAULT_BUNDLE_PACK_ROOT
    supporting_dir = root / safe_filename(bundle) / "supporting_materials"
    if not supporting_dir.exists():
        return []
    return [
        str(path)
        for path in sorted(supporting_dir.iterdir(), key=lambda item: item.name.lower())
        if path.exists()
    ]


def attach_start_here_paths(payload: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    start_dir = out_dir / "active_bundle_start_here"
    rows = []
    for row in payload["rows"]:
        row_copy = dict(row)
        if row_copy.get("active"):
            filename = f"{safe_filename(str(row_copy.get('bundle', '')))}_START_HERE.md"
            row_copy["start_here_path"] = str(start_dir / filename)
        rows.append(row_copy)
    return {**payload, "start_here_dir": str(start_dir), "rows": rows}


def split_display_paths(value: object) -> list[str]:
    return split_paths(value)


def build_start_here_markdown(row: dict[str, Any], generated_at: str) -> str:
    input_paths = split_display_paths(row.get("all_input_paths"))
    supporting_materials = split_display_paths(row.get("supporting_material_paths"))
    evidence_dirs = split_display_paths(row.get("final_evidence_dir"))
    filename_examples = split_display_paths(row.get("filename_examples"))
    lines = [
        f"# {row['bundle']} START_HERE",
        "",
        f"- generated_at: `{generated_at}`",
        f"- scenarios: `{row['scenarios']}`",
        f"- owner: `{row['owner']}`",
        f"- current_status: `{row['current_status']}`",
        "- safety: `operator guide only; no approval, no external operation, no evidence copy`",
        "",
        "## 0. Minimum Input Shortcut",
        "",
        f"- unified_input_csv: `{row['unified_input_csv']}`",
        f"- entry_key: `{row['unified_entry_keys']}`",
        "- fill_only: `operator_result`, `reviewer`, `reviewed_at`",
        "- Leave the existing `final_evidence_path` as-is unless the evidence folder changes.",
        "- The fixed safe runner syncs nonblank values from this one CSV back into the bundle intake CSV.",
        "",
        "## 1. Complete Input Files",
        "",
    ]
    if input_paths:
        lines.extend(f"- `{path}`" for path in input_paths)
    else:
        lines.append("- No supporting input file is listed.")
    lines.extend(["", "## 1.5 Prepared Supporting Materials", ""])
    if supporting_materials:
        lines.extend(f"- `{path}`" for path in supporting_materials)
    else:
        lines.append("- No prepared supporting material folder is listed.")
    lines.extend(
        [
            "",
            "## 2. Put Final Evidence Here",
            "",
        ]
    )
    if evidence_dirs:
        lines.extend(f"- `{path}`" for path in evidence_dirs)
    else:
        lines.append("- Final evidence folder is not listed yet.")
    lines.extend(
        [
            "",
            "## 3. Use These File Names",
            "",
        ]
    )
    if filename_examples:
        lines.extend(f"- `{filename}`" for filename in filename_examples)
    else:
        lines.append("- Use a clear timestamped filename matching the evidence content.")
    lines.extend(
        [
            "",
            "## 4. Update Intake CSV",
            "",
            f"- intake_csv: `{row['target_intake_path']}`" if row.get("target_intake_path") else "- intake_csv: `NOT_LISTED`",
            "- required_fields: `operator_result`, `evidence_path`, `reviewer`, `reviewed_at`",
            "- `evidence_path` must point to an existing final evidence file or non-empty final evidence folder.",
            "",
            "## Hard Stops",
            "",
            f"- {row['forbidden']}" if row.get("forbidden") else "- Keep all scenario hard stops in force.",
            "",
            "## After Action",
            "",
            f"- next_action: {row['next_action']}",
            f"- fixed_safe_runner: `{row['after_action_command']}`" if row.get("after_action_command") else "- fixed_safe_runner: `NOT_LISTED`",
            "- This file is not approval evidence. It only tells the operator what to fill and where to put proof.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    active_rows = [row for row in rows if row["active"]]
    completed_rows = [row for row in rows if not row["active"]]
    lines = [
        "# Remaining approval next steps 2026-06-21",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- active_bundle_count: `{payload['active_bundle_count']}`",
        f"- completed_bundle_count: `{payload['completed_bundle_count']}`",
        f"- next_active_bundle: `{payload['next_active_bundle']}`",
        f"- safety: `{payload['safety']}`",
        "",
        "## Read This First",
        "",
        "- This is only a field guide. It does not approve or execute anything.",
        "- Complete one bundle at a time, starting from the first active row.",
        "- After each bundle, rerun the fixed safe runner shown at the end.",
        f"- Minimum input packet index: `{payload['minimum_input_index']}`",
        "- To reduce hunting, fill the `unified_input_csv` and `entry_key` shown in each START_HERE file.",
        "- Keep hard stops in place: no production registration, real mail, real print, payment execution, Azure paid OCR, RK10 ButtonRun, or production writes unless explicitly approved.",
        "",
        "## Active Bundle START_HERE Files",
        "",
    ]
    if active_rows:
        lines.extend(
            f"- {row['bundle']}: `{row.get('start_here_path', '')}`"
            for row in active_rows
        )
    else:
        lines.append("- No active bundles.")
    lines.extend(
        [
            "",
            "## Active Bundles",
            "",
            "| Rank | Bundle | Scenarios | Owner | First Input | Other Inputs | Final Evidence | Intake CSV | Next Action | Forbidden |",
            "|---:|---|---|---|---|---:|---|---|---|---|",
        ]
    )
    for row in active_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["rank"] or ""),
                    str(row["bundle"]),
                    str(row["scenarios"]),
                    str(row["owner"]),
                    format_path(str(row["first_input_path"])),
                    str(row["additional_input_count"]),
                    format_path(str(row["final_evidence_dir"])),
                    format_path(str(row["target_intake_path"])),
                    str(row["next_action"]),
                    str(row["forbidden"]),
                ]
            )
            + " |"
        )
    if completed_rows:
        lines.extend(
            [
                "",
                "## Completed / Excluded Bundles",
                "",
                "| Bundle | Scenarios | Status | Evidence Intake |",
                "|---|---|---|---|",
            ]
        )
        for row in completed_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["bundle"]),
                        str(row["scenarios"]),
                        str(row["current_status"]),
                        format_path(str(row["target_intake_path"])),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## After Action",
            "",
            f"- fixed_safe_runner: `{payload['after_action_command']}`",
            f"- operator_prefill_json: `{payload['operator_prefill_json']}`",
            f"- next_queue_json: `{payload['next_queue_json']}`",
            f"- completion_gate_json: `{payload['completion_gate_json']}`",
            f"- bundle_sync_json: `{payload['bundle_sync_json']}`",
            f"- unified_input_csv: `{payload['unified_input_csv']}`",
            f"- minimum_input_index: `{payload['minimum_input_index']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = attach_start_here_paths(payload, out_dir)
    json_path = out_dir / "remaining_approval_next_steps.json"
    md_path = out_dir / "remaining_approval_next_steps.md"
    csv_path = out_dir / "remaining_approval_next_steps.csv"
    for row in payload["rows"]:
        if not row.get("active") or not row.get("start_here_path"):
            continue
        start_path = Path(str(row["start_here_path"]))
        start_path.parent.mkdir(parents=True, exist_ok=True)
        start_path.write_text(
            build_start_here_markdown(row, str(payload["generated_at"])),
            encoding="utf-8",
        )
        write_numbered_copy(start_path)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_csv(csv_path, payload["rows"])
    write_numbered_copy(md_path)
    write_numbered_copy(csv_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate remaining approval next-step guide.")
    parser.add_argument("--operator-prefill-json", type=Path, default=DEFAULT_OPERATOR_PREFILL_JSON)
    parser.add_argument("--next-queue-json", type=Path, default=DEFAULT_NEXT_QUEUE_JSON)
    parser.add_argument("--completion-gate-json", type=Path, default=DEFAULT_COMPLETION_GATE_JSON)
    parser.add_argument("--bundle-sync-json", type=Path, default=DEFAULT_BUNDLE_SYNC_JSON)
    parser.add_argument("--unified-input-csv", type=Path, default=DEFAULT_UNIFIED_INPUT_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        args.operator_prefill_json,
        args.next_queue_json,
        args.completion_gate_json,
        args.bundle_sync_json,
        args.unified_input_csv,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
