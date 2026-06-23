"""Collect business-data approval evidence into the bundle intake.

This tool never performs production registration, mail sending, payment, or
MainSV/source-file writes. It only packages existing per-scenario approval
records after the business owner has recorded target data, stop condition,
count/amount, source evidence, latest clean log, and approver.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
SCENARIOS = ("43", "47", "55", "63")
APPROVAL_FIELDNAMES = [
    "scenario",
    "target_data_confirmed",
    "stop_condition_confirmed",
    "business_approver",
    "approved_item_count",
    "approved_total_amount_yen",
    "source_evidence_path",
    "latest_clean_log_path",
    "production_write_allowed_now",
    "mail_allowed_now",
    "payment_allowed_now",
]
DEFAULT_APPROVAL_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "business_data_approval_bundle"
    / "business_data_approval_checklist.csv"
)
DEFAULT_COST_MAP_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "business_cost_evidence_map_20260620"
    / "business_cost_evidence_map.json"
)
DEFAULT_RKS_RUNTIME_VALIDATION_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "rks_runtime_operator_intake_validation_20260620"
    / "rks_runtime_operator_intake_validation.json"
)
DEFAULT_INTAKE_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "business_data_approval_bundle"
    / "final_evidence_intake.csv"
)
DEFAULT_FINAL_EVIDENCE_ROOT = (
    ROOT
    / "plans"
    / "reports"
    / "bundle_evidence_packs_20260620"
    / "business_data_approval_bundle"
    / "final_evidence"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "business_data_approval_evidence_collect_20260620"
SYNC_NOTE = "business_data_approval_evidence_auto_collected_20260620"
TODO_PREFIX = "TODO"
TRUE_VALUES = {"1", "true", "yes", "y", "ok", "confirmed", "済", "確認済", "承認済", "はい"}
FALSE_VALUES = {"", "0", "false", "no", "n", "ng", "none", "未", "未実施", "禁止"}


@dataclass(frozen=True)
class ScenarioResult:
    scenario: str
    status: str
    ready_for_intake: bool
    updated_intake: bool
    target_data_confirmed: bool
    stop_condition_confirmed: bool
    business_approver: str
    approved_item_count: int | None
    approved_total_amount_yen: int | None
    cost_map_item_count: int | None
    cost_map_total_amount_yen: int | None
    count_difference: int | None
    amount_difference_yen: int | None
    source_evidence_path: str
    source_evidence_exists: bool
    latest_clean_log_path: str
    latest_clean_log_exists: bool
    production_write_allowed_now: bool
    mail_allowed_now: bool
    payment_allowed_now: bool
    final_evidence_dir: str
    final_evidence_files: list[str]
    blockers: str


@dataclass(frozen=True)
class CollectionResult:
    generated_at: str
    status: str
    ready_scenario_count: int
    updated_scenario_count: int
    required_scenario_count: int
    approval_csv: str
    approval_csv_exists: bool
    approval_template_created: bool
    approval_prefill_updated_count: int
    approval_csv_sha256: str
    cost_map_json: str
    cost_map_exists: bool
    rks_runtime_validation_json: str
    rks_runtime_validation_exists: bool
    intake_csv: str
    scenarios: list[ScenarioResult]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    for encoding in ("utf-8-sig", "cp932", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = list(reader.fieldnames or [])
                rows = [
                    {str(key): str(value).strip() for key, value in row.items() if key is not None}
                    for row in reader
                ]
            return fieldnames, rows
        except UnicodeDecodeError:
            continue
    return [], []


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize(value: object) -> str:
    return str(value or "").strip()


def normalized_lower(value: object) -> str:
    return normalize(value).lower()


def parse_int(value: object) -> int | None:
    text = normalize(value).replace(",", "")
    if not text or text.upper().startswith(TODO_PREFIX):
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def is_truthy(value: object) -> bool:
    return normalized_lower(value) in TRUE_VALUES


def is_filled(value: object) -> bool:
    text = normalize(value)
    return bool(text) and not text.upper().startswith(TODO_PREFIX)


def path_exists(path_text: str) -> bool:
    if not is_filled(path_text):
        return False
    return Path(path_text).exists()


def approval_rows_by_scenario(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("scenario", ""): row for row in rows}


def cost_map_rows_by_scenario(cost_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = cost_map.get("rows")
    if not isinstance(rows, list):
        return {}
    return {
        normalize(row.get("scenario")): row
        for row in rows
        if isinstance(row, dict) and normalize(row.get("scenario"))
    }


def approved_rks_logs_by_scenario(validation_json: Path | None) -> dict[str, str]:
    if validation_json is None:
        return {}
    payload = read_json(validation_json)
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {}
    approved_logs: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        scenario = normalize(row.get("scenario"))
        latest_log_path = normalize(row.get("latest_log_path"))
        if not scenario or not latest_log_path:
            continue
        if row.get("approved") is True and Path(latest_log_path).exists():
            approved_logs[scenario] = latest_log_path
    return approved_logs


def template_text(value: object, placeholder: str) -> str:
    text = normalize(value)
    return text if text else placeholder


def cost_row_has_safe_count_amount_evidence(cost_row: dict[str, Any]) -> bool:
    source = normalize(cost_row.get("source"))
    return (
        normalize(cost_row.get("validation_result")) == "PASS"
        and parse_int(cost_row.get("item_count")) is not None
        and parse_int(cost_row.get("total_amount_yen")) is not None
        and bool(source)
        and Path(source).exists()
    )


def latest_clean_log_template_text(
    cost_row: dict[str, Any],
    rks_latest_log_path: str = "",
) -> str:
    if cost_row_has_safe_count_amount_evidence(cost_row):
        return normalize(cost_row.get("source"))
    if is_filled(rks_latest_log_path) and Path(rks_latest_log_path).exists():
        return rks_latest_log_path
    return "TODO_LATEST_CLEAN_LOG_PATH"


def build_approval_template_rows(
    cost_map_json: Path,
    rks_runtime_validation_json: Path | None = None,
) -> list[dict[str, str]]:
    costs = cost_map_rows_by_scenario(read_json(cost_map_json))
    rks_logs = approved_rks_logs_by_scenario(rks_runtime_validation_json)
    rows = []
    for scenario in SCENARIOS:
        cost_row = costs.get(scenario, {})
        rows.append(
            {
                "scenario": scenario,
                "target_data_confirmed": "TODO_CONFIRM_TARGET_DATA",
                "stop_condition_confirmed": "TODO_CONFIRM_STOP_CONDITION",
                "business_approver": "TODO_APPROVER",
                "approved_item_count": template_text(cost_row.get("item_count"), "TODO_ITEM_COUNT"),
                "approved_total_amount_yen": template_text(
                    cost_row.get("total_amount_yen"),
                    "TODO_TOTAL_AMOUNT_YEN",
                ),
                "source_evidence_path": template_text(cost_row.get("source"), "TODO_SOURCE_EVIDENCE_PATH"),
                "latest_clean_log_path": latest_clean_log_template_text(
                    cost_row,
                    rks_logs.get(scenario, ""),
                ),
                "production_write_allowed_now": "NO",
                "mail_allowed_now": "NO",
                "payment_allowed_now": "NO",
            }
        )
    return rows


def ensure_approval_csv_template(
    approval_csv: Path,
    cost_map_json: Path,
    rks_runtime_validation_json: Path | None = None,
) -> bool:
    if approval_csv.exists():
        return False
    rows = build_approval_template_rows(cost_map_json, rks_runtime_validation_json)
    write_csv_rows(approval_csv, APPROVAL_FIELDNAMES, rows)
    return True


def prefill_existing_approval_csv_from_cost_map(
    approval_csv: Path,
    cost_map_json: Path,
    rks_runtime_validation_json: Path | None = None,
) -> int:
    fieldnames, rows = read_csv_rows(approval_csv)
    if not rows:
        return 0
    costs = cost_map_rows_by_scenario(read_json(cost_map_json))
    rks_logs = approved_rks_logs_by_scenario(rks_runtime_validation_json)
    updated_count = 0
    new_rows = []
    for row in rows:
        scenario = row.get("scenario", "")
        cost_row = costs.get(scenario, {})
        updated_row = dict(row)
        if cost_row_has_safe_count_amount_evidence(cost_row):
            source_path = normalize(cost_row.get("source"))
            if not is_filled(updated_row.get("approved_item_count")):
                updated_row["approved_item_count"] = normalize(cost_row.get("item_count"))
            if not is_filled(updated_row.get("approved_total_amount_yen")):
                updated_row["approved_total_amount_yen"] = normalize(cost_row.get("total_amount_yen"))
            if not is_filled(updated_row.get("source_evidence_path")):
                updated_row["source_evidence_path"] = source_path
            if not is_filled(updated_row.get("latest_clean_log_path")):
                updated_row["latest_clean_log_path"] = source_path
        elif not is_filled(updated_row.get("latest_clean_log_path")):
            rks_latest_log_path = rks_logs.get(scenario, "")
            if is_filled(rks_latest_log_path):
                updated_row["latest_clean_log_path"] = rks_latest_log_path
        if updated_row != row:
            updated_count += 1
        new_rows.append(updated_row)
    if updated_count:
        write_csv_rows(approval_csv, fieldnames or APPROVAL_FIELDNAMES, new_rows)
    return updated_count


def calculate_difference(left: int | None, right: int | None) -> int | None:
    if left is None or right is None:
        return None
    return left - right


def build_blockers(
    approval_row: dict[str, str],
    approved_item_count: int | None,
    approved_total_amount: int | None,
    count_difference: int | None,
    amount_difference: int | None,
    source_evidence_path: str,
    latest_clean_log_path: str,
) -> list[str]:
    blockers: list[str] = []
    if not approval_row:
        blockers.append("APPROVAL_ROW_MISSING")
    if not is_truthy(approval_row.get("target_data_confirmed")):
        blockers.append("TARGET_DATA_NOT_CONFIRMED")
    if not is_truthy(approval_row.get("stop_condition_confirmed")):
        blockers.append("STOP_CONDITION_NOT_CONFIRMED")
    if not is_filled(approval_row.get("business_approver")):
        blockers.append("BUSINESS_APPROVER_NOT_FILLED")
    if approved_item_count is None:
        blockers.append("APPROVED_ITEM_COUNT_NOT_FILLED")
    if approved_total_amount is None:
        blockers.append("APPROVED_TOTAL_AMOUNT_NOT_FILLED")
    if not path_exists(source_evidence_path):
        blockers.append("SOURCE_EVIDENCE_PATH_MISSING_OR_NOT_FOUND")
    if not path_exists(latest_clean_log_path):
        blockers.append("LATEST_CLEAN_LOG_PATH_MISSING_OR_NOT_FOUND")
    if is_truthy(approval_row.get("production_write_allowed_now")):
        blockers.append("PRODUCTION_WRITE_ALLOWED_FLAG_IS_UNSAFE")
    if is_truthy(approval_row.get("mail_allowed_now")):
        blockers.append("MAIL_ALLOWED_FLAG_IS_UNSAFE")
    if is_truthy(approval_row.get("payment_allowed_now")):
        blockers.append("PAYMENT_ALLOWED_FLAG_IS_UNSAFE")
    if count_difference not in (None, 0):
        blockers.append("COUNT_DIFFERENCE_NOT_ZERO")
    if amount_difference not in (None, 0):
        blockers.append("AMOUNT_DIFFERENCE_NOT_ZERO")
    return blockers


def evidence_token() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_final_evidence(
    scenario: str,
    result_base: dict[str, Any],
    final_evidence_dir: Path,
    token: str,
) -> list[Path]:
    final_evidence_dir.mkdir(parents=True, exist_ok=True)
    log_path = final_evidence_dir / f"scenario_{scenario}_safe_run_log_{token}.txt"
    summary_path = final_evidence_dir / f"scenario_{scenario}_count_amount_summary_{token}.csv"
    log_lines = [
        f"Scenario {scenario} business-data approval evidence collection",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        "scope=read-only evidence packaging; no production registration, no mail, no payment, no MainSV/source write",
        f"target_data_confirmed={result_base['target_data_confirmed']}",
        f"stop_condition_confirmed={result_base['stop_condition_confirmed']}",
        f"business_approver={result_base['business_approver']}",
        f"approved_item_count={result_base['approved_item_count']}",
        f"approved_total_amount_yen={result_base['approved_total_amount_yen']}",
        f"cost_map_item_count={result_base['cost_map_item_count']}",
        f"cost_map_total_amount_yen={result_base['cost_map_total_amount_yen']}",
        f"count_difference={result_base['count_difference']}",
        f"amount_difference_yen={result_base['amount_difference_yen']}",
        f"source_evidence_path={result_base['source_evidence_path']}",
        f"latest_clean_log_path={result_base['latest_clean_log_path']}",
        f"production_write_allowed_now={result_base['production_write_allowed_now']}",
        f"mail_allowed_now={result_base['mail_allowed_now']}",
        f"payment_allowed_now={result_base['payment_allowed_now']}",
    ]
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    summary_keys = {
        "target_data_confirmed",
        "stop_condition_confirmed",
        "business_approver",
        "approved_item_count",
        "approved_total_amount_yen",
        "cost_map_item_count",
        "cost_map_total_amount_yen",
        "count_difference",
        "amount_difference_yen",
        "source_evidence_path",
        "latest_clean_log_path",
    }
    rows = [
        {"metric": key, "value": str(value)}
        for key, value in result_base.items()
        if key in summary_keys
    ]
    write_csv_rows(summary_path, ["metric", "value"], rows)
    return [log_path, summary_path]


def append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing}; {note}"


def update_intake_row(
    intake_csv: Path,
    scenario: str,
    final_evidence_dir: Path,
) -> bool:
    fieldnames, rows = read_csv_rows(intake_csv)
    if not rows:
        return False
    updated = False
    new_rows = []
    for row in rows:
        if row.get("bundle") == "BUSINESS_DATA_APPROVAL_BUNDLE" and row.get("scenario") == scenario:
            row = {
                **row,
                "final_evidence_path": str(final_evidence_dir),
                "notes": append_note(row.get("notes", ""), SYNC_NOTE),
            }
            updated = True
        new_rows.append(row)
    if updated:
        write_csv_rows(intake_csv, fieldnames, new_rows)
    return updated


def build_scenario_result(
    scenario: str,
    approval_row: dict[str, str],
    cost_row: dict[str, Any],
    intake_csv: Path,
    final_evidence_root: Path,
) -> ScenarioResult:
    approved_item_count = parse_int(approval_row.get("approved_item_count"))
    approved_total_amount = parse_int(approval_row.get("approved_total_amount_yen"))
    cost_map_item_count = parse_int(cost_row.get("item_count"))
    cost_map_total_amount = parse_int(cost_row.get("total_amount_yen"))
    count_difference = calculate_difference(approved_item_count, cost_map_item_count)
    amount_difference = calculate_difference(approved_total_amount, cost_map_total_amount)
    source_evidence_path = normalize(approval_row.get("source_evidence_path") or cost_row.get("source"))
    latest_clean_log_path = normalize(approval_row.get("latest_clean_log_path"))
    result_base = {
        "target_data_confirmed": is_truthy(approval_row.get("target_data_confirmed")),
        "stop_condition_confirmed": is_truthy(approval_row.get("stop_condition_confirmed")),
        "business_approver": normalize(approval_row.get("business_approver")),
        "approved_item_count": approved_item_count,
        "approved_total_amount_yen": approved_total_amount,
        "cost_map_item_count": cost_map_item_count,
        "cost_map_total_amount_yen": cost_map_total_amount,
        "count_difference": count_difference,
        "amount_difference_yen": amount_difference,
        "source_evidence_path": source_evidence_path,
        "latest_clean_log_path": latest_clean_log_path,
        "production_write_allowed_now": is_truthy(approval_row.get("production_write_allowed_now")),
        "mail_allowed_now": is_truthy(approval_row.get("mail_allowed_now")),
        "payment_allowed_now": is_truthy(approval_row.get("payment_allowed_now")),
    }
    blockers = build_blockers(
        approval_row,
        approved_item_count,
        approved_total_amount,
        count_difference,
        amount_difference,
        source_evidence_path,
        latest_clean_log_path,
    )
    final_evidence_dir = final_evidence_root / f"scenario_{scenario}"
    evidence_files: list[Path] = []
    updated_intake = False
    if not blockers:
        evidence_files = write_final_evidence(scenario, result_base, final_evidence_dir, evidence_token())
        updated_intake = update_intake_row(intake_csv, scenario, final_evidence_dir)
    if blockers:
        status = "WAITING_FOR_BUSINESS_DATA_APPROVAL"
    elif updated_intake:
        status = "READY_FOR_OPERATOR_FINAL_FIELDS"
    else:
        status = "BLOCKED_INTAKE_ROW_NOT_FOUND"
        blockers = ["BUSINESS_DATA_APPROVAL_INTAKE_ROW_NOT_FOUND"]
    return ScenarioResult(
        scenario=scenario,
        status=status,
        ready_for_intake=not blockers,
        updated_intake=updated_intake,
        target_data_confirmed=result_base["target_data_confirmed"],
        stop_condition_confirmed=result_base["stop_condition_confirmed"],
        business_approver=result_base["business_approver"],
        approved_item_count=approved_item_count,
        approved_total_amount_yen=approved_total_amount,
        cost_map_item_count=cost_map_item_count,
        cost_map_total_amount_yen=cost_map_total_amount,
        count_difference=count_difference,
        amount_difference_yen=amount_difference,
        source_evidence_path=source_evidence_path,
        source_evidence_exists=path_exists(source_evidence_path),
        latest_clean_log_path=latest_clean_log_path,
        latest_clean_log_exists=path_exists(latest_clean_log_path),
        production_write_allowed_now=result_base["production_write_allowed_now"],
        mail_allowed_now=result_base["mail_allowed_now"],
        payment_allowed_now=result_base["payment_allowed_now"],
        final_evidence_dir=str(final_evidence_dir),
        final_evidence_files=[str(path) for path in evidence_files],
        blockers=", ".join(blockers),
    )


def build_result(
    approval_csv: Path,
    cost_map_json: Path,
    intake_csv: Path,
    final_evidence_root: Path,
    rks_runtime_validation_json: Path | None = None,
    approval_template_created: bool = False,
    approval_prefill_updated_count: int = 0,
) -> CollectionResult:
    _fieldnames, approval_rows = read_csv_rows(approval_csv)
    approvals = approval_rows_by_scenario(approval_rows)
    costs = cost_map_rows_by_scenario(read_json(cost_map_json))
    scenario_results = [
        build_scenario_result(
            scenario,
            approvals.get(scenario, {}),
            costs.get(scenario, {}),
            intake_csv,
            final_evidence_root,
        )
        for scenario in SCENARIOS
    ]
    ready_count = sum(1 for row in scenario_results if row.ready_for_intake)
    updated_count = sum(1 for row in scenario_results if row.updated_intake)
    if ready_count == len(SCENARIOS):
        status = "READY_FOR_OPERATOR_FINAL_FIELDS"
    elif ready_count:
        status = "PARTIAL_READY_FOR_OPERATOR_FINAL_FIELDS"
    else:
        status = "WAITING_FOR_BUSINESS_DATA_APPROVAL"
    return CollectionResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status=status,
        ready_scenario_count=ready_count,
        updated_scenario_count=updated_count,
        required_scenario_count=len(SCENARIOS),
        approval_csv=str(approval_csv),
        approval_csv_exists=approval_csv.exists(),
        approval_template_created=approval_template_created,
        approval_prefill_updated_count=approval_prefill_updated_count,
        approval_csv_sha256=file_sha256(approval_csv),
        cost_map_json=str(cost_map_json),
        cost_map_exists=cost_map_json.exists(),
        rks_runtime_validation_json=str(rks_runtime_validation_json or ""),
        rks_runtime_validation_exists=bool(
            rks_runtime_validation_json and rks_runtime_validation_json.exists()
        ),
        intake_csv=str(intake_csv),
        scenarios=scenario_results,
    )


def build_markdown(result: CollectionResult) -> str:
    lines = [
        "# Business-data approval evidence collection 2026-06-20",
        "",
        f"- generated_at: `{result.generated_at}`",
        f"- status: `{result.status}`",
        f"- ready_scenario_count: `{result.ready_scenario_count}/{result.required_scenario_count}`",
        f"- updated_scenario_count: `{result.updated_scenario_count}`",
        f"- approval_csv: `{result.approval_csv}`",
        f"- approval_csv_exists: `{result.approval_csv_exists}`",
        f"- approval_template_created: `{result.approval_template_created}`",
        f"- approval_prefill_updated_count: `{result.approval_prefill_updated_count}`",
        f"- approval_csv_sha256: `{result.approval_csv_sha256}`",
        f"- cost_map_json: `{result.cost_map_json}`",
        f"- cost_map_exists: `{result.cost_map_exists}`",
        f"- rks_runtime_validation_json: `{result.rks_runtime_validation_json}`",
        f"- rks_runtime_validation_exists: `{result.rks_runtime_validation_exists}`",
        f"- intake_csv: `{result.intake_csv}`",
        "",
        "## Safety",
        "",
        "- This collector does not perform production registration, send mail, pay, write MainSV/source files, or run RK10 ButtonRun.",
        "- Rows that set production write, mail, or payment as allowed are rejected as unsafe.",
        "- Operator result, reviewer identity, and reviewed_at still must be supplied before the bundle can sync as final evidence.",
        "",
        "## Scenario Matrix",
        "",
        "| Scenario | Status | Ready | Updated | Approved Count | Approved Amount | Cost Count | Cost Amount | Count Diff | Amount Diff | Blockers |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in result.scenarios:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.scenario,
                    row.status,
                    "YES" if row.ready_for_intake else "NO",
                    "YES" if row.updated_intake else "NO",
                    str(row.approved_item_count),
                    str(row.approved_total_amount_yen),
                    str(row.cost_map_item_count),
                    str(row.cost_map_total_amount_yen),
                    str(row.count_difference),
                    str(row.amount_difference_yen),
                    f"`{row.blockers}`",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Final Evidence Files", ""])
    for row in result.scenarios:
        if row.final_evidence_files:
            lines.extend(f"- `{path}`" for path in row.final_evidence_files)
    if not any(row.final_evidence_files for row in result.scenarios):
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect business-data approval evidence.")
    parser.add_argument("--approval-csv", type=Path, default=DEFAULT_APPROVAL_CSV)
    parser.add_argument("--cost-map-json", type=Path, default=DEFAULT_COST_MAP_JSON)
    parser.add_argument("--rks-runtime-validation-json", type=Path, default=DEFAULT_RKS_RUNTIME_VALIDATION_JSON)
    parser.add_argument("--intake-csv", type=Path, default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--final-evidence-root", type=Path, default=DEFAULT_FINAL_EVIDENCE_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    approval_template_created = ensure_approval_csv_template(
        args.approval_csv,
        args.cost_map_json,
        args.rks_runtime_validation_json,
    )
    approval_prefill_updated_count = prefill_existing_approval_csv_from_cost_map(
        args.approval_csv,
        args.cost_map_json,
        args.rks_runtime_validation_json,
    )
    result = build_result(
        args.approval_csv,
        args.cost_map_json,
        args.intake_csv,
        args.final_evidence_root,
        args.rks_runtime_validation_json,
        approval_template_created,
        approval_prefill_updated_count,
    )
    json_path = args.out_dir / "business_data_approval_evidence_collect.json"
    md_path = args.out_dir / "business_data_approval_evidence_collect.md"
    json_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(result), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
