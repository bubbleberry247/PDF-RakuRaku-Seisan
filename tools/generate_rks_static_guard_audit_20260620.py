"""Generate a read-only RK10 RKS static guard audit.

This tool reuses the RK10 RKS Safety skill's metadata guard/status wording
helpers. It does not open RK10, build RKS files, execute ButtonRun, send mail,
print, submit, execute payments, call Azure, or write outside this repository.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "rks_static_guard_audit_20260620"
RKS_SAFETY_SCRIPT_DIR = Path(r"C:\Users\masam\.codex\skills\rk10-rks-safety\scripts")

NO_GUI_STATUS_REASON = (
    "static/non-GUI audit only; RK10 editor open/build/runtime/latest clean log "
    "must be supplied by separate operator evidence"
)
STATUS_TOKEN_PATTERN = (
    r"(OK|OK_FOR_SAFE_STOP_TEST|OK_FOR_BUSINESS_WRITE_TEST|"
    r"OK_FOR_OPEN_BUILD_TEST|UNCONFIRMED|NG)"
)


@dataclass(frozen=True)
class RksAuditCandidate:
    scenario: str
    label: str
    rks_path: str
    intended_scope: str
    existing_status_gate_evidence: str
    required_next_gate: str


@dataclass(frozen=True)
class RksAuditRow:
    scenario: str
    label: str
    rks_path: str
    rks_exists: bool
    static_guard_status: str
    file_size: int | None
    program_cs_bytes: int | None
    meta_bytes: int | None
    id_bytes: int | None
    root_meta_bytes: int | None
    version_bytes: int | None
    has_safe_test: bool
    has_show_alert_dialog: bool
    compile_risk_patterns: str
    non_gui_status_gate: str
    non_gui_status_reason: str
    existing_status_gate_evidence: str
    existing_status_gate_exists: bool
    existing_status_gate_status: str
    intended_scope: str
    production_ready: bool
    required_next_gate: str


def load_skill_function(module_filename: str, function_name: str) -> Callable[..., Any]:
    module_path = RKS_SAFETY_SCRIPT_DIR / module_filename
    if not module_path.exists():
        raise FileNotFoundError(f"RKS safety helper not found: {module_path}")
    module_name = module_filename.replace(".py", "")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    function = getattr(module, function_name)
    if not callable(function):
        raise TypeError(f"{function_name} is not callable in {module_path}")
    return function


def default_candidates() -> list[RksAuditCandidate]:
    status_gate_dir = (
        r"C:\ProgramData\RK10\Robots\migration\reports"
        r"\rk10_open_build_safe_stop_status_gate_20260618_1019"
    )
    return [
        RksAuditCandidate(
            "37",
            "status-gate representative v1.1",
            r"C:\ProgramData\RK10\Robots\37レコル公休・有休登録\senario\37レコル公休有休登録_完成版_v1.1.rks",
            "safe-stop",
            status_gate_dir + r"\s37.status_gate.md.numbered",
            "business data target, RecoRu write boundary, latest clean runtime log per scenario",
        ),
        RksAuditCandidate(
            "47",
            "status-gate representative v5",
            r"C:\ProgramData\RK10\Robots\47出退勤確認\senario\４７レコル出退勤_完成版_v5.rks",
            "safe-stop",
            status_gate_dir + r"\s47_v5.status_gate.md.numbered",
            "business data target, mail boundary, latest clean runtime log per scenario",
        ),
        RksAuditCandidate(
            "55",
            "v2 production candidate",
            r"C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\scenario\５５_自動化版_v2.rks",
            "safe-stop",
            status_gate_dir + r"\s55_v2.status_gate.md.numbered",
            "ExcelWriterV2/source-copy row-insert validation with business totals",
        ),
        RksAuditCandidate(
            "63",
            "status-gate representative v7",
            r"C:\ProgramData\RK10\Robots\【63楽楽精算申請（毎月同額支払い分】2026-02-02\scenario\63_楽楽精算申請_毎月同額支払い_本番候補_v7.rks",
            "safe-stop",
            status_gate_dir + r"\s63_v7.status_gate.md.numbered",
            "business target, Rakuraku write boundary, latest clean runtime log per scenario",
        ),
        RksAuditCandidate(
            "38",
            "current primary candidate",
            r"C:\ProgramData\RK10\Robots\38受注登録\senario\scenario_v2026.06.08.1.rks",
            "open-build",
            r"C:\ProgramData\RK10\Robots\migration\reports\s38_local_safe_route_fix_20260619_1103\rks_status_gate.stdout.txt.numbered",
            "RK10 Editor Save As regenerated candidate or Python/BAT entry decision",
        ),
        RksAuditCandidate(
            "42",
            "fixed production file candidate",
            r"C:\ProgramData\RK10\Robots\42ドライブレポート抽出作業\senario\42ドライブレポート_本番.rks",
            "open-build",
            "",
            "choose confirmed entry, then RK10 open/build/runtime/latest clean log",
        ),
        RksAuditCandidate(
            "44",
            "PDF general expense RKS v7",
            r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\scenario\44_PDF一般経費楽楽精算申請_PROD確認_v7_20260530.rks",
            "open-build",
            "",
            "business OK rows, handoff live generation, processed move evidence before RKS",
        ),
        RksAuditCandidate(
            "51/52",
            "Excel-save selected production entry",
            r"C:\ProgramData\RK10\Robots\51&52ソフトバンク部門集計楽楽精算申請\scenario\51&52_ソフトバンク_PROD_担当者選択_合算分離_Excel保存まで_20260608.rks",
            "open-build",
            r"C:\ProgramData\RK10\Robots\migration\reports\prod_files_after_feedback_final_reconfirm_20260618_161709\s51_52_selected_rks_status_gate.txt",
            "RK10 open/build/safe-stop only if operating through the RKS entry",
        ),
        RksAuditCandidate(
            "56",
            "LOCAL save/mail verification candidate",
            r"C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\senario\56_資金繰り表_LOCAL実保存メール_検証候補_v1_20260602.rks",
            "open-build",
            r"C:\ProgramData\RK10\Robots\migration\reports\56_local_rks_verified_20260602_1849.json",
            "current workbook copy/no-write evidence and deployable entry decision",
        ),
        RksAuditCandidate(
            "57",
            "current v2 local save/mail candidate",
            r"C:\ProgramData\RK10\Robots\【57基幹システムより仕訳はきだし】\scenario\57_入金仕訳吐き出し_LOCAL実保存メール_検証候補_v2_20260602.rks",
            "open-build",
            r"C:\ProgramData\RK10\Robots\migration\reports\s57_current_rks_editor_open_build_probe_20260618_103111\summary.tsv.numbered",
            "no-mail/no-upload/no-write runtime safe-stop and latest clean log",
        ),
        RksAuditCandidate(
            "58",
            "payment extract launch RKS v1",
            r"C:\ProgramData\RK10\Robots\【58基幹システムより査定支払い分はきだし（25日・末日】2026-01-27\scenario\58_査定支払い分はきだし_起動用RKS_v1.rks",
            "open-build",
            "",
            "operator-select, real date/category, no-mail/no-write runtime evidence",
        ),
        RksAuditCandidate(
            "70",
            "payment confirmation launch RKS v1",
            r"C:\ProgramData\RK10\Robots\70楽楽精算支払い確定\scenario\70_楽楽精算支払い確定_起動用RKS_v1.rks",
            "open-build",
            "",
            "payment approval before RKS runtime; confirm-preview, expected count/amount, bank evidence, approver",
        ),
        RksAuditCandidate(
            "71",
            "Azure OCR wrapper v3",
            r"C:\ProgramData\RK10\Robots\【71法定調書用　士業請求書集計】2026-01-28\scenario\71_法定調書用_士業請求書集計_AzureOCRラッパー_v3.rks",
            "open-build",
            "",
            "Azure OCR gate before RKS runtime; endpoint/key, budget approval, paid OCR smoke with workbook copy",
        ),
        RksAuditCandidate(
            "12/13",
            "Python/Outlook COM flow only",
            "",
            "n/a",
            "",
            "no primary RKS; restore Outlook COM then dry-run/no-print/no-mail",
        ),
    ]


def parse_existing_status_gate(path_text: str) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    final_status = re.search(r"Final status:\s*`([^`]+)`", text)
    if final_status:
        return final_status.group(1)
    first_tab_status = re.search(
        rf"^\s*\d*:\s*{STATUS_TOKEN_PATTERN}\t",
        text,
        flags=re.MULTILINE,
    )
    if first_tab_status:
        return first_tab_status.group(1)
    bare_status = re.search(rf"^{STATUS_TOKEN_PATTERN}\t", text, flags=re.MULTILINE)
    if bare_status:
        return bare_status.group(1)
    return ""


def to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def inspect_candidate(
    candidate: RksAuditCandidate,
    inspect_rks: Callable[[Path], dict[str, Any]],
    decide: Callable[[str, str, str, str, str, str], tuple[str, str]],
) -> RksAuditRow:
    if not candidate.rks_path:
        return RksAuditRow(
            scenario=candidate.scenario,
            label=candidate.label,
            rks_path="",
            rks_exists=False,
            static_guard_status="N_A_NO_PRIMARY_RKS",
            file_size=None,
            program_cs_bytes=None,
            meta_bytes=None,
            id_bytes=None,
            root_meta_bytes=None,
            version_bytes=None,
            has_safe_test=False,
            has_show_alert_dialog=False,
            compile_risk_patterns="",
            non_gui_status_gate="N_A_NO_PRIMARY_RKS",
            non_gui_status_reason=NO_GUI_STATUS_REASON,
            existing_status_gate_evidence=candidate.existing_status_gate_evidence,
            existing_status_gate_exists=False,
            existing_status_gate_status="",
            intended_scope=candidate.intended_scope,
            production_ready=False,
            required_next_gate=candidate.required_next_gate,
        )

    rks_path = Path(candidate.rks_path)
    existing_evidence = Path(candidate.existing_status_gate_evidence) if candidate.existing_status_gate_evidence else None
    if not rks_path.exists():
        static_guard_status = "MISSING_RKS"
        status_gate, reason = "NG", f"target not found: {rks_path}"
        guard: dict[str, Any] = {}
    else:
        guard = inspect_rks(rks_path)
        static_guard_status = str(guard["status"])
        status_gate, reason = decide(
            static_guard_status,
            "unconfirmed",
            "unconfirmed",
            "unconfirmed",
            "none",
            "open-build" if candidate.intended_scope == "n/a" else candidate.intended_scope,
        )

    return RksAuditRow(
        scenario=candidate.scenario,
        label=candidate.label,
        rks_path=candidate.rks_path,
        rks_exists=rks_path.exists(),
        static_guard_status=static_guard_status,
        file_size=to_int(guard.get("file_size")),
        program_cs_bytes=to_int(guard.get("Program.cs")),
        meta_bytes=to_int(guard.get("meta")),
        id_bytes=to_int(guard.get("id")),
        root_meta_bytes=to_int(guard.get("rootMeta")),
        version_bytes=to_int(guard.get("version")),
        has_safe_test=bool(guard.get("has_safe_test")),
        has_show_alert_dialog=bool(guard.get("has_show_alert_dialog")),
        compile_risk_patterns=str(guard.get("compile_risk_patterns") or ""),
        non_gui_status_gate=status_gate,
        non_gui_status_reason=reason,
        existing_status_gate_evidence=candidate.existing_status_gate_evidence,
        existing_status_gate_exists=existing_evidence.exists() if existing_evidence else False,
        existing_status_gate_status=parse_existing_status_gate(candidate.existing_status_gate_evidence),
        intended_scope=candidate.intended_scope,
        production_ready=False,
        required_next_gate=candidate.required_next_gate,
    )


def build_rows(candidates: list[RksAuditCandidate] | None = None) -> list[RksAuditRow]:
    inspect_rks = load_skill_function("rks_metadata_guard.py", "inspect_rks")
    decide = load_skill_function("rks_status_gate.py", "decide")
    selected = default_candidates() if candidates is None else candidates
    return [inspect_candidate(candidate, inspect_rks, decide) for candidate in selected]


def build_payload(candidates: list[RksAuditCandidate] | None = None) -> dict[str, object]:
    generated_at = datetime.now().isoformat(timespec="seconds")
    rows = build_rows(candidates)
    existing_rows = [row for row in rows if row.rks_exists]
    ok_candidates = [row for row in rows if row.static_guard_status == "OK_CANDIDATE"]
    risky_rows = [
        row
        for row in rows
        if row.static_guard_status
        not in {
            "OK_CANDIDATE",
            "N_A_NO_PRIMARY_RKS",
        }
    ]
    safe_stop_evidence_rows = [
        row
        for row in rows
        if row.existing_status_gate_status == "OK_FOR_SAFE_STOP_TEST"
    ]
    return {
        "generated_at": generated_at,
        "safety": (
            "read-only static RKS metadata guard audit; no RK10 editor/build/runtime, "
            "no ButtonRun, no business writes"
        ),
        "candidate_count": len(rows),
        "existing_rks_count": len(existing_rows),
        "ok_candidate_count": len(ok_candidates),
        "risk_or_missing_count": len(risky_rows),
        "safe_stop_evidence_count": len(safe_stop_evidence_rows),
        "production_ready_count": 0,
        "overall_production_ready": False,
        "rows": [asdict(row) for row in rows],
    }


def csv_fields() -> list[str]:
    return [
        "scenario",
        "label",
        "rks_path",
        "rks_exists",
        "static_guard_status",
        "file_size",
        "program_cs_bytes",
        "meta_bytes",
        "id_bytes",
        "root_meta_bytes",
        "version_bytes",
        "has_safe_test",
        "has_show_alert_dialog",
        "compile_risk_patterns",
        "non_gui_status_gate",
        "non_gui_status_reason",
        "existing_status_gate_evidence",
        "existing_status_gate_exists",
        "existing_status_gate_status",
        "intended_scope",
        "production_ready",
        "required_next_gate",
    ]


def build_markdown(payload: dict[str, object]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# RKS Static Guard Audit 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- safety: `{payload['safety']}`",
        f"- candidate_count: `{payload['candidate_count']}`",
        f"- existing_rks_count: `{payload['existing_rks_count']}`",
        f"- ok_candidate_count: `{payload['ok_candidate_count']}`",
        f"- risk_or_missing_count: `{payload['risk_or_missing_count']}`",
        f"- safe_stop_evidence_count: `{payload['safe_stop_evidence_count']}`",
        f"- production_ready_count: `{payload['production_ready_count']}`",
        f"- overall_production_ready: `{payload['overall_production_ready']}`",
        "",
        "## Meaning",
        "",
        "- `OK_CANDIDATE` is only the RK10 package structure guard result.",
        "- This audit does not prove RK10 Editor open, RK10 build, runtime/safe-stop, or production readiness.",
        "- `existing_status_gate_status` is previously saved operator evidence when a status-gate report is present.",
        "",
        "## Audit Rows",
        "",
        "| Scenario | Static Guard | Non-GUI Gate | Existing Status Gate | RKS Exists | Scope | Required Next Gate |",
        "|---|---|---|---|---:|---|---|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    str(row["static_guard_status"]).replace("|", "/"),
                    str(row["non_gui_status_gate"]).replace("|", "/"),
                    str(row["existing_status_gate_status"] or "-").replace("|", "/"),
                    "YES" if row["rks_exists"] else "NO",
                    str(row["intended_scope"]).replace("|", "/"),
                    str(row["required_next_gate"]).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Candidate Paths", ""])
    for row in rows:
        assert isinstance(row, dict)
        path_text = row["rks_path"] or "(no primary RKS)"
        lines.append(f"- {row['scenario']} {row['label']}: `{path_text}`")
    lines.extend(["", "## Existing Status Gate Evidence", ""])
    for row in rows:
        assert isinstance(row, dict)
        evidence = row["existing_status_gate_evidence"] or "(none)"
        exists = "YES" if row["existing_status_gate_exists"] else "NO"
        status = row["existing_status_gate_status"] or "-"
        lines.append(f"- {row['scenario']}: exists={exists}, status=`{status}`, source=`{evidence}`")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, object], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "rks_static_guard_audit.json"
    md_path = out_dir / "rks_static_guard_audit.md"
    csv_path = out_dir / "rks_static_guard_audit.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=csv_fields())
        writer.writeheader()
        rows = payload["rows"]
        assert isinstance(rows, list)
        writer.writerows(rows)
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "csv": str(csv_path),
    }


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a read-only RKS static guard audit.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
