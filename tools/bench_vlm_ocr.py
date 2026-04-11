#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VLM OCR 5エンジン統一ベンチマーク

対象エンジン:
  1. gpt54      — GPT-5.4 Vision API (現行ベースライン)
  2. qianfan    — Qianfan-OCR 4B (Baidu, transformers)
  3. hunyuan    — HunyuanOCR ~1B (Tencent, vLLM)
  4. paddlevl   — PaddleOCR-VL 1.5 0.9B (PaddlePaddle)
  5. docling    — docling + SmolDocling (IBM, パイプライン)

使い方:
  # 請求書カテゴリで全エンジンテスト
  python bench_vlm_ocr.py --engines gpt54,paddlevl --category invoice --limit 20

  # レシートカテゴリ
  python bench_vlm_ocr.py --engines gpt54 --category receipt --limit 20

  # 建築許可証カテゴリ
  python bench_vlm_ocr.py --engines gpt54 --category permit --limit 20

  # 結果をスコアリング
  python bench_vlm_ocr.py --score results_paddlevl_invoice_20260410.jsonl

依存関係 (エンジンごとに必要):
  gpt54:    pip install openai pymupdf
  qianfan:  pip install torch transformers pillow
  hunyuan:  pip install vllm transformers pillow
  paddlevl: pip install paddlepaddle-gpu paddleocr[doc-parser]
  docling:  pip install docling
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base paths (auto-convert Windows paths on WSL2)
# ---------------------------------------------------------------------------
def _wsl(p: str) -> Path:
    """Convert Windows path to WSL2 /mnt/c/ if running on Linux."""
    if sys.platform != "win32" and len(p) >= 3 and p[1] == ":":
        return Path("/mnt/" + p[0].lower() + "/" + p[3:].replace(chr(92), "/"))
    return Path(p)

CREDENTIALS_DIR = _wsl(r"C:\ProgramData\RK10\credentials")
RESULTS_DIR = Path(__file__).parent / "bench_results"

# ---------------------------------------------------------------------------
# Category-specific prompts
# ---------------------------------------------------------------------------
INVOICE_PROMPT = (
    "あなたは建設業の経理担当です。この請求書画像から以下の情報を抽出し、"
    "JSON形式で返してください。\n\n"
    "## 抽出ルール\n"
    "- vendor_name: 請求書の差出人（発行元）の会社名。宛先ではない。\n"
    "- issue_date: 発行日をYYYYMMDD形式の8桁数字で。\n"
    "- amount: 税込合計金額を数値のみで（カンマなし）。"
    "差引請求額があればそれを優先。\n"
    "- invoice_number: 適格請求書番号（T+13桁数字）。なければ空文字。\n\n"
    '## 出力形式（厳密に従うこと）\n'
    '{"vendor_name": "会社名", "issue_date": "YYYYMMDD", '
    '"amount": 数値, "invoice_number": "T..."}\n'
)

RECEIPT_PROMPT = (
    "この日本語のレシート・領収書から以下の情報を抽出し、"
    "JSON形式で返してください。\n\n"
    "## 抽出ルール\n"
    "- vendor_name: 発行元の店名・会社名。\n"
    "- issue_date: 発行日をYYYYMMDD形式の8桁数字で。\n"
    "- amount: 税込合計金額を数値のみで（カンマなし）。\n"
    "- invoice_number: 適格請求書番号（T+13桁数字）。なければ空文字。\n\n"
    '## 出力形式（厳密に従うこと）\n'
    '{"vendor_name": "店名", "issue_date": "YYYYMMDD", '
    '"amount": 数値, "invoice_number": "T..."}\n'
)

PERMIT_PROMPT = (
    "この日本語の建設業許可証・通知書から以下の情報を抽出し、"
    "JSON形式で返してください。\n\n"
    "## 抽出ルール\n"
    "- vendor_name: 許可を受けた建設業者（会社）の正式名称。\n"
    "- issue_date: 許可通知日をYYYYMMDD形式の8桁数字で。\n"
    "- invoice_number: 許可番号の数字部分のみ（例: '般-5第12345号' → '12345'）。\n\n"
    '## 出力形式（厳密に従うこと）\n'
    '{"vendor_name": "会社名", "issue_date": "YYYYMMDD", "invoice_number": "数字のみ"}\n'
)

