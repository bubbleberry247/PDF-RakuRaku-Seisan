"""Simulate the post-operator-input gate chain on isolated copies.

This tool proves what happens after the remaining operator stamps are filled,
without writing to source packets, source bundle intakes, RK10, Rakuraku,
mail, print, payment, or paid OCR systems.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import generate_goal_completion_gate_20260620_open_probe_20260622 as completion_gate
import simulate_remaining_operator_input_completion_20260623 as operator_sim
import sync_bundle_evidence_intake_20260620 as bundle_sync
import sync_unified_final_evidence_intake_20260621 as unified_sync
import validate_bundle_evidence_packs_20260620 as bundle_validate


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_OUT_DIR = REPORTS / "remaining_operator_full_gate_simulation_20260623"
SOURCE_PACK_ROOT = REPORTS / "bundle_evidence_packs_20260620"
SOURCE_PACK_JSON = SOURCE_PACK_ROOT / "bundle_evidence_packs.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_intake_paths(pack_json: Path = SOURCE_PACK_JSON) -> list[Path]:
    payload = read_json(pack_json)
    paths = []
    for pack in payload.get("packs", []):
        if isinstance(pack, dict) and str(pack.get("intake_path", "")).strip():
            paths.append(Path(str(pack["intake_path"])))
    return paths


def source_hash_paths() -> list[Path]:
    packet_dir = REPORTS / "goal_execution_packet_20260620"
    return [
        REPORTS
        / "remaining_operator_input_packet_20260623"
        / "remaining_operator_input.csv",
        REPORTS
        / "unified_final_evidence_intake_20260621"
        / "unified_final_evidence_input.csv",
        REPORTS / "bundle_operator_sheet_20260620" / "bundle_operator_sheet.csv",
        SOURCE_PACK_JSON,
        *sorted(packet_dir.glob("*_bundle.csv")),
        *source_intake_paths(),
    ]


def hash_existing_files(paths: list[Path]) -> dict[str, str]:
    return {str(path): hash_file(path) for path in paths if path.exists()}


def replace_bundle_pack_root_text(text: str, work_pack_root: Path) -> str:
    source_root = str(SOURCE_PACK_ROOT)
    target_root = str(work_pack_root)
    return text.replace(source_root, target_root).replace(
        source_root.replace("\\", "\\\\"),
        target_root.replace("\\", "\\\\"),
    )


def remap_bundle_pack_path(path: Path, work_pack_root: Path) -> Path:
    return work_pack_root / path.relative_to(SOURCE_PACK_ROOT)


def copy_text_file_with_remap(source: Path, destination: Path, work_pack_root: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8-sig")
    destination.write_text(
        replace_bundle_pack_root_text(text, work_pack_root),
        encoding="utf-8",
    )


def copy_required_pack_files(pack: dict[str, Any], work_pack_root: Path) -> None:
    text_keys = (
        "manifest_path",
        "checklist_path",
        "intake_path",
        "reference_snapshot_path",
        "filename_template_path",
        "filename_template_markdown_path",
    )
    for key in text_keys:
        source = Path(str(pack.get(key, "")))
        if source.exists() and source.is_file():
            copy_text_file_with_remap(
                source,
                remap_bundle_pack_path(source, work_pack_root),
                work_pack_root,
            )
        numbered_source = Path(f"{source}.numbered")
        if numbered_source.exists() and numbered_source.is_file():
            copy_text_file_with_remap(
                numbered_source,
                remap_bundle_pack_path(numbered_source, work_pack_root),
                work_pack_root,
            )

    final_evidence_dir = Path(str(pack.get("final_evidence_dir", "")))
    if final_evidence_dir.exists() and final_evidence_dir.is_dir():
        shutil.copytree(
            final_evidence_dir,
            remap_bundle_pack_path(final_evidence_dir, work_pack_root),
            dirs_exist_ok=True,
        )


def copy_and_remap_bundle_pack(out_dir: Path) -> Path:
    work_pack_root = out_dir / "p"
    work_pack_root.mkdir(parents=True, exist_ok=True)
    source_payload = read_json(SOURCE_PACK_JSON)
    for pack in source_payload.get("packs", []):
        if isinstance(pack, dict):
            copy_required_pack_files(pack, work_pack_root)
    work_pack_json = work_pack_root / "bundle_evidence_packs.json"
    copy_text_file_with_remap(SOURCE_PACK_JSON, work_pack_json, work_pack_root)
    return work_pack_json


def write_json_and_markdown(
    payload: dict[str, Any],
    out_dir: Path,
    json_name: str,
    md_name: str,
    markdown: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / json_name
    md_path = out_dir / md_name
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)


def gate_names(payload: dict[str, Any], passed: bool) -> list[str]:
    return [
        str(gate.get("gate", ""))
        for gate in payload.get("gates", [])
        if isinstance(gate, dict) and bool(gate.get("passed")) is passed
    ]


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Remaining Operator Full Gate Simulation 2026-06-23",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- full_chain_simulation_passed: `{payload['full_chain_simulation_passed']}`",
        f"- source_files_modified: `{payload['source_files_modified']}`",
        f"- production_completion_scope: `{payload['production_completion_scope']}`",
        f"- operator_completion_passed: `{payload['operator_completion_passed']}`",
        f"- unified_updated_intake_count: `{payload['unified_updated_intake_count']}`",
        f"- bundle_ready_to_sync_count: `{payload['bundle_ready_to_sync_count']}/{payload['bundle_count']}`",
        f"- bundle_final_evidence_ready_count: `{payload['bundle_final_evidence_ready_count']}/{payload['bundle_count']}`",
        f"- simulated_gate_final_goal_complete: `{payload['simulated_gate_final_goal_complete']}`",
        f"- simulated_gate_progress: `{payload['simulated_gate_passed_count']}/{payload['simulated_gate_count']}`",
        f"- simulated_blocking_gate_count: `{payload['simulated_blocking_gate_count']}`",
        "",
        "## Boundary",
        "",
        "- This is an isolated-copy simulation using sample operator stamps.",
        "- It does not replace actual customer/operator approval.",
        "- It does not edit source CSVs or execute RK10 ButtonRun, production writes, mail, print, final submit, payment, paid Azure OCR, or Rakuraku data creation/deletion.",
        "",
        "## Simulated Blocking Gates",
        "",
    ]
    for gate in payload["simulated_blocking_gates"]:
        lines.append(f"- `{gate}`")
    lines.extend(
        [
            "",
            "## Key Reports",
            "",
            f"- operator_completion_report: `{payload['operator_completion_report']}`",
            f"- unified_sync_report: `{payload['unified_sync_report']}`",
            f"- bundle_sync_report: `{payload['bundle_sync_report']}`",
            f"- bundle_validation_report: `{payload['bundle_validation_report']}`",
            f"- simulated_gate_report: `{payload['simulated_gate_report']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def build_payload(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source_hashes_before = hash_existing_files(source_hash_paths())

    operator_out_dir = out_dir / "op"
    operator_payload = operator_sim.build_payload(out_dir=operator_out_dir)
    operator_sim.write_outputs(operator_payload, operator_out_dir)
    work_reports = Path(str(operator_payload["work_reports_dir"]))
    work_pack_json = copy_and_remap_bundle_pack(out_dir)
    work_unified_csv = (
        work_reports
        / "unified_final_evidence_intake_20260621"
        / "unified_final_evidence_input.csv"
    )
    work_bundle_sheet = work_reports / "bundle_operator_sheet_20260620" / "bundle_operator_sheet.csv"

    unified_payload = unified_sync.build_payload(
        work_pack_json,
        work_unified_csv,
        apply_updates=True,
    )
    unified_out_dir = out_dir / "unified_sync"
    unified_sync.write_outputs(unified_payload, unified_out_dir)

    bundle_sync_payload = bundle_sync.build_payload(
        work_pack_json,
        work_bundle_sheet,
        apply_updates=True,
    )
    bundle_sync_out_dir = out_dir / "bundle_sync"
    bundle_sync.write_outputs(bundle_sync_payload, bundle_sync_out_dir)

    bundle_validation_payload = bundle_validate.build_payload(
        work_pack_json,
        work_bundle_sheet,
        bundle_sync_out_dir / "bundle_evidence_intake_sync.json",
    )
    bundle_validation_out_dir = out_dir / "bundle_validation"
    bundle_validate.write_outputs(bundle_validation_payload, bundle_validation_out_dir)

    gate_sources = dict(completion_gate.DEFAULT_SOURCES)
    gate_sources["packet_validation"] = (
        operator_out_dir / "validation" / "goal_execution_packet_validation.json"
    )
    gate_sources["bundle_evidence_pack_validation"] = (
        bundle_validation_out_dir / "bundle_evidence_pack_validation.json"
    )
    simulated_gate_payload = completion_gate.build_payload(gate_sources)
    gate_out_dir = out_dir / "completion_gate"
    write_json_and_markdown(
        simulated_gate_payload,
        gate_out_dir,
        "goal_completion_gate.json",
        "goal_completion_gate.md",
        completion_gate.build_markdown(simulated_gate_payload),
    )

    source_hashes_after = hash_existing_files(source_hash_paths())
    source_files_modified = source_hashes_before != source_hashes_after
    bundle_count = int(bundle_sync_payload.get("bundle_count", 0) or 0)
    bundle_ready_count = int(bundle_sync_payload.get("ready_to_sync_count", 0) or 0)
    bundle_final_ready_count = int(
        bundle_validation_payload.get("final_evidence_ready_count", 0) or 0
    )
    full_chain_simulation_passed = (
        operator_payload.get("simulation_passed") is True
        and int(unified_payload.get("updated_intake_count", 0) or 0) > 0
        and bundle_count > 0
        and bundle_ready_count == bundle_count
        and bundle_final_ready_count == bundle_count
        and simulated_gate_payload.get("final_goal_complete") is True
        and not source_files_modified
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "full_chain_simulation_passed": full_chain_simulation_passed,
        "source_files_modified": source_files_modified,
        "production_completion_scope": "SIMULATION_ONLY_NOT_ACTUAL_APPROVAL",
        "operator_completion_passed": operator_payload.get("simulation_passed") is True,
        "operator_sample_completed_row_count": operator_payload.get(
            "sample_completed_row_count", 0
        ),
        "unified_updated_intake_count": int(
            unified_payload.get("updated_intake_count", 0) or 0
        ),
        "unified_updated_field_count": int(
            unified_payload.get("updated_field_count", 0) or 0
        ),
        "bundle_count": bundle_count,
        "bundle_ready_to_sync_count": bundle_ready_count,
        "bundle_updated_bundle_count": int(
            bundle_sync_payload.get("updated_bundle_count", 0) or 0
        ),
        "bundle_final_evidence_ready_count": bundle_final_ready_count,
        "simulated_gate_final_goal_complete": simulated_gate_payload.get(
            "final_goal_complete"
        )
        is True,
        "simulated_gate_count": int(simulated_gate_payload.get("gate_count", 0) or 0),
        "simulated_gate_passed_count": int(
            simulated_gate_payload.get("passed_gate_count", 0) or 0
        ),
        "simulated_blocking_gate_count": int(
            simulated_gate_payload.get("blocking_gate_count", 0) or 0
        ),
        "simulated_passed_gates": gate_names(simulated_gate_payload, True),
        "simulated_blocking_gates": gate_names(simulated_gate_payload, False),
        "operator_completion_report": str(
            operator_out_dir / "remaining_operator_input_completion_simulation.md.numbered"
        ),
        "unified_sync_report": str(
            unified_out_dir / "unified_final_evidence_intake_sync.md.numbered"
        ),
        "bundle_sync_report": str(
            bundle_sync_out_dir / "bundle_evidence_intake_sync.md.numbered"
        ),
        "bundle_validation_report": str(
            bundle_validation_out_dir / "bundle_evidence_pack_validation.md.numbered"
        ),
        "simulated_gate_report": str(gate_out_dir / "goal_completion_gate.md.numbered"),
        "work_reports_dir": str(work_reports),
    }


def write_outputs(payload: dict[str, Any], out_dir: Path = DEFAULT_OUT_DIR) -> None:
    write_json_and_markdown(
        payload,
        out_dir,
        "remaining_operator_full_gate_simulation.json",
        "remaining_operator_full_gate_simulation.md",
        build_markdown(payload),
    )


def main() -> int:
    payload = build_payload()
    write_outputs(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
