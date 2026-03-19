from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import fitz

from score_ocr_bench import score_amount, score_date, score_vendor
from vision_ocr import extract


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = ROOT_DIR / "config" / "golden_dataset_v4_eval.json"
DEFAULT_PDF_DIR = ROOT_DIR / "samples" / "bench_v4"
DEFAULT_OUTPUT_DIR = Path(r"C:\tmp\ocr_overlay_preview")


def load_golden(path: Path) -> dict[int, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(row["id"]): row for row in data}


def render_first_page(pdf_path: Path, output_path: Path, dpi: int = 150) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    try:
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        output_path.write_bytes(pix.tobytes("png"))
    finally:
        doc.close()


def summarize_metric_status(ok: bool | None, detail: str) -> str:
    if ok is None:
        return "SKIP"
    return "OK" if ok else f"NG ({detail})"


def build_card(entry: dict, image_rel: str, result: dict) -> str:
    vendor_ok, vendor_detail = score_vendor(
        result.get("vendor"),
        entry.get("vendor") or "",
        filename=entry.get("filename"),
    )
    date_ok, date_detail = score_date(result.get("issue_date"), entry.get("issue_date") or "")
    amount_ok, amount_detail = score_amount(result.get("amount"), entry.get("amount") or "", tolerance_ratio=0.0)

    overlay_lines = [
        f"vendor: {result.get('vendor') or '-'}",
        f"issue_date: {result.get('issue_date') or '-'}",
        f"amount: {result.get('amount') or '-'}",
        f"confidence: {result.get('confidence') or '-'}",
        f"review_reasons: {', '.join(result.get('review_reasons') or []) or '-'}",
        f"benchmark: vendor={summarize_metric_status(vendor_ok, vendor_detail)} / date={summarize_metric_status(date_ok, date_detail)} / amount={summarize_metric_status(amount_ok, amount_detail)}",
    ]
    overlay_html = "<br>".join(html.escape(line) for line in overlay_lines)

    return f"""
    <section class="card">
      <h2>#{entry['id']} {html.escape(entry['filename'])}</h2>
      <div class="meta">
        golden: vendor={html.escape(entry.get('vendor') or '-')},
        issue_date={html.escape(entry.get('issue_date') or '-')},
        amount={html.escape(entry.get('amount') or '-')}
      </div>
      <div class="page">
        <img src="{html.escape(image_rel)}" alt="{html.escape(entry['filename'])}">
        <div class="overlay">{overlay_html}</div>
      </div>
    </section>
    """


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="+", type=int, required=True)
    ap.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    ap.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    ap.add_argument("--provider", default="openai")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    golden = load_golden(args.golden)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = args.output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    cards: list[str] = []
    for item_id in args.ids:
        entry = golden[item_id]
        pdf_path = args.pdf_dir / entry["filename"]
        image_path = assets_dir / f"{item_id:03d}.png"
        render_first_page(pdf_path, image_path)
        ocr = extract(pdf_path, provider=args.provider)
        result = {
            "vendor": ocr.vendor,
            "issue_date": ocr.issue_date,
            "amount": str(ocr.amount) if ocr.amount is not None else None,
            "confidence": ocr.confidence,
            "review_reasons": list(ocr.review_reasons),
        }
        cards.append(build_card(entry, f"assets/{image_path.name}", result))
        print(json.dumps({"id": item_id, "filename": entry["filename"], **result}, ensure_ascii=False))

    summary_html = """
    <section class="summary">
      <h1>OCR Overlay Preview</h1>
      <p>Current benchmark (500件, GPT-4o only): Vendor 98.7%, Date 99.8%, Amount exact 79.8%, Amount ±10% 82.2%</p>
    </section>
    """

    html_doc = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OCR Overlay Preview</title>
  <style>
    body {{
      margin: 0;
      font-family: 'Yu Gothic UI', 'Hiragino Sans', sans-serif;
      background: linear-gradient(180deg, #f4efe5 0%, #ece6da 100%);
      color: #1b1b1b;
      padding: 24px;
    }}
    .summary {{
      max-width: 1080px;
      margin: 0 auto 24px;
      padding: 20px 24px;
      background: rgba(255,255,255,0.82);
      border: 1px solid #d4cab8;
      border-radius: 16px;
      box-shadow: 0 12px 28px rgba(63, 41, 24, 0.08);
    }}
    .card {{
      max-width: 1080px;
      margin: 0 auto 24px;
      padding: 20px;
      background: rgba(255,255,255,0.88);
      border: 1px solid #d4cab8;
      border-radius: 16px;
      box-shadow: 0 12px 28px rgba(63, 41, 24, 0.08);
    }}
    .meta {{
      margin-bottom: 12px;
      color: #5b5144;
      font-size: 14px;
    }}
    .page {{
      position: relative;
      overflow: hidden;
      border-radius: 12px;
      border: 1px solid #d6d0c7;
      background: #fff;
    }}
    img {{
      width: 100%;
      display: block;
      height: auto;
    }}
    .overlay {{
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      padding: 16px 18px;
      background: linear-gradient(180deg, rgba(255,255,255,0.08) 0%, rgba(255,248,248,0.92) 35%, rgba(255,248,248,0.96) 100%);
      color: #c1121f;
      font-size: 18px;
      line-height: 1.45;
      font-weight: 700;
      text-shadow: 0 1px 0 rgba(255,255,255,0.7);
      border-top: 2px solid rgba(193,18,31,0.22);
    }}
    h1, h2 {{ margin: 0 0 10px; }}
  </style>
</head>
<body>
  {summary_html}
  {''.join(cards)}
</body>
</html>
"""
    output_html = args.output_dir / "index.html"
    output_html.write_text(html_doc, encoding="utf-8")
    print(json.dumps({"html": str(output_html)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
