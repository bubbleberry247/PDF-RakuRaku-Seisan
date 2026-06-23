"""Run Scenario 70 sample confirm-preview validation without payment execution.

This tool builds sample payment-confirm records, reuses the existing Scenario
70 classification and expectation gates, and writes report artifacts only. It
does not open Rakuraku, press confirmation OK, send mail, run RK10, access bank
systems, or write production/shared folders.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
TOOLS_DIR = ROOT / "tools"
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "s70_sample_confirm_preview_20260620"
DEFAULT_PAYMENT_DATE = "2026/02/27"
DEFAULT_TRANSFER_SOURCE = "三菱UFJ銀行（当座）/110"
EXPECTED_COUNT = 2
EXPECTED_TOTAL_AMOUNT_YEN = 12_345 + 67_890

sys.path.insert(0, str(TOOLS_DIR))
from rakuraku_payment_confirm import (  # noqa: E402
    SlipRecord,
    classify_slip_record,
    parse_slip_block_texts,
    validate_selection_expectations,
)


@dataclass(frozen=True)
class SampleConfirmPreviewResult:
    generated_at: str
    status: str
    payment_date: str
    transfer_source: str
    inventory_records: int
    selected_records: int
    anomaly_records: int
    manual_excluded_records: int
    expected_count: int
    expected_total_amount_yen: int
    selected_total_amount_yen: int
    confirmation_ok_pressed: bool
    payment_execute_performed: bool
    mail_sent: bool
    rk10_button_run: bool
    selected_csv: str
    inventory_csv: str
    anomaly_csv: str
    manual_excluded_csv: str
    next_action: str


def build_sample_inventory(payment_date: str) -> list[SlipRecord]:
    records = [
        parse_slip_block_texts(
            row1_text=f"00027001\n東海インプル建設株式会社\n経理 太郎\n2026/02/01\n2026/02/02\n12,345\n{payment_date}\n保存不要",
            row2_text="サンプル建材株式会社",
            row3_text="材料費 サンプル1\n当方負担",
            checkbox_name="kakutei(27001)",
            page_no=1,
            row_group_index=1,
        ),
        parse_slip_block_texts(
            row1_text=f"00027002\n東海インプル建設株式会社\n経理 花子\n2026/02/03\n2026/02/04\n67,890\n{payment_date}\n保存不要",
            row2_text="サンプル設備株式会社",
            row3_text="設備費 サンプル2\n当方負担",
            checkbox_name="kakutei(27002)",
            page_no=1,
            row_group_index=2,
        ),
        parse_slip_block_texts(
            row1_text=f"00027003\n東海インプル建設株式会社\n経理 次郎\n2026/02/05\n2026/02/06\n5,000\n{payment_date}\n保存不要",
            row2_text="サンプルリース株式会社",
            row3_text="リース料 サンプル3\n当方負担",
            checkbox_name="kakutei(27003)",
            page_no=1,
            row_group_index=3,
        ),
    ]
    return [
        record if index < 2 else record.__class__(**{**asdict(record), "payment_method": "口座振替", "payment_method_source": "sample_detail"})
        for index, record in enumerate(
            [
                record.__class__(**{**asdict(record), "payment_method": "総合振込", "payment_method_source": "sample_detail"})
                for record in records
            ]
        )
    ]


def classify_records(records: Iterable[SlipRecord], payment_date: str) -> tuple[list[SlipRecord], list[SlipRecord], list[SlipRecord]]:
    selected: list[SlipRecord] = []
    anomalies: list[SlipRecord] = []
    manual_excluded: list[SlipRecord] = []
    for record in records:
        classified = classify_slip_record(record, payment_date)
        if classified.decision == "selected":
            selected.append(classified)
        elif classified.decision == "anomaly":
            anomalies.append(classified)
        elif classified.decision == "manual_excluded":
            manual_excluded.append(classified)
    return selected, anomalies, manual_excluded


def record_to_row(record: SlipRecord) -> dict[str, object]:
    return {
        "page_no": record.page_no,
        "row_group_index": record.row_group_index,
        "slip_no": record.slip_no,
        "request_date": record.request_date or "",
        "approval_date": record.approval_date or "",
        "requested_payment_date": record.payment_date,
        "vendor": record.vendor or "",
        "amount_yen": record.amount_yen or 0,
        "fee_burden": record.fee_burden or "",
        "payment_method": record.payment_method or "",
        "decision": record.decision,
        "decision_reason": record.decision_reason,
        "checkbox_name": record.checkbox_name or "",
        "raw_text": record.raw_text,
    }


def write_csv(path: Path, records: list[SlipRecord]) -> None:
    fieldnames = [
        "page_no",
        "row_group_index",
        "slip_no",
        "request_date",
        "approval_date",
        "requested_payment_date",
        "vendor",
        "amount_yen",
        "fee_burden",
        "payment_method",
        "decision",
        "decision_reason",
        "checkbox_name",
        "raw_text",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record_to_row(record))


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def build_markdown(result: SampleConfirmPreviewResult) -> str:
    return "\n".join(
        [
            "# Scenario 70 sample confirm-preview",
            "",
            f"- generated_at: `{result.generated_at}`",
            f"- status: `{result.status}`",
            f"- payment_date: `{result.payment_date}`",
            f"- transfer_source: `{result.transfer_source}`",
            f"- inventory_records: `{result.inventory_records}`",
            f"- selected_records: `{result.selected_records}`",
            f"- anomaly_records: `{result.anomaly_records}`",
            f"- manual_excluded_records: `{result.manual_excluded_records}`",
            f"- expected_count: `{result.expected_count}`",
            f"- expected_total_amount_yen: `{result.expected_total_amount_yen}`",
            f"- selected_total_amount_yen: `{result.selected_total_amount_yen}`",
            f"- confirmation_ok_pressed: `{result.confirmation_ok_pressed}`",
            f"- payment_execute_performed: `{result.payment_execute_performed}`",
            f"- mail_sent: `{result.mail_sent}`",
            f"- rk10_button_run: `{result.rk10_button_run}`",
            f"- selected_csv: `{result.selected_csv}`",
            f"- inventory_csv: `{result.inventory_csv}`",
            f"- anomaly_csv: `{result.anomaly_csv}`",
            f"- manual_excluded_csv: `{result.manual_excluded_csv}`",
            f"- next_action: {result.next_action}",
            "",
            "## Safety",
            "",
            "- This is a local sample validation only.",
            "- Rakuraku is not opened.",
            "- Confirmation dialog OK is not pressed.",
            "- Payment execution, mail, RK10 ButtonRun, bank upload, and production writes are not executed.",
        ]
    ) + "\n"


def run_sample_confirm_preview(out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    inventory = build_sample_inventory(DEFAULT_PAYMENT_DATE)
    selected, anomalies, manual_excluded = classify_records(inventory, DEFAULT_PAYMENT_DATE)
    selected_total = validate_selection_expectations(
        selected,
        expected_count=EXPECTED_COUNT,
        expected_total_amount_yen=EXPECTED_TOTAL_AMOUNT_YEN,
    )
    inventory_csv = out_dir / "full_inventory.csv"
    selected_csv = out_dir / "selected_candidates.csv"
    anomaly_csv = out_dir / "anomaly.csv"
    manual_excluded_csv = out_dir / "manual_excluded.csv"
    write_csv(inventory_csv, inventory)
    write_csv(selected_csv, selected)
    write_csv(anomaly_csv, anomalies)
    write_csv(manual_excluded_csv, manual_excluded)
    result = SampleConfirmPreviewResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        status="CONFIRM_PREVIEW_SAMPLE_OK",
        payment_date=DEFAULT_PAYMENT_DATE,
        transfer_source=DEFAULT_TRANSFER_SOURCE,
        inventory_records=len(inventory),
        selected_records=len(selected),
        anomaly_records=len(anomalies),
        manual_excluded_records=len(manual_excluded),
        expected_count=EXPECTED_COUNT,
        expected_total_amount_yen=EXPECTED_TOTAL_AMOUNT_YEN,
        selected_total_amount_yen=selected_total,
        confirmation_ok_pressed=False,
        payment_execute_performed=False,
        mail_sent=False,
        rk10_button_run=False,
        selected_csv=str(selected_csv),
        inventory_csv=str(inventory_csv),
        anomaly_csv=str(anomaly_csv),
        manual_excluded_csv=str(manual_excluded_csv),
        next_action="Use real approved count/amount for live confirm-preview; keep --execute as a separate gate.",
    )
    payload = asdict(result)
    json_path = out_dir / "s70_sample_confirm_preview.json"
    md_path = out_dir / "s70_sample_confirm_preview.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(result), encoding="utf-8")
    write_numbered_copy(json_path)
    write_numbered_copy(md_path)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Scenario 70 local sample confirm-preview validation.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_sample_confirm_preview(args.out_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "CONFIRM_PREVIEW_SAMPLE_OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
