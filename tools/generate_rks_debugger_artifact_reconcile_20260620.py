"""Reconcile audited RK10 RKS files with existing RK10 Debugger artifacts.

This tool is read-only. It does not open RK10, build RKS files, execute
ButtonRun, repack RKS ZIPs, send mail, print, submit, run payments, or write
production data. Debugger artifacts are supporting evidence only and never
auto-approve the runtime operator intake.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_STATIC_AUDIT_JSON = (
    ROOT / "plans" / "reports" / "rks_static_guard_audit_20260620" / "rks_static_guard_audit.json"
)
DEFAULT_DEBUGGER_DIR = Path(r"C:\Users\masam\AppData\Local\KEYENCE\RkScenarioManager\Debugger")
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "rks_debugger_artifact_reconcile_20260620"
CSV_COLUMNS = [
    "scenario",
    "rks_path",
    "static_guard_status",
    "rks_program_found",
    "debugger_program_match_count",
    "build_artifact_found",
    "newest_match_program",
    "newest_match_dir",
    "newest_match_mtime",
    "build_artifact_paths",
    "supporting_scope",
    "operator_auto_approval",
    "note",
]
BUILD_ARTIFACT_RELATIVE_PATHS = (
    Path("obj") / "Debug" / "net8.0-windows" / "Temp.dll",
    Path("obj") / "Debug" / "net8.0-windows" / "Temp.pdb",
    Path("obj") / "Debug" / "net8.0-windows" / "apphost.exe",
    Path("bin") / "Debug" / "net8.0-windows" / "Temp.dll",
    Path("bin") / "Debug" / "net8.0-windows" / "Temp.exe",
    Path("bin") / "Debug" / "net8.0-windows" / "apphost.exe",
)


@dataclass(frozen=True)
class ProgramSignature:
    raw_sha256: str
    normalized_sha256: str
    byte_count: int


@dataclass(frozen=True)
class DebuggerProgram:
    program_path: str
    match_dir: str
    signature: ProgramSignature
    modified_at: str
    modified_timestamp: float
    build_artifact_paths: tuple[str, ...]


@dataclass(frozen=True)
class ReconcileRow:
    scenario: str
    rks_path: str
    static_guard_status: str
    rks_exists: bool
    rks_program_found: bool
    rks_program_sha256: str
    rks_program_normalized_sha256: str
    rks_program_bytes: int
    debugger_program_match_count: int
    build_artifact_found: bool
    newest_match_program: str
    newest_match_dir: str
    newest_match_mtime: str
    build_artifact_paths: str
    supporting_scope: str
    operator_auto_approval: str
    note: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"static audit JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_program_bytes(data: bytes) -> bytes:
    text = data.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
    return text.encode("utf-8")


def build_signature(data: bytes) -> ProgramSignature:
    return ProgramSignature(
        raw_sha256=hashlib.sha256(data).hexdigest(),
        normalized_sha256=hashlib.sha256(normalized_program_bytes(data)).hexdigest(),
        byte_count=len(data),
    )


def read_rks_program_signature(path: Path) -> ProgramSignature | None:
    if not path.exists():
        return None
    try:
        with zipfile.ZipFile(path) as archive:
            program_names = [name for name in archive.namelist() if name.endswith("Program.cs")]
            if not program_names:
                return None
            return build_signature(archive.read(program_names[0]))
    except (OSError, zipfile.BadZipFile):
        return None


def iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def find_build_artifacts(temp_dir: Path) -> tuple[str, ...]:
    paths = [
        str(temp_dir / relative_path)
        for relative_path in BUILD_ARTIFACT_RELATIVE_PATHS
        if (temp_dir / relative_path).exists()
    ]
    return tuple(paths)


def scan_debugger_programs(debugger_dir: Path) -> list[DebuggerProgram]:
    if not debugger_dir.exists():
        return []
    programs: list[DebuggerProgram] = []
    for program_path in debugger_dir.glob("*/Temp/Program.cs"):
        try:
            data = program_path.read_bytes()
            modified_timestamp = program_path.stat().st_mtime
        except OSError:
            continue
        temp_dir = program_path.parent
        programs.append(
            DebuggerProgram(
                program_path=str(program_path),
                match_dir=str(temp_dir.parent),
                signature=build_signature(data),
                modified_at=iso_from_timestamp(modified_timestamp),
                modified_timestamp=modified_timestamp,
                build_artifact_paths=find_build_artifacts(temp_dir),
            )
        )
    return sorted(programs, key=lambda item: item.modified_timestamp, reverse=True)


def build_row(source: dict[str, Any], debugger_programs: list[DebuggerProgram]) -> ReconcileRow:
    scenario = str(source.get("scenario", ""))
    rks_path_text = str(source.get("rks_path", ""))
    static_guard_status = str(source.get("static_guard_status", ""))
    rks_path = Path(rks_path_text) if rks_path_text else Path()
    signature = read_rks_program_signature(rks_path) if rks_path_text else None
    matches = [
        program
        for program in debugger_programs
        if signature is not None
        and program.signature.normalized_sha256 == signature.normalized_sha256
    ]
    build_artifact_paths = sorted(
        {
            artifact_path
            for program in matches
            for artifact_path in program.build_artifact_paths
        }
    )
    newest_match = matches[0] if matches else None
    if not rks_path_text:
        note = "No primary RKS; not applicable."
    elif signature is None:
        note = "RKS Program.cs could not be read; no debugger reconciliation possible."
    elif not matches:
        note = "No matching Debugger Program.cs found for this audited RKS Program.cs."
    elif build_artifact_paths:
        note = "Matching Debugger Program.cs and build artifacts found; supporting evidence only."
    else:
        note = "Matching Debugger Program.cs found, but build artifacts were not found."
    supporting_scope = (
        "debugger_program_match, build_artifact_present"
        if build_artifact_paths
        else "debugger_program_match_only"
        if matches
        else ""
    )
    return ReconcileRow(
        scenario=scenario,
        rks_path=rks_path_text,
        static_guard_status=static_guard_status,
        rks_exists=bool(rks_path_text) and rks_path.exists(),
        rks_program_found=signature is not None,
        rks_program_sha256=signature.raw_sha256 if signature else "",
        rks_program_normalized_sha256=signature.normalized_sha256 if signature else "",
        rks_program_bytes=signature.byte_count if signature else 0,
        debugger_program_match_count=len(matches),
        build_artifact_found=bool(build_artifact_paths),
        newest_match_program=newest_match.program_path if newest_match else "",
        newest_match_dir=newest_match.match_dir if newest_match else "",
        newest_match_mtime=newest_match.modified_at if newest_match else "",
        build_artifact_paths="; ".join(build_artifact_paths),
        supporting_scope=supporting_scope,
        operator_auto_approval="NO",
        note=note,
    )


def build_payload(
    static_audit_json: Path,
    debugger_dir: Path,
    out_dir: Path,
) -> dict[str, Any]:
    static_payload = read_json(static_audit_json)
    source_rows = static_payload.get("rows", [])
    if not isinstance(source_rows, list):
        raise TypeError("static audit rows must be a list")
    debugger_programs = scan_debugger_programs(debugger_dir)
    rows = [
        build_row(row, debugger_programs)
        for row in source_rows
        if isinstance(row, dict)
    ]
    matched_rows = [row for row in rows if row.debugger_program_match_count > 0]
    artifact_rows = [row for row in rows if row.build_artifact_found]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": (
            "read-only debugger artifact reconciliation; no RK10 editor/build/runtime, "
            "no ButtonRun, no RKS repack, no production write"
        ),
        "static_audit_json": str(static_audit_json),
        "debugger_dir": str(debugger_dir),
        "debugger_dir_exists": debugger_dir.exists(),
        "out_dir": str(out_dir),
        "debugger_program_count": len(debugger_programs),
        "row_count": len(rows),
        "debugger_program_matched_row_count": len(matched_rows),
        "build_artifact_matched_row_count": len(artifact_rows),
        "operator_auto_approved_count": 0,
        "overall_rks_runtime_complete": False,
        "rows": [asdict(row) for row in rows],
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in CSV_COLUMNS})


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# RK10 Debugger Artifact Reconcile 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- safety: `{payload['safety']}`",
        f"- static_audit_json: `{payload['static_audit_json']}`",
        f"- debugger_dir: `{payload['debugger_dir']}`",
        f"- debugger_dir_exists: `{payload['debugger_dir_exists']}`",
        f"- debugger_program_count: `{payload['debugger_program_count']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- debugger_program_matched_row_count: `{payload['debugger_program_matched_row_count']}`",
        f"- build_artifact_matched_row_count: `{payload['build_artifact_matched_row_count']}`",
        f"- operator_auto_approved_count: `{payload['operator_auto_approved_count']}`",
        f"- overall_rks_runtime_complete: `{payload['overall_rks_runtime_complete']}`",
        "",
        "## 判定ルール",
        "",
        "- この照合は既存Debugger成果物の読み取りだけであり、RK10 Editor open/build/runtimeを新規実行しない。",
        "- `build_artifact_found=True` でも、runtime/safe-stopとlatest clean logは自動承認しない。",
        "- `operator_auto_approval` は常に `NO`。最終判定はRKS runtime intake validatorで行う。",
        "- RKSをZIPとして再パックしたり、Program.csを差し替えたりしない。",
        "",
        "## Rows",
        "",
        "| Scenario | Static Guard | Program Match Count | Build Artifact | Supporting Scope | Auto Approval | Newest Match | Note |",
        "|---|---|---:|---:|---|---|---|---|",
    ]
    for row in payload["rows"]:
        assert isinstance(row, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    str(row["static_guard_status"]).replace("|", "/"),
                    str(row["debugger_program_match_count"]),
                    "YES" if row["build_artifact_found"] else "NO",
                    str(row["supporting_scope"]).replace("|", "/") or "-",
                    str(row["operator_auto_approval"]),
                    f"`{row['newest_match_program']}`" if row["newest_match_program"] else "-",
                    str(row["note"]).replace("|", "/"),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = payload["rows"]
    assert isinstance(rows, list)
    json_path = out_dir / "rks_debugger_artifact_reconcile.json"
    csv_path = out_dir / "rks_debugger_artifact_reconcile.csv"
    md_path = out_dir / "rks_debugger_artifact_reconcile.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, rows)
    md_path.write_text(build_markdown(payload) + "\n", encoding="utf-8")
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile RKS Program.cs with RK10 Debugger artifacts.")
    parser.add_argument("--static-audit-json", type=Path, default=DEFAULT_STATIC_AUDIT_JSON)
    parser.add_argument("--debugger-dir", type=Path, default=DEFAULT_DEBUGGER_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.static_audit_json, args.debugger_dir, args.out_dir)
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
