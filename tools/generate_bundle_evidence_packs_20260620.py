"""Generate evidence pack folders for the six RK10 approval bundles.

This tool only reads the execution packet and writes repository reports. It
does not copy production data, open GUI applications, or operate external
systems. The packs are preparation folders for final operator evidence; they
are not approvals by themselves.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_PACKET_JSON = (
    ROOT
    / "plans"
    / "reports"
    / "goal_execution_packet_20260620"
    / "goal_execution_packet.json"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "bundle_evidence_packs_20260620"
RK10_RUNTIME_BUNDLE = "RK10_EDITOR_RUNTIME_BUNDLE"
OUTLOOK_COM_BUNDLE = "OUTLOOK_COM_BUNDLE"
RKS_RUNTIME_FOCUS_CSV = "rks_runtime_operator_focus.csv"


def configure_csv_field_size_limit() -> int:
    limit = sys.maxsize
    while limit > 0:
        try:
            csv.field_size_limit(limit)
            return limit
        except OverflowError:
            limit //= 10
    return csv.field_size_limit()


CSV_FIELD_SIZE_LIMIT = configure_csv_field_size_limit()


@dataclass(frozen=True)
class ScenarioEvidence:
    scenario: str
    source: str
    source_exists: bool
    current_reference_evidence: str
    current_reference_exists: bool


@dataclass(frozen=True)
class BundleEvidencePack:
    bundle: str
    owner: str
    scenarios: str
    scenario_count: int
    pack_dir: str
    manifest_path: str
    checklist_path: str
    intake_path: str
    reference_snapshot_path: str
    filename_template_path: str
    filename_template_markdown_path: str
    final_evidence_dir: str
    required_final_evidence: str
    hard_stops: str
    scenario_evidence: list[ScenarioEvidence]


def slugify(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return text or "bundle"


def scenario_slug(value: str) -> str:
    return "scenario_" + slugify(value)


def suggested_final_evidence_folder(pack: BundleEvidencePack, scenario: str) -> str:
    return str(Path(pack.final_evidence_dir) / scenario_slug(scenario))


def split_scenarios(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def path_exists(value: str) -> bool:
    return bool(value.strip()) and Path(value).exists()


def file_size_bytes(value: str) -> int:
    if not value.strip():
        return 0
    path = Path(value)
    if not path.is_file():
        return 0
    return path.stat().st_size


def file_sha256(value: str) -> str:
    if not value.strip():
        return ""
    path = Path(value)
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_packet(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"execution packet not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_scenario_evidence(
    scenarios: str,
    source_map: dict[str, str],
    current_evidence_map: dict[str, str],
) -> list[ScenarioEvidence]:
    rows = []
    for scenario in split_scenarios(scenarios):
        source = str(source_map.get(scenario, ""))
        current_evidence = str(current_evidence_map.get(scenario, ""))
        rows.append(
            ScenarioEvidence(
                scenario=scenario,
                source=source,
                source_exists=path_exists(source),
                current_reference_evidence=current_evidence,
                current_reference_exists=path_exists(current_evidence),
            )
        )
    return rows


def build_packs(packet_payload: dict[str, Any], out_dir: Path) -> list[BundleEvidencePack]:
    source_map = {
        str(key): str(value)
        for key, value in dict(packet_payload.get("source_map", {})).items()
    }
    current_evidence_map = {
        str(key): str(value)
        for key, value in dict(packet_payload.get("current_evidence_map", {})).items()
    }
    packs = []
    for packet in packet_payload.get("packets", []):
        bundle = str(packet["bundle"])
        pack_dir = out_dir / slugify(bundle)
        manifest_path = pack_dir / "evidence_manifest.json"
        checklist_path = pack_dir / "operator_evidence_checklist.md"
        intake_path = pack_dir / "final_evidence_intake.csv"
        reference_snapshot_path = pack_dir / "reference_evidence_snapshot.csv"
        filename_template_path = pack_dir / "operator_evidence_filename_template.csv"
        filename_template_markdown_path = pack_dir / "operator_evidence_filename_template.md"
        final_evidence_dir = pack_dir / "final_evidence"
        scenarios = str(packet["scenarios"])
        packs.append(
            BundleEvidencePack(
                bundle=bundle,
                owner=str(packet["owner"]),
                scenarios=scenarios,
                scenario_count=len(split_scenarios(scenarios)),
                pack_dir=str(pack_dir),
                manifest_path=str(manifest_path),
                checklist_path=str(checklist_path),
                intake_path=str(intake_path),
                reference_snapshot_path=str(reference_snapshot_path),
                filename_template_path=str(filename_template_path),
                filename_template_markdown_path=str(filename_template_markdown_path),
                final_evidence_dir=str(final_evidence_dir),
                required_final_evidence=str(packet["evidence_to_capture"]),
                hard_stops=str(packet["hard_stops"]),
                scenario_evidence=build_scenario_evidence(
                    scenarios,
                    source_map,
                    current_evidence_map,
                ),
            )
        )
    return packs


def build_payload(packet_path: Path, out_dir: Path) -> dict[str, Any]:
    packet_payload = load_packet(packet_path)
    packs = build_packs(packet_payload, out_dir)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": "report/folder preparation only; no external operation and no production data copy",
        "packet_path": str(packet_path),
        "out_dir": str(out_dir),
        "bundle_count": len(packs),
        "scenario_count": sum(pack.scenario_count for pack in packs),
        "packs": [
            {
                **asdict(pack),
                "scenario_evidence": [asdict(row) for row in pack.scenario_evidence],
            }
            for pack in packs
        ],
    }


def build_pack_markdown(pack: BundleEvidencePack) -> str:
    lines = [
        f"# {pack.bundle} 証跡パック",
        "",
        f"- owner: `{pack.owner}`",
        f"- scenarios: `{pack.scenarios}`",
        f"- scenario_count: `{pack.scenario_count}`",
        f"- pack_dir: `{pack.pack_dir}`",
        f"- final_evidence_dir: `{pack.final_evidence_dir}`",
        f"- intake_path: `{pack.intake_path}`",
        f"- reference_snapshot_path: `{pack.reference_snapshot_path}`",
        f"- filename_template_path: `{pack.filename_template_path}`",
        f"- filename_template_markdown_path: `{pack.filename_template_markdown_path}`",
        "",
        "## Required Final Evidence",
        "",
        f"- {pack.required_final_evidence}",
        "",
        "## Hard Stops",
        "",
        f"- {pack.hard_stops}",
        "",
        "## Current Reference Evidence",
        "",
        "| Scenario | Source Exists | Source | Current Reference Exists | Current Reference Evidence |",
        "|---|---:|---|---:|---|",
    ]
    for row in pack.scenario_evidence:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.scenario,
                    "YES" if row.source_exists else "NO",
                    f"`{row.source}`" if row.source else "-",
                    "YES" if row.current_reference_exists else "NO",
                    f"`{row.current_reference_evidence}`" if row.current_reference_evidence else "-",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Reference Snapshot",
            "",
            f"- reference_snapshot_csv: `{pack.reference_snapshot_path}`",
            "- This CSV records current known source/reference evidence hashes only.",
            "- It is reference-only and must not be used as final approval evidence.",
        ]
    )
    focus_csv_path = focused_runtime_csv_path(pack)
    if focus_csv_path:
        lines.extend(
            [
                "",
                "## Focused RKS Runtime Evidence",
                "",
                f"- current_focus_csv: `{focus_csv_path}`",
                "- まずこのCSVの57/58など現在入力が必要な行だけ確認する。",
                "- 37/47/55/63の取込済みsafe-stop証跡や、前提条件待ち行を再レビュー対象にしない。",
                "- 最終OK判定は `rks_runtime_operator_intake_validation.md.numbered` で行う。",
                "- このCSVがない場合は固定ランナーを再実行して再生成する。",
            ]
        )
    lines.extend(
        [
            "",
            "## Operator Instructions",
            "",
            "- Put final run logs, screenshots, exported reports, or review files for every scenario in this bundle under this folder or a subfolder.",
            "- Use the `suggested_final_evidence_folder` column as the preferred per-scenario drop location.",
            "- Use `final_evidence_intake.csv` to track one collected evidence path per scenario before marking the bundle complete.",
            "- Use `operator_evidence_filename_template.csv` only as a naming guide; it is not final evidence.",
            "- Put final evidence files under `final_evidence` or point the bundle sheet to a non-empty final evidence folder.",
            "- Do not use this pack alone as approval; it is only a prepared evidence container.",
            "- After adding final evidence, set the bundle sheet `evidence_path` to `final_evidence` or a specific final proof path; do not use the prepared pack root as final evidence.",
            "- Keep hard stops in force unless a separate explicit approval exists.",
        ]
    )
    return "\n".join(lines) + "\n"


def focused_runtime_csv_path(pack: BundleEvidencePack) -> str:
    if pack.bundle != RK10_RUNTIME_BUNDLE:
        return ""
    return str(Path(pack.pack_dir) / RKS_RUNTIME_FOCUS_CSV)


def filename_template_rows(pack: BundleEvidencePack) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for scenario in split_scenarios(pack.scenarios):
        scenario_folder = suggested_final_evidence_folder(pack, scenario)
        prefix = scenario_slug(scenario)
        if pack.bundle == OUTLOOK_COM_BUNDLE:
            templates = [
                ("log", f"{prefix}_outlook_com_preflight_exit0_YYYYMMDD_HHMMSS.txt", "Outlook COM preflight exit 0 log"),
                ("log", f"{prefix}_dryrun_no_print_no_mail_YYYYMMDD_HHMMSS.log", "Dry-run log showing no print and no mail"),
                ("csv", f"{prefix}_saved_pdf_count_summary_YYYYMMDD_HHMMSS.csv", "Saved PDF count and target summary"),
                ("screenshot", f"{prefix}_no_print_no_mail_screen_YYYYMMDD_HHMMSS.png", "Screen proof that print/mail was not executed"),
            ]
        elif pack.bundle == RK10_RUNTIME_BUNDLE:
            templates = [
                ("log", f"{prefix}_rk10_metadata_guard_YYYYMMDD_HHMMSS.txt", "RKS metadata guard output"),
                ("screenshot", f"{prefix}_rk10_editor_open_build_YYYYMMDD_HHMMSS.png", "RK10 editor open/build proof"),
                ("log", f"{prefix}_safe_stop_latest_clean_log_YYYYMMDD_HHMMSS.txt", "Safe-stop runtime latest clean log"),
                ("log", f"{prefix}_rks_status_gate_YYYYMMDD_HHMMSS.txt", "RKS status gate output"),
            ]
        else:
            templates = [
                ("log", f"{prefix}_safe_run_log_YYYYMMDD_HHMMSS.txt", "Safe execution or review log"),
                ("summary", f"{prefix}_count_amount_summary_YYYYMMDD_HHMMSS.csv", "Count/amount/review summary"),
                ("screenshot", f"{prefix}_operator_review_screen_YYYYMMDD_HHMMSS.png", "Operator review proof when applicable"),
            ]
        for evidence_kind, example_filename, purpose in templates:
            rows.append(
                {
                    "bundle": pack.bundle,
                    "scenario": scenario,
                    "template_only_not_final_evidence": "YES",
                    "save_under_folder": scenario_folder,
                    "evidence_kind": evidence_kind,
                    "example_filename": example_filename,
                    "purpose": purpose,
                    "notes": "Create the actual file only after the allowed safe run/review. Do not treat this template row as evidence.",
                }
            )
    return rows


def build_summary_markdown(payload: dict[str, Any]) -> str:
    packs = payload["packs"]
    assert isinstance(packs, list)
    lines = [
        "# 6束証跡パック 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- bundle_count: `{payload['bundle_count']}`",
        f"- scenario_count: `{payload['scenario_count']}`",
        f"- out_dir: `{payload['out_dir']}`",
        "",
        "## Pack Matrix",
        "",
        "| Bundle | Scenarios | Scenario Count | Pack Dir | Checklist |",
        "|---|---|---:|---|---|",
    ]
    for pack in packs:
        assert isinstance(pack, dict)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(pack["bundle"]),
                    str(pack["scenarios"]).replace("|", "/"),
                    str(pack["scenario_count"]),
                    f"`{pack['pack_dir']}`",
                    f"`{pack['checklist_path']}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Important Boundary",
            "",
            "- These folders only prepare where final evidence should be placed.",
            "- They do not prove production completion, payment execution, mail sending, printing, RK10 runtime, or Azure OCR.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


INTAKE_FIELDNAMES = [
    "bundle",
    "scenario",
    "required_final_evidence",
    "hard_stops",
    "current_reference_evidence",
    "suggested_final_evidence_folder",
    "final_evidence_path",
    "required_update_fields",
    "operator_result",
    "reviewer",
    "reviewed_at",
    "rakuraku_customer_login_used",
    "temporary_save_created",
    "created_data_cleanup_status",
    "created_data_cleanup_evidence_path",
    "cleanup_reviewer",
    "cleanup_reviewed_at",
    "notes",
]

PRESERVED_INTAKE_FIELDS = [
    "final_evidence_path",
    "operator_result",
    "reviewer",
    "reviewed_at",
    "rakuraku_customer_login_used",
    "temporary_save_created",
    "created_data_cleanup_status",
    "created_data_cleanup_evidence_path",
    "cleanup_reviewer",
    "cleanup_reviewed_at",
    "notes",
]


def existing_intake_rows_by_scenario(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            str(row.get("scenario", "")): row
            for row in csv.DictReader(handle)
            if row.get("scenario")
        }


def preserve_existing_intake_values(
    scenario: str,
    generated_row: dict[str, str],
    existing_rows: dict[str, dict[str, str]],
) -> dict[str, str]:
    existing_row = existing_rows.get(scenario, {})
    merged_row = dict(generated_row)
    for field in PRESERVED_INTAKE_FIELDS:
        existing_value = str(existing_row.get(field, ""))
        if existing_value:
            merged_row[field] = existing_value
    return merged_row


def write_intake_csv(pack: BundleEvidencePack) -> None:
    path = Path(pack.intake_path)
    existing_rows = existing_intake_rows_by_scenario(path)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INTAKE_FIELDNAMES)
        writer.writeheader()
        for row in pack.scenario_evidence:
            generated_row = {
                "bundle": pack.bundle,
                "scenario": row.scenario,
                "required_final_evidence": pack.required_final_evidence,
                "hard_stops": pack.hard_stops,
                "current_reference_evidence": row.current_reference_evidence,
                "suggested_final_evidence_folder": suggested_final_evidence_folder(
                    pack,
                    row.scenario,
                ),
                "final_evidence_path": "",
                "required_update_fields": "final_evidence_path, operator_result, reviewer, reviewed_at",
                "operator_result": "",
                "reviewer": "",
                "reviewed_at": "",
                "rakuraku_customer_login_used": "",
                "temporary_save_created": "",
                "created_data_cleanup_status": "",
                "created_data_cleanup_evidence_path": "",
                "cleanup_reviewer": "",
                "cleanup_reviewed_at": "",
                "notes": "",
            }
            writer.writerow(
                preserve_existing_intake_values(
                    row.scenario,
                    generated_row,
                    existing_rows,
                )
            )


def write_reference_snapshot_csv(pack: BundleEvidencePack) -> None:
    path = Path(pack.reference_snapshot_path)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "bundle",
                "scenario",
                "evidence_scope",
                "source",
                "source_exists",
                "source_size_bytes",
                "source_sha256",
                "current_reference_evidence",
                "current_reference_exists",
                "current_reference_size_bytes",
                "current_reference_sha256",
                "final_evidence_allowed",
                "notes",
            ],
        )
        writer.writeheader()
        for row in pack.scenario_evidence:
            writer.writerow(
                {
                    "bundle": pack.bundle,
                    "scenario": row.scenario,
                    "evidence_scope": "REFERENCE_ONLY_NOT_FINAL",
                    "source": row.source,
                    "source_exists": "YES" if row.source_exists else "NO",
                    "source_size_bytes": file_size_bytes(row.source),
                    "source_sha256": file_sha256(row.source),
                    "current_reference_evidence": row.current_reference_evidence,
                    "current_reference_exists": "YES" if row.current_reference_exists else "NO",
                    "current_reference_size_bytes": file_size_bytes(row.current_reference_evidence),
                    "current_reference_sha256": file_sha256(row.current_reference_evidence),
                    "final_evidence_allowed": "NO",
                    "notes": "Use for orientation/hash check only; collect final evidence separately.",
                }
            )


def write_filename_template_csv(pack: BundleEvidencePack) -> None:
    path = Path(pack.filename_template_path)
    rows = filename_template_rows(pack)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "bundle",
                "scenario",
                "template_only_not_final_evidence",
                "save_under_folder",
                "evidence_kind",
                "example_filename",
                "purpose",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def build_filename_template_markdown(pack: BundleEvidencePack) -> str:
    lines = [
        f"# {pack.bundle} 証跡ファイル名テンプレート",
        "",
        "- scope: `TEMPLATE_ONLY_NOT_FINAL_EVIDENCE`",
        "- このファイルは命名ガイドであり、完了証跡ではない。",
        "- 実行後に作成した実ファイルだけを `final_evidence` 配下へ置く。",
        "",
        "| Scenario | Kind | Save Under Folder | Example Filename | Purpose |",
        "|---|---|---|---|---|",
    ]
    for row in filename_template_rows(pack):
        lines.append(
            "| "
            + " | ".join(
                [
                    row["scenario"],
                    row["evidence_kind"],
                    f"`{row['save_under_folder']}`",
                    f"`{row['example_filename']}`",
                    row["purpose"],
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_filename_template_markdown(pack: BundleEvidencePack) -> None:
    path = Path(pack.filename_template_markdown_path)
    path.write_text(build_filename_template_markdown(pack), encoding="utf-8")
    write_numbered_copy(path)


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "bundle_evidence_packs.json"
    md_path = out_dir / "bundle_evidence_packs.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_summary_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)
    for pack_payload in payload["packs"]:
        pack = BundleEvidencePack(
            **{
                **pack_payload,
                "scenario_evidence": [
                    ScenarioEvidence(**row)
                    for row in pack_payload["scenario_evidence"]
                ],
            }
        )
        pack_dir = Path(pack.pack_dir)
        pack_dir.mkdir(parents=True, exist_ok=True)
        Path(pack.final_evidence_dir).mkdir(parents=True, exist_ok=True)
        for row in pack.scenario_evidence:
            Path(suggested_final_evidence_folder(pack, row.scenario)).mkdir(
                parents=True,
                exist_ok=True,
            )
        Path(pack.manifest_path).write_text(
            json.dumps(
                {
                    **asdict(pack),
                    "scenario_evidence": [asdict(row) for row in pack.scenario_evidence],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        Path(pack.checklist_path).write_text(build_pack_markdown(pack), encoding="utf-8")
        write_numbered_copy(Path(pack.checklist_path))
        write_intake_csv(pack)
        write_reference_snapshot_csv(pack)
        write_filename_template_csv(pack)
        write_filename_template_markdown(pack)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate six bundle evidence packs.")
    parser.add_argument("--packet-json", type=Path, default=DEFAULT_PACKET_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.packet_json, args.out_dir)
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
