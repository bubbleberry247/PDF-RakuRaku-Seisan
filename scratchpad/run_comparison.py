"""Comparison framework for OCR method evaluation.

Usage:
    python run_comparison.py --method 1 [--use-cache] [--filter KEYWORD]
    python run_comparison.py --method 1 --summary   # summary only (no OCR run)

Compares new methods against EasyOCR baseline (ocr_cache.json).
"""
import json, os, sys, re, glob, time, importlib, argparse, unicodedata
from dataclasses import dataclass, asdict
from typing import Optional

PDF_DIR = r"C:\ProgramData\RK10\Tools\PDF-Rename-Tool\2025年12月支払依頼サンプルPDF"
CACHE_FILE = os.path.join(os.path.dirname(__file__), "ocr_cache.json")
COMPARISON_CACHE = os.path.join(os.path.dirname(__file__), "comparison_cache_{method}.json")


# ── Expected-value loading (reused from run_regression.py) ──────────────


def parse_txt_rakuraku(txt_path):
    """Parse expected values from 楽楽精算 TXT export."""
    if not os.path.exists(txt_path):
        return {}
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    result = {}
    for line in lines:
        if line.startswith("支払先\t"):
            v = line.split("\t", 1)[1].strip()
            if v:
                result["vendor"] = v
                break

    in_table = False
    amounts = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "金額":
            in_table = True
            continue
        if in_table and stripped == "合計":
            for j in range(i + 1, min(i + 3, len(lines))):
                val = lines[j].strip().replace(",", "")
                if val.isdigit():
                    result["amount"] = val
                    break
            break
        if in_table and stripped.replace(",", "").isdigit():
            amounts.append(int(stripped.replace(",", "")))

    if "amount" not in result and amounts:
        result["amount"] = str(sum(amounts))

    return result


def parse_filename(fname):
    result = {}
    m = re.match(r'^(.+?)_(\d{8})_(\d[\d,]+)', fname)
    if m:
        result["fn_vendor"] = m.group(1)
        result["fn_date"] = m.group(2)
        result["fn_amount"] = m.group(3).replace(",", "")
    else:
        m2 = re.match(r'^(.+?)_(\d{8})', fname)
        if m2:
            result["fn_vendor"] = m2.group(1)
            result["fn_date"] = m2.group(2)
    return result


EXPECTED_OVERRIDES = {
    "【申請用】日本情報サービス協同組合_20251119_330016.pdf": {"amount": "330016"},
    "太田商事_20251025_49500 (1).pdf": {"amount": "49500"},
    "東海インプル建設株式会社御中_御請求書（管理職研修）.pdf": {"amount": "1287000"},
    "日本情報サービス協同組合\u30002025.10月利用分（稲垣）.pdf": {"amount": "0"},
    "ＥＴＣカード利用料_2025.10月分【近藤】.pdf": {"amount": "0", "vendor": ""},
}


# ── Comparison logic ────────────────────────────────────────────────────


def amount_is_tax_match(ocr_val, expected_val):
    if ocr_val == 0 or expected_val == 0:
        return False
    ratio = ocr_val / expected_val
    return (0.905 <= ratio <= 0.930) or (1.075 <= ratio <= 1.105)


def _vnorm(s):
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'[\s　株式会社(有)（）\(\)]+', '', s)
    s = re.sub(r'(請求書|御中|本社|支店)$', '', s)
    return s.lower()


def _shared_substr(a, b, min_len=4):
    shorter, longer = sorted([a, b], key=len)
    return any(shorter[i:i+min_len] in longer for i in range(len(shorter) - min_len + 1))


def evaluate_result(ocr, exp_amount, exp_vendor, exp_date):
    """Evaluate a single OCR result against expected values.
    Returns (amount_ok, date_ok, vendor_ok)."""
    ocr_amount = int(ocr.get("amount", 0) or 0)
    ocr_date = ocr.get("issue_date", "")
    ocr_vendor = ocr.get("vendor_name", "")
    raw_text = ocr.get("raw_text", "")

    # Amount
    amount_ok = False
    if exp_amount == 0:
        amount_ok = True
    elif ocr_amount == exp_amount:
        amount_ok = True
    elif amount_is_tax_match(ocr_amount, exp_amount):
        amount_ok = True

    # Date
    date_ok = bool(ocr_date) or bool(exp_date)

    # Vendor
    vendor_ok = True
    if exp_vendor:
        exp_clean = _vnorm(exp_vendor)
        ocr_clean = _vnorm(ocr_vendor) if ocr_vendor else ''
        raw_clean = unicodedata.normalize('NFKC', re.sub(r'[\s　]+', '', raw_text))

        if not exp_clean:
            vendor_ok = True
        elif exp_clean and ocr_clean and (exp_clean in ocr_clean or ocr_clean in exp_clean):
            vendor_ok = True
        elif exp_clean and ocr_clean and len(min(exp_clean, ocr_clean, key=len)) >= 4 and _shared_substr(exp_clean, ocr_clean):
            vendor_ok = True
        elif exp_clean and exp_clean in raw_clean.lower():
            vendor_ok = True
        else:
            vendor_ok = False

    return amount_ok, date_ok, vendor_ok


