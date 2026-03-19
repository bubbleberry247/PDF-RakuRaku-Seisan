"""Unit tests for L1 sender-based routing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from outlook_save_pdf_and_batch_print import (
    SenderRule,
    RoutingConfig,
    RoutingRule,
    ToolConfig,
    _resolve_route_by_sender,
    _determine_route_subdir,
    _sanitize_filename,
)


def _make_routing_cfg(
    sender_rules=(),
    ban_senders=frozenset(),
    rules=(),
    fallback="手動対応",
    threshold=1,
    tie_margin=None,
):
    return RoutingConfig(
        enabled=True,
        fallback_subdir=fallback,
        rules=rules,
        sender_rules=sender_rules,
        ban_senders=ban_senders,
        threshold=threshold,
        tie_margin=tie_margin,
    )


def _make_tool_cfg(routing_cfg):
    return ToolConfig(routing=routing_cfg)


# --- _resolve_route_by_sender tests ---

def test_known_sender_with_keyword_match():
    """既知sender + keyword一致 → 正しいsubdir"""
    cfg = _make_routing_cfg(
        sender_rules=(
            SenderRule(sender="test@example.com", subdir="3285_中村", keywords=("中島三丁目",)),
        ),
    )
    result = _resolve_route_by_sender(
        routing_cfg=cfg,
        sender="test@example.com",
        attachment_name="中島三丁目計画新築工事.pdf",
        subject="請求書",
    )
    assert result == "3285_中村", f"Expected '3285_中村', got '{result}'"
    print("PASS: test_known_sender_with_keyword_match")


def test_known_sender_keyword_mismatch():
    """既知sender + keyword不一致 → 空文字（fallback行き）"""
    cfg = _make_routing_cfg(
        sender_rules=(
            SenderRule(sender="test@example.com", subdir="3285_中村", keywords=("中島三丁目",)),
        ),
    )
    result = _resolve_route_by_sender(
        routing_cfg=cfg,
        sender="test@example.com",
        attachment_name="全然関係ない.pdf",
        subject="全然関係ない件名",
    )
    assert result == "", f"Expected '', got '{result}'"
    print("PASS: test_known_sender_keyword_mismatch")


def test_known_sender_no_keywords():
    """既知sender + keywords空 → sender一致のみで振り分け"""
    cfg = _make_routing_cfg(
        sender_rules=(
            SenderRule(sender="nokey@example.com", subdir="営繕", keywords=()),
        ),
    )
    result = _resolve_route_by_sender(
        routing_cfg=cfg,
        sender="nokey@example.com",
        attachment_name="任意.pdf",
        subject="任意の件名",
    )
    assert result == "営繕", f"Expected '営繕', got '{result}'"
    print("PASS: test_known_sender_no_keywords")


def test_unknown_sender():
    """未知sender → 空文字"""
    cfg = _make_routing_cfg(
        sender_rules=(
            SenderRule(sender="known@example.com", subdir="3285_中村", keywords=()),
        ),
    )
    result = _resolve_route_by_sender(
        routing_cfg=cfg,
        sender="unknown@example.com",
        attachment_name="test.pdf",
        subject="test",
    )
    assert result == "", f"Expected '', got '{result}'"
    print("PASS: test_unknown_sender")


def test_sender_case_insensitive():
    """sender比較はcase-insensitive"""
    cfg = _make_routing_cfg(
        sender_rules=(
            SenderRule(sender="test@example.com", subdir="営繕", keywords=()),
        ),
    )
    result = _resolve_route_by_sender(
        routing_cfg=cfg,
        sender="TEST@Example.COM",
        attachment_name="test.pdf",
        subject="test",
    )
    assert result == "営繕", f"Expected '営繕', got '{result}'"
    print("PASS: test_sender_case_insensitive")


# --- _determine_route_subdir tests ---

def test_ban_sender_goes_to_fallback():
    """BAN sender → fallback"""
    routing_cfg = _make_routing_cfg(
        sender_rules=(
            SenderRule(sender="banned@example.com", subdir="3285_中村", keywords=()),
        ),
        ban_senders=frozenset({"banned@example.com"}),
        fallback="手動対応_test",
    )
    tool_cfg = _make_tool_cfg(routing_cfg)
    result = _determine_route_subdir(
        cfg=tool_cfg,
        sender="banned@example.com",
        attachment_name="中村区test.pdf",
        subject="test",
        full_text="test",
    )
    assert result == "手動対応_test", f"Expected '手動対応_test', got '{result}'"
    print("PASS: test_ban_sender_goes_to_fallback")


def test_l1_takes_priority_over_l2():
    """L1がL2より優先される"""
    routing_cfg = _make_routing_cfg(
        sender_rules=(
            SenderRule(sender="test@example.com", subdir="L1_result", keywords=()),
        ),
        fallback="fallback",
    )
    tool_cfg = _make_tool_cfg(routing_cfg)
    result = _determine_route_subdir(
        cfg=tool_cfg,
        sender="test@example.com",
        attachment_name="test.pdf",
        subject="test",
        full_text="irrelevant text",
    )
    assert result == "L1_result", f"Expected 'L1_result', got '{result}'"
    print("PASS: test_l1_takes_priority_over_l2")


def test_routing_disabled():
    """routing disabled → 空文字"""
    routing_cfg = RoutingConfig(
        enabled=False,
        sender_rules=(SenderRule(sender="test@example.com", subdir="3285_中村", keywords=()),),
    )
    tool_cfg = _make_tool_cfg(routing_cfg)
    result = _determine_route_subdir(
        cfg=tool_cfg,
        sender="test@example.com",
        attachment_name="test.pdf",
        subject="test",
        full_text="test",
    )
    assert result == "", f"Expected '', got '{result}'"
    print("PASS: test_routing_disabled")


def test_fallback_when_no_match():
    """L1不一致 + L2不一致 → fallback"""
    routing_cfg = _make_routing_cfg(
        sender_rules=(
            SenderRule(sender="other@example.com", subdir="3285_中村", keywords=()),
        ),
        fallback="手動対応_test",
    )
    tool_cfg = _make_tool_cfg(routing_cfg)
    result = _determine_route_subdir(
        cfg=tool_cfg,
        sender="nomatch@example.com",
        attachment_name="test.pdf",
        subject="test",
        full_text="irrelevant",
    )
    assert result == "手動対応_test", f"Expected '手動対応_test', got '{result}'"
    print("PASS: test_fallback_when_no_match")


if __name__ == "__main__":
    tests = [
        test_known_sender_with_keyword_match,
        test_known_sender_keyword_mismatch,
        test_known_sender_no_keywords,
        test_unknown_sender,
        test_sender_case_insensitive,
        test_ban_sender_goes_to_fallback,
        test_l1_takes_priority_over_l2,
        test_routing_disabled,
        test_fallback_when_no_match,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {t.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed > 0:
        sys.exit(1)
    print("ALL TESTS PASSED")
