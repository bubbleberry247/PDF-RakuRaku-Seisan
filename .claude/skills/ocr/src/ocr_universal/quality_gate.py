"""
quality_gate.py — Stage 4: 品質ゲート（決定論的判定）

confidenceは参考情報のみ。判定は決定論的検証の結果に基づく。
"""
from __future__ import annotations

from .contracts import (
    PageContext,
    PipelineResult,
    RoutingDecision,
    ValidatedField,
    ValidationStatus,
)


def route_result(
    validated_fields: list[ValidatedField],
    field_defs: list[dict],
    has_api_error: bool = False,
) -> tuple[RoutingDecision, str]:
    """
    Determine routing based on deterministic validation results.

    Rules:
    1. API error → FORCED_REVIEW
    2. Any required field missing (raw_ja=None) → HUMAN_REVIEW
    3. Any FAIL validation → HUMAN_REVIEW
    4. Any WARN validation → QUICK_REVIEW
    5. All PASS → AUTO_ACCEPT
    """
    if has_api_error:
        return RoutingDecision.FORCED_REVIEW, "API呼び出し失敗"

    # Build lookup
    field_map = {f.name: f for f in validated_fields}
    required_defs = {fd["name"] for fd in field_defs if fd.get("required")}

    reasons: list[str] = []

    # Check required fields
    for name in required_defs:
        f = field_map.get(name)
        if not f or f.raw_ja is None:
            return RoutingDecision.HUMAN_REVIEW, f"必須フィールド欠損: {name}"

    # Check validation statuses
    has_fail = False
    has_warn = False

    for f in validated_fields:
        if f.validation_status == ValidationStatus.FAIL:
            has_fail = True
            reasons.append(f"{f.name}: {f.validation_message}")
        elif f.validation_status == ValidationStatus.WARN:
            has_warn = True
            reasons.append(f"{f.name}: {f.validation_message}")

    if has_fail:
        return RoutingDecision.HUMAN_REVIEW, "検証FAIL: " + "; ".join(reasons)

    if has_warn:
        return RoutingDecision.QUICK_REVIEW, "検証WARN: " + "; ".join(reasons)

    return RoutingDecision.AUTO_ACCEPT, "全フィールド検証PASS"


# ---------------------------------------------------------------------------
# PaddleOCR fallback trigger
# ---------------------------------------------------------------------------

def needs_paddle_fallback(
    validated_fields: list[ValidatedField],
    field_defs: list[dict],
) -> tuple[bool, str]:
    """
    Determine if PaddleOCR fallback should be triggered.

    Checks beyond just Null:
    - Null required fields
    - Format invalid (normalization failed)
    - Plausibility issues (future date, zero amount, etc.)

    Returns:
        (needs_fallback, reason)
    """
    field_map = {f.name: f for f in validated_fields}
    required_defs = {fd["name"]: fd for fd in field_defs if fd.get("required")}

    reasons = []

    for name, fd in required_defs.items():
        f = field_map.get(name)

        # Null check
        if not f or f.raw_ja is None:
            reasons.append(f"{name}: null")
            continue

        # Format validity (normalization failed)
        if f.validation_status == ValidationStatus.FAIL:
            reasons.append(f"{name}: format_invalid ({f.validation_message})")
            continue

        # Type-specific plausibility checks
        field_type = fd.get("type", "text")

        if field_type == "amount" and f.normalized is not None:
            if f.normalized == 0:
                reasons.append(f"{name}: zero_amount")
            elif f.normalized < 0:
                reasons.append(f"{name}: negative_amount")

        if field_type == "date" and f.normalized is not None:
            try:
                from datetime import date as date_type
                d = date_type.fromisoformat(str(f.normalized))
                if d.year < 2000:
                    reasons.append(f"{name}: suspicious_year ({d.year})")
            except (ValueError, TypeError):
                reasons.append(f"{name}: date_parse_error")

        if field_type == "company" and f.normalized is not None:
            # Check if vendor name is suspiciously short or only symbols
            text = str(f.normalized).strip()
            if len(text) < 2:
                reasons.append(f"{name}: too_short ({text})")

    if reasons:
        return True, "; ".join(reasons)

    return False, ""
