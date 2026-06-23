"""Sync staged candidate final evidence into execution packet CSVs.

This tool copies nonblank `final_evidence_path` values from the unified final
evidence input CSV into blank `evidence_path` cells in repository-local execution
packet CSVs. When the unified row already has a complete operator/reviewer stamp,
the same existing stamp is copied into matching blank packet fields. It does not
create approvals, create evidence, run external applications, or write production
data.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_UNIFIED_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "unified_final_evidence_intake_20260621"
    / "unified_final_evidence_input.csv"
)
DEFAULT_PACKET_DIR = ROOT / "plans" / "reports" / "goal_execution_packet_20260620"
DEFAULT_OUT_DIR = (
    ROOT / "plans" / "reports" / "execution_packet_candidate_path_sync_20260621"
)
PACKET_FIELDS = [
    "scenario",
    "bundle",
    "owner",
    "approval_scope",
    "preconditions",
    "allowed_operations",
    "evidence_to_capture",
    "cleanup_rule",
    "hard_stops",
    "supporting_input_paths",
    "source",
    "current_safe_evidence",
    "current_safe_evidence_scope",
    "operator_result",
    "evidence_path",
    "reviewer",
    "reviewed_at",
    "rakuraku_customer_login_used",
    "temporary_save_created",
    "created_data_cleanup_status",
    "created_data_cleanup_evidence_path",
    "cleanup_reviewer",
    "cleanup_reviewed_at",
]

SYNC_OPERATOR_FIELDS = ["operator_result", "reviewer", "reviewed_at"]


@dataclass(frozen=True)
class CandidateEvidence:
    final_evidence_path: str
    operator_result: str
    reviewer: str
    reviewed_at: str

    def has_complete_operator_stamp(self) -> bool:
        return bool(self.operator_result and self.reviewer and self.reviewed_at)


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
class PacketPathSyncResult:
    bundle: str
    scenario: str
    packet_csv: str
    candidate_path: str
    candidate_exists: bool
    operator_fields_available: bool
    updated_fields: str
    updated: bool
    skipped_reason: str


def slugify(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return text or "bundle"


def entry_key(bundle: str, scenario: str) -> tuple[str, str]:
    return bundle.strip(), scenario.strip()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {str(key): str(value).strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def csv_fieldnames(path: Path, fallback: list[str]) -> list[str]:
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or fallback)


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def candidates_by_key(unified_csv: Path) -> dict[tuple[str, str], CandidateEvidence]:
    rows = read_csv_rows(unified_csv)
    candidates: dict[tuple[str, str], CandidateEvidence] = {}
    for row in rows:
        bundle = row.get("bundle", "")
        scenario = row.get("scenario", "")
        final_path = row.get("final_evidence_path", "")
        if bundle and scenario and final_path:
            candidates[entry_key(bundle, scenario)] = CandidateEvidence(
                final_evidence_path=final_path,
                operator_result=row.get("operator_result", ""),
                reviewer=row.get("reviewer", ""),
                reviewed_at=row.get("reviewed_at", ""),
            )
    return candidates


def sync_packet_csv(
    packet_csv: Path,
    candidates: dict[tuple[str, str], CandidateEvidence],
) -> tuple[list[PacketPathSyncResult], bool]:
    rows = read_csv_rows(packet_csv)
    fieldnames = csv_fieldnames(packet_csv, PACKET_FIELDS)
    if not rows:
        return [], False
    changed = False
    results: list[PacketPathSyncResult] = []
    updated_rows = []
    for row in rows:
        bundle = row.get("bundle", "")
        scenario = row.get("scenario", "")
        candidate = candidates.get(entry_key(bundle, scenario))
        candidate_path = candidate.final_evidence_path if candidate else ""
        candidate_exists = bool(candidate_path) and Path(candidate_path).exists()
        operator_fields_available = bool(candidate and candidate.has_complete_operator_stamp())
        if not candidate_path:
            updated_rows.append(row)
            results.append(
                PacketPathSyncResult(
                    bundle=bundle,
                    scenario=scenario,
                    packet_csv=str(packet_csv),
                    candidate_path="",
                    candidate_exists=False,
                    operator_fields_available=False,
                    updated_fields="",
                    updated=False,
                    skipped_reason="NO_CANDIDATE_PATH",
                )
            )
            continue
        next_row = dict(row)
        updated_fields: list[str] = []
        if not next_row.get("evidence_path", ""):
            next_row["evidence_path"] = candidate_path
            updated_fields.append("evidence_path")
        if candidate and operator_fields_available:
            for field in SYNC_OPERATOR_FIELDS:
                if not next_row.get(field, ""):
                    next_row[field] = getattr(candidate, field)
                    updated_fields.append(field)
        if not updated_fields:
            updated_rows.append(row)
            results.append(
                PacketPathSyncResult(
                    bundle=bundle,
                    scenario=scenario,
                    packet_csv=str(packet_csv),
                    candidate_path=candidate_path,
                    candidate_exists=candidate_exists,
                    operator_fields_available=operator_fields_available,
                    updated_fields="",
                    updated=False,
                    skipped_reason="NO_BLANK_TARGET_FIELDS",
                )
            )
            continue
        updated_rows.append(next_row)
        changed = True
        results.append(
            PacketPathSyncResult(
                bundle=bundle,
                scenario=scenario,
                packet_csv=str(packet_csv),
                candidate_path=candidate_path,
                candidate_exists=candidate_exists,
                operator_fields_available=operator_fields_available,
                updated_fields=", ".join(updated_fields),
                updated=True,
                skipped_reason="",
            )
        )
    if changed:
        backup_path = packet_csv.with_name(
            f"{packet_csv.stem}.before_candidate_path_sync_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}{packet_csv.suffix}"
        )
        backup_path.write_bytes(packet_csv.read_bytes())
        write_csv_rows(packet_csv, fieldnames, updated_rows)
    return results, changed


def packet_csv_paths(packet_dir: Path, candidates: dict[tuple[str, str], CandidateEvidence]) -> list[Path]:
    bundles = sorted({bundle for bundle, _scenario in candidates})
    return [packet_dir / f"{slugify(bundle)}.csv" for bundle in bundles]


def build_payload(unified_csv: Path, packet_dir: Path, apply_updates: bool) -> dict[str, Any]:
    candidates = candidates_by_key(unified_csv)
    all_results: list[PacketPathSyncResult] = []
    changed_csv_count = 0
    missing_packet_csvs: list[str] = []
    if apply_updates:
        for packet_csv in packet_csv_paths(packet_dir, candidates):
            if not packet_csv.exists():
                missing_packet_csvs.append(str(packet_csv))
                continue
            results, changed = sync_packet_csv(packet_csv, candidates)
            all_results.extend(results)
            if changed:
                changed_csv_count += 1
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": "repository-local packet evidence-path prefill only; no approval and no external operation",
        "apply_updates": apply_updates,
        "unified_csv": str(unified_csv),
        "packet_dir": str(packet_dir),
        "candidate_count": len(candidates),
        "result_count": len(all_results),
        "updated_row_count": sum(1 for result in all_results if result.updated),
        "operator_field_sync_row_count": sum(
            1
            for result in all_results
            if any(field in result.updated_fields.split(", ") for field in SYNC_OPERATOR_FIELDS)
        ),
        "changed_csv_count": changed_csv_count,
        "missing_packet_csv_count": len(missing_packet_csvs),
        "missing_packet_csvs": missing_packet_csvs,
        "results": [asdict(result) for result in all_results],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Execution packet candidate evidence path sync 2026-06-21",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- apply_updates: `{payload['apply_updates']}`",
        f"- candidate_count: `{payload['candidate_count']}`",
        f"- result_count: `{payload['result_count']}`",
        f"- updated_row_count: `{payload['updated_row_count']}`",
        f"- operator_field_sync_row_count: `{payload['operator_field_sync_row_count']}`",
        f"- changed_csv_count: `{payload['changed_csv_count']}`",
        f"- missing_packet_csv_count: `{payload['missing_packet_csv_count']}`",
        "",
        "## Boundary",
        "",
        "- This copies candidate evidence paths into blank packet `evidence_path` cells.",
        "- If the unified row already has `operator_result`, `reviewer`, and `reviewed_at`, those existing values are copied only into blank matching packet fields.",
        "- It does not create approval values; partial or blank operator stamps remain untouched.",
        "",
        "## Sync Results",
        "",
        "| Bundle | Scenario | Updated | Updated Fields | Candidate Exists | Operator Fields Available | Candidate Path | Packet CSV | Skipped Reason |",
        "|---|---|---:|---|---:|---:|---|---|---|",
    ]
    for result in payload["results"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(result["bundle"]),
                    str(result["scenario"]),
                    "YES" if result["updated"] else "NO",
                    str(result["updated_fields"]) if result["updated_fields"] else "-",
                    "YES" if result["candidate_exists"] else "NO",
                    "YES" if result["operator_fields_available"] else "NO",
                    f"`{result['candidate_path']}`" if result["candidate_path"] else "-",
                    f"`{result['packet_csv']}`",
                    str(result["skipped_reason"]) if result["skipped_reason"] else "-",
                ]
            )
            + " |"
        )
    if payload["missing_packet_csvs"]:
        lines.extend(["", "## Missing Packet CSVs", ""])
        for path in payload["missing_packet_csvs"]:
            lines.append(f"- `{path}`")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "execution_packet_candidate_path_sync.json"
    md_path = out_dir / "execution_packet_candidate_path_sync.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync candidate evidence paths into execution packet CSVs."
    )
    parser.add_argument("--unified-csv", type=Path, default=DEFAULT_UNIFIED_CSV)
    parser.add_argument("--packet-dir", type=Path, default=DEFAULT_PACKET_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        unified_csv=args.unified_csv,
        packet_dir=args.packet_dir,
        apply_updates=not args.dry_run,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
