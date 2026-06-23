"""Generate a six-row operator sheet for RK10 approval bundles.

This tool only reads the generated execution packet and writes repository
reports. It does not open Outlook, RK10, Rakuraku, Azure, printers, mail,
payment systems, MainSV, or production files.
"""

from __future__ import annotations

import argparse
import csv
import json
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
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "bundle_operator_sheet_20260620"
DEFAULT_EVIDENCE_PACK_DIR = ROOT / "plans" / "reports" / "bundle_evidence_packs_20260620"
OPERATOR_FIELDS = ["operator_result", "evidence_path", "reviewer", "reviewed_at", "notes"]
CLEANUP_FIELDS = [
    "rakuraku_customer_login_used",
    "temporary_save_created",
    "created_data_cleanup_status",
    "created_data_cleanup_evidence_path",
    "cleanup_reviewer",
    "cleanup_reviewed_at",
]
YES_VALUES = {"1", "true", "yes", "y", "used", "created", "はい", "あり", "有", "作成", "作成済"}


@dataclass(frozen=True)
class BundleSheetRow:
    bundle: str
    owner: str
    scenarios: str
    scenario_count: int
    approval_scope: str
    allowed_operations: str
    evidence_to_capture: str
    hard_stops: str
    packet_csv_path: str
    prepared_evidence_pack_path: str
    operator_result: str
    evidence_path: str
    reviewer: str
    reviewed_at: str
    rakuraku_customer_login_used: str
    temporary_save_created: str
    created_data_cleanup_status: str
    created_data_cleanup_evidence_path: str
    cleanup_reviewer: str
    cleanup_reviewed_at: str
    notes: str


