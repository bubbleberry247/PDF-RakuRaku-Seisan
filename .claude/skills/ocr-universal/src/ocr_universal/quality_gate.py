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