# Backward compat alias
EXTRACT_PROMPT = INVOICE_PROMPT

# ---------------------------------------------------------------------------
# Category configuration
# ---------------------------------------------------------------------------
CATEGORY_CONFIG: dict[str, dict] = {
    "invoice": {
        "golden_path": _wsl(
            r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan"
            r"\config\golden_dataset_v4.json"
        ),
        "pdf_dirs": [
            _wsl(
                r"C:\ProgramData\RK10\Robots"
                r"\12・13受信メールのPDFを保存・一括印刷\samples\PDF教師データ"
            ),
            _wsl(
                r"C:\ProgramData\RK10\Robots"
                r"\12・13受信メールのPDFを保存・一括印刷\artifacts"
            ),
        ],
        "score_fields": ["vendor", "date", "amount"],
        "prompt": INVOICE_PROMPT,
    },
    "receipt": {
        "golden_path": _wsl(
            r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan"
            r"\config\golden_dataset_receipt_v1.json"
        ),
        "pdf_dirs": [
            _wsl(r"C:\ProgramData\RK10\Tools\sample PDF"),
        ],
        "score_fields": ["vendor", "date", "amount"],
        "prompt": RECEIPT_PROMPT,
    },
    "permit": {
        "golden_path": _wsl(
            r"C:\ProgramData\Generative AI\Github\construction-permit-tracker"
            r"\config\golden_dataset_permit_v1.json"
        ),
        "pdf_dirs": [
            _wsl(
                r"C:\ProgramData\Generative AI\Github\construction-permit-tracker"
                r"\data\all_documents"
            ),
        ],
        "score_fields": ["vendor", "date", "invoice_number"],  # amount はスキップ
        "prompt": PERMIT_PROMPT,
    },
}

# Default paths (invoice)
GOLDEN_DATASET = CATEGORY_CONFIG["invoice"]["golden_path"]
PDF_SEARCH_DIRS = CATEGORY_CONFIG["invoice"]["pdf_dirs"]


# ---------------------------------------------------------------------------
# PDF → image conversion
# ---------------------------------------------------------------------------
try:
    import fitz  # PyMuPDF

    def pdf_to_png_bytes(pdf_path: str, dpi: int = 300) -> list[bytes]:
        doc = fitz.open(pdf_path)
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            images.append(pix.tobytes("png"))
        doc.close()
        return images

except ImportError:
    fitz = None

    def pdf_to_png_bytes(pdf_path: str, dpi: int = 300) -> list[bytes]:
        raise ImportError("PyMuPDF (fitz) required: pip install pymupdf")


def pdf_to_base64(pdf_path: str, dpi: int = 300) -> str:
    """First page of PDF as base64-encoded PNG."""
    images = pdf_to_png_bytes(pdf_path, dpi)
    return base64.b64encode(images[0]).decode()


def save_temp_png(pdf_path: str, dpi: int = 300) -> str:
    """First page of PDF saved as temp PNG, return path."""
    import tempfile

    images = pdf_to_png_bytes(pdf_path, dpi)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(images[0])
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# JSON extraction from LLM output
# ---------------------------------------------------------------------------
def extract_json_from_text(text: str) -> dict | None:
    """Extract first JSON object from LLM text output."""
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            pass
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError):
            pass
    return None


# ===================================================================
# Engine: GPT-5.4 Vision API
# ===================================================================
class GPT54Engine:
    name = "gpt54"

    def __init__(self):
        key_file = CREDENTIALS_DIR / "openai_api_key.txt"
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key and key_file.exists():
            api_key = key_file.read_text(encoding="utf-8").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)

    def extract(self, pdf_path: str, prompt: str | None = None) -> dict:
        b64 = pdf_to_base64(pdf_path)
        used_prompt = prompt or INVOICE_PROMPT
        resp = self.client.chat.completions.create(
            model="gpt-5.4",
            response_format={"type": "json_object"},
            max_completion_tokens=2000,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": used_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
        )
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        tokens = {
            "input": usage.prompt_tokens if usage else 0,
            "output": usage.completion_tokens if usage else 0,
        }
        result = extract_json_from_text(text) or {}
        result["_tokens"] = tokens
        return result


