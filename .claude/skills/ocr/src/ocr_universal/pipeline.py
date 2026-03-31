"""
pipeline.py — 4段階パイプラインオーケストレーター

PDF → [Stage1 分類] → [Stage2 GPT-5.4] → [Stage3 正規化+検証] → [Stage4 品質ゲート]
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from .contracts import (
    ExtractedField,
    PageContext,
    PipelineResult,
    RoutingDecision,
    ValidatedField,
    ValidationStatus,
    make_idempotency_key,
)
from .gpt54_extractor import extract_fields
from .jp_norm import normalize_field
from .quality_gate import route_result


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_scenario_config(scenario_dir: Path) -> dict:
    """Load fields.yaml from scenario directory."""
    import yaml
    fields_path = scenario_dir / "fields.yaml"
    if not fields_path.exists():
        raise FileNotFoundError(f"Scenario config not found: {fields_path}")
    with fields_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Stage 1: PDF Classification + Extraction
# ---------------------------------------------------------------------------

def _classify_pdf(pdf_path: str) -> list[PageContext]:
    """Classify PDF and extract page images."""
    path = Path(pdf_path)
    pdf_bytes = path.read_bytes()

    doc = fitz.open(pdf_path)
    pages: list[PageContext] = []

    for page_no in range(len(doc)):
        page = doc[page_no]

        # Extract text layer
        text = page.get_text("text") or ""

        # Calculate CJK ratio
        cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff"
                        or "\u3040" <= ch <= "\u309f"
                        or "\u30a0" <= ch <= "\u30ff")
        total_chars = len(text.strip())
        cjk_ratio = cjk_count / total_chars if total_chars > 0 else 0.0

        has_text = total_chars > 50 and cjk_ratio > 0.3

        # Render page as image (for GPT-5.4)
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom = ~144 DPI
        pix = page.get_pixmap(matrix=mat)
        image_bytes = pix.tobytes("png")

        ctx = PageContext(
            doc_id="",  # Set later with idempotency key
            page_no=page_no + 1,
            total_pages=len(doc),
            pdf_path=str(path),
            image_bytes=image_bytes,
            text_layer=text,
            has_text_layer=has_text,
            cjk_ratio=cjk_ratio,
        )
        pages.append(ctx)

    doc.close()
    return pages


# ---------------------------------------------------------------------------
# Stage 3: Normalize + Validate
# ---------------------------------------------------------------------------

def _normalize_and_validate(
    ctx: PageContext,
    field_defs: list[dict],
    validations: list[dict] | None = None,
) -> PageContext:
    """Apply jp_norm and field validation."""
    for ef in ctx.extracted_fields:
        # Find field def
        fd = next((d for d in field_defs if d["name"] == ef.name), None)
        field_type = fd["type"] if fd else "text"

        # Normalize
        normalized, success = normalize_field(ef.raw_ja, field_type)

        # Determine validation status
        if ef.raw_ja is None:
            status = ValidationStatus.PASS  # null = not found (OK if not required)
            msg = ""
        elif not success:
            status = ValidationStatus.FAIL
            msg = f"正規化失敗: raw='{ef.raw_ja}'"
        else:
            status = ValidationStatus.PASS
            msg = ""

        ctx.validated_fields.append(ValidatedField(
            name=ef.name,
            raw_ja=ef.raw_ja,
            normalized=normalized,
            validation_status=status,
            validation_message=msg,
            evidence=ef.evidence,
            page_no=ef.page_no,
        ))

    # Cross-field validations (from scenario config)
    if validations:
        _apply_cross_field_validations(ctx, validations)

    return ctx


def _apply_cross_field_validations(
    ctx: PageContext,
    validations: list[dict],
) -> None:
    """Apply cross-field validation rules."""
    field_map = {f.name: f for f in ctx.validated_fields}

    for rule_def in validations:
        rule = rule_def.get("rule", "")
        severity = rule_def.get("severity", "WARN")

        # Simple rule evaluation (safe subset)
        try:
            if "==" in rule and "+" in rule:
                # e.g., "total_amount == subtotal + tax_amount"
                parts = rule.split("==")
                lhs_name = parts[0].strip()
                rhs_parts = parts[1].strip().split("+")

                lhs = field_map.get(lhs_name)
                if not lhs or lhs.normalized is None:
                    continue

                rhs_sum = 0
                all_present = True
                for rp in rhs_parts:
                    rp = rp.strip()
                    rf = field_map.get(rp)
                    if not rf or rf.normalized is None:
                        all_present = False
                        break
                    rhs_sum += rf.normalized

                if all_present and lhs.normalized != rhs_sum:
                    status = ValidationStatus.FAIL if severity == "FAIL" else ValidationStatus.WARN
                    lhs.validation_status = status
                    lhs.validation_message = f"クロスフィールド不一致: {rule}"

            elif "<= today" in rule:
                # e.g., "issue_date <= today"
                field_name = rule.replace("<= today", "").strip()
                f = field_map.get(field_name)
                if f and f.normalized:
                    from datetime import date as date_type
                    try:
                        d = date_type.fromisoformat(str(f.normalized))
                        if d > date_type.today():
                            status = ValidationStatus.WARN if severity == "WARN" else ValidationStatus.FAIL
                            f.validation_status = status
                            f.validation_message = f"未来の日付: {f.normalized}"
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass  # Skip malformed rules silently


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

class UniversalOCRPipeline:
    """4-stage OCR pipeline orchestrator."""

    def __init__(
        self,
        scenario: str,
        scenario_dir: Path | None = None,
        api_key: str | None = None,
        model: str = "gpt-5.4",
    ):
        self.scenario = scenario
        self.api_key = api_key
        self.model = model

        # Load scenario config
        if scenario_dir is None:
            skill_root = Path(__file__).parent.parent.parent
            scenario_dir = skill_root / "scenarios" / scenario

        self.config = load_scenario_config(scenario_dir)
        self.field_defs = self.config.get("fields", [])
        self.validations = self.config.get("validations", [])

    def process(self, pdf_path: str) -> PipelineResult:
        """Process a PDF through the 4-stage pipeline."""
        start_time = time.time()

        # Read PDF bytes for idempotency key
        pdf_bytes = Path(pdf_path).read_bytes()
        idem_key = make_idempotency_key(pdf_bytes, self.scenario)

        # Stage 1: Classify + Extract pages
        pages = _classify_pdf(pdf_path)
        for p in pages:
            p.doc_id = idem_key

        # Stage 2: GPT-5.4 extraction (or text layer)
        for page in pages:
            if page.has_text_layer:
                # Use text layer directly (create pseudo-extracted fields)
                page.source = "text_layer"
                # TODO: Parse text layer into fields (scenario-specific)
                # For now, still send to API
                page = extract_fields(page, self.field_defs, self.api_key, self.model)
            else:
                page = extract_fields(page, self.field_defs, self.api_key, self.model)

        # Stage 3: Normalize + Validate
        for page in pages:
            page = _normalize_and_validate(page, self.field_defs, self.validations)

        # Multi-page merge (use first page with data)
        merged_fields: list[ValidatedField] = []
        if len(pages) == 1:
            merged_fields = pages[0].validated_fields
        else:
            # Merge strategy: first non-null value per field
            seen: set[str] = set()
            for page in pages:
                for vf in page.validated_fields:
                    if vf.name not in seen and vf.raw_ja is not None:
                        merged_fields.append(vf)
                        seen.add(vf.name)
            # Fill missing from any page
            for page in pages:
                for vf in page.validated_fields:
                    if vf.name not in seen:
                        merged_fields.append(vf)
                        seen.add(vf.name)

        # Stage 4: Quality Gate
        has_api_error = any(p.source == "api_failed" for p in pages)
        routing, reason = route_result(merged_fields, self.field_defs, has_api_error)

        # Build result
        fields_dict = {}
        for vf in merged_fields:
            fields_dict[vf.name] = vf.normalized

        total_cost = sum(p.api_cost_usd for p in pages)
        total_tokens = sum(p.api_tokens_used for p in pages)
        all_errors = []
        for p in pages:
            all_errors.extend(p.errors)

        result = PipelineResult(
            doc_id=idem_key,
            idempotency_key=idem_key,
            scenario=self.scenario,
            routing=routing,
            routing_reason=reason,
            fields=fields_dict,
            validated_fields=merged_fields,
            pages=pages,
            total_api_cost_usd=total_cost,
            total_tokens=total_tokens,
            errors=all_errors,
        )

        return result
