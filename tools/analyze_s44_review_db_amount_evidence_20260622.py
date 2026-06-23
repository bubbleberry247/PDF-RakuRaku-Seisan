"""Build read-only Scenario 44 review DB amount evidence.

This tool compares the Scenario 44 business-review aid CSV against the current
review.db queue_items amounts. It never updates the live review database, source
CSV, handoff files, Rakuraku, mail, printers, RK10, or production state.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan")
DEFAULT_AID_CSV = (
    ROOT
    / "plans"
    / "reports"
    / "s44_spot_check_handoff_candidates_20260620"
    / "s44_business_review_aid.csv"
)
DEFAULT_REVIEW_DB = (
    Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請")
    / "state"
    / "review.db"
)
DEFAULT_OUT_DIR = ROOT / "plans" / "reports" / "s44_review_db_amount_evidence_20260622"
SAFETY_TEXT = (
    "read-only review.db and PDF text-layer inspection only; no source CSV write, "
    "live review.db update, live handoff, Rakuraku operation, PDF processed move, "
    "mail, print, RK10 ButtonRun, payment, submit, or production write"
)


@dataclass(frozen=True)
class EvidenceRow:
    operation_id: str
    review_bucket: str
    vendor_name: str
    filename: str
    pdf_path: str
    pdf_exists: str
    pdf_text_status: str
    pdf_amount_candidates: str
    source_amount_estimate: str
    filename_amount: str
    review_db_amount_total: str
    review_db_amounts_json: str
    review_db_ocr_confidence: str
    review_db_state: str
    review_db_current_state: str
    amount_evidence_status: str
    source_estimate_vs_review_db: str
    filename_vs_review_db: str
    still_requires_business_review: str
    operator_review_hint: str


def normalize(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_amount(value: object) -> int | None:
    text = normalize(value)
    if not text:
        return None
    cleaned = re.sub(r"[,，\s円¥￥]", "", text)
    if not re.fullmatch(r"-?\d+", cleaned):
        return None
    return int(cleaned)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else list(EvidenceRow.__dataclass_fields__)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_numbered_copy(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_text = "\n".join(f"{index:5}: {line}" for index, line in enumerate(lines, 1))
    Path(str(path) + ".numbered").write_text(numbered_text + "\n", encoding="utf-8")


def sum_amounts_json(value: object) -> int | None:
    text = normalize(value)
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None
    total = 0
    found = False
    for item in payload:
        if not isinstance(item, dict):
            continue
        amount = parse_amount(item.get("amount"))
        if amount is None:
            continue
        total += amount
        found = True
    return total if found else None


def extract_amount_candidates(text: str) -> list[int]:
    candidates: set[int] = set()
    patterns = [
        r"(?:合計|総合計|請求金額|税込|金額)[^\d]{0,12}(\d{1,3}(?:[,，]\d{3})+|\d{3,9})",
        r"(?:¥|￥)\s*(\d{1,3}(?:[,，]\d{3})+|\d{3,9})",
        r"(?<!\d)(\d{1,3}(?:[,，]\d{3})+|\d{4,9})(?!\d)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            amount = parse_amount(match.group(1))
            if amount is not None and amount >= 100:
                candidates.add(amount)
    return sorted(candidates)


def extract_pdf_text(path: Path, max_pages: int = 2) -> tuple[str, str]:
    if not path.exists():
        return "PDF_MISSING", ""
    try:
        from pypdf import PdfReader
    except ImportError:
        return "PYPDF_MISSING", ""
    try:
        reader = PdfReader(str(path))
        page_texts = [
            page.extract_text() or ""
            for page in reader.pages[:max_pages]
        ]
    except Exception:
        return "PDF_TEXT_READ_ERROR", ""
    text = "\n".join(page_texts).strip()
    if not text:
        return "NO_TEXT_LAYER", ""
    return "TEXT_EXTRACTED", text


def connect_review_db_read_only(path: Path) -> sqlite3.Connection:
    uri = "file:" + path.as_posix() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def load_review_db_rows(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with connect_review_db_read_only(path) as connection:
        rows = connection.execute(
            """
            select
                operation_id,
                filename,
                vendor_name,
                amounts_json,
                ocr_confidence,
                state,
                current_state
            from queue_items
            """
        ).fetchall()
    return {normalize(row["operation_id"]): dict(row) for row in rows}


def compare_amount(left: int | None, right: int | None) -> str:
    if left is None or right is None:
        return "UNCOMPARABLE"
    if left == right:
        return "MATCH"
    return f"DIFF:{left - right}"


def classify_amount_evidence(
    source_amount: int | None,
    filename_amount: int | None,
    review_db_amount: int | None,
    db_found: bool,
) -> tuple[str, str]:
    if not db_found:
        return (
            "REVIEW_DB_ROW_MISSING",
            "Open the PDF and source row manually; no review.db row was found.",
        )
    if review_db_amount is None:
        return (
            "REVIEW_DB_AMOUNT_MISSING",
            "Open the PDF manually; review.db has no parsable amount total.",
        )
    if review_db_amount == filename_amount == source_amount:
        return (
            "DB_FILENAME_SOURCE_AMOUNT_MATCH",
            "Fast review candidate: review.db, filename, and source estimate agree; human OK/NG is still required.",
        )
    if review_db_amount == filename_amount and review_db_amount != source_amount:
        return (
            "DB_FILENAME_MATCH_SOURCE_ESTIMATE_DIFFERS",
            "Use review.db amount and filename amount as supporting evidence, then confirm the PDF/business meaning before OK/NG.",
        )
    if review_db_amount != filename_amount:
        return (
            "DB_AMOUNT_DIFFERS_FROM_FILENAME",
            "High-risk review: compare PDF, review.db, and filename before any OK/NG.",
        )
    return (
        "AMOUNT_EVIDENCE_UNCLEAR",
        "Open the PDF and review all available amount evidence before OK/NG.",
    )


def build_evidence_rows(
    aid_rows: list[dict[str, str]],
    review_db_rows: dict[str, dict[str, Any]],
    inspect_pdf_text: bool = True,
) -> list[EvidenceRow]:
    evidence_rows: list[EvidenceRow] = []
    for row in aid_rows:
        operation_id = normalize(row.get("operation_id"))
        db_row = review_db_rows.get(operation_id)
        db_found = db_row is not None
        source_amount = parse_amount(row.get("amount_estimate"))
        filename_amount = parse_amount(row.get("filename_amount"))
        review_db_amount = sum_amounts_json(db_row.get("amounts_json")) if db_row else None
        pdf_path = normalize(row.get("pdf_path"))
        pdf_text_status = "PDF_TEXT_NOT_INSPECTED"
        pdf_amount_candidates: list[int] = []
        if inspect_pdf_text and pdf_path:
            pdf_text_status, pdf_text = extract_pdf_text(Path(pdf_path))
            if pdf_text:
                pdf_amount_candidates = extract_amount_candidates(pdf_text)
        status, review_hint = classify_amount_evidence(
            source_amount,
            filename_amount,
            review_db_amount,
            db_found,
        )
        evidence_rows.append(
            EvidenceRow(
                operation_id=operation_id,
                review_bucket=normalize(row.get("review_bucket")),
                vendor_name=normalize(row.get("vendor_name")),
                filename=normalize(row.get("filename")),
                pdf_path=pdf_path,
                pdf_exists=normalize(row.get("pdf_exists")),
                pdf_text_status=pdf_text_status,
                pdf_amount_candidates=";".join(str(value) for value in pdf_amount_candidates),
                source_amount_estimate=normalize(row.get("amount_estimate")),
                filename_amount=normalize(row.get("filename_amount")),
                review_db_amount_total="" if review_db_amount is None else str(review_db_amount),
                review_db_amounts_json=normalize(db_row.get("amounts_json")) if db_row else "",
                review_db_ocr_confidence=normalize(db_row.get("ocr_confidence")) if db_row else "",
                review_db_state=normalize(db_row.get("state")) if db_row else "",
                review_db_current_state=normalize(db_row.get("current_state")) if db_row else "",
                amount_evidence_status=status,
                source_estimate_vs_review_db=compare_amount(source_amount, review_db_amount),
                filename_vs_review_db=compare_amount(filename_amount, review_db_amount),
                still_requires_business_review="YES",
                operator_review_hint=review_hint,
            )
        )
    return evidence_rows


def build_payload(
    aid_csv: Path,
    review_db: Path,
    out_dir: Path,
    inspect_pdf_text: bool = True,
) -> dict[str, Any]:
    aid_rows = read_csv_rows(aid_csv)
    review_db_rows = load_review_db_rows(review_db)
    evidence_rows = build_evidence_rows(aid_rows, review_db_rows, inspect_pdf_text)
    status_counts = Counter(row.amount_evidence_status for row in evidence_rows)
    bucket_counts = Counter(row.review_bucket for row in evidence_rows)
    pdf_text_counts = Counter(row.pdf_text_status for row in evidence_rows)
    source_diff_count = sum(
        1 for row in evidence_rows if row.source_estimate_vs_review_db.startswith("DIFF:")
    )
    filename_match_count = sum(
        1 for row in evidence_rows if row.filename_vs_review_db == "MATCH"
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_goal_complete": False,
        "safety": SAFETY_TEXT,
        "aid_csv": str(aid_csv),
        "review_db": str(review_db),
        "out_dir": str(out_dir),
        "aid_row_count": len(aid_rows),
        "evidence_row_count": len(evidence_rows),
        "review_db_operation_match_count": sum(
            1 for row in evidence_rows if row.amount_evidence_status != "REVIEW_DB_ROW_MISSING"
        ),
        "filename_vs_review_db_match_count": filename_match_count,
        "source_estimate_vs_review_db_diff_count": source_diff_count,
        "business_review_required_count": len(evidence_rows),
        "amount_evidence_status_counts": dict(sorted(status_counts.items())),
        "review_bucket_counts": dict(sorted(bucket_counts.items())),
        "pdf_text_status_counts": dict(sorted(pdf_text_counts.items())),
        "evidence_csv": str(out_dir / "s44_review_db_amount_evidence.csv"),
        "rows": [asdict(row) for row in evidence_rows],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Scenario 44 review.db amount evidence 2026-06-22",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- overall_goal_complete: `{payload['overall_goal_complete']}`",
        f"- safety: `{payload['safety']}`",
        f"- aid_csv: `{payload['aid_csv']}`",
        f"- review_db: `{payload['review_db']}`",
        f"- evidence_csv: `{payload['evidence_csv']}`",
        f"- aid_row_count: `{payload['aid_row_count']}`",
        f"- evidence_row_count: `{payload['evidence_row_count']}`",
        f"- review_db_operation_match_count: `{payload['review_db_operation_match_count']}`",
        f"- filename_vs_review_db_match_count: `{payload['filename_vs_review_db_match_count']}`",
        f"- source_estimate_vs_review_db_diff_count: `{payload['source_estimate_vs_review_db_diff_count']}`",
        f"- business_review_required_count: `{payload['business_review_required_count']}`",
        "",
        "## Boundary",
        "",
        "- This report is supporting evidence only; it never enters OK/NG.",
        "- `still_requires_business_review=YES` for every row.",
        "- Text-layer PDF extraction is opportunistic; image PDFs can show `NO_TEXT_LAYER` and still require review.",
        "",
        "## Amount Evidence Status",
        "",
    ]
    status_counts = payload["amount_evidence_status_counts"]
    assert isinstance(status_counts, dict)
    for status, count in status_counts.items():
        lines.append(f"- {status}: `{count}`")
    lines.extend(["", "## Review Buckets", ""])
    bucket_counts = payload["review_bucket_counts"]
    assert isinstance(bucket_counts, dict)
    for bucket, count in bucket_counts.items():
        lines.append(f"- {bucket}: `{count}`")
    lines.extend(["", "## PDF Text Status", ""])
    pdf_text_counts = payload["pdf_text_status_counts"]
    assert isinstance(pdf_text_counts, dict)
    for status, count in pdf_text_counts.items():
        lines.append(f"- {status}: `{count}`")
    lines.extend(
        [
            "",
            "## Operator Use",
            "",
            "- First sort the evidence CSV by `amount_evidence_status`.",
            "- Rows marked `DB_FILENAME_MATCH_SOURCE_ESTIMATE_DIFFERS` should be checked against PDF/business meaning before OK/NG; the mismatch is between the spot-check source estimate and current review.db/filename.",
            "- Rows marked `DB_FILENAME_SOURCE_AMOUNT_MATCH` are faster review candidates, but still require reviewer and reviewed_at before any handoff candidate is created.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    evidence_csv = out_dir / "s44_review_db_amount_evidence.csv"
    json_path = out_dir / "s44_review_db_amount_evidence.json"
    md_path = out_dir / "s44_review_db_amount_evidence.md"
    rows = payload["rows"]
    assert isinstance(rows, list)
    write_csv(evidence_csv, rows)
    json_payload = {**payload, "rows": rows}
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    write_numbered_copy(md_path)
    write_numbered_copy(json_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Scenario 44 review.db amount evidence.")
    parser.add_argument("--aid-csv", type=Path, default=DEFAULT_AID_CSV)
    parser.add_argument("--review-db", type=Path, default=DEFAULT_REVIEW_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--skip-pdf-text",
        action="store_true",
        help="Skip opportunistic pypdf text-layer inspection.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        args.aid_csv,
        args.review_db,
        args.out_dir,
        inspect_pdf_text=not args.skip_pdf_text,
    )
    write_outputs(payload, args.out_dir)
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