# ===================================================================
# Engine: Qianfan-OCR (Baidu, 4B, transformers)
# ===================================================================
class QianfanEngine:
    name = "qianfan"

    def __init__(self):
        import torch
        from transformers import AutoModel, AutoTokenizer

        model_path = os.environ.get("QIANFAN_MODEL", "baidu/Qianfan-OCR")
        log.info("Loading Qianfan-OCR from %s ...", model_path)
        self.model = AutoModel.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            trust_remote_code=True,
            device_map="auto",
        ).eval()
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True
        )
        self._torch = torch

    def _load_image(self, path: str, input_size: int = 448, max_num: int = 12):
        import torchvision.transforms as T
        from torchvision.transforms.functional import InterpolationMode
        from PIL import Image

        MEAN = (0.485, 0.456, 0.406)
        STD = (0.229, 0.224, 0.225)
        transform = T.Compose([
            T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
            T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(mean=MEAN, std=STD),
        ])
        image = Image.open(path).convert("RGB")
        w, h = image.size
        ar = w / h
        ratios = sorted(
            {(i, j) for n in range(1, max_num + 1) for i in range(1, n + 1) for j in range(1, n + 1) if i * j <= max_num},
            key=lambda x: x[0] * x[1],
        )
        best = min(ratios, key=lambda r: abs(ar - r[0] / r[1]))
        tw, th = input_size * best[0], input_size * best[1]
        blocks = best[0] * best[1]
        resized = image.resize((tw, th))
        tiles = []
        for i in range(blocks):
            x0 = (i % (tw // input_size)) * input_size
            y0 = (i // (tw // input_size)) * input_size
            tiles.append(resized.crop((x0, y0, x0 + input_size, y0 + input_size)))
        if len(tiles) != 1:
            tiles.append(image.resize((input_size, input_size)))
        pixel_values = self._torch.stack([transform(t) for t in tiles])
        return pixel_values

    def extract(self, pdf_path: str, prompt: str | None = None) -> dict:
        png_path = save_temp_png(pdf_path)
        try:
            pixel_values = self._load_image(png_path).to(
                self._torch.bfloat16
            ).to(self.model.device)
            used_prompt = prompt or (
                "この日本語の請求書画像からJSON形式で以下を抽出してください: "
                "vendor_name, issue_date(YYYYMMDD), amount(数値), invoice_number(T+13桁)"
            )
            with self._torch.no_grad():
                response = self.model.chat(
                    self.tokenizer,
                    pixel_values=pixel_values,
                    question=used_prompt,
                    generation_config={"max_new_tokens": 2048},
                )
            result = extract_json_from_text(response) or {"_raw": response}
            return result
        finally:
            os.unlink(png_path)


# ===================================================================
# Engine: HunyuanOCR (Tencent, ~1B, vLLM)
# ===================================================================
class HunyuanEngine:
    name = "hunyuan"

    def __init__(self):
        from vllm import LLM, SamplingParams
        from transformers import AutoProcessor

        model_path = os.environ.get("HUNYUAN_MODEL", "tencent/HunyuanOCR")
        log.info("Loading HunyuanOCR from %s ...", model_path)
        self.llm = LLM(model=model_path, trust_remote_code=True)
        self.processor = AutoProcessor.from_pretrained(model_path)
        self.sampling_params = SamplingParams(temperature=0, max_tokens=2048)

    def extract(self, pdf_path: str, prompt: str | None = None) -> dict:
        from PIL import Image

        png_path = save_temp_png(pdf_path)
        try:
            img = Image.open(png_path)
            used_prompt = prompt or (
                "この日本語の請求書画像からJSON形式で以下を抽出してください: "
                "vendor_name, issue_date(YYYYMMDD), amount(数値), "
                "invoice_number(T+13桁)"
            )
            messages = [
                {"role": "system", "content": ""},
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": png_path},
                        {"type": "text", "text": used_prompt},
                    ],
                },
            ]
            formatted = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = {"prompt": formatted, "multi_modal_data": {"image": [img]}}
            output = self.llm.generate([inputs], self.sampling_params)[0]
            text = output.outputs[0].text
            result = extract_json_from_text(text) or {"_raw": text}
            return result
        finally:
            os.unlink(png_path)


# ===================================================================
# Engine: PaddleOCR-VL 1.5 (0.9B)
# ===================================================================
class PaddleVLEngine:
    name = "paddlevl"

    def __init__(self):
        from paddleocr import PaddleOCRVL

        device = os.environ.get("PADDLE_DEVICE", "gpu")
        log.info("Loading PaddleOCR-VL 1.5 (device=%s) ...", device)
        self.pipeline = PaddleOCRVL(device=device)

    def extract(self, pdf_path: str, prompt: str | None = None) -> dict:
        png_path = save_temp_png(pdf_path)
        try:
            output = self.pipeline.predict(png_path)
            full_text = ""
            for res in output:
                if hasattr(res, "text"):
                    full_text += res.text + "\n"
                elif hasattr(res, "rec_texts"):
                    full_text += "\n".join(res.rec_texts) + "\n"
                else:
                    full_text += str(res) + "\n"

            result = self._parse_from_markdown(full_text)
            result["_raw"] = full_text[:2000]
            return result
        finally:
            os.unlink(png_path)

    def _parse_from_markdown(self, text: str) -> dict:
        """Parse fields from markdown/text output."""
        result: dict = {}

        parsed = extract_json_from_text(text)
        if parsed and "vendor_name" in parsed:
            return parsed

        vendor_m = re.search(
            r"(?:発行[者元]|請求[者元]|差出人|会社名|業者名)[：:\s]*(.+?)(?:\n|$)", text
        )
        if vendor_m:
            result["vendor_name"] = vendor_m.group(1).strip()

        date_m = re.search(
            r"(?:発行日|請求日|許可日|日付)[：:\s]*(\d{4}[./年-]\d{1,2}[./月-]\d{1,2})", text
        )
        if date_m:
            raw = date_m.group(1)
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 8:
                result["issue_date"] = digits[:8]

        amt_m = re.search(r"(?:合計|請求額|税込|差引)[^0-9]*([0-9,]+)", text)
        if amt_m:
            result["amount"] = int(amt_m.group(1).replace(",", ""))

        inv_m = re.search(r"(T\d{13})", text)
        if inv_m:
            result["invoice_number"] = inv_m.group(1)

        permit_m = re.search(r"第(\d+)号", text)
        if permit_m and "invoice_number" not in result:
            result["invoice_number"] = permit_m.group(1)

        return result


# ===================================================================
# Engine: docling (IBM, pipeline)
# ===================================================================
class DoclingEngine:
    name = "docling"

    def __init__(self):
        from docling.document_converter import DocumentConverter

        log.info("Loading docling DocumentConverter ...")
        self.converter = DocumentConverter()

    def extract(self, pdf_path: str, prompt: str | None = None) -> dict:
        result_doc = self.converter.convert(pdf_path)
        md_text = result_doc.document.export_to_markdown()

        result = self._parse_from_markdown(md_text)
        result["_raw"] = md_text[:2000]
        return result

    def _parse_from_markdown(self, text: str) -> dict:
        result: dict = {}

        vendor_m = re.search(
            r"(?:発行[者元]|請求[者元]|差出人|会社名|業者名)[：:\s]*(.+?)(?:\n|$)", text
        )
        if vendor_m:
            result["vendor_name"] = vendor_m.group(1).strip()

        date_m = re.search(
            r"(?:発行日|請求日|許可日|日付)[：:\s]*(\d{4}[./年-]\d{1,2}[./月-]\d{1,2})", text
        )
        if date_m:
            raw = date_m.group(1)
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 8:
                result["issue_date"] = digits[:8]

        amt_m = re.search(r"(?:合計|請求額|税込|差引)[^0-9]*([0-9,]+)", text)
        if amt_m:
            result["amount"] = int(amt_m.group(1).replace(",", ""))

        inv_m = re.search(r"(T\d{13})", text)
        if inv_m:
            result["invoice_number"] = inv_m.group(1)

        permit_m = re.search(r"第(\d+)号", text)
        if permit_m and "invoice_number" not in result:
            result["invoice_number"] = permit_m.group(1)

        return result


# ---------------------------------------------------------------------------
# Engine registry
# ---------------------------------------------------------------------------
ENGINE_CLASSES: dict[str, type] = {
    "gpt54": GPT54Engine,
    "qianfan": QianfanEngine,
    "hunyuan": HunyuanEngine,
    "paddlevl": PaddleVLEngine,
    "docling": DoclingEngine,
}


# ---------------------------------------------------------------------------
# PDF file locator
# ---------------------------------------------------------------------------
def find_pdf(filename: str, search_dirs: list[Path] | None = None) -> Path | None:
    """Search for a PDF in the given directories (falls back to PDF_SEARCH_DIRS)."""
    dirs = search_dirs or PDF_SEARCH_DIRS
    for base in dirs:
        if not base.exists():
            continue
        for p in base.rglob(filename):
            return p
    return None


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------
def _normalize_date(value: str | None) -> str | None:
    """Convert any date string to YYYYMMDD 8-digit string."""
    normalized = unicodedata.normalize("NFKC", value or "")
    digits = re.sub(r"\D", "", normalized)
    if len(digits) == 8 and digits.startswith("20"):
        try:
            datetime.strptime(digits, "%Y%m%d")
            return digits
        except ValueError:
            return None
    return None


def score_invoice_number(predicted: str | None, expected: str) -> tuple[bool, str]:
    """Permit number match: expected digits must appear in predicted."""
    if not expected:
        return False, "missing_expected"
    if not predicted:
        return False, "missing"
    pred_digits = re.sub(r"\D", "", predicted or "")
    exp_digits = re.sub(r"\D", "", expected or "")
    if not exp_digits:
        return False, "invalid_expected"
    if exp_digits in pred_digits:
        return True, "match"
    return False, f"mismatch({pred_digits[:20]} vs {exp_digits})"


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------
def run_benchmark(
    engine_names: list[str],
    limit: int | None = None,
    category: str = "invoice",
) -> dict[str, list[dict]]:
    """Run extraction on golden dataset for each engine. Return {engine: [results]}."""
    cfg = CATEGORY_CONFIG.get(category)
    if not cfg:
        log.error("Unknown category: %s (available: %s)", category, list(CATEGORY_CONFIG))
        return {}

    golden_path = cfg["golden_path"]
    pdf_dirs = cfg["pdf_dirs"]
    cat_prompt = cfg["prompt"]

    if not golden_path.exists():
        log.error("Golden dataset not found: %s", golden_path)
        return {}

    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    if limit:
        golden = golden[:limit]

    log.info("Category: %s | Golden dataset: %d entries | Prompt: %s...",
             category, len(golden), cat_prompt[:40])

    RESULTS_DIR.mkdir(exist_ok=True)
    all_results: dict[str, list[dict]] = {}

    for eng_name in engine_names:
        cls = ENGINE_CLASSES.get(eng_name)
        if not cls:
            log.error("Unknown engine: %s (available: %s)", eng_name, list(ENGINE_CLASSES))
            continue

        log.info("=== Initializing engine: %s ===", eng_name)
        try:
            engine = cls()
        except Exception as e:
            log.error("Failed to init %s: %s", eng_name, e)
            continue

        results: list[dict] = []
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = RESULTS_DIR / f"results_{eng_name}_{category}_{ts}.jsonl"

        for i, entry in enumerate(golden):
            filename = entry["filename"]
            entry_id = entry.get("id", i + 1)
            pdf_path = find_pdf(filename, pdf_dirs)

            if not pdf_path or not pdf_path.exists():
                log.warning("#%d SKIP (not found): %s", entry_id, filename[:60])
                results.append({
                    "id": entry_id,
                    "filename": filename,
                    "category": category,
                    "error": "pdf_not_found",
                })
                continue

            log.info("#%d/%d [%s/%s] %s", i + 1, len(golden), eng_name, category, filename[:50])
            t0 = time.time()
            try:
                extracted = engine.extract(str(pdf_path), prompt=cat_prompt)
                elapsed = time.time() - t0

                row = {
                    "id": entry_id,
                    "filename": filename,
                    "category": category,
                    "vendor": extracted.get("vendor_name"),
                    "issue_date": str(extracted.get("issue_date", "")),
                    "amount": str(extracted.get("amount", "")),
                    "invoice_no": extracted.get("invoice_number", ""),
                    "elapsed_sec": round(elapsed, 2),
                    "engine": eng_name,
                }
                if "_tokens" in extracted:
                    row["tokens"] = extracted["_tokens"]
                if "_raw" in extracted:
                    row["raw_preview"] = extracted["_raw"][:500]

                results.append(row)
                log.info(
                    "  → vendor=%s date=%s amount=%s inv=%s (%.1fs)",
                    row["vendor"],
                    row["issue_date"],
                    row["amount"],
                    row["invoice_no"],
                    elapsed,
                )

            except Exception as e:
                elapsed = time.time() - t0
                log.error("  → ERROR: %s (%.1fs)", e, elapsed)
                results.append({
                    "id": entry_id,
                    "filename": filename,
                    "category": category,
                    "error": str(e),
                    "elapsed_sec": round(elapsed, 2),
                    "engine": eng_name,
                })

            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(results[-1], ensure_ascii=False) + "\n")

        log.info("=== %s/%s complete: %d results → %s ===", eng_name, category, len(results), out_path)
        all_results[eng_name] = results

    return all_results


