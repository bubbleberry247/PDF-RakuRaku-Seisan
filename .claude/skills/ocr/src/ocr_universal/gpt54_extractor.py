"""
gpt54_extractor.py — Stage 2: GPT-5.4 Vision API でフィールド候補値を抽出

モデルにはraw出力のみを要求。正規化はしない。
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any

from .contracts import ExtractedField, PageContext

PROMPT_PATH = Path(__file__).parent.parent.parent / "templates" / "prompt.system.txt"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


def _load_system_prompt() -> str:
    """Load system prompt from template file."""
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _build_field_schema(field_defs: list[dict]) -> dict:
    """Build JSON Schema for structured output from field definitions."""
    properties = {}
    required = []

    for fd in field_defs:
        name = fd["name"]
        properties[name] = {
            "type": "object",
            "properties": {
                "raw_ja": {"type": ["string", "null"]},
                "evidence": {"type": "string"},
            },
            "required": ["raw_ja", "evidence"],
        }
        if fd.get("required"):
            required.append(name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 data URI."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def extract_fields(
    ctx: PageContext,
    field_defs: list[dict],
    api_key: str | None = None,
    model: str = "gpt-5.4",
) -> PageContext:
    """
    Call GPT-5.4 Vision API to extract fields from a page image.

    Args:
        ctx: PageContext with image_bytes set
        field_defs: List of field definitions from scenario config
        api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        model: Model name

    Returns:
        Updated PageContext with extracted_fields populated
    """
    try:
        from openai import OpenAI
    except ImportError:
        ctx.errors.append("openai package not installed. Run: pip install openai")
        return ctx

    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        ctx.errors.append("OPENAI_API_KEY not set")
        return ctx

    if not ctx.image_bytes:
        ctx.errors.append("No image_bytes in PageContext")
        return ctx

    client = OpenAI(api_key=api_key)
    system_prompt = _load_system_prompt()
    schema = _build_field_schema(field_defs)

    field_names = [fd["name"] for fd in field_defs]
    user_prompt = (
        f"Extract the following fields from this document image:\n"
        f"{json.dumps(field_names, ensure_ascii=False)}\n\n"
        f"Return JSON matching this schema:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )

    image_url = _image_to_base64(ctx.image_bytes)

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
            ],
        },
    ]

    # Retry with exponential backoff
    start_time = time.time()
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                max_completion_tokens=2000,
                temperature=0.0,
            )

            raw_text = response.choices[0].message.content or "{}"
            ctx.api_raw_response = json.loads(raw_text)
            ctx.api_tokens_used = response.usage.total_tokens if response.usage else 0

            # Estimate cost (GPT-5.4 pricing approximate)
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            ctx.api_cost_usd = (prompt_tokens * 0.00001) + (completion_tokens * 0.00003)

            # Parse response into ExtractedField list
            for fd in field_defs:
                name = fd["name"]
                field_data = ctx.api_raw_response.get(name, {})
                if isinstance(field_data, dict):
                    ctx.extracted_fields.append(ExtractedField(
                        name=name,
                        raw_ja=field_data.get("raw_ja"),
                        evidence=field_data.get("evidence", ""),
                        page_no=ctx.page_no,
                    ))
                else:
                    ctx.extracted_fields.append(ExtractedField(
                        name=name,
                        raw_ja=str(field_data) if field_data else None,
                        evidence="",
                        page_no=ctx.page_no,
                    ))

            ctx.source = "gpt54"
            ctx.processing_time_ms = int((time.time() - start_time) * 1000)
            return ctx

        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                time.sleep(delay)

    # All retries failed
    ctx.errors.append(f"GPT-5.4 API failed after {MAX_RETRIES} retries: {last_error}")
    ctx.source = "api_failed"
    ctx.processing_time_ms = int((time.time() - start_time) * 1000)
    return ctx


# ---------------------------------------------------------------------------
# 2nd pass: Verify/Complete with auxiliary OCR text
# ---------------------------------------------------------------------------

_VERIFY_SYSTEM_PROMPT = """あなたは請求書画像から抽出済みの1回目OCR結果を検証・補完する役割です。
補助OCRテキストは別エンジンの参考情報です。補助OCRテキストのみを根拠に新規推測してはいけません。

