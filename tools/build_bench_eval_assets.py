"""Build cleaned golden dataset and sender-aware benchmark results."""

from __future__ import annotations

import json
from pathlib import Path

from training_data import build_combined_attachment_context_map, normalize_attachment_name
from vendor_matching import is_non_vendor_candidate

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"

GOLDEN_PATH = CONFIG_DIR / "golden_dataset_v4.json"
GOLDEN_EVAL_PATH = CONFIG_DIR / "golden_dataset_v4_eval.json"
RESULTS_PATH = Path(r"C:\tmp\bench_v4_results_dedup_refreshed_missing.jsonl")
RESULTS_WITH_CONTEXT_PATH = Path(r"C:\tmp\bench_v4_results_dedup_with_context.jsonl")


def _build_attachment_context_map() -> dict[str, dict[str, str]]:
    return build_combined_attachment_context_map(artifact_dir=ARTIFACTS_DIR)


def build_clean_golden() -> list[dict]:
    rows = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    cleaned: list[dict] = []
    for row in rows:
        item = dict(row)
        skip_vendor_scoring = False
        flags: list[str] = []
        is_noise, reasons = is_non_vendor_candidate(item.get("vendor"))
        if is_noise:
            skip_vendor_scoring = True
            flags.extend(reasons)
        item["skip_vendor_scoring"] = skip_vendor_scoring
        if flags:
            item["vendor_scoring_notes"] = list(flags)
        cleaned.append(item)
    return cleaned


def build_context_results(context_map: dict[str, dict[str, str]]) -> list[dict]:
    rows = [
        json.loads(line)
        for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    enriched: list[dict] = []
    for row in rows:
        item = dict(row)
        context = context_map.get(normalize_attachment_name(str(item.get("filename") or "").strip()))
        if context:
            item["sender"] = context.get("sender")
            item["subject"] = context.get("subject")
        enriched.append(item)
    return enriched


def main() -> None:
    context_map = _build_attachment_context_map()
    cleaned_golden = build_clean_golden()
    enriched_results = build_context_results(context_map)

    GOLDEN_EVAL_PATH.write_text(
        json.dumps(cleaned_golden, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    RESULTS_WITH_CONTEXT_PATH.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in enriched_results) + "\n",
        encoding="utf-8",
    )

    context_hits = sum(1 for row in enriched_results if row.get("sender") or row.get("subject"))
    skip_rows = sum(1 for row in cleaned_golden if row.get("skip_vendor_scoring"))
    print(
        json.dumps(
            {
                "golden_eval_path": str(GOLDEN_EVAL_PATH),
                "results_with_context_path": str(RESULTS_WITH_CONTEXT_PATH),
                "context_hits": context_hits,
                "skip_vendor_rows": skip_rows,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