# ---------------------------------------------------------------------------
# Scoring (inline, category-aware)
# ---------------------------------------------------------------------------
def score_results(jsonl_path: Path, category: str | None = None) -> None:
    """Score a JSONL results file against golden dataset."""
    # Detect category from filename if not specified
    if not category:
        stem = jsonl_path.stem  # e.g. results_gpt54_receipt_20260410_120000
        for cat in CATEGORY_CONFIG:
            if f"_{cat}_" in stem or stem.endswith(f"_{cat}"):
                category = cat
                break
        if not category:
            category = "invoice"
        log.info("Detected category: %s", category)

    cfg = CATEGORY_CONFIG[category]
    golden_path = cfg["golden_path"]
    score_fields = cfg["score_fields"]

    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    golden_map = {str(e["id"]): e for e in golden}

    rows = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        rows.append(item)

    stats = {
        "total": 0,
        "vendor_ok": 0,
        "date_ok": 0,
        "amount_ok": 0,
        "invoice_number_ok": 0,
        "errors": 0,
    }
    details: list[str] = []

    for row in rows:
        rid = str(row.get("id", ""))
        if row.get("error"):
            stats["errors"] += 1
            continue
        if rid not in golden_map:
            continue

        expected = golden_map[rid]
        # Skip entries with empty expected values
        if not expected.get("vendor") and not expected.get("issue_date"):
            continue

        stats["total"] += 1
        mismatches = []

        # Vendor
        if "vendor" in score_fields:
            pred_v = row.get("vendor") or ""
            exp_v = expected.get("vendor") or ""
            # Simple fuzzy: normalize and compare
            def _norm(s):
                s = unicodedata.normalize("NFKC", s or "")
                s = re.sub(r"[株式会社有限会社合同会社\s　]", "", s)
                return s.lower()
            v_ok = _norm(pred_v) == _norm(exp_v) if exp_v else False
            if v_ok:
                stats["vendor_ok"] += 1
            else:
                mismatches.append(f"vendor: got={pred_v[:20]} exp={exp_v[:20]}")

        # Date
        if "date" in score_fields:
            pred_d = _normalize_date(row.get("issue_date"))
            exp_d = _normalize_date(expected.get("issue_date"))
            if exp_d:
                d_ok = pred_d == exp_d
                if d_ok:
                    stats["date_ok"] += 1
                else:
                    mismatches.append(f"date: got={pred_d} exp={exp_d}")

        # Amount
        if "amount" in score_fields:
            pred_a_str = re.sub(r"[^0-9]", "", str(row.get("amount") or ""))
            exp_a_str = re.sub(r"[^0-9]", "", str(expected.get("amount") or ""))
            if exp_a_str and pred_a_str:
                a_ok = pred_a_str == exp_a_str
                if a_ok:
                    stats["amount_ok"] += 1
                else:
                    mismatches.append(f"amount: got={pred_a_str} exp={exp_a_str}")
            elif exp_a_str:
                mismatches.append(f"amount: missing (exp={exp_a_str})")

        # Invoice number (permit number)
        if "invoice_number" in score_fields:
            pred_inv = row.get("invoice_no") or ""
            exp_inv = expected.get("invoice_number") or ""
            if exp_inv:
                inv_ok, _ = score_invoice_number(pred_inv, exp_inv)
                if inv_ok:
                    stats["invoice_number_ok"] += 1
                else:
                    mismatches.append(f"invoice_no: got={pred_inv[:20]} exp={exp_inv}")

        if mismatches:
            details.append(f"  #{rid}: " + " | ".join(mismatches))

    total = max(stats["total"], 1)
    engine_name = jsonl_path.stem.split("_")[1] if "_" in jsonl_path.stem else "?"

    print(f"\n{'='*60}")
    print(f"Benchmark Score: {engine_name} / category={category}")
    print(f"{'='*60}")
    print(f"  Total scored : {stats['total']}")
    print(f"  Errors/skips : {stats['errors']}")
    print(f"  Score fields : {score_fields}")
    if "vendor" in score_fields:
        print(f"  Vendor  : {stats['vendor_ok']}/{total} ({100*stats['vendor_ok']/total:.1f}%)")
    if "date" in score_fields:
        print(f"  Date    : {stats['date_ok']}/{total} ({100*stats['date_ok']/total:.1f}%)")
    if "amount" in score_fields:
        print(f"  Amount  : {stats['amount_ok']}/{total} ({100*stats['amount_ok']/total:.1f}%)")
    if "invoice_number" in score_fields:
        print(f"  Permit# : {stats['invoice_number_ok']}/{total} ({100*stats['invoice_number_ok']/total:.1f}%)")

    if details:
        print(f"\nMismatches (first 20):")
        for d in details[:20]:
            print(d)
    print()


