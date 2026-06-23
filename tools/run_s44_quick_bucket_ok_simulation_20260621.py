"""Run an isolated Scenario 44 quick-bucket OK simulation.

This simulation proves the Scenario 44 shadow-handoff path can accept the
minimum quick-review bucket input and generate a verified shadow handoff. It is
not approval evidence and never updates the source spot-check CSV, live
review.db, live handoff, processed PDFs, Rakuraku, mail, print, RK10, or any
production file.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import build_s44_spot_check_handoff_candidates_20260620 as s44


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "s44_quick_bucket_ok_simulation_20260621"
SIMULATION_REVIEWER = "SIMULATION_ONLY_NOT_APPROVAL"
QUICK_BUCKET = "AMOUNT_MATCH_QUICK_REVIEW"
SIMULATION_NOTE = (
    "Simulation only: if every quick-review row is business-approved, this "
    "single bucket OK should produce shadow-handoff candidates. This is not "
    "final approval."
)


@dataclass(frozen=True)
class SimulationResult:
    generated_at: str
    status: str
    safety: str
    source_csv: str
    source_exists: bool
    source_sha256_before: str
    source_sha256_after: str
    source_unchanged: bool
    out_dir: str
    simulation_seed_csv: str
    single_entry_input_csv: str
    decision_input_csv: str
    bucket_decision_input_csv: str
    ok_count: int
    blank_count: int
    invalid_ok_count: int
    missing_pdf_count: int
    bucket_decision_overlay_applied_count: int
    bucket_decision_overlay_invalid_count: int
    shadow_handoff_generated: bool
    shadow_handoff_verified: bool
    shadow_handoff_item_count: int
    shadow_handoff_data_file: str
    shadow_handoff_latest_ready_file: str
    shadow_handoff_checksum: str
    builder_report_json: str
    builder_report_md: str
    notes: str


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def simulation_single_entry_row(reviewed_at: str) -> dict[str, str]:
    return {
        "entry_type": "BUCKET",
        "review_bucket": QUICK_BUCKET,
        "operation_id": "",
        "decision": "OK",
        "reject_reason": "",
        "reviewer": SIMULATION_REVIEWER,
        "reviewed_at": reviewed_at,
        "eligible_row_count": "5",
        "can_apply_ok": "YES",
        "can_apply_ng": "YES",
        "operator_next_action": SIMULATION_NOTE,
        "vendor_name": "",
        "amount_estimate": "",
        "filename_amount": "",
        "amount_difference_yen": "",
        "receiving_date": "",
        "invoice_number": "",
        "filename": "",
        "pdf_path": "",
        "pdf_exists": "",
        "allowed_scope": "Applies only to quick-review rows with blank row-level operator_entry_confirm_ok.",
        "still_forbidden": (
            "No source CSV write, live review.db update, live handoff, Rakuraku "
            "operation, PDF processed move, mail, print, RK10 ButtonRun, or "
            "production write."
        ),
    }


def write_simulation_input(single_entry_csv: Path, reviewed_at: str) -> None:
    single_entry_csv.parent.mkdir(parents=True, exist_ok=True)
    s44.write_csv(
        single_entry_csv,
        [simulation_single_entry_row(reviewed_at)],
        fieldnames=s44.SINGLE_ENTRY_INPUT_FIELDS,
    )


def build_result(spot_check_csv: Path, out_dir: Path) -> SimulationResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().isoformat(timespec="seconds")
    run_token = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = out_dir / f"run_{run_token}"
    run_dir.mkdir(parents=True, exist_ok=True)
    source_before = s44.file_sha256(spot_check_csv)
    decision_input_csv = run_dir / "s44_business_review_decision_input.csv"
    bucket_decision_input_csv = run_dir / "s44_business_review_bucket_decision_input.csv"
    single_entry_input_csv = run_dir / "s44_business_review_single_entry_input.csv"
    simulation_seed_csv = run_dir / "s44_quick_bucket_ok_simulation_seed.csv"

    s44.ensure_decision_input_template(spot_check_csv, decision_input_csv)
    s44.ensure_bucket_decision_input_template(
        spot_check_csv,
        decision_input_csv,
        bucket_decision_input_csv,
    )
    write_simulation_input(simulation_seed_csv, generated_at)
    write_simulation_input(single_entry_input_csv, generated_at)
    s44.sync_single_entry_input_to_decision_inputs(
        single_entry_input_csv,
        decision_input_csv,
        bucket_decision_input_csv,
    )
    summary = s44.analyze_spot_check(
        spot_check_csv,
        decision_input_csv,
        bucket_decision_input_csv,
    )
    payload = s44.write_reports(summary, run_dir, single_entry_input_csv)
    source_after = s44.file_sha256(spot_check_csv)
    shadow_handoff = payload.get("shadow_handoff", {})
    if not isinstance(shadow_handoff, dict):
        shadow_handoff = {}
    return SimulationResult(
        generated_at=generated_at,
        status=summary.status,
        safety=(
            "repo-local simulation only; no approval, no source CSV write, no "
            "live handoff, no Rakuraku, no mail, no print, no RK10, no production write"
        ),
        source_csv=str(spot_check_csv),
        source_exists=spot_check_csv.exists(),
        source_sha256_before=source_before,
        source_sha256_after=source_after,
        source_unchanged=source_before == source_after,
        out_dir=str(run_dir),
        simulation_seed_csv=str(simulation_seed_csv),
        single_entry_input_csv=str(single_entry_input_csv),
        decision_input_csv=str(decision_input_csv),
        bucket_decision_input_csv=str(bucket_decision_input_csv),
        ok_count=summary.ok_count,
        blank_count=summary.blank_count,
        invalid_ok_count=summary.invalid_ok_count,
        missing_pdf_count=summary.missing_pdf_count,
        bucket_decision_overlay_applied_count=summary.bucket_decision_overlay_applied_count,
        bucket_decision_overlay_invalid_count=summary.bucket_decision_overlay_invalid_count,
        shadow_handoff_generated=bool(shadow_handoff.get("generated")),
        shadow_handoff_verified=bool(shadow_handoff.get("verified")),
        shadow_handoff_item_count=int(shadow_handoff.get("item_count", 0) or 0),
        shadow_handoff_data_file=str(shadow_handoff.get("data_file", "")),
        shadow_handoff_latest_ready_file=str(shadow_handoff.get("latest_ready_file", "")),
        shadow_handoff_checksum=str(shadow_handoff.get("checksum", "")),
        builder_report_json=str(run_dir / "s44_spot_check_handoff_candidates.json"),
        builder_report_md=str(run_dir / "s44_spot_check_handoff_candidates.md"),
        notes=SIMULATION_NOTE,
    )


def build_markdown(result: SimulationResult) -> str:
    return "\n".join(
        [
            "# Scenario 44 quick-bucket OK simulation 2026-06-21",
            "",
            f"- generated_at: `{result.generated_at}`",
            f"- status: `{result.status}`",
            f"- safety: `{result.safety}`",
            f"- source_csv: `{result.source_csv}`",
            f"- source_exists: `{result.source_exists}`",
            f"- source_unchanged: `{result.source_unchanged}`",
            f"- ok_count: `{result.ok_count}`",
            f"- blank_count: `{result.blank_count}`",
            f"- invalid_ok_count: `{result.invalid_ok_count}`",
            f"- missing_pdf_count: `{result.missing_pdf_count}`",
            f"- bucket_decision_overlay_applied_count: `{result.bucket_decision_overlay_applied_count}`",
            f"- bucket_decision_overlay_invalid_count: `{result.bucket_decision_overlay_invalid_count}`",
            f"- shadow_handoff_generated: `{result.shadow_handoff_generated}`",
            f"- shadow_handoff_verified: `{result.shadow_handoff_verified}`",
            f"- shadow_handoff_item_count: `{result.shadow_handoff_item_count}`",
            f"- shadow_handoff_data_file: `{result.shadow_handoff_data_file}`",
            f"- shadow_handoff_latest_ready_file: `{result.shadow_handoff_latest_ready_file}`",
            f"- shadow_handoff_checksum: `{result.shadow_handoff_checksum}`",
            "",
            "## Boundary",
            "",
            "- This is not business approval evidence.",
            "- It proves the repo-local Scenario 44 shadow-handoff path can run when the allowed quick-review bucket input is supplied.",
            "- The source spot-check CSV hash must remain unchanged.",
            "",
            "## Inputs / Outputs",
            "",
            f"- simulation_seed_csv: `{result.simulation_seed_csv}`",
            f"- single_entry_input_csv: `{result.single_entry_input_csv}`",
            f"- decision_input_csv: `{result.decision_input_csv}`",
            f"- bucket_decision_input_csv: `{result.bucket_decision_input_csv}`",
            f"- builder_report_json: `{result.builder_report_json}`",
            f"- builder_report_md: `{result.builder_report_md}`",
            "",
            "## Notes",
            "",
            f"- {result.notes}",
        ]
    ) + "\n"


def write_outputs(result: SimulationResult, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "s44_quick_bucket_ok_simulation.json"
    md_path = out_dir / "s44_quick_bucket_ok_simulation.md"
    json_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(result), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Scenario 44 quick-bucket OK simulation.")
    parser.add_argument("--spot-check-csv", type=Path, default=s44.SPOT_CHECK_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(args.spot_check_csv, args.out_dir)
    write_outputs(result, args.out_dir)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if result.status != "READY_FOR_SHADOW_HANDOFF":
        return 1
    if not result.source_unchanged:
        return 1
    if result.ok_count != 5 or result.shadow_handoff_item_count != 5:
        return 1
    if not result.shadow_handoff_generated or not result.shadow_handoff_verified:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
