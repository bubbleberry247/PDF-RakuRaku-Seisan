"""Generate non-approving operator evidence prefill guidance.

This tool reads current bundle evidence packs and approval queue reports, then
writes a draft CSV/Markdown that tells the operator which evidence folder to
use and which blocker evidence explains the current stop. It does not approve
rows, copy production data, open external apps, or fill operator fields.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_PACK_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "bundle_evidence_packs.json"
)
DEFAULT_NEXT_QUEUE_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "next_approval_queue_20260620"
    / "next_approval_queue.json"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "operator_evidence_prefill_20260620"
S44_DECISION_INPUT_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_decision_input.csv"
)
S44_SINGLE_ENTRY_INPUT_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_single_entry_input.csv"
)
S44_BUCKET_DECISION_INPUT_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_bucket_decision_input.csv"
)
S44_REVIEW_AID_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_aid.csv"
)
S44_PRIORITY_QUEUE_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_priority_queue.csv"
)
S44_NEXT_STEPS_MD = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_next_steps.md"
)
S44_AMOUNT_ZERO_REVIEW_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_review_01_amount_zero_review.csv"
)
S44_AMOUNT_MISMATCH_REVIEW_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_review_02_amount_mismatch_review.csv"
)
S44_AMOUNT_MATCH_QUICK_REVIEW_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_review_03_amount_match_quick_review.csv"
)
BUSINESS_DATA_APPROVAL_CHECKLIST_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "business_data_approval_bundle"
    / "business_data_approval_checklist.csv"
)
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
        S44_SINGLE_ENTRY_INPUT_CSV,
        S44_NEXT_STEPS_MD,
        S44_DECISION_INPUT_CSV,
        S44_BUCKET_DECISION_INPUT_CSV,
        S44_PRIORITY_QUEUE_CSV,
        S44_AMOUNT_ZERO_REVIEW_CSV,
        S44_AMOUNT_MISMATCH_REVIEW_CSV,
        S44_AMOUNT_MATCH_QUICK_REVIEW_CSV,
        S44_REVIEW_AID_CSV,
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
class PrefillRow:
    bundle: str
    owner: str
    scenarios: str
    scenario_count: int
    current_queue_rank: str
    current_status: str
    current_blocker_evidence_path: str
    target_intake_path: str
    final_evidence_dir: str
    suggested_scenario_folders: str
    filename_template_path: str
    filename_template_markdown_path: str
    supporting_input_paths: str
    filename_example_count: int
    filename_examples: str
    reference_snapshot_path: str
    reference_evidence_count: int
    proposed_operator_result: str
    proposed_evidence_path: str
    reviewer_required: str
    reviewed_at_required: str
    can_auto_approve: str
    reason_not_auto_approved: str
    next_action: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return text or "scenario"


def split_scenarios(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def suggested_scenario_folders(final_evidence_dir: str, scenarios: str) -> str:
    if not final_evidence_dir.strip():
        return ""
    return " / ".join(
        str(Path(final_evidence_dir) / f"scenario_{slugify(scenario)}")
        for scenario in split_scenarios(scenarios)
    )


def reference_evidence_count(pack: dict[str, Any]) -> int:
    scenario_evidence = pack.get("scenario_evidence", [])
    if not isinstance(scenario_evidence, list):
        return 0
    return sum(
        1
        for row in scenario_evidence
        if isinstance(row, dict) and row.get("current_reference_exists") is True
    )


def read_filename_examples(path: str, limit: int = 5) -> list[str]:
    if not path.strip():
        return []
    template_path = Path(path)
    if not template_path.exists():
        return []
    with template_path.open("r", encoding="utf-8-sig", newline="") as handle:
        examples = [
            str(row.get("example_filename", "")).strip()
            for row in csv.DictReader(handle)
            if str(row.get("example_filename", "")).strip()
        ]
    return examples[:limit]


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


def queue_rows_by_bundle(next_queue_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = next_queue_payload.get("rows", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("bundle", "")): row
        for row in rows
        if isinstance(row, dict) and row.get("bundle")
    }


def queue_status_for_bundle(
    bundle: str,
    next_queue_payload: dict[str, Any],
    queue_row: dict[str, Any] | None,
) -> tuple[str, str]:
    if bundle == "OUTLOOK_COM_BUNDLE":
        return (
            str(next_queue_payload.get("outlook_com_status", "")),
            str(next_queue_payload.get("outlook_com_diagnosis_report", "")),
        )
    if bundle == "RK10_EDITOR_RUNTIME_BUNDLE":
        return (
            str(next_queue_payload.get("rk10_editor_cold_status", "")),
            str(next_queue_payload.get("rk10_recovery_checklist", "")),
        )
    if queue_row:
        return ("WAITING_OPERATOR_OR_BUSINESS_APPROVAL", str(queue_row.get("evidence_pack_path", "")))
    return ("QUEUE_ROW_MISSING", "")


def next_action_for_bundle(
    pack: dict[str, Any],
    queue_row: dict[str, Any] | None,
    current_status: str,
) -> str:
    if queue_row and queue_row.get("operator_action"):
        return str(queue_row["operator_action"])
    required = str(pack.get("required_final_evidence", ""))
    if required:
        return f"final_evidenceへ証跡を置き、intake CSVへoperator_result/reviewer/reviewed_atを記入する: {required}"
    return "final_evidenceへ証跡を置き、intake CSVへoperator_result/reviewer/reviewed_atを記入する"


def build_rows(
    pack_json_path: Path = DEFAULT_PACK_JSON,
    next_queue_json_path: Path = DEFAULT_NEXT_QUEUE_JSON,
) -> list[PrefillRow]:
    pack_payload = read_json(pack_json_path)
    queue_payload = read_json(next_queue_json_path)
    queue_by_bundle = queue_rows_by_bundle(queue_payload)
    packs = pack_payload.get("packs", [])
    if not isinstance(packs, list):
        return []
    rows: list[PrefillRow] = []
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        bundle = str(pack.get("bundle", ""))
        scenarios = str(pack.get("scenarios", ""))
        queue_row = queue_by_bundle.get(bundle)
        current_status, blocker_evidence = queue_status_for_bundle(
            bundle,
            queue_payload,
            queue_row,
        )
        final_evidence_dir = str(pack.get("final_evidence_dir", ""))
        filename_template_path = str(pack.get("filename_template_path", ""))
        filename_examples = read_filename_examples(filename_template_path)
        rows.append(
            PrefillRow(
                bundle=bundle,
                owner=str(pack.get("owner", "")),
                scenarios=scenarios,
                scenario_count=int(pack.get("scenario_count", 0)),
                current_queue_rank=str(queue_row.get("rank", "")) if queue_row else "",
                current_status=current_status,
                current_blocker_evidence_path=blocker_evidence,
                target_intake_path=str(pack.get("intake_path", "")),
                final_evidence_dir=final_evidence_dir,
                suggested_scenario_folders=suggested_scenario_folders(final_evidence_dir, scenarios),
                filename_template_path=filename_template_path,
                filename_template_markdown_path=str(pack.get("filename_template_markdown_path", "")),
                supporting_input_paths=supporting_input_paths_for_bundle(bundle),
                filename_example_count=len(filename_examples),
                filename_examples=" / ".join(filename_examples),
                reference_snapshot_path=str(pack.get("reference_snapshot_path", "")),
                reference_evidence_count=reference_evidence_count(pack),
                proposed_operator_result="",
                proposed_evidence_path=final_evidence_dir,
                reviewer_required="YES",
                reviewed_at_required="YES",
                can_auto_approve="NO",
                reason_not_auto_approved=(
                    "operator_result/reviewer/reviewed_at require explicit review; "
                    "reference evidence is not final evidence"
                ),
                next_action=next_action_for_bundle(pack, queue_row, current_status),
            )
        )
    return sorted(
        rows,
        key=lambda row: int(row.current_queue_rank or "999"),
    )


def build_payload(
    pack_json_path: Path = DEFAULT_PACK_JSON,
    next_queue_json_path: Path = DEFAULT_NEXT_QUEUE_JSON,
) -> dict[str, Any]:
    rows = build_rows(pack_json_path, next_queue_json_path)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": "draft guidance only; no approval, no external operation, no evidence copy",
        "pack_json_path": str(pack_json_path),
        "next_queue_json_path": str(next_queue_json_path),
        "row_count": len(rows),
        "auto_approved_count": sum(1 for row in rows if row.can_auto_approve == "YES"),
        "rows": [asdict(row) for row in rows],
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(PrefillRow)]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def scenario_folder_summary(row: dict[str, Any]) -> str:
    suggested = str(row.get("suggested_scenario_folders", ""))
    if not suggested:
        return str(row.get("proposed_evidence_path", ""))
    return suggested


def build_field_action_summary(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "rank": str(row.get("current_queue_rank", "")),
            "bundle": str(row.get("bundle", "")),
            "scenarios": str(row.get("scenarios", "")),
            "put_final_evidence_here": scenario_folder_summary(row),
            "save_with_these_names": str(row.get("filename_examples", "")),
            "then_update_this_csv": str(row.get("target_intake_path", "")),
            "complete_these_input_files": str(row.get("supporting_input_paths", "")),
            "filename_template": str(row.get("filename_template_path", "")),
            "current_blocker": str(row.get("current_status", "")),
            "blocker_source": str(row.get("current_blocker_evidence_path", "")),
            "next_action": str(row.get("next_action", "")),
        }
        for row in rows
    ]


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    field_actions = build_field_action_summary(rows)
    lines = [
        "# Operator Evidence Prefill 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- auto_approved_count: `{payload['auto_approved_count']}`",
        "",
        "## Field Action Summary",
        "",
        "- This section is the operator's short path: first complete the listed input files, then put evidence in the listed folder and update the listed CSV.",
        "- It still does not approve anything automatically.",
        "",
        "| Rank | Bundle | Scenarios | Complete These Input Files | Put Final Evidence Here | Save With These Names | Then Update This CSV | Current Blocker | Next Action |",
        "|---:|---|---|---|---|---|---|---|---|",
    ]
    for action in field_actions:
        lines.append(
            "| "
            + " | ".join(
                [
                    action["rank"],
                    action["bundle"],
                    action["scenarios"],
                    f"`{action['complete_these_input_files']}`"
                    if action["complete_these_input_files"]
                    else "-",
                    f"`{action['put_final_evidence_here']}`" if action["put_final_evidence_here"] else "-",
                    f"`{action['save_with_these_names']}`" if action["save_with_these_names"] else "-",
                    f"`{action['then_update_this_csv']}`" if action["then_update_this_csv"] else "-",
                    action["current_blocker"].replace("|", "/"),
                    action["next_action"].replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Rank | Bundle | Status | Supporting Input Paths | Proposed Evidence Path | Suggested Scenario Folders | Filename Template | Filename Examples | Blocker Evidence | Next Action | Auto Approve |",
            "|---:|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["current_queue_rank"]),
                    str(row["bundle"]),
                    str(row["current_status"]).replace("|", "/"),
                    f"`{row['supporting_input_paths']}`" if row.get("supporting_input_paths") else "-",
                    f"`{row['proposed_evidence_path']}`",
                    f"`{row['suggested_scenario_folders']}`" if row.get("suggested_scenario_folders") else "-",
                    f"`{row['filename_template_path']}`" if row.get("filename_template_path") else "-",
                    f"`{row['filename_examples']}`" if row.get("filename_examples") else "-",
                    f"`{row['current_blocker_evidence_path']}`",
                    str(row["next_action"]).replace("|", "/"),
                    str(row["can_auto_approve"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Usage",
            "",
            "- This file is a draft helper, not approval evidence.",
            "- Complete the supporting input path first when one is listed.",
            "- Put final proof under the suggested scenario folder or proposed `final_evidence` path, then update the intake CSV or six-row bundle operator sheet.",
            "- Do not set approved/complete until the scenario-specific hard stops and required final evidence are actually satisfied.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate operator evidence prefill guidance.")
    parser.add_argument("--pack-json", type=Path, default=DEFAULT_PACK_JSON)
    parser.add_argument("--next-queue-json", type=Path, default=DEFAULT_NEXT_QUEUE_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.pack_json, args.next_queue_json)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "operator_evidence_prefill.json"
    csv_path = args.out_dir / "operator_evidence_prefill.csv"
    md_path = args.out_dir / "operator_evidence_prefill.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, payload["rows"])
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