# ---------------------------------------------------------------------------
# Summary across engines
# ---------------------------------------------------------------------------
def print_summary(all_results: dict[str, list[dict]], category: str) -> None:
    """Print a quick summary table across engines."""
    print(f"\n{'='*70}")
    print(f"Quick Summary (before scoring) — category={category}")
    print(f"{'='*70}")
    print(f"{'Engine':<12} {'Total':>6} {'OK':>6} {'Error':>6} {'Avg sec':>8}")
    print("-" * 70)

    for eng, rows in all_results.items():
        total = len(rows)
        errors = sum(1 for r in rows if r.get("error"))
        ok = total - errors
        times = [r["elapsed_sec"] for r in rows if "elapsed_sec" in r and not r.get("error")]
        avg_t = sum(times) / len(times) if times else 0
        print(f"{eng:<12} {total:>6} {ok:>6} {errors:>6} {avg_t:>8.2f}")

    print()
    print("Score each result with:  python bench_vlm_ocr.py --score <jsonl_path>")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="VLM OCR 5エンジン統一ベンチマーク")
    parser.add_argument(
        "--engines",
        default="gpt54",
        help="Comma-separated engine names: gpt54,qianfan,hunyuan,paddlevl,docling",
    )
    parser.add_argument(
        "--category",
        default="invoice",
        choices=list(CATEGORY_CONFIG.keys()),
        help="Document category: invoice / receipt / permit",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of golden entries to process",
    )
    parser.add_argument(
        "--score",
        type=str,
        default=None,
        help="Score an existing JSONL results file",
    )
    parser.add_argument(
        "--list-engines",
        action="store_true",
        help="List available engines and exit",
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List available categories and exit",
    )
    args = parser.parse_args()

    if args.list_engines:
        print("Available engines:")
        for name in ENGINE_CLASSES:
            print(f"  {name}")
        return

    if args.list_categories:
        print("Available categories:")
        for cat, cfg in CATEGORY_CONFIG.items():
            gp = cfg["golden_path"]
            exists = "OK" if gp.exists() else "MISSING"
            print(f"  {cat:<10} golden={gp.name} [{exists}]  fields={cfg['score_fields']}")
        return

    if args.score:
        score_results(Path(args.score))
        return

    engine_names = [e.strip() for e in args.engines.split(",") if e.strip()]
    all_results = run_benchmark(engine_names, limit=args.limit, category=args.category)
    print_summary(all_results, args.category)


if __name__ == "__main__":
    main()
