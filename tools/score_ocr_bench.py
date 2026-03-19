"""Automated OCR benchmark scoring against golden dataset."""

import argparse
import json
import logging
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from vendor_matching import (
    canonicalize_vendor,
    infer_vendor_from_sender_context,
    normalize_vendor_key,
    vendor_match_equal,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def normalize_vendor(v: str) -> str:
    """Normalize vendor name for fuzzy matching."""
    return normalize_vendor_key(v, strip_company_tokens=False)


def normalize_bench_date(value: str | None) -> str | None:
    normalized = unicodedata.normalize("NFKC", value or "")
    digits = re.sub(r"\D", "", normalized)
    if len(digits) == 8 and digits.startswith("20"):
        try:
            datetime.strptime(digits, "%Y%m%d")
            return digits
        except ValueError:
            return None
    if len(digits) == 9:
        today = datetime.now().date()
        candidates: list[tuple[int, int, str]] = []
        for idx in range(9):
            cand = normalize_bench_date(digits[:idx] + digits[idx + 1 :])
            if not cand:
                continue
            cand_date = datetime.strptime(cand, "%Y%m%d").date()
            future_penalty = 0 if cand_date <= today else 1
            candidates.append((future_penalty, abs((today - cand_date).days), cand))
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1], item[2]))
            return candidates[0][2]
    if len(digits) == 7 and digits.startswith("20"):
        try:
            year = int(digits[:4])
            month = int(digits[4:5])
            day = int(digits[5:7])
            datetime(year, month, day)
            return f"{year:04d}{month:02d}{day:02d}"
        except ValueError:
            return None
    if len(digits) == 6:
        try:
            year = 2000 + int(digits[:2])
            month = int(digits[2:4])
            day = int(digits[4:6])
            datetime(year, month, day)
            return f"{year:04d}{month:02d}{day:02d}"
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def score_vendor(
    predicted: str | None,
    expected: str,
    *,
    sender: str | None = None,
    subject: str | None = None,
    filename: str | None = None,
) -> tuple[bool | None, str]:
    """Vendor match - fuzzy matching."""
    if not expected:
        return False, "missing_expected"

    context_text = " ".join(v for v in (subject, filename) if v)
    normalized_pred = (
        canonicalize_vendor(predicted, sender=sender, context_text=context_text, drop_non_vendor=False)
        if predicted
        else None
    )
    if not normalized_pred and sender:
        sender_match = infer_vendor_from_sender_context(
            sender=sender,
            subject=subject,
            attachment_name=filename,
            context_text=context_text,
        )
        normalized_pred = sender_match.canonical

    if normalized_pred is not None:
        predicted = normalized_pred
    return vendor_match_equal(predicted, expected)


def score_date(predicted: str | None, expected: str) -> tuple[bool, str]:
    """Date match - exact 8-digit match."""
    if not predicted:
        return False, "missing"
    # Strip non-digits for robustness
    pred_clean = normalize_bench_date(predicted)
    exp_clean = normalize_bench_date(expected)
    if not exp_clean:
        return False, "invalid_expected"
    if not pred_clean:
        return False, "invalid_predicted"
    if pred_clean == exp_clean:
        return True, "exact"
    return False, "mismatch"


def score_amount(
    predicted: str | None,
    expected: str,
    *,
    tolerance_ratio: float | None = 0.1,
) -> tuple[bool, str]:
    """Amount match - numeric comparison with 10% tolerance."""
    if not predicted:
        return False, "missing"
    try:
        pred_val = int(re.sub(r"[^0-9]", "", predicted))
        exp_val = int(re.sub(r"[^0-9]", "", expected))
        if pred_val == exp_val:
            return True, "exact"
        ratio = pred_val / exp_val if exp_val > 0 else 0
        if tolerance_ratio is not None and (1 - tolerance_ratio) <= ratio <= (1 + tolerance_ratio):
            return True, f"approx(10%)"
        return False, f"mismatch({pred_val} vs {exp_val})"
    except ValueError:
        return False, "parse_error"