ルール:
1. 1回目OCR結果を優先する
2. 1回目が null、空文字、または形式不正のフィールドのみ補完対象とする
3. 1回目と補助OCRが矛盾する場合は、必ず画像を見て判断する
4. 画像で確認できない場合は、値を変更せず元の値を維持する
5. 補助OCRテキストからの推測補完は禁止
6. 出力は指定JSONのみ。説明文は不要
7. 各フィールドに source を付ける: "vision_first" (1回目の値を維持) / "vision_corrected_with_aux" (補助OCRで補完・修正) / "unresolved" (確定できず)"""


def extract_fields_with_aux(
    ctx: PageContext,
    field_defs: list[dict],
    first_pass_fields: dict,
    aux_ocr_text: str,
    api_key: str | None = None,
    model: str = "gpt-5.4",
) -> PageContext:
    """
    2nd pass: Re-extract fields using image + auxiliary OCR text.

    Args:
        ctx: PageContext with image_bytes
        field_defs: Field definitions
        first_pass_fields: Dict of first-pass extracted values {name: raw_ja}
        aux_ocr_text: PaddleOCR full text output
        api_key: OpenAI API key
        model: Model name

    Returns:
        Updated PageContext with re-extracted fields
    """
    try:
        from openai import OpenAI
    except ImportError:
        ctx.errors.append("openai package not installed")
        return ctx

    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        ctx.errors.append("OPENAI_API_KEY not set")
        return ctx

    if not ctx.image_bytes:
        ctx.errors.append("No image_bytes in PageContext")
        return ctx

    client = OpenAI(api_key=api_key)

    # Build schema with source field
    schema = _build_field_schema(field_defs)
    # Add source to each field's properties
    for prop in schema["properties"].values():
        prop["properties"]["source"] = {"type": "string", "enum": ["vision_first", "vision_corrected_with_aux", "unresolved"]}
        prop["required"].append("source")

    # Format first-pass results
    first_pass_summary = json.dumps(first_pass_fields, ensure_ascii=False, indent=2)

    user_prompt = (
        f"1回目OCR結果:\n{first_pass_summary}\n\n"
        f"--- 補助OCRテキスト（別エンジン出力）---\n{aux_ocr_text}\n\n"
        f"上記を踏まえ、以下のフィールドを検証・補完してください:\n"
        f"{json.dumps([fd['name'] for fd in field_defs], ensure_ascii=False)}\n\n"
        f"Return JSON matching this schema:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )

    image_url = _image_to_base64(ctx.image_bytes)

    messages = [
        {"role": "system", "content": _VERIFY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
            ],
        },
    ]

    start_time = time.time()
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                max_completion_tokens=2000,
                temperature=0.0,
            )

            raw_text = response.choices[0].message.content or "{}"
            ctx.api_raw_response = json.loads(raw_text)
            ctx.api_tokens_used += response.usage.total_tokens if response.usage else 0

            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            ctx.api_cost_usd += (prompt_tokens * 0.00001) + (completion_tokens * 0.00003)

            # Clear previous extracted/validated fields for re-extraction
            ctx.extracted_fields.clear()
            ctx.validated_fields.clear()

            for fd in field_defs:
                name = fd["name"]
                field_data = ctx.api_raw_response.get(name, {})
                if isinstance(field_data, dict):
                    ef = ExtractedField(
                        name=name,
                        raw_ja=field_data.get("raw_ja"),
                        evidence=field_data.get("evidence", ""),
                        page_no=ctx.page_no,
                    )
                    ctx.extracted_fields.append(ef)
                else:
                    ctx.extracted_fields.append(ExtractedField(
                        name=name,
                        raw_ja=str(field_data) if field_data else None,
                        evidence="",
                        page_no=ctx.page_no,
                    ))

            ctx.source = "gpt54_with_aux"
            ctx.processing_time_ms += int((time.time() - start_time) * 1000)
            return ctx

        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                time.sleep(delay)

    ctx.errors.append(f"GPT-5.4 2nd pass failed after {MAX_RETRIES} retries: {last_error}")
    ctx.processing_time_ms += int((time.time() - start_time) * 1000)
    return ctx
