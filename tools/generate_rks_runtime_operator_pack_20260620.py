"""Generate operator evidence pack for RK10 RKS runtime gates.

This tool reads the existing static RKS audit and creates a manual evidence
intake sheet for RK10 editor open/build/runtime checks. It never opens RK10,
executes RKS files, repacks ZIPs, presses ButtonRun, or writes production data.
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
REPORTS = ROOT / "plans" / "reports"
DEFAULT_STATIC_AUDIT_JSON = (
    REPORTS / "rks_static_guard_audit_20260620" / "rks_static_guard_audit.json"
)
DEFAULT_OUT_DIR = REPORTS / "rks_runtime_operator_pack_20260620"
DEFAULT_BUNDLE_PACK_DIR = (
    REPORTS / "bundle_evidence_packs_20260620" / "rk10_editor_runtime_bundle"
)
HARD_STOPS = (
    "ButtonRun禁止; 本番書込禁止; 実メール禁止; 実印刷禁止; 最終申請禁止; "
    "ZIP直接RKS改変禁止"
)
DEFERRED_RUNTIME_NEXT_GATE_PATTERNS = (
    ("before RKS", "WAITING_PREREQUISITE_BEFORE_RKS_RUNTIME"),
    ("choose confirmed entry", "WAITING_ENTRY_SELECTION_BEFORE_RKS_RUNTIME"),
    ("only if operating through the RKS entry", "WAITING_CONDITIONAL_RKS_ENTRY_DECISION"),
    ("entry decision", "WAITING_ENTRY_DECISION_BEFORE_RKS_RUNTIME"),
)
REQUIRED_COLUMNS = [
    "scenario",
    "rks_path",
    "operator_decision",
    "rk10_editor_open",
    "rk10_build",
    "runtime_or_safe_stop",
    "latest_log_clean",
    "latest_log_path",
    "save_as_path",
    "operator_name",
    "checked_at",
    "notes",
]
OPERATOR_INPUT_COLUMNS = REQUIRED_COLUMNS[2:]
ALLOWED_COMPLETE_DECISIONS = {
    "OPEN_BUILD_ONLY",
    "SAFE_STOP_ONLY",
    "REGENERATE_SAVE_AS_REQUIRED",
}
FOCUS_COLUMNS = [
    "scenario",
    "status",
    "intended_scope",
    "rks_path",
    "evidence_folder",
    "known_confirmed_scope",
    "known_evidence_path",
    "required_next_gate",
    "missing_fields",
    "remaining_operator_fields",
    "next_safe_action",
    "blocked_operations",
]


@dataclass(frozen=True)
class RksRuntimeRow:
    scenario: str
    label: str
    rks_path: str
    rks_exists: bool
    static_guard_status: str
    existing_status_gate_evidence: str
    existing_status_gate_exists: bool
    existing_status_gate_status: str
    intended_scope: str
    required_next_gate: str
    requires_rk10_evidence: bool
    evidence_folder: str
    status: str
    hard_stops: str


@dataclass(frozen=True)
class RksRuntimeFocusRow:
    scenario: str
    status: str
    intended_scope: str
    rks_path: str
    evidence_folder: str
    known_confirmed_scope: str
    known_evidence_path: str
    required_next_gate: str
    missing_fields: str
    remaining_operator_fields: str
    next_safe_action: str
    blocked_operations: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"static RKS audit JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def deferred_runtime_status(required_next_gate: str) -> str:
    normalized_next_gate = required_next_gate.lower()
    for marker, status in DEFERRED_RUNTIME_NEXT_GATE_PATTERNS:
        if marker.lower() in normalized_next_gate:
            return status
    return ""


def build_row(source: dict[str, Any], final_evidence_dir: Path) -> RksRuntimeRow:
    scenario = str(source.get("scenario", ""))
    rks_path = str(source.get("rks_path", ""))
    static_status = str(source.get("static_guard_status", ""))
    rks_exists = bool(source.get("rks_exists", False))
    required_next_gate = str(source.get("required_next_gate", ""))
    deferred_status = deferred_runtime_status(required_next_gate)
    existing_status_gate = str(source.get("existing_status_gate_status", ""))
    requires_rk10 = bool(rks_path) and rks_exists and static_status == "OK_CANDIDATE"
    if not rks_path:
        status = "NO_PRIMARY_RKS"
    elif not rks_exists:
        status = "RKS_FILE_MISSING"
    elif static_status != "OK_CANDIDATE":
        status = "STATIC_GUARD_NOT_OK"
    elif existing_status_gate == "NG":
        status = "EXISTING_STATUS_GATE_NG_REGENERATE_OR_ENTRY_DECISION"
        requires_rk10 = False
    elif deferred_status:
        status = deferred_status
        requires_rk10 = False
    else:
        status = "WAITING_OPERATOR_RK10_EVIDENCE"
    scenario_folder = final_evidence_dir / safe_folder_name(scenario)
    return RksRuntimeRow(
        scenario=scenario,
        label=str(source.get("label", "")),
        rks_path=rks_path,
        rks_exists=rks_exists,
        static_guard_status=static_status,
        existing_status_gate_evidence=str(source.get("existing_status_gate_evidence", "")),
        existing_status_gate_exists=bool(source.get("existing_status_gate_exists", False)),
        existing_status_gate_status=existing_status_gate,
        intended_scope=str(source.get("intended_scope", "")),
        required_next_gate=required_next_gate,
        requires_rk10_evidence=requires_rk10,
        evidence_folder=str(scenario_folder),
        status=status,
        hard_stops=HARD_STOPS,
    )


def safe_folder_name(value: str) -> str:
    return (
        value.replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )


def build_rows(static_payload: dict[str, Any], final_evidence_dir: Path) -> list[RksRuntimeRow]:
    source_rows = static_payload.get("rows", [])
    if not isinstance(source_rows, list):
        raise TypeError("static audit rows must be a list")
    return [
        build_row(row, final_evidence_dir)
        for row in source_rows
        if isinstance(row, dict)
    ]


def build_payload(static_audit_json: Path, out_dir: Path, bundle_pack_dir: Path) -> dict[str, Any]:
    static_payload = read_json(static_audit_json)
    final_evidence_dir = bundle_pack_dir / "final_evidence" / "rks_runtime"
    rows = build_rows(static_payload, final_evidence_dir)
    evidence_required_count = sum(1 for row in rows if row.requires_rk10_evidence)
    missing_rks_count = sum(1 for row in rows if row.status == "RKS_FILE_MISSING")
    no_primary_count = sum(1 for row in rows if row.status == "NO_PRIMARY_RKS")
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "overall_rks_runtime_complete": False,
        "safety": (
            "operator evidence sheet generation only; no RK10 editor/build/runtime, "
            "no ButtonRun, no production write"
        ),
        "static_audit_json": str(static_audit_json),
        "out_dir": str(out_dir),
        "bundle_pack_dir": str(bundle_pack_dir),
        "intake_csv": str(out_dir / "rks_runtime_operator_intake.csv"),
        "bundle_intake_csv": str(bundle_pack_dir / "rks_runtime_operator_intake.csv"),
        "row_count": len(rows),
        "evidence_required_count": evidence_required_count,
        "missing_rks_count": missing_rks_count,
        "no_primary_count": no_primary_count,
        "ready_to_complete_count": 0,
        "preserved_out_intake_row_count": 0,
        "preserved_bundle_intake_row_count": 0,
        "hard_stops": HARD_STOPS,
        "rows": [asdict(row) for row in rows],
    }


def intake_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("scenario", "")).strip(), str(row.get("rks_path", "")).strip()


def read_existing_intake_fields(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            intake_key(row): {
                field: str(row.get(field, ""))
                for field in OPERATOR_INPUT_COLUMNS
            }
            for row in csv.DictReader(handle)
            if intake_key(row)[0] and intake_key(row)[1]
        }


def has_operator_input(row: dict[str, str]) -> bool:
    return any(str(row.get(field, "")).strip() for field in OPERATOR_INPUT_COLUMNS)


def log_path_exists(value: str) -> bool:
    return bool(value.strip()) and Path(value).exists()


def missing_focus_fields(fields: dict[str, str]) -> list[str]:
    missing: list[str] = []
    if str(fields.get("operator_decision", "")).strip() not in ALLOWED_COMPLETE_DECISIONS:
        missing.append("operator_decision")
    if str(fields.get("rk10_editor_open", "")).strip() != "CONFIRMED":
        missing.append("rk10_editor_open")
    if str(fields.get("rk10_build", "")).strip() != "CONFIRMED":
        missing.append("rk10_build")
    if str(fields.get("runtime_or_safe_stop", "")).strip() != "CONFIRMED":
        missing.append("runtime_or_safe_stop")
    if str(fields.get("latest_log_clean", "")).strip() != "YES":
        missing.append("latest_log_clean")
    if not log_path_exists(str(fields.get("latest_log_path", "")).strip()):
        missing.append("latest_log_path")
    if not str(fields.get("operator_name", "")).strip():
        missing.append("operator_name")
    if not str(fields.get("checked_at", "")).strip():
        missing.append("checked_at")
    if (
        str(fields.get("operator_decision", "")).strip() == "REGENERATE_SAVE_AS_REQUIRED"
        and not log_path_exists(str(fields.get("save_as_path", "")).strip())
    ):
        missing.append("save_as_path")
    return missing


def known_confirmed_scope(row: dict[str, Any]) -> str:
    scenario = str(row.get("scenario", ""))
    status_gate = str(row.get("existing_status_gate_status", ""))
    evidence_path = str(row.get("existing_status_gate_evidence", ""))
    evidence_exists = bool(row.get("existing_status_gate_exists", False))
    if status_gate == "OK_FOR_SAFE_STOP_TEST" and evidence_exists:
        return "rk10_editor_open, rk10_build, runtime_safe_stop, latest_clean_log"
    if scenario == "57" and evidence_path and evidence_exists:
        return "rk10_editor_open, rk10_build_artifact_only"
    return ""


def remaining_operator_fields(missing_fields: list[str], known_scope: str) -> str:
    remaining = list(missing_fields)
    if "rk10_editor_open" in remaining and "rk10_editor_open" in known_scope:
        remaining.remove("rk10_editor_open")
    if "rk10_build" in remaining and (
        "rk10_build" in known_scope or "rk10_build_artifact_only" in known_scope
    ):
        remaining.remove("rk10_build")
    return ", ".join(remaining)


def next_safe_action(row: dict[str, Any]) -> str:
    scenario = str(row.get("scenario", ""))
    if scenario == "57":
        return (
            "RK10 Editor open/build確認後、no-mail/no-upload/no-write safe-stopで実行し、"
            "latest clean logをevidence folderへ保存"
        )
    if scenario == "58":
        return (
            "支払日と対象区分を確認してRK10 Editor open/build確認後、"
            "no-mail/no-write safe-stopで実行し、latest clean logを保存"
        )
    return (
        "RK10 Editor open/build確認後、runtime/safe-stopとlatest clean logを"
        "evidence folderへ保存"
    )


def blocked_operations(row: dict[str, Any]) -> str:
    scenario = str(row.get("scenario", ""))
    if scenario == "57":
        return "MainSV確定書込; メール実送信; 本番TXT確定出力; RK10 ButtonRun"
    if scenario == "58":
        return "MainSV本番TXT書込; 保存通知メール送信; RK10 ButtonRun"
    return HARD_STOPS


def build_focus_rows(
    rows: list[dict[str, Any]],
    existing_fields: dict[tuple[str, str], dict[str, str]],
) -> list[RksRuntimeFocusRow]:
    focus_rows: list[RksRuntimeFocusRow] = []
    for row in rows:
        if not bool(row.get("requires_rk10_evidence")):
            continue
        fields = existing_fields.get(intake_key(row), {})
        missing_fields = missing_focus_fields(fields)
        if not missing_fields:
            continue
        known_scope = known_confirmed_scope(row)
        focus_rows.append(
            RksRuntimeFocusRow(
                scenario=str(row.get("scenario", "")),
                status=str(row.get("status", "")),
                intended_scope=str(row.get("intended_scope", "")),
                rks_path=str(row.get("rks_path", "")),
                evidence_folder=str(row.get("evidence_folder", "")),
                known_confirmed_scope=known_scope,
                known_evidence_path=str(row.get("existing_status_gate_evidence", "")),
                required_next_gate=str(row.get("required_next_gate", "")),
                missing_fields=", ".join(missing_fields),
                remaining_operator_fields=remaining_operator_fields(missing_fields, known_scope),
                next_safe_action=next_safe_action(row),
                blocked_operations=blocked_operations(row),
            )
        )
    return focus_rows


def write_focus_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FOCUS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_intake_csv(
    path: Path,
    rows: list[dict[str, Any]],
    existing_fields: dict[tuple[str, str], dict[str, str]] | None = None,
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    preserved_count = 0
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for row in rows:
            preserved = (existing_fields or {}).get(intake_key(row), {})
            if has_operator_input(preserved):
                preserved_count += 1
            writer.writerow(
                {
                    "scenario": row["scenario"],
                    "rks_path": row["rks_path"],
                    **{
                        field: preserved.get(field, "")
                        for field in OPERATOR_INPUT_COLUMNS
                    },
                }
            )
    return preserved_count


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# RK10 RKS Runtime Operator Pack 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- overall_rks_runtime_complete: `{payload['overall_rks_runtime_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- evidence_required_count: `{payload['evidence_required_count']}`",
        f"- missing_rks_count: `{payload['missing_rks_count']}`",
        f"- no_primary_count: `{payload['no_primary_count']}`",
        f"- intake_csv: `{payload['intake_csv']}`",
        f"- bundle_intake_csv: `{payload['bundle_intake_csv']}`",
        f"- current_focus_count: `{payload.get('current_focus_count', 0)}`",
        f"- current_focus_csv: `{payload.get('current_focus_csv', '')}`",
        f"- bundle_focus_csv: `{payload.get('bundle_focus_csv', '')}`",
        f"- hard_stops: `{payload['hard_stops']}`",
        "",
        "## 判定ルール",
        "",
        "- `OK_CANDIDATE` は静的構造候補であり、RK10実行OKではない。",
        "- 完了にはRK10 Editor open、RK10 build、runtime/safe-stop、latest clean logが必要。",
        "- 38のように既存RKSがNGの場合、ZIP直接修正ではなくRK10 Editor Save Asで別名再生成する。",
        "- 業務前提条件待ち・入口選定待ちの行はRKS実行OKではなく、前提条件完了後に再生成してruntime対象に戻す。",
        "- `ButtonRun`、本番書込、実メール、実印刷、最終申請はこのパックでは禁止。",
        "- 再生成時は既存CSVの操作者入力欄を保持する。RKSパスが変わった行は安全のため保持しない。",
        "- `Focused Current Runtime Evidence Rows` は入力漏れ防止の誘導欄であり、最終OK判定は validator のみで行う。",
        "- `known_confirmed_scope` は既存証跡の参照欄であり、runtime/safe-stopやlatest clean logを自動承認しない。",
        "",
        "## Focused Current Runtime Evidence Rows",
        "",
        "| Scenario | Status | Known Confirmed Scope | Missing Fields | Remaining Operator Fields | Next Safe Action | Blocked Operations | Evidence Folder |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in payload.get("current_focus_rows", []):
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    str(row["status"]).replace("|", "/"),
                    str(row["known_confirmed_scope"]).replace("|", "/") or "-",
                    str(row["missing_fields"]).replace("|", "/"),
                    str(row["remaining_operator_fields"]).replace("|", "/") or "-",
                    str(row["next_safe_action"]).replace("|", "/"),
                    str(row["blocked_operations"]).replace("|", "/"),
                    f"`{row['evidence_folder']}`",
                ]
            )
            + " |"
        )
    if not payload.get("current_focus_rows", []):
        lines.append("| - | - | - | - | - | 現在の入力漏れ誘導行はありません。validatorで最終確認してください。 | - | - |")
    lines.extend(
        [
            "",
            "## Operator Intake",
            "",
            "| Scenario | Status | Scope | Existing Gate | RKS Exists | Evidence Folder | Required Next Gate |",
            "|---|---|---|---|---:|---|---|",
        ]
    )
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    str(row["status"]).replace("|", "/"),
                    str(row["intended_scope"]).replace("|", "/"),
                    str(row["existing_status_gate_status"]).replace("|", "/"),
                    "YES" if row["rks_exists"] else "NO",
                    f"`{row['evidence_folder']}`",
                    str(row["required_next_gate"]).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Evidence Columns",
            "",
            "- `operator_decision`: `OPEN_BUILD_ONLY`, `SAFE_STOP_ONLY`, `NOT_RKS_ENTRY`, `REGENERATE_SAVE_AS_REQUIRED` のいずれか。",
            "- `rk10_editor_open`: `CONFIRMED` / `NG` / `UNCONFIRMED`。",
            "- `rk10_build`: `CONFIRMED` / `NG` / `UNCONFIRMED`。",
            "- `runtime_or_safe_stop`: `CONFIRMED` / `NG` / `UNCONFIRMED`。",
            "- `latest_log_clean`: `YES` / `NO`。",
            "- `latest_log_path`: clean logまたはエラーログの実在フルパス。",
            "- `save_as_path`: Save As再生成した場合の別名RKSフルパス。",
            "",
        ]
    )
    return "\n".join(lines)


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path, bundle_pack_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_pack_dir.mkdir(parents=True, exist_ok=True)
    rows = payload["rows"]
    assert isinstance(rows, list)
    json_path = out_dir / "rks_runtime_operator_pack.json"
    md_path = out_dir / "rks_runtime_operator_pack.md"
    csv_path = out_dir / "rks_runtime_operator_intake.csv"
    focus_csv_path = out_dir / "rks_runtime_operator_focus.csv"
    bundle_csv_path = bundle_pack_dir / "rks_runtime_operator_intake.csv"
    bundle_focus_csv_path = bundle_pack_dir / "rks_runtime_operator_focus.csv"
    out_existing = read_existing_intake_fields(csv_path)
    bundle_existing = read_existing_intake_fields(bundle_csv_path)
    focus_rows = build_focus_rows(rows, bundle_existing)
    focus_row_dicts = [asdict(row) for row in focus_rows]
    payload["current_focus_count"] = len(focus_rows)
    payload["current_focus_csv"] = str(focus_csv_path)
    payload["bundle_focus_csv"] = str(bundle_focus_csv_path)
    payload["current_focus_rows"] = focus_row_dicts
    write_focus_csv(focus_csv_path, focus_row_dicts)
    write_focus_csv(bundle_focus_csv_path, focus_row_dicts)
    payload["preserved_out_intake_row_count"] = write_intake_csv(csv_path, rows, out_existing)
    payload["preserved_bundle_intake_row_count"] = write_intake_csv(bundle_csv_path, rows, bundle_existing)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload) + "\n", encoding="utf-8")
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RK10 RKS runtime operator pack.")
    parser.add_argument("--static-audit-json", type=Path, default=DEFAULT_STATIC_AUDIT_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--bundle-pack-dir", type=Path, default=DEFAULT_BUNDLE_PACK_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.static_audit_json, args.out_dir, args.bundle_pack_dir)
    write_outputs(payload, args.out_dir, args.bundle_pack_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