# ---------------------------------------------------------------------------
# Result parsing (from existing markdown benchmark output)
# ---------------------------------------------------------------------------

def parse_results_markdown(md_path: Path) -> list[dict]:
    """Parse a markdown benchmark result table into a list of dicts.

    Expected table columns (pipe-separated):
        | # | File | Vendor | Date | Amount | Invoice No | ...
    """
    text = md_path.read_text(encoding="utf-8")
    rows = []
    in_table = False
    header_indices: dict[str, int] = {}

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            in_table = False
            continue

        cells = [c.strip() for c in line.split("|")]
        # Remove empty first/last from leading/trailing pipes
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]

        if not cells:
            continue

        # Detect header row
        if not in_table and any(k in cells[0].lower() for k in ["#", "id", "no"]):
            for i, c in enumerate(cells):
                cl = c.lower().strip()
                if cl in ("#", "id", "no"):
                    header_indices["id"] = i
                elif "file" in cl:
                    header_indices["filename"] = i
                elif "vendor" in cl:
                    header_indices["vendor"] = i
                elif "date" in cl:
                    header_indices["date"] = i
                elif "amount" in cl:
                    header_indices["amount"] = i
                elif "invoice" in cl:
                    header_indices["invoice_no"] = i
            in_table = True
            continue

        # Skip separator row
        if in_table and all(set(c.strip()) <= {"-", ":"} for c in cells):
            continue

        if in_table and header_indices:
            row: dict = {}
            for key, idx in header_indices.items():
                if idx < len(cells):
                    val = cells[idx].strip()
                    if val in ("", "-", "null", "None"):
                        val = None
                    row[key] = val
            if row.get("id"):
                rows.append(row)

    log.info("Parsed %d result rows from %s", len(rows), md_path)
    return rows


def parse_results_jsonl(jsonl_path: Path) -> list[dict]:
    """Parse JSONL benchmark results into the scorer input shape."""
    rows = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        rows.append(
            {
                "id": str(item.get("id") or ""),
                "filename": item.get("filename"),
                "vendor": item.get("vendor"),
                "date": item.get("issue_date") or item.get("date"),
                "amount": item.get("amount"),
                "invoice_no": item.get("invoice_no"),
                "error": item.get("error"),
                "sender": item.get("sender"),
                "subject": item.get("subject"),
            }
        )

    log.info("Parsed %d result rows from %s", len(rows), jsonl_path)
    return rows


# ---------------------------------------------------------------------------
# Vision OCR execution (thin wrapper)
# ---------------------------------------------------------------------------

