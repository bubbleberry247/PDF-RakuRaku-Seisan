"""
jp_norm.py — Stage 3: 日本語正規化（唯一の正規化パス）

モデル出力のraw_jaテキストを決定論的に正規化する。
冪等: 何度適用しても同じ結果。
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date


# ---------------------------------------------------------------------------
# 文字幅正規化（全角→半角）
# ---------------------------------------------------------------------------

def normalize_width(text: str) -> str:
    """全角英数→半角、半角カナ→全角カナ。"""
    return unicodedata.normalize("NFKC", text)


# ---------------------------------------------------------------------------
# 漢数字→算用数字
# ---------------------------------------------------------------------------

_KANJI_DIGITS = {
    "〇": 0, "零": 0, "一": 1, "壱": 1, "二": 2, "弐": 2,
    "三": 3, "参": 3, "四": 4, "五": 5, "伍": 5, "六": 6,
    "七": 7, "八": 8, "九": 9,
}
_KANJI_UNITS = {
    "十": 10, "拾": 10, "百": 100, "千": 1000, "阡": 1000,
}
_KANJI_BIG = {
    "万": 10_000, "萬": 10_000, "億": 100_000_000,
    "兆": 1_000_000_000_000,
}


def kanji_to_int(text: str) -> int | None:
    """漢数字テキストを整数に変換。変換できなければNone。"""
    text = normalize_width(text).strip()

    # Remove common suffixes
    for suffix in ["円", "圓", "￥", "¥"]:
        text = text.replace(suffix, "")
    text = text.strip()

    if not text:
        return None

    # If already a number
    cleaned = text.replace(",", "").replace(".", "").replace(" ", "")
    if cleaned.isdigit():
        return int(cleaned)

    # Parse kanji
    try:
        total = 0
        big_unit_val = 0
        current = 0
        last_unit = 1

        for ch in text:
            if ch in _KANJI_DIGITS:
                current = _KANJI_DIGITS[ch]
            elif ch in _KANJI_UNITS:
                unit = _KANJI_UNITS[ch]
                if current == 0:
                    current = 1
                big_unit_val += current * unit
                current = 0
                last_unit = unit
            elif ch in _KANJI_BIG:
                big = _KANJI_BIG[ch]
                big_unit_val += current
                if big_unit_val == 0:
                    big_unit_val = 1
                total += big_unit_val * big
                big_unit_val = 0
                current = 0
            else:
                return None  # Unrecognized character

        total += big_unit_val + current
        return total if total > 0 else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 金額正規化
# ---------------------------------------------------------------------------

def normalize_amount(raw: str | None) -> int | None:
    """金額テキストを整数に正規化。"""
    if not raw:
        return None

    text = normalize_width(str(raw)).strip()

    # Remove currency symbols and whitespace
    for ch in ["￥", "¥", "円", "圓", "JPY", "jpy", "\\", "　", " "]:
        text = text.replace(ch, "")

    # Remove thousand separators
    text = text.replace(",", "")

    # Remove trailing hyphen/dash (e.g., "108,278-" → "108278")
    text = text.rstrip("-ー−‐")

    # Try direct integer parse
    text = text.strip()
    if not text:
        return None

    # Handle negative
    negative = False
    if text.startswith("-") or text.startswith("△") or text.startswith("▲"):
        negative = True
        text = text[1:]

    # Try numeric
    try:
        val = int(float(text))
        return -val if negative else val
    except (ValueError, TypeError):
        pass

    # Try kanji
    val = kanji_to_int(text)
    if val is not None:
        return -val if negative else val

    return None


# ---------------------------------------------------------------------------
# 和暦→西暦
# ---------------------------------------------------------------------------

_ERA_OFFSETS = {
    "令和": 2018, "R": 2018, "r": 2018,
    "平成": 1988, "H": 1988, "h": 1988,
    "昭和": 1925, "S": 1925, "s": 1925,
    "大正": 1911, "T": 1911, "t": 1911,
    "明治": 1867, "M": 1867, "m": 1867,
}

_DATE_PATTERNS = [
    # 令和7年3月15日
    re.compile(r"(令和|平成|昭和|大正|明治)\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    # R7.3.15 or R7/3/15
    re.compile(r"([RHSTMrhstm])\s*(\d{1,2})\s*[./年]\s*(\d{1,2})\s*[./月]\s*(\d{1,2})"),
    # 2025年3月15日
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    # 2025/03/15 or 2025-03-15 or 2025.03.15
    re.compile(r"(\d{4})\s*[/\-\.]\s*(\d{1,2})\s*[/\-\.]\s*(\d{1,2})"),
    # 25年12月24日 (2桁年号 — 元号なし、20xx年と推定)
    re.compile(r"(\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
]

# Month-only patterns (日が省略されたケース: "2025年12月ご請求分" → 2025-12-01)
_DATE_MONTH_PATTERNS = [
    # 2025年12月
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月"),
    # 令和7年12月
    re.compile(r"(令和|平成|昭和|大正|明治)\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月"),
]


def normalize_date(raw: str | None) -> str | None:
    """日付テキストをYYYY-MM-DD形式に正規化。"""
    if not raw:
        return None

    text = normalize_width(str(raw)).strip()

    # Try full date patterns first (year + month + day)
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue

        groups = m.groups()

        if len(groups) == 4:
            era_or_year = groups[0]
            y_raw, month, day = int(groups[1]), int(groups[2]), int(groups[3])

            if era_or_year in _ERA_OFFSETS:
                year = _ERA_OFFSETS[era_or_year] + y_raw
            else:
                year = y_raw
        elif len(groups) == 3:
            y_val = int(groups[0])
            month, day = int(groups[1]), int(groups[2])
            # 2桁年号の補完: 0-49 → 2000+, 50-99 → 1900+
            if y_val < 100:
                year = 2000 + y_val if y_val < 50 else 1900 + y_val
            else:
                year = y_val
        else:
            continue

        try:
            d = date(year, month, day)
            return d.isoformat()
        except (ValueError, TypeError):
            continue

    # Fallback: month-only patterns (日が省略: "2025年12月ご請求分" → 2025-12-01)
    for pattern in _DATE_MONTH_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue

        groups = m.groups()
        if len(groups) == 3:
            # 和暦 + 年 + 月
            era = groups[0]
            y_raw, month = int(groups[1]), int(groups[2])
            if era in _ERA_OFFSETS:
                year = _ERA_OFFSETS[era] + y_raw
            else:
                continue
        elif len(groups) == 2:
            # 西暦 + 月
            year, month = int(groups[0]), int(groups[1])
        else:
            continue

        try:
            d = date(year, month, 1)  # 日は1日で補完
            return d.isoformat()
        except (ValueError, TypeError):
            continue

    return None


# ---------------------------------------------------------------------------
# 会社名正規化
# ---------------------------------------------------------------------------

_COMPANY_VARIANTS = [
    ("㈱", "株式会社"), ("㈲", "有限会社"), ("㈳", "一般社団法人"),
    ("(株)", "株式会社"), ("(有)", "有限会社"),
    ("（株）", "株式会社"), ("（有）", "有限会社"),
]


def normalize_company(raw: str | None) -> str | None:
    """会社名を正規化。"""
    if not raw:
        return None

    text = normalize_width(str(raw)).strip()

    # Replace abbreviations
    for abbr, full in _COMPANY_VARIANTS:
        text = text.replace(abbr, full)

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text if text else None


# ---------------------------------------------------------------------------
# ID正規化
# ---------------------------------------------------------------------------

def normalize_id(raw: str | None) -> str | None:
    """ID/番号を半角英数に正規化。"""
    if not raw:
        return None

    text = normalize_width(str(raw)).strip()
    # Remove common prefixes/suffixes
    text = text.replace("第", "").replace("号", "").strip()
    # Remove spaces
    text = text.replace(" ", "").replace("　", "")

    return text if text else None


# ---------------------------------------------------------------------------
# Unified normalizer
# ---------------------------------------------------------------------------

def normalize_field(raw: str | None, field_type: str) -> tuple[Any, bool]:
    """
    Normalize a raw field value based on its type.

    Returns:
        (normalized_value, success)
    """
    if raw is None:
        return None, True  # null is valid (field not found)

    if field_type == "amount":
        val = normalize_amount(raw)
        return val, val is not None

    if field_type == "date":
        val = normalize_date(raw)
        return val, val is not None

    if field_type == "company":
        val = normalize_company(raw)
        return val, val is not None

    if field_type == "id":
        val = normalize_id(raw)
        return val, val is not None

    # text: just width-normalize
    val = normalize_width(str(raw)).strip()
    return val, True
