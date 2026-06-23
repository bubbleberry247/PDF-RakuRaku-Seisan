"""Generate minimum input packets for approval gates.

The packet is an operator aid only. It pre-fills paths and allowed fields, but
does not approve rows, submit data, send mail, print, pay, run RK10, or write to
production systems.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
REPORTS = ROOT / "plans" / "reports"
DEFAULT_FILL_QUEUE_CSV = (
    REPORTS / "final_evidence_fill_queue_20260621" / "final_evidence_fill_queue.csv"
)
DEFAULT_BUNDLE_PACK_ROOT = REPORTS / "bundle_evidence_packs_20260620"
DEFAULT_OUT_DIR = REPORTS / "next_bundle_minimum_input_packet_20260622"
SUPPORTING_DIR_NAME = "scenario_44_minimum_input_packet_20260622"
BLANK_OPERATOR_FIELDS = ("operator_result", "reviewer", "reviewed_at")
BUNDLE_SLUGS = {
    "BUSINESS_REVIEW_BUNDLE": "business_review_bundle",
    "PAYMENT_APPROVAL_BUNDLE": "payment_approval_bundle",
    "PAID_AZURE_OCR_BUNDLE": "paid_azure_ocr_bundle",
    "BUSINESS_DATA_APPROVAL_BUNDLE": "business_data_approval_bundle",
    "RK10_EDITOR_RUNTIME_BUNDLE": "rk10_editor_runtime_bundle",
    "OUTLOOK_COM_BUNDLE": "outlook_com_bundle",
}
BUNDLE_PACKET_DIR_NAMES = {
    "PAYMENT_APPROVAL_BUNDLE": "payment_approval_minimum_input_packet_20260622",
    "PAID_AZURE_OCR_BUNDLE": "paid_azure_ocr_minimum_input_packet_20260622",
    "BUSINESS_DATA_APPROVAL_BUNDLE": "business_data_approval_minimum_input_packet_20260622",
    "RK10_EDITOR_RUNTIME_BUNDLE": "rk10_editor_runtime_minimum_input_packet_20260622",
    "OUTLOOK_COM_BUNDLE": "outlook_com_minimum_input_packet_20260622",
}


@dataclass(frozen=True)
class MinimumInputRow:
    entry_key: str
    bundle: str
    scenario: str
    operator_result: str
    reviewer: str
    reviewed_at: str
    final_evidence_path: str
    source_unified_input_csv: str
    source_bundle_intake_csv: str
    start_here_path: str
    allowed_operator_result_values: str
    hard_stop: str
    do_not_change: str
    after_action_command: str


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def split_entry_keys(value: str) -> list[str]:
    return [part.strip() for part in value.split(" / ") if part.strip()]


def split_scenarios(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def select_active_row(rows: list[dict[str, str]], bundle: str | None) -> dict[str, str]:
    if bundle:
        for row in rows:
            if row.get("bundle") == bundle:
                return row
        raise ValueError(f"bundle not found in fill queue: {bundle}")
    for row in rows:
        if row.get("active") == "True":
            return row
    raise ValueError("no active bundle row found in fill queue")


def select_active_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    active_rows = [row for row in rows if row.get("active") == "True"]
    if not active_rows:
        raise ValueError("no active bundle rows found in fill queue")
    return active_rows


def bundle_slug(bundle: str) -> str:
    return BUNDLE_SLUGS.get(bundle, bundle.lower())


def supporting_output_dir(bundle: str, scenario: str, bundle_pack_root: Path) -> Path:
    if bundle == "BUSINESS_REVIEW_BUNDLE" and scenario == "44":
        return (
            bundle_pack_root
            / "business_review_bundle"
            / "supporting_materials"
            / SUPPORTING_DIR_NAME
        )
    packet_dir_name = BUNDLE_PACKET_DIR_NAMES.get(
        bundle,
        f"{scenario.replace('/', '_')}_minimum_input_packet_20260622",
    )
    return bundle_pack_root / bundle_slug(bundle) / "supporting_materials" / packet_dir_name


def build_rows(queue_row: dict[str, str]) -> list[MinimumInputRow]:
    scenarios = split_scenarios(queue_row.get("scenarios", ""))
    entry_keys = split_entry_keys(queue_row.get("unified_entry_keys", ""))
    if len(entry_keys) == 1 and len(scenarios) > 1:
        entry_keys = [entry_keys[0] for _scenario in scenarios]
    rows: list[MinimumInputRow] = []
    for index, scenario in enumerate(scenarios):
        entry_key = entry_keys[index] if index < len(entry_keys) else ""
        rows.append(
            MinimumInputRow(
                entry_key=entry_key,
                bundle=queue_row.get("bundle", ""),
                scenario=scenario,
                operator_result="",
                reviewer="",
                reviewed_at="",
                final_evidence_path=queue_row.get("suggested_final_evidence_path", ""),
                source_unified_input_csv=queue_row.get("unified_input_csv", ""),
                source_bundle_intake_csv=queue_row.get("target_intake_path", ""),
                start_here_path=queue_row.get("start_here_path", ""),
                allowed_operator_result_values="OK / NG / HOLD",
                hard_stop=queue_row.get("forbidden", ""),
                do_not_change="final_evidence_path unless the evidence folder changes",
                after_action_command=queue_row.get("after_action_command", ""),
            )
        )
    return rows


def build_payload(
    fill_queue_csv: Path,
    bundle_pack_root: Path,
    bundle: str | None = None,
) -> dict[str, Any]:
    queue_rows = read_csv_dicts(fill_queue_csv)
    active_row = select_active_row(queue_rows, bundle)
    rows = build_rows(active_row)
    scenario = rows[0].scenario if rows else active_row.get("scenarios", "")
    out_dir = supporting_output_dir(active_row.get("bundle", ""), scenario, bundle_pack_root)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": (
            "operator aid only; no approval, no external operation, no production "
            "write, no RK10 ButtonRun"
        ),
        "selected_bundle": active_row.get("bundle", ""),
        "selected_scenarios": active_row.get("scenarios", ""),
        "row_count": len(rows),
        "operator_fields_prefilled": 0,
        "blank_operator_fields": list(BLANK_OPERATOR_FIELDS),
        "output_dir": str(out_dir),
        "source_fill_queue_csv": str(fill_queue_csv),
        "rows": [asdict(row) for row in rows],
    }


def build_payload_for_row(
    queue_row: dict[str, str],
    fill_queue_csv: Path,
    bundle_pack_root: Path,
) -> dict[str, Any]:
    rows = build_rows(queue_row)
    scenario = rows[0].scenario if rows else queue_row.get("scenarios", "")
    out_dir = supporting_output_dir(queue_row.get("bundle", ""), scenario, bundle_pack_root)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": (
            "operator aid only; no approval, no external operation, no production "
            "write, no RK10 ButtonRun"
        ),
        "selected_bundle": queue_row.get("bundle", ""),
        "selected_scenarios": queue_row.get("scenarios", ""),
        "row_count": len(rows),
        "operator_fields_prefilled": 0,
        "blank_operator_fields": list(BLANK_OPERATOR_FIELDS),
        "output_dir": str(out_dir),
        "source_fill_queue_csv": str(fill_queue_csv),
        "rows": [asdict(row) for row in rows],
    }


def build_all_active_payloads(
    fill_queue_csv: Path,
    bundle_pack_root: Path,
) -> list[dict[str, Any]]:
    queue_rows = read_csv_dicts(fill_queue_csv)
    return [
        build_payload_for_row(row, fill_queue_csv, bundle_pack_root)
        for row in select_active_rows(queue_rows)
    ]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(MinimumInputRow)]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Next Bundle Minimum Input Packet 2026-06-22",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- selected_bundle: `{payload['selected_bundle']}`",
        f"- selected_scenarios: `{payload['selected_scenarios']}`",
        f"- row_count: `{payload['row_count']}`",
        f"- operator_fields_prefilled: `{payload['operator_fields_prefilled']}`",
        f"- blank_operator_fields: `{', '.join(payload['blank_operator_fields'])}`",
        f"- safety: `{payload['safety']}`",
        "",
        "## How To Use",
        "",
        "1. Open `minimum_input.csv`.",
        "2. Fill only `operator_result`, `reviewer`, and `reviewed_at`.",
        "3. Copy those same values to the matching row in the listed `source_unified_input_csv`.",
        "4. Run the listed fixed safe runner.",
        "5. Do not run production registration, mail, print, payment, or RK10 ButtonRun from this packet.",
        "",
        "## Rows",
        "",
        "| Entry Key | Bundle | Scenario | Final Evidence Path | Source Unified Input CSV | Hard Stop |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                str(row.get(key, "")).replace("|", "/")
                for key in [
                    "entry_key",
                    "bundle",
                    "scenario",
                    "final_evidence_path",
                    "source_unified_input_csv",
                    "hard_stop",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- csv: `{Path(payload['output_dir']) / 'minimum_input.csv'}`",
            f"- json: `{Path(payload['output_dir']) / 'minimum_input_packet.json'}`",
            f"- report: `{Path(payload['output_dir']) / 'minimum_input_packet.md'}`",
        ]
    )
    return "\n".join(lines) + "\n"


def build_index_payload(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "safety": (
            "operator aid index only; no approval, no external operation, "
            "no production write, no RK10 ButtonRun"
        ),
        "packet_count": len(payloads),
        "selected_bundles": [payload["selected_bundle"] for payload in payloads],
        "operator_fields_prefilled": 0,
        "blank_operator_fields": list(BLANK_OPERATOR_FIELDS),
        "packets": [
            {
                "selected_bundle": payload["selected_bundle"],
                "selected_scenarios": payload["selected_scenarios"],
                "row_count": payload["row_count"],
                "output_dir": payload["output_dir"],
                "minimum_input_csv": str(Path(payload["output_dir"]) / "minimum_input.csv"),
                "minimum_input_report": str(
                    Path(payload["output_dir"]) / "minimum_input_packet.md.numbered"
                ),
            }
            for payload in payloads
        ],
    }


def build_index_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Next Bundle Minimum Input Packet Index 2026-06-22",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- packet_count: `{payload['packet_count']}`",
        f"- operator_fields_prefilled: `{payload['operator_fields_prefilled']}`",
        f"- blank_operator_fields: `{', '.join(payload['blank_operator_fields'])}`",
        f"- safety: `{payload['safety']}`",
        "",
        "## How To Use",
        "",
        "1. Open the relevant `minimum_input.csv` below.",
        "2. Fill only `operator_result`, `reviewer`, and `reviewed_at`.",
        "3. Do not change radio buttons in the RK10 license dialog; if `RPA開発版AI付き` is already selected, press OK only.",
        "4. Run the fixed safe runner after filling evidence fields.",
        "",
        "## Packets",
        "",
        "| Bundle | Scenarios | Rows | Minimum Input CSV | Report |",
        "|---|---|---:|---|---|",
    ]
    for packet in payload["packets"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(packet["selected_bundle"]),
                    str(packet["selected_scenarios"]),
                    str(packet["row_count"]),
                    f"`{packet['minimum_input_csv']}`",
                    f"`{packet['minimum_input_report']}`",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any], out_dir: Path | None = None) -> None:
    output_dir = out_dir or Path(payload["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "minimum_input_packet.json"
    csv_path = output_dir / "minimum_input.csv"
    md_path = output_dir / "minimum_input_packet.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, payload["rows"])
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)
    write_numbered_copy(csv_path)


def write_all_active_index(payloads: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_index_payload(payloads)
    json_path = out_dir / "next_bundle_minimum_input_packet_index.json"
    md_path = out_dir / "next_bundle_minimum_input_packet_index.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_index_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate next-bundle minimum input packet.")
    parser.add_argument("--fill-queue-csv", type=Path, default=DEFAULT_FILL_QUEUE_CSV)
    parser.add_argument("--bundle-pack-root", type=Path, default=DEFAULT_BUNDLE_PACK_ROOT)
    parser.add_argument("--bundle", default=None)
    parser.add_argument(
        "--all-active",
        action="store_true",
        help="Generate packets for all active bundle rows in the fill queue.",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.all_active:
        payloads = build_all_active_payloads(args.fill_queue_csv, args.bundle_pack_root)
        for payload in payloads:
            write_outputs(payload)
        write_all_active_index(payloads, args.out_dir or DEFAULT_OUT_DIR)
        print(
            json.dumps(
                {
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "packet_count": len(payloads),
                    "selected_bundles": [
                        payload["selected_bundle"] for payload in payloads
                    ],
                    "output_dirs": [payload["output_dir"] for payload in payloads],
                    "index_dir": str(args.out_dir or DEFAULT_OUT_DIR),
                    "operator_fields_prefilled": 0,
                    "blank_operator_fields": list(BLANK_OPERATOR_FIELDS),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    payload = build_payload(args.fill_queue_csv, args.bundle_pack_root, args.bundle)
    write_outputs(payload, args.out_dir)
    print(json.dumps({k: v for k, v in payload.items() if k != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