def run_vision_ocr(provider: str, golden: list[dict], pdf_dir: Path | None) -> list[dict]:
    """Run vision_ocr.extract() on each golden entry and return results."""
    try:
        # vision_ocr.py is expected in the same directory
        tools_dir = Path(__file__).parent
        sys.path.insert(0, str(tools_dir))
        from vision_ocr import extract  # type: ignore
    except ImportError:
        log.error("vision_ocr.py not found in %s. Use --results instead.", tools_dir)
        sys.exit(1)

    results = []
    for entry in golden:
        filename = entry["filename"]
        if pdf_dir:
            pdf_path = pdf_dir / filename
        else:
            pdf_path = Path(filename)

        log.info("Processing #%d: %s", entry["id"], filename[:60])
        try:
            result = extract(str(pdf_path), provider=provider)
            # Support both dict and dataclass (VisionOcrResult) return types
            _get = (lambda k, d=None: result.get(k, d)) if hasattr(result, "get") else (lambda k, d=None: getattr(result, k, d))
            results.append({
                "id": str(entry["id"]),
                "filename": filename,
                "vendor": _get("vendor"),
                "date": _get("issue_date"),
                "amount": str(_get("amount", "")) if _get("amount") else None,
                "invoice_no": _get("invoice_no"),
            })
        except Exception as e:
            log.warning("#%d: extract failed: %s", entry["id"], e)
            results.append({
                "id": str(entry["id"]),
                "filename": filename,
                "vendor": None,
                "date": None,
                "amount": None,
                "invoice_no": None,
                "error": str(e),
            })
    return results


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def score_all(golden: list[dict], results: list[dict]) -> list[dict]:
    """Score each result against golden dataset. Returns scored rows."""
    # Index results by filename (partial match - result filename may be truncated)
    result_by_filename: dict[str, dict] = {}
    for r in results:
        fname = r.get("filename", "")
        if fname:
            result_by_filename[fname] = r

    def _find_result(golden_filename: str) -> dict:
        """Find result matching golden filename. Supports partial/truncated matching."""
        # Exact match
        if golden_filename in result_by_filename:
            return result_by_filename[golden_filename]
        # Partial match (result filename may be truncated by markdown table)
        for rfname, rdata in result_by_filename.items():
            if golden_filename.startswith(rfname) or rfname.startswith(golden_filename):
                return rdata
        # Fallback: substring match
        for rfname, rdata in result_by_filename.items():
            if golden_filename[:30] in rfname or rfname[:30] in golden_filename:
                return rdata
        return {}

    scored = []
    for g in golden:
        gid = str(g["id"])
        r = _find_result(g["filename"])

        row: dict = {"id": gid, "filename": g["filename"]}

        # Vendor
        if g.get("skip_vendor_scoring"):
            v_ok, v_detail = None, "skipped"
        else:
            v_ok, v_detail = score_vendor(
                r.get("vendor"),
                g["vendor"],
                sender=r.get("sender"),
                subject=r.get("subject"),
                filename=g["filename"],
            )
        row["vendor_ok"] = v_ok
        row["vendor_detail"] = v_detail
        row["vendor_pred"] = r.get("vendor", "")
        row["vendor_exp"] = g["vendor"]

        # Date
        normalized_expected_date = normalize_bench_date(g.get("issue_date"))
        if not normalized_expected_date:
            row["date_ok"] = None  # skip
            row["date_detail"] = "skipped(invalid)"
        else:
            d_ok, d_detail = score_date(r.get("date"), normalized_expected_date)
            row["date_ok"] = d_ok
            row["date_detail"] = d_detail
        row["date_pred"] = r.get("date", "")
        row["date_exp"] = normalized_expected_date or g.get("issue_date")

        # Amount
        a_ok, a_detail = score_amount(r.get("amount"), g["amount"], tolerance_ratio=0.0)
        row["amount_ok"] = a_ok
        row["amount_detail"] = a_detail
        row["amount_pred"] = r.get("amount", "")
        row["amount_exp"] = g["amount"]

        # Amount approx (separate flag for +-10%)
        a2_ok, _ = score_amount(r.get("amount"), g["amount"], tolerance_ratio=0.1)
        row["amount_approx"] = a2_ok

        # Error
        row["error"] = r.get("error", "")

        scored.append(row)

    return scored


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(scored: list[dict], provider: str, golden_path: str) -> str:
    """Generate markdown scoring report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(scored)

    vendor_scorable = [s for s in scored if s["vendor_ok"] is not None]
    vendor_ok = sum(1 for s in vendor_scorable if s["vendor_ok"])
    vendor_total = len(vendor_scorable)
    date_scorable = [s for s in scored if s["date_ok"] is not None]
    date_ok = sum(1 for s in date_scorable if s["date_ok"])
    date_total = len(date_scorable)
    amount_exact = sum(1 for s in scored if s["amount_ok"] and "exact" in s["amount_detail"])
    amount_approx = sum(1 for s in scored if s["amount_approx"])

    def pct(n: int, d: int) -> str:
        return f"{n / d * 100:.1f}%" if d > 0 else "N/A"

    lines = [
        f"# OCR Benchmark Scoring Report",
        f"Date: {now}",
        f"Golden dataset: {Path(golden_path).stem} ({total} entries)",
        f"Provider: {provider}",
        "",
        "## Summary",
        "| Metric | Score | Rate |",
        "|--------|-------|------|",
        f"| Vendor (exact+fuzzy) | {vendor_ok}/{vendor_total} | {pct(vendor_ok, vendor_total)} |",
        f"| Date | {date_ok}/{date_total} | {pct(date_ok, date_total)} |",
        f"| Amount (exact) | {amount_exact}/{total} | {pct(amount_exact, total)} |",
        f"| Amount (+-10%) | {amount_approx}/{total} | {pct(amount_approx, total)} |",
        "",
        "## Detail",
        "| # | File | Vendor | Date | Amount | Notes |",
        "|---|------|--------|------|--------|-------|",
    ]

    errors = []
    for s in scored:
        short_file = s["filename"][:50] + "..." if len(s["filename"]) > 50 else s["filename"]

        # Vendor cell
        if s["vendor_ok"] is None:
            v_cell = "SKIP"
        elif s["vendor_ok"]:
            v_cell = f"OK {s['vendor_detail']}"
        else:
            v_cell = f"NG {s['vendor_detail']}"
            if s["vendor_pred"]:
                v_cell += f" (got: {s['vendor_pred']}, exp: {s['vendor_exp']})"

        # Date cell
        if s["date_ok"] is None:
            d_cell = "SKIP (invalid date)"
        elif s["date_ok"]:
            d_cell = f"OK {s['date_detail']}"
        else:
            d_cell = f"NG {s['date_detail']}"
            if s["date_pred"]:
                d_cell += f" (got: {s['date_pred']}, exp: {s['date_exp']})"

        # Amount cell
        if s["amount_ok"]:
            a_cell = f"OK {s['amount_detail']}"
        else:
            a_cell = f"NG {s['amount_detail']}"

        notes = s.get("error", "")
        lines.append(f"| {s['id']} | {short_file} | {v_cell} | {d_cell} | {a_cell} | {notes} |")

        # Collect errors for summary
        error_parts = []
        if s["vendor_ok"] is False:
            error_parts.append(f"vendor {s['vendor_detail']}")
        if s["date_ok"] is not None and not s["date_ok"]:
            error_parts.append(f"date {s['date_detail']}")
        if not s["amount_ok"]:
            error_parts.append(f"amount {s['amount_detail']}")
        if s.get("error"):
            error_parts.append(f"API error ({s['error']})")
        if error_parts:
            errors.append(f"- #{s['id']}: {', '.join(error_parts)}")

    lines.append("")
    lines.append("## Errors")
    if errors:
        lines.extend(errors)
    else:
        lines.append("No errors.")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Score OCR benchmark results against golden dataset."
    )
    parser.add_argument(
        "--golden", required=True,
        help="Path to golden_dataset_v1.json"
    )
    parser.add_argument(
        "--results",
        help="Path to existing benchmark result file (.md table or .jsonl) (skip OCR execution)"
    )
    parser.add_argument(
        "--provider", default="auto",
        help="Vision OCR provider (e.g., gpt-4o, gemini, claude, auto)"
    )
    parser.add_argument(
        "--pdf-dir",
        help="Directory containing PDF files (for --provider mode)"
    )
    parser.add_argument(
        "--output",
        help="Output path for scoring report markdown (default: stdout)"
    )
    args = parser.parse_args()

    # Load golden dataset
    golden_path = Path(args.golden)
    if not golden_path.exists():
        log.error("Golden dataset not found: %s", golden_path)
        sys.exit(1)
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    log.info("Loaded %d golden entries from %s", len(golden), golden_path)

    # Get results
    if args.results:
        results_path = Path(args.results)
        if not results_path.exists():
            log.error("Results file not found: %s", results_path)
            sys.exit(1)
        if results_path.suffix.lower() == ".jsonl":
            results = parse_results_jsonl(results_path)
        else:
            results = parse_results_markdown(results_path)
    else:
        pdf_dir = Path(args.pdf_dir) if args.pdf_dir else None
        results = run_vision_ocr(args.provider, golden, pdf_dir)

    if not results:
        log.error("No results to score.")
        sys.exit(1)

    # Score
    scored = score_all(golden, results)

    # Generate report
    provider_label = args.provider if not args.results else Path(args.results).stem
    report = generate_report(scored, provider_label, str(golden_path))

    # Output
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        log.info("Report written to %s", out_path)
    else:
        print(report)


if __name__ == "__main__":
    main()
