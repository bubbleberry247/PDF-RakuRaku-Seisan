# -*- coding: utf-8 -*-
"""
Gemini multimodal OCR validator.

Sends document image + OCR text to Gemini for structured extraction.
Used as a validation/enhancement layer after YomiToku regex extraction.

API pattern reused from tools/video2pdd/phase1_video.py.

Auth (in priority order):
  1. GEMINI_API_KEY env var → Generative Language API (simplest)
  2. gcloud ADC → Vertex AI endpoint (requires GCP project)

Created: 2026-02-08
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"
MAX_RETRIES = 3
RETRY_DELAY_SEC = 3

PROMPT_DIR = Path(__file__).parent / "prompts"
EXTRACT_PROMPT_FILE = PROMPT_DIR / "ocr_multimodal_extract.txt"
RECONCILE_PROMPT_FILE = PROMPT_DIR / "ocr_reconcile.txt"

# Vertex AI config (used when no API key available)
VERTEX_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "robotic-catwalk-464100-m3")
VERTEX_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")


def _get_api_key() -> Optional[str]:
    """Get Gemini API key from environment variable (returns None if not set)."""
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _get_gcloud_token() -> str:
    """Get access token from gcloud CLI."""
    gcloud_paths = [
        r"C:\Users\masam\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        "gcloud",
    ]
    for gcloud in gcloud_paths:
        try:
            token = subprocess.check_output(
                [gcloud, "auth", "print-access-token"],
                text=True,
                shell=True,
                timeout=10,
            ).strip()
            if token:
                return token
        except (subprocess.SubprocessError, FileNotFoundError):
            continue
    raise RuntimeError(
        "Cannot authenticate with Gemini API.\n"
        "Option 1: Set GEMINI_API_KEY (get from https://aistudio.google.com/apikey)\n"
        "Option 2: Install gcloud CLI and run: gcloud auth login"
    )


def _extract_json(raw_output: str) -> dict[str, Any]:
    """Extract JSON from Gemini output (handles markdown fences)."""
    text = raw_output.strip()

    # Remove markdown code fences if present
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()

    # Try parsing as-is first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try finding the first { ... } block
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not parse Gemini output as JSON. "
        f"First 200 chars: {raw_output[:200]}"
    )


def _pdf_to_png_bytes(pdf_path: Path, dpi: int = 300) -> bytes:
    """Convert first page of PDF to PNG bytes for Gemini input."""
    import fitz

    doc = fitz.open(str(pdf_path))
    page = doc[0]

    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)

    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes


def _load_prompt(prompt_file: Path) -> str:
    """Load prompt template from file."""
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    return prompt_file.read_text(encoding="utf-8")


class GeminiOCRValidator:
    """
    Gemini multimodal OCR validation/enhancement.

    Sends document image + OCR text to Gemini for structured extraction.
    Returns extraction result compatible with PDFExtractResult.

    Auth strategy:
      1. If GEMINI_API_KEY set → use google-genai SDK (simplest)
      2. Else → use Vertex AI REST API with gcloud token
    """

    def __init__(
        self,
        model: str = GEMINI_MODEL,
        extract_prompt_path: Optional[Path] = None,
        reconcile_prompt_path: Optional[Path] = None,
    ):
        self.model = model
        self._client = None
        self._auth_mode: Optional[str] = None  # "api_key" or "vertex_ai"
        self._extract_prompt = _load_prompt(
            extract_prompt_path or EXTRACT_PROMPT_FILE
        )
        self._reconcile_prompt = _load_prompt(
            reconcile_prompt_path or RECONCILE_PROMPT_FILE
        )

    def _init_auth(self) -> None:
        """Determine and initialize auth method."""
        if self._auth_mode is not None:
            return

        api_key = _get_api_key()
        if api_key:
            from google import genai

            self._client = genai.Client(api_key=api_key)
            self._auth_mode = "api_key"
            logger.info("Gemini auth: API key")
        else:
            # Verify gcloud token works
            _get_gcloud_token()
            self._auth_mode = "vertex_ai"
            logger.info("Gemini auth: Vertex AI (gcloud)")

    def _call_gemini_with_image(
        self,
        image_bytes: bytes,
        prompt_text: str,
    ) -> str:
        """Call Gemini API with image bytes and prompt. Returns raw text."""
        self._init_auth()

        for attempt in range(1, MAX_RETRIES + 1):
            logger.info(
                "Gemini OCR validation attempt %d/%d...",
                attempt,
                MAX_RETRIES,
            )
            try:
                if self._auth_mode == "api_key":
                    text = self._call_via_sdk(image_bytes, prompt_text)
                else:
                    text = self._call_via_vertex(image_bytes, prompt_text)

                if text:
                    return text

                logger.warning(
                    "Gemini attempt %d returned empty response", attempt,
                )

            except Exception as e:
                logger.warning(
                    "Gemini attempt %d failed: %s",
                    attempt,
                    str(e)[:200],
                )

            if attempt < MAX_RETRIES:
                logger.info("Retrying in %d seconds...", RETRY_DELAY_SEC)
                time.sleep(RETRY_DELAY_SEC)

        raise RuntimeError(
            f"Gemini API failed after {MAX_RETRIES} attempts."
        )

    def _call_via_sdk(self, image_bytes: bytes, prompt_text: str) -> str:
        """Call via google-genai SDK (API key auth)."""
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/png",
                ),
                prompt_text,
            ],
        )
        return response.text.strip() if response.text else ""

    def _call_via_vertex(self, image_bytes: bytes, prompt_text: str) -> str:
        """Call via Vertex AI REST API (gcloud auth)."""
        token = _get_gcloud_token()
        url = (
            f"https://{VERTEX_LOCATION}-aiplatform.googleapis.com/v1/"
            f"projects/{VERTEX_PROJECT}/locations/{VERTEX_LOCATION}/"
            f"publishers/google/models/{self.model}:generateContent"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                        {"text": prompt_text},
                    ],
                }
            ],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip() if text else ""

    def validate(
        self,
        pdf_path: Path,
        ocr_text: str,
        dpi: int = 300,
    ) -> dict[str, Any]:
        """
        Send document image + OCR text to Gemini for multimodal extraction.

        Args:
            pdf_path: Path to preprocessed PDF file.
            ocr_text: Raw OCR text from YomiToku.
            dpi: Resolution for PDF to image conversion.

        Returns:
            Dict with extracted fields:
            vendor_name, issue_date, amount, invoice_number,
            document_type, description, confidence, reasoning.
        """
        # Convert PDF to PNG bytes (no temp file needed)
        image_bytes = _pdf_to_png_bytes(pdf_path, dpi=dpi)

        # Build prompt with OCR text
        prompt = self._extract_prompt.replace("{ocr_text}", ocr_text or "(no OCR text available)")

        # Call Gemini
        raw_output = self._call_gemini_with_image(image_bytes, prompt)

        # Parse JSON response
        result = _extract_json(raw_output)

        # Normalize fields
        result["vendor_name"] = str(result.get("vendor_name", "")).strip()
        result["issue_date"] = str(result.get("issue_date", "")).strip()
        result["invoice_number"] = str(result.get("invoice_number", "")).strip()
        result["document_type"] = str(result.get("document_type", "領収書")).strip()
        result["description"] = str(result.get("description", "")).strip()
        result["reasoning"] = str(result.get("reasoning", "")).strip()

        # Normalize amount to int
        raw_amount = result.get("amount", 0)
        if isinstance(raw_amount, str):
            raw_amount = re.sub(r"[,，\s¥￥円]", "", raw_amount)
        try:
            result["amount"] = int(float(raw_amount))
        except (ValueError, TypeError):
            result["amount"] = 0

        # Normalize confidence to float
        try:
            result["confidence"] = float(result.get("confidence", 0.0))
        except (ValueError, TypeError):
            result["confidence"] = 0.0

        # Validate invoice_number format (T + 13 digits)
        inv = result["invoice_number"]
        if inv and not re.match(r"^T\d{13}$", inv):
            # Try to fix common OCR misreads
            cleaned = re.sub(r"^[7１1I]", "T", inv)
            cleaned = re.sub(r"[^\dT]", "", cleaned)
            if re.match(r"^T\d{13}$", cleaned):
                result["invoice_number"] = cleaned
            else:
                result["invoice_number"] = ""

        logger.info(
            "Gemini extraction: vendor=%s, date=%s, amount=%s, confidence=%.2f",
            result["vendor_name"],
            result["issue_date"],
            result["amount"],
            result["confidence"],
        )

        return result

    def reconcile(
        self,
        pdf_path: Path,
        regex_result: dict[str, Any],
        llm_result: dict[str, Any],
        dpi: int = 300,
    ) -> dict[str, Any]:
        """
        When regex and LLM disagree, send both candidates to Gemini
        for reconciliation.

        Args:
            pdf_path: Path to preprocessed PDF file.
            regex_result: Fields extracted by regex.
            llm_result: Fields extracted by LLM.
            dpi: Resolution for PDF to image conversion.

        Returns:
            Dict with reconciled field values and corrections array.
        """
        # Find disagreements
        compare_fields = ["vendor_name", "issue_date", "amount", "invoice_number"]
        disagreements = []
        for field in compare_fields:
            rv = regex_result.get(field, "")
            lv = llm_result.get(field, "")
            # Both non-empty and different
            if rv and lv and str(rv) != str(lv):
                disagreements.append(
                    f"- {field}: A={rv}, B={lv}"
                )

        if not disagreements:
            logger.info("No disagreements between regex and LLM — skipping reconciliation.")
            return llm_result

        # Convert PDF to PNG bytes
        image_bytes = _pdf_to_png_bytes(pdf_path, dpi=dpi)

        # Build prompt
        prompt = self._reconcile_prompt
        prompt = prompt.replace(
            "{regex_result}",
            json.dumps(
                {k: regex_result.get(k, "") for k in compare_fields},
                ensure_ascii=False,
            ),
        )
        prompt = prompt.replace(
            "{llm_result}",
            json.dumps(
                {k: llm_result.get(k, "") for k in compare_fields},
                ensure_ascii=False,
            ),
        )
        prompt = prompt.replace("{disagreements}", "\n".join(disagreements))

        # Call Gemini
        raw_output = self._call_gemini_with_image(image_bytes, prompt)
        reconciled = _extract_json(raw_output)

        # Log corrections
        corrections = reconciled.get("corrections", [])
        for c in corrections:
            logger.info(
                "Reconciliation: %s → chose %s (%s)",
                c.get("field", "?"),
                c.get("chosen", "?"),
                c.get("reason", ""),
            )

        return reconciled
