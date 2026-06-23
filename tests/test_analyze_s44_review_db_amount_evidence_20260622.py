import csv
import importlib.util
import sqlite3
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "analyze_s44_review_db_amount_evidence_20260622.py"
    spec = importlib.util.spec_from_file_location(
        "analyze_s44_review_db_amount_evidence_20260622",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_aid_csv(path: Path) -> None:
    rows = [
        {
            "review_bucket": "AMOUNT_MATCH_QUICK_REVIEW",
            "operation_id": "op-1",
            "vendor_name": "Vendor A",
            "amount_estimate": "1,000",
            "filename_amount": "1000",
            "filename": "op-1_Vendor A_202606_1000.pdf",
            "pdf_path": str(path.parent / "missing.pdf"),
            "pdf_exists": "NO",
        },
        {
            "review_bucket": "AMOUNT_ZERO_REVIEW",
            "operation_id": "op-2",
            "vendor_name": "Vendor B",
            "amount_estimate": "0",
            "filename_amount": "220",
            "filename": "op-2_Vendor B_202606_220.pdf",
            "pdf_path": str(path.parent / "missing2.pdf"),
            "pdf_exists": "NO",
        },
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_review_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        create table queue_items (
            operation_id text primary key,
            filename text,
            vendor_name text,
            amounts_json text,
            ocr_confidence real,
            state text,
            current_state text
        )
        """
    )
    connection.executemany(
        """
        insert into queue_items (
            operation_id,
            filename,
            vendor_name,
            amounts_json,
            ocr_confidence,
            state,
            current_state
        )
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "op-1",
                "op-1_Vendor A_202606_1000.pdf",
                "Vendor A",
                '[{"amount": 1000, "note": null}]',
                0.95,
                "pending",
                "classified_auto",
            ),
            (
                "op-2",
                "op-2_Vendor B_202606_220.pdf",
                "Vendor B",
                '[{"amount": 220, "note": null}]',
                0.95,
                "pending",
                "classified_auto",
            ),
        ],
    )
    connection.commit()
    connection.close()


def test_parse_amount_accepts_yen_and_commas() -> None:
    module = load_module()

    assert module.parse_amount("￥1,234円") == 1234
    assert module.parse_amount("bad") is None


def test_sum_amounts_json_totals_valid_amount_lines() -> None:
    module = load_module()

    assert module.sum_amounts_json('[{"amount": 100}, {"amount": "200"}]') == 300
    assert module.sum_amounts_json("not-json") is None


def test_build_payload_keeps_business_review_required_and_counts_diff(tmp_path: Path) -> None:
    module = load_module()
    aid_csv = tmp_path / "aid.csv"
    review_db = tmp_path / "review.db"
    write_aid_csv(aid_csv)
    write_review_db(review_db)

    payload = module.build_payload(
        aid_csv,
        review_db,
        tmp_path / "out",
        inspect_pdf_text=False,
    )

    assert payload["evidence_row_count"] == 2
    assert payload["review_db_operation_match_count"] == 2
    assert payload["filename_vs_review_db_match_count"] == 2
    assert payload["source_estimate_vs_review_db_diff_count"] == 1
    assert payload["business_review_required_count"] == 2
    assert payload["amount_evidence_status_counts"] == {
        "DB_FILENAME_MATCH_SOURCE_ESTIMATE_DIFFERS": 1,
        "DB_FILENAME_SOURCE_AMOUNT_MATCH": 1,
    }
    assert all(row["still_requires_business_review"] == "YES" for row in payload["rows"])


def test_write_outputs_creates_csv_json_markdown_numbered(tmp_path: Path) -> None:
    module = load_module()
    aid_csv = tmp_path / "aid.csv"
    review_db = tmp_path / "review.db"
    out_dir = tmp_path / "out"
    write_aid_csv(aid_csv)
    write_review_db(review_db)
    payload = module.build_payload(aid_csv, review_db, out_dir, inspect_pdf_text=False)

    module.write_outputs(payload, out_dir)

    assert (out_dir / "s44_review_db_amount_evidence.csv").exists()
    assert (out_dir / "s44_review_db_amount_evidence.json").exists()
    assert (out_dir / "s44_review_db_amount_evidence.md").exists()
    assert (out_dir / "s44_review_db_amount_evidence.md.numbered").exists()