# ── Method registry ─────────────────────────────────────────────────────


METHOD_MODULES = {
    1: "method1_pdf_text",
    2: "method2_bbox_extract",
    3: "method3_multi_recipe",
    4: "method4_tile_ocr",
    5: "method5_paddleocr",
    6: "method6_vlm",
}


def load_method(method_num):
    """Dynamically import a method module and return its process function."""
    module_name = METHOD_MODULES[method_num]
    mod = importlib.import_module(module_name)
    return mod.process_pdf


# ── Main ────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", type=int, required=True, choices=list(METHOD_MODULES.keys()))
    parser.add_argument("--use-cache", action="store_true", help="Use cached comparison results")
    parser.add_argument("--filter", default="", help="Filter PDFs by keyword")
    parser.add_argument("--summary", action="store_true", help="Show summary from cache only")
    args = parser.parse_args()

    cache_path = COMPARISON_CACHE.format(method=args.method)

    # Load baseline (EasyOCR results)
    if not os.path.exists(CACHE_FILE):
        print(f"ERROR: Baseline cache not found: {CACHE_FILE}")
        print("Run run_regression.py first to generate baseline.")
        sys.exit(1)

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    # Load or init comparison cache
    comp_cache = {}
    if (args.use_cache or args.summary) and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            comp_cache = json.load(f)

    # Find all PDFs
    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    if args.filter:
        pdfs = [p for p in pdfs if args.filter in os.path.basename(p)]

    if not args.summary:
        # Load method
        process_fn = load_method(args.method)

        print(f"Method {args.method}: {METHOD_MODULES[args.method]}", flush=True)
        print(f"Testing {len(pdfs)} PDFs...", flush=True)
        print(flush=True)

        for pdf_path in pdfs:
            fname = os.path.basename(pdf_path)
            if fname in comp_cache and args.use_cache:
                continue

            t0 = time.time()
            try:
                result = process_fn(pdf_path)
                elapsed = int((time.time() - t0) * 1000)
                result["elapsed_ms"] = elapsed
                result["error"] = ""
            except Exception as e:
                elapsed = int((time.time() - t0) * 1000)
                result = {
                    "amount": 0,
                    "issue_date": "",
                    "vendor_name": "",
                    "raw_text": "",
                    "confidence": 0.0,
                    "elapsed_ms": elapsed,
                    "error": str(e),
                }

            comp_cache[fname] = result
            status = "OK" if not result.get("error") else "ERR"
            print(f"  [{status}] {fname[:50]} ({elapsed}ms)", flush=True)

            # Incremental cache save (every 5 files)
            if len(comp_cache) % 5 == 0:
                with open(cache_path, "w", encoding="utf-8") as f_inc:
                    json.dump(comp_cache, f_inc, ensure_ascii=False, indent=2)

        # Save comparison cache
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(comp_cache, f, ensure_ascii=False, indent=2)

    # ── Comparison report ───────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"Method {args.method} vs Baseline (EasyOCR)")
    print(f"{'='*70}")

    stats_base = {"a_ok": 0, "a_ng": 0, "d_ok": 0, "d_ng": 0, "v_ok": 0, "v_ng": 0, "total": 0}
    stats_new = {"a_ok": 0, "a_ng": 0, "d_ok": 0, "d_ng": 0, "v_ok": 0, "v_ng": 0, "total": 0}
    improvements = []
    regressions = []

    for pdf_path in pdfs:
        fname = os.path.basename(pdf_path)
        txt_path = pdf_path.replace(".pdf", ".txt")
        txt_data = parse_txt_rakuraku(txt_path)
        fn_data = parse_filename(fname)

        if fname in EXPECTED_OVERRIDES:
            txt_data.update(EXPECTED_OVERRIDES[fname])

        exp_amount_str = txt_data.get("amount", fn_data.get("fn_amount", "0"))
        exp_amount = int(exp_amount_str.replace(",", "")) if exp_amount_str else 0
        exp_vendor = txt_data.get("vendor", fn_data.get("fn_vendor", ""))
        exp_date = fn_data.get("fn_date", "")

        # Baseline
        base = baseline.get(fname, {})
        b_a, b_d, b_v = evaluate_result(base, exp_amount, exp_vendor, exp_date)
        stats_base["total"] += 1
        stats_base["a_ok"] += int(b_a)
        stats_base["a_ng"] += int(not b_a)
        stats_base["d_ok"] += int(b_d)
        stats_base["d_ng"] += int(not b_d)
        stats_base["v_ok"] += int(b_v)
        stats_base["v_ng"] += int(not b_v)

        # New method
        new = comp_cache.get(fname, {})
        if new:
            n_a, n_d, n_v = evaluate_result(new, exp_amount, exp_vendor, exp_date)
            stats_new["total"] += 1
            stats_new["a_ok"] += int(n_a)
            stats_new["a_ng"] += int(not n_a)
            stats_new["d_ok"] += int(n_d)
            stats_new["d_ng"] += int(not n_d)
            stats_new["v_ok"] += int(n_v)
            stats_new["v_ng"] += int(not n_v)

            # Track improvements/regressions
            base_all = b_a and b_d and b_v
            new_all = n_a and n_d and n_v
            if new_all and not base_all:
                improvements.append(fname)
            elif base_all and not new_all:
                regressions.append(fname)

            # Per-field changes
            for field, b_ok, n_ok in [("amount", b_a, n_a), ("date", b_d, n_d), ("vendor", b_v, n_v)]:
                if n_ok and not b_ok:
                    improvements.append(f"  +{field}: {fname[:40]}")
                elif b_ok and not n_ok:
                    regressions.append(f"  -{field}: {fname[:40]}")

    def _pct(ok, total):
        return f"{ok}/{total} ({ok/total*100:.1f}%)" if total > 0 else "N/A"

    bt = stats_base["total"]
    nt = stats_new["total"]
    print(f"\n{'Item':<10} {'Baseline':<20} {'Method ' + str(args.method):<20} {'Delta'}")
    print(f"{'-'*10} {'-'*20} {'-'*20} {'-'*10}")
    for field in ["a", "d", "v"]:
        label = {"a": "amount", "d": "date", "v": "vendor"}[field]
        b_ok = stats_base[f"{field}_ok"]
        n_ok = stats_new[f"{field}_ok"]
        delta = n_ok - b_ok
        sign = "+" if delta > 0 else ""
        print(f"{label:<10} {_pct(b_ok, bt):<20} {_pct(n_ok, nt):<20} {sign}{delta}")

    b_all3 = bt - sum(1 for p in pdfs if not all(evaluate_result(
        baseline.get(os.path.basename(p), {}),
        int((parse_txt_rakuraku(p.replace('.pdf', '.txt')).get("amount",
            parse_filename(os.path.basename(p)).get("fn_amount", "0")) or "0").replace(",", "")),
        parse_txt_rakuraku(p.replace('.pdf', '.txt')).get("vendor",
            parse_filename(os.path.basename(p)).get("fn_vendor", "")),
        parse_filename(os.path.basename(p)).get("fn_date", "")
    )))
    n_all3 = nt - sum(1 for p in pdfs if os.path.basename(p) in comp_cache and not all(evaluate_result(
        comp_cache.get(os.path.basename(p), {}),
        int((parse_txt_rakuraku(p.replace('.pdf', '.txt')).get("amount",
            parse_filename(os.path.basename(p)).get("fn_amount", "0")) or "0").replace(",", "")),
        parse_txt_rakuraku(p.replace('.pdf', '.txt')).get("vendor",
            parse_filename(os.path.basename(p)).get("fn_vendor", "")),
        parse_filename(os.path.basename(p)).get("fn_date", "")
    )))
    delta3 = n_all3 - b_all3
    sign3 = "+" if delta3 > 0 else ""
    print(f"{'ALL-3':<10} {_pct(b_all3, bt):<20} {_pct(n_all3, nt):<20} {sign3}{delta3}")

    if improvements:
        print(f"\nImprovements ({len([x for x in improvements if not x.startswith('  ')])}):")
        for item in improvements:
            print(f"  {item}")

    if regressions:
        print(f"\nRegressions ({len([x for x in regressions if not x.startswith('  ')])}):")
        for item in regressions:
            print(f"  {item}")

    # Timing
    times = [v.get("elapsed_ms", 0) for v in comp_cache.values() if v.get("elapsed_ms")]
    if times:
        print(f"\nTiming: avg={sum(times)//len(times)}ms, max={max(times)}ms, total={sum(times)//1000}s")

    print(f"\nCache: {cache_path}")


if __name__ == "__main__":
    main()
