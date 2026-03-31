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
