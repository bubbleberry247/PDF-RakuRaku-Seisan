from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from training_data import build_combined_attachment_context_map, normalize_attachment_name
from vision_ocr import extract


ROOT_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT_DIR / "artifacts"


def build_attachment_context_map() -> dict[str, dict[str, str]]:
    return build_combined_attachment_context_map(artifact_dir=ARTIFACTS_DIR)


def load_jsonl_ids(path: Path) -> set[int]:
    if not path.exists():
        return set()
    done: set[int] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        item_id = item.get("id")
        if item_id is None:
            continue
        try:
            done.add(int(item_id))
        except Exception:
            continue
    return done


def run_one(
    entry: dict,
    pdf_dir: Path,
    provider: str,
    timeout_s: float,
    context_map: dict[str, dict[str, str]],
) -> dict:
    filename = str(entry["filename"])
    pdf_path = pdf_dir / filename
    context = context_map.get(normalize_attachment_name(filename), {})
    sender = context.get("sender")
    subject = context.get("subject")

    try:
        result = extract(
            str(pdf_path),
            provider=provider,
            timeout_s=timeout_s,
            sender_hint=sender,
            subject_hint=subject,
        )
        return {
            "id": entry["id"],
            "filename": filename,
            "vendor": result.vendor,
            "issue_date": result.issue_date,
            "amount": result.amount,
            "invoice_no": result.invoice_no,
            "error": result.error,
            "elapsed_s": result.elapsed_s,
            "provider": result.provider,
            "confidence": result.confidence,
            "fallback_used": result.fallback_used,
            "fallback_from": result.fallback_from,
            "requires_manual": result.requires_manual,
            "review_reasons": list(result.review_reasons),
            "sender": sender,
            "subject": subject,
        }
    except Exception as e:
        return {
            "id": entry["id"],
            "filename": filename,
            "vendor": None,
            "issue_date": None,
            "amount": None,
            "invoice_no": None,
            "error": f"{type(e).__name__}: {e}",
            "elapsed_s": None,
            "provider": provider,
            "confidence": "low",
            "fallback_used": False,
            "fallback_from": None,
            "requires_manual": True,
            "review_reasons": [],
            "sender": sender,
            "subject": subject,
        }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", required=True)
    ap.add_argument("--pdf-dir", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--provider", default="openai")
    ap.add_argument("--timeout-s", type=float, default=45.0)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    golden_path = Path(args.golden)
    pdf_dir = Path(args.pdf_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    context_map = build_attachment_context_map()
    completed_ids = load_jsonl_ids(output_path)
    pending = [entry for entry in golden if int(entry["id"]) not in completed_ids]

    print(
        json.dumps(
            {
                "golden_entries": len(golden),
                "completed_ids": len(completed_ids),
                "pending": len(pending),
                "context_hits_total": sum(
                    1 for entry in golden if context_map.get(normalize_attachment_name(str(entry["filename"])))
                ),
                "output": str(output_path),
                "workers": args.workers,
                "provider": args.provider,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    if not pending:
        return 0

    write_lock = threading.Lock()
    total = len(pending)
    completed = 0

    with output_path.open("a", encoding="utf-8", newline="\n") as fh:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    run_one,
                    entry,
                    pdf_dir,
                    args.provider,
                    args.timeout_s,
                    context_map,
                ): entry
                for entry in pending
            }
            for future in as_completed(futures):
                row = future.result()
                with write_lock:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fh.flush()
                completed += 1
                print(
                    json.dumps(
                        {
                            "done": completed,
                            "total": total,
                            "id": row.get("id"),
                            "filename": row.get("filename"),
                            "error": row.get("error"),
                            "confidence": row.get("confidence"),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
