"""
contracts.py — パイプライン全段を流れるデータ契約

全ステージはこれらの型を入出力とする。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FieldType(str, Enum):
    AMOUNT = "amount"
    DATE = "date"
    COMPANY = "company"
    ID = "id"
    TEXT = "text"


class ValidationStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class RoutingDecision(str, Enum):
    AUTO_ACCEPT = "auto_accept"
    QUICK_REVIEW = "quick_review"
    HUMAN_REVIEW = "human_review"
    FORCED_REVIEW = "forced_review"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    FORCED_REVIEW = "FORCED_REVIEW"


# ---------------------------------------------------------------------------
# Field definition (from scenario fields.yaml)
# ---------------------------------------------------------------------------

@dataclass
class FieldDef:
    """Scenario-specific field definition."""
    name: str
    type: FieldType
    required: bool = False
    critical: bool = False  # critical fields have stricter thresholds


# ---------------------------------------------------------------------------
# Extracted field value (output of Stage 2)
# ---------------------------------------------------------------------------

@dataclass
class ExtractedField:
    """Raw field extracted by GPT-5.4 Vision (no normalization)."""
    name: str
    raw_ja: str | None = None       # exact text from document
    evidence: str = ""               # where in the document
    page_no: int = 1


# ---------------------------------------------------------------------------
# Normalized + validated field (output of Stage 3)
# ---------------------------------------------------------------------------

@dataclass
class ValidatedField:
    """Field after jp_norm normalization + validation."""
    name: str
    raw_ja: str | None = None        # original from model
    normalized: Any = None            # after jp_norm (int for amount, str for date, etc.)
    validation_status: ValidationStatus = ValidationStatus.PASS
    validation_message: str = ""
    evidence: str = ""
    page_no: int = 1
    source: str = ""                  # "vision_first" | "vision_corrected_with_aux" | "unresolved"


# ---------------------------------------------------------------------------
# Page context (flows through entire pipeline)
# ---------------------------------------------------------------------------

@dataclass
class PageContext:
    """Single page flowing through the pipeline."""
    doc_id: str                       # deterministic: hash(pdf_bytes + scenario + schema_version)
    page_no: int = 1
    total_pages: int = 1
    pdf_path: str = ""
    image_bytes: bytes | None = None
    text_layer: str = ""              # from PyMuPDF (if available)
    has_text_layer: bool = False
    cjk_ratio: float = 0.0

    # PaddleOCR auxiliary text
    aux_ocr_text: str = ""            # PaddleOCR full text output
    aux_ocr_available: bool = False   # whether PaddleOCR was run

    # Stage 2 output
    extracted_fields: list[ExtractedField] = field(default_factory=list)
    api_raw_response: dict[str, Any] = field(default_factory=dict)

    # Stage 3 output
    validated_fields: list[ValidatedField] = field(default_factory=list)

    # Stage 4 output
    routing: RoutingDecision = RoutingDecision.HUMAN_REVIEW
    routing_reason: str = ""

    # Metadata
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source: str = ""                  # "gpt54" | "text_layer" | "fallback"
    processing_time_ms: int = 0
    api_tokens_used: int = 0
    api_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Pipeline result (final output)
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Final result of the OCR pipeline."""
    doc_id: str
    idempotency_key: str              # hash(pdf_bytes + scenario + schema_version)
    scenario: str
    routing: RoutingDecision
    routing_reason: str
    fields: dict[str, Any]            # {field_name: normalized_value}
    validated_fields: list[ValidatedField] = field(default_factory=list)
    pages: list[PageContext] = field(default_factory=list)
    total_api_cost_usd: float = 0.0
    total_tokens: int = 0
    errors: list[str] = field(default_factory=list)
    paddle_mode: str = ""             # "always" | "fallback" | "off"


# ---------------------------------------------------------------------------
# Idempotency key generation
# ---------------------------------------------------------------------------

def make_idempotency_key(pdf_bytes: bytes, scenario: str, schema_version: str = "1") -> str:
    """Generate deterministic idempotency key from PDF content + scenario."""
    h = hashlib.sha256()
    h.update(pdf_bytes)
    h.update(scenario.encode("utf-8"))
    h.update(schema_version.encode("utf-8"))
    return h.hexdigest()[:32]