def split_scenarios(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def slugify(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return text or "bundle"


def load_packet(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"execution packet not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def is_yes(value: str) -> bool:
    return value.strip().lower() in YES_VALUES


def read_existing_sheet(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            str(row.get("bundle", "")).strip(): {
                field: str(row.get(field, ""))
                for field in [*OPERATOR_FIELDS, *CLEANUP_FIELDS]
            }
            for row in csv.DictReader(handle)
            if str(row.get("bundle", "")).strip()
        }


def build_rows(
    packet_payload: dict[str, Any],
    existing_path: Path,
    evidence_pack_dir: Path = DEFAULT_EVIDENCE_PACK_DIR,
) -> list[BundleSheetRow]:
    existing = read_existing_sheet(existing_path)
    rows = []
    for packet in packet_payload.get("packets", []):
        bundle = str(packet["bundle"])
        preserved = existing.get(bundle, {})
        scenarios = str(packet["scenarios"])
        rows.append(
            BundleSheetRow(
                bundle=bundle,
                owner=str(packet["owner"]),
                scenarios=scenarios,
                scenario_count=len(split_scenarios(scenarios)),
                approval_scope=str(packet["approval_scope"]),
                allowed_operations=str(packet["allowed_operations"]),
                evidence_to_capture=str(packet["evidence_to_capture"]),
                hard_stops=str(packet["hard_stops"]),
                packet_csv_path=str(packet["csv_path"]),
                prepared_evidence_pack_path=str(evidence_pack_dir / slugify(bundle)),
                operator_result=preserved.get("operator_result", ""),
                evidence_path=preserved.get("evidence_path", ""),
                reviewer=preserved.get("reviewer", ""),
                reviewed_at=preserved.get("reviewed_at", ""),
                rakuraku_customer_login_used=preserved.get("rakuraku_customer_login_used", ""),
                temporary_save_created=preserved.get("temporary_save_created", ""),
                created_data_cleanup_status=preserved.get("created_data_cleanup_status", ""),
                created_data_cleanup_evidence_path=preserved.get("created_data_cleanup_evidence_path", ""),
                cleanup_reviewer=preserved.get("cleanup_reviewer", ""),
                cleanup_reviewed_at=preserved.get("cleanup_reviewed_at", ""),
                notes=preserved.get("notes", ""),
            )
        )
    return rows


def count_complete_bundle_rows(rows: list[BundleSheetRow]) -> int:
    return sum(1 for row in rows if row_fields_complete(row))


def row_fields_complete(row: BundleSheetRow) -> bool:
    return (
        bool(row.operator_result.strip())
        and bool(row.evidence_path.strip())
        and bool(row.reviewer.strip())
        and bool(row.reviewed_at.strip())
    )


def build_payload(
    packet_path: Path,
    out_dir: Path,
    evidence_pack_dir: Path = DEFAULT_EVIDENCE_PACK_DIR,
) -> dict[str, Any]:
    sheet_path = out_dir / "bundle_operator_sheet.csv"
    packet_payload = load_packet(packet_path)
    rows = build_rows(packet_payload, sheet_path, evidence_pack_dir)
    complete_bundle_count = count_complete_bundle_rows(rows)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": "report generation only; no external operation",
        "packet_path": str(packet_path),
        "sheet_path": str(sheet_path),
        "evidence_pack_dir": str(evidence_pack_dir),
        "bundle_count": len(rows),
        "complete_bundle_count": complete_bundle_count,
        "needs_attention_bundle_count": len(rows) - complete_bundle_count,
        "rows": [asdict(row) for row in rows],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    assert isinstance(rows, list)
    lines = [
        "# 6束オペレーター入力シート 2026-06-20",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- bundle_count: `{payload['bundle_count']}`",
        f"- complete_bundle_count: `{payload['complete_bundle_count']}`",
        f"- needs_attention_bundle_count: `{payload['needs_attention_bundle_count']}`",
        f"- sheet_path: `{payload['sheet_path']}`",
        f"- evidence_pack_dir: `{payload['evidence_pack_dir']}`",
        "",
        "## 使い方",
        "",
        "- 15シナリオ個別ではなく、この6行だけに `operator_result` / `evidence_path` / `reviewer` / `reviewed_at` を記入する。",
        "- `evidence_path` はBundle内シナリオすべての証跡が入った実在ファイルまたはフォルダにする。",
        "- `prepared_evidence_pack_path` は最終証跡を置くための準備フォルダで、承認そのものではない。",
        "- `rakuraku_customer_login_used` / `temporary_save_created` / cleanup系列は任意記録欄。削除証跡は承認ゲートの必須条件にしない。",
        "- 実メール・実印刷・支払実行・本番申請・RK10 ButtonRun・Azure課金は、このシート記入だけでは許可されない。",
        "- 記入後に固定ランナーを再実行すると、束単位の入力が15シナリオ行の検証に反映される。",
        "",
        "## Bundle Rows",
        "",
        "| Bundle | Owner | Scenarios | Scenario Count | Complete Fields | Prepared Evidence Pack | Evidence Path | Hard Stops | Packet CSV |",
        "|---|---|---|---:|---:|---|---|---|---|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        complete = row_fields_complete(BundleSheetRow(**row))
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["bundle"]),
                    str(row["owner"]),
                    str(row["scenarios"]).replace("|", "/"),
                    str(row["scenario_count"]),
                    "YES" if complete else "NO",
                    f"`{row['prepared_evidence_pack_path']}`",
                    f"`{row['evidence_path']}`" if row["evidence_path"] else "-",
                    str(row["hard_stops"]).replace("|", "/"),
                    f"`{row['packet_csv_path']}`",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_csv(rows: list[BundleSheetRow], path: Path) -> None:
    fieldnames = [
        "bundle",
        "owner",
        "scenarios",
        "scenario_count",
        "approval_scope",
        "allowed_operations",
        "evidence_to_capture",
        "hard_stops",
        "packet_csv_path",
        "prepared_evidence_pack_path",
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
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate six-row bundle operator sheet.")
    parser.add_argument("--packet-json", type=Path, default=DEFAULT_PACKET_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--evidence-pack-dir", type=Path, default=DEFAULT_EVIDENCE_PACK_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args.packet_json, args.out_dir, args.evidence_pack_dir)
    rows = [
        BundleSheetRow(**row)
        for row in payload["rows"]
    ]
    csv_path = args.out_dir / "bundle_operator_sheet.csv"
    json_path = args.out_dir / "bundle_operator_sheet.json"
    md_path = args.out_dir / "bundle_operator_sheet.md"
    write_csv(rows, csv_path)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
