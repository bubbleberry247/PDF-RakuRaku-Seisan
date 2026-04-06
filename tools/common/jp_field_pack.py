"""Japanese field validation + normalization pack.

Enhances OCR post-processing with:
- Dual output (raw + normalized + provenance)
- Tax mode detection (tax_included / tax_excluded)
- Date precision tags (year / year_month / full)
- Company name provenance tracking
- Invoice number format validation

Designed to extend jp_norm.py without modifying it.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


# ---------------------------------------------------------------------------
# Output Schema
# ---------------------------------------------------------------------------

@dataclass
class NormalizedField:
    """Dual output: raw OCR text + normalized value + provenance."""
    raw: str                                          # Original OCR text (audit trail)
    value: Any                                        # Normalized value (machine-readable)
    confidence: float = 1.0                           # 0.0-1.0
    provenance: list[str] = field(default_factory=list)   # Applied rules
    metadata: dict[str, Any] = field(default_factory=dict)  # Extra info


@dataclass
class AmountField(NormalizedField):
    """Amount with tax mode."""
    price_mode: str | None = None     # "tax_included", "tax_excluded", None
    tax_rate: float | None = None     # 0.10, 0.08, None
    currency: str = "JPY"


@dataclass
class DateField(NormalizedField):
    """Date with precision."""
    precision: str = "full"           # "year", "year_month", "full"
    era: str | None = None            # "R", "H", "S", "T", "M"


@dataclass
class CompanyField(NormalizedField):
    """Company name with matching info."""
    similar_candidates: list[str] = field(default_factory=list)


@dataclass
class InvoiceNoField(NormalizedField):
    """Invoice number with format validation."""
    format_valid: bool = True
    format_type: str | None = None    # "t_number", "custom", None


# ---------------------------------------------------------------------------
# 1. Character Normalization
# ---------------------------------------------------------------------------

# Specific character unification mappings (applied after NFKC)
_CHAR_UNIFY = str.maketrans({
    # Wave dash variants → standard wave dash
    "～": "~",
    "〜": "~",
    # Long vowel / hyphen unification
    "ー": "ー",   # Katakana prolonged sound mark (keep as-is; ensure no half-width leaks)
    "−": "-",   # MINUS SIGN → hyphen-minus
    "－": "-",   # FULLWIDTH HYPHEN-MINUS → hyphen-minus
    "‐": "-",   # HYPHEN
    "‑": "-",   # NON-BREAKING HYPHEN
    "‒": "-",   # FIGURE DASH
    "–": "-",   # EN DASH
    "—": "-",   # EM DASH
    # Dot variants
    "．": ".",   # FULLWIDTH FULL STOP (numeric context)
    "。": "。",  # IDEOGRAPHIC FULL STOP (keep)
    # Comma variants (keep FULLWIDTH for number separators; NFKC handles most)
})

_ZERO_WIDTH = re.compile(
    r"[\u200b\u200c\u200d\ufeff\u00ad]"  # ZWSP, ZWNJ, ZWJ, BOM, SHY
)


def normalize_chars(text: str) -> str:
    """NFKC + zen/han normalization.

    Applies:
    - NFKC: Full-width alphanumeric → half-width, half-width katakana → full-width
    - Wave dash / long vowel / hyphen unification
    - Zero-width character removal
    """
    # Step 1: NFKC normalization
    text = unicodedata.normalize("NFKC", text)
    # Step 2: specific character unification
    text = text.translate(_CHAR_UNIFY)
    # Step 3: remove zero-width characters
    text = _ZERO_WIDTH.sub("", text)
    return text


# ---------------------------------------------------------------------------
# 2. Amount Parsing
# ---------------------------------------------------------------------------

RE_MONEY = re.compile(
    r"([¥￥]?\s*[0-9０-９][0-9０-９,，\.．\s]*)\s*(?:円|圓)?"
)
RE_TAX_INCL = re.compile(r"(税込|内税|総額|税込み|消費税込)")
RE_TAX_EXCL = re.compile(r"(税別|外税|本体価格|税抜|税抜き)")
RE_TAX_RATE_10 = re.compile(r"(10\s*%|１０\s*％|標準税率)")
RE_TAX_RATE_8 = re.compile(r"(8\s*%|８\s*％|軽減税率|軽減)")

# Kanji numeral tables (Standard + Formal/Legal)
KANJI_DIGITS: dict[str, int] = {
    "〇": 0, "零": 0,
    "一": 1, "壱": 1, "壹": 1,
    "二": 2, "弐": 2, "貳": 2,
    "三": 3, "参": 3, "參": 3,
    "四": 4, "肆": 4,
    "五": 5, "伍": 5,
    "六": 6, "陸": 6,
    "七": 7, "漆": 7, "柒": 7,
    "八": 8, "捌": 8,
    "九": 9, "玖": 9,
}

KANJI_UNITS: dict[str, int] = {
    "十": 10, "拾": 10,
    "百": 100, "佰": 100,
    "千": 1000, "阡": 1000, "仟": 1000,
}

KANJI_BIG: dict[str, int] = {
    "万": 10_000, "萬": 10_000,
    "億": 100_000_000,
    "兆": 1_000_000_000_000,
}

# Era validity ranges: (start_year, end_year_inclusive)
_ERA_VALID_RANGES: dict[str, tuple[int, int]] = {
    "M": (1868, 1912),
    "T": (1912, 1926),
    "S": (1926, 1989),
    "H": (1989, 2019),
    "R": (2019, 2100),  # Upper bound: far future
}


def kanji_to_int(text: str) -> int | None:
    """Convert kanji number string to integer.

    Handles:
    - Standard kanji: 一二三...九
    - Unit kanji: 十百千万億兆
    - Formal (legal) kanji: 壱弐参肆伍陸漆捌玖拾佰阡萬
    - Mixed: 3万5千, 1億2,345万
    - Returns None if text contains unrecognized characters
    """
    text = normalize_chars(text).strip()

    # Remove suffixes
    for suffix in ["円", "圓", "¥", "￥", "JPY"]:
        text = text.replace(suffix, "")
    text = text.strip()

    if not text:
        return None

    # If already a number (after removing separators)
    cleaned = text.replace(",", "").replace(".", "").replace(" ", "").replace("　", "")
    if cleaned.lstrip("-").isdigit():
        val = int(cleaned)
        return val if val != 0 else 0

    # Parse kanji number
    try:
        total = 0
        big_accumulator = 0   # accumulates before a big unit (万, 億, 兆)
        small_accumulator = 0  # accumulates before a small unit (十, 百, 千)
        last_digit = 0

        for ch in text:
            if ch in KANJI_DIGITS:
                last_digit = KANJI_DIGITS[ch]
                small_accumulator = last_digit
            elif ch in KANJI_UNITS:
                unit = KANJI_UNITS[ch]
                if small_accumulator == 0:
                    small_accumulator = 1  # implied "one" before unit (e.g., 百 = 一百)
                big_accumulator += small_accumulator * unit
                small_accumulator = 0
                last_digit = 0
            elif ch in KANJI_BIG:
                big = KANJI_BIG[ch]
                big_accumulator += small_accumulator
                if big_accumulator == 0:
                    big_accumulator = 1  # implied "one" (e.g., 万 = 一万)
                total += big_accumulator * big
                big_accumulator = 0
                small_accumulator = 0
                last_digit = 0
            elif ch in (",", "、", " ", "　"):
                pass  # separators: ignore
            else:
                return None  # Unrecognized character → bail out

        total += big_accumulator + small_accumulator
        return total if total > 0 else None
    except Exception:
        return None


def parse_amount(text: str, context: str = "") -> AmountField:
    """Parse amount with tax mode detection.

    Steps:
    1. Normalize characters
    2. Extract numeric value (including kanji numbers)
    3. Detect tax mode from surrounding context (or inline text)
    4. Detect tax rate from surrounding context
    """
    provenance: list[str] = []
    normalized = normalize_chars(text)
    search_text = normalized + " " + normalize_chars(context)

    # --- Tax mode detection ---
    price_mode: str | None = None
    if RE_TAX_INCL.search(search_text):
        price_mode = "tax_included"
        provenance.append("tax_included検出")
    elif RE_TAX_EXCL.search(search_text):
        price_mode = "tax_excluded"
        provenance.append("tax_excluded検出")

    # --- Tax rate detection ---
    tax_rate: float | None = None
    if RE_TAX_RATE_10.search(search_text):
        tax_rate = 0.10
        provenance.append("税率10%検出")
    elif RE_TAX_RATE_8.search(search_text):
        tax_rate = 0.08
        provenance.append("税率8%検出")

    # --- Numeric extraction ---
    # Strip currency symbols, tax annotations for pure number extraction.
    # Note: normalize_chars() (NFKC) converts （税込） → (税込) and ％ → %
    # so we must match both half-width and full-width forms.
    raw_for_num = normalized
    # Remove tax annotation phrases (longest first to avoid partial matches)
    for token in [
        "消費税込", "税込み", "税込",
        "本体価格", "税抜き", "税抜",
        "内税", "総額", "外税", "税別",
        # parenthesized variants (full-width parens become half-width after NFKC)
        "(税込み)", "(税込)", "(税別)", "(税抜き)", "(税抜)",
        "(内税)", "(外税)",
    ]:
        raw_for_num = raw_for_num.replace(token, " ")
    # Remove orphaned parentheses that may remain
    # Remove any parenthesized annotations (e.g., "( ・10%)", "(税込・標準税率)")
    raw_for_num = re.sub(r"\([^)]*\)", " ", raw_for_num)

    value: int | None = _extract_numeric_value(raw_for_num, provenance)

    confidence = 1.0 if value is not None else 0.0

    return AmountField(
        raw=text,
        value=value,
        confidence=confidence,
        provenance=provenance,
        price_mode=price_mode,
        tax_rate=tax_rate,
        currency="JPY",
    )


def _extract_numeric_value(text: str, provenance: list[str]) -> int | None:
    """Internal: extract integer amount from normalized text."""
    text = text.strip()

    # Remove currency symbols and whitespace.
    # NFKC converts ￥ (U+FFE5 FULLWIDTH YEN SIGN) → ¥ (U+00A5 YEN SIGN)
    # Both must be listed. Also remove the ASCII backslash used as yen in some fonts.
    for ch in ["\xa5", "\uffe5", "円", "圓", "JPY", "jpy", "\\", "　"]:
        text = text.replace(ch, "")
    text = text.strip()

    # Detect negative sign
    negative = False
    if text and text[0] in ("-", "△", "▲"):
        negative = True
        text = text[1:].strip()
        provenance.append("負の金額")

    # Remove thousand separators and trailing dashes
    text = text.replace(",", "").replace("，", "")
    text = text.rstrip("-ー−‐")
    text = text.strip()

    if not text:
        return None

    # Try direct integer parse (handles decimal like "1234.00")
    try:
        val = int(Decimal(text).to_integral_value(rounding=ROUND_HALF_UP))
        provenance.append("数値直接解析")
        return -val if negative else val
    except Exception:
        pass

    # Try kanji-to-int
    val = kanji_to_int(text)
    if val is not None:
        provenance.append("漢数字変換")
        return -val if negative else val

    return None


# ---------------------------------------------------------------------------
# 3. Date Parsing
# ---------------------------------------------------------------------------

ERA_TABLE: dict[str, tuple[int, str]] = {
    "明治": (1867, "M"), "大正": (1911, "T"), "昭和": (1925, "S"),
    "平成": (1988, "H"), "令和": (2018, "R"),
    # Short forms (uppercase)
    "M": (1867, "M"), "T": (1911, "T"), "S": (1925, "S"),
    "H": (1988, "H"), "R": (2018, "R"),
    # Lowercase (case-insensitive support)
    "m": (1867, "M"), "t": (1911, "T"), "s": (1925, "S"),
    "h": (1988, "H"), "r": (2018, "R"),
}

# Kanji digit map for date parsing (月日用)
_KANJI_DATE_DIGITS: dict[str, str] = {
    "〇": "0", "一": "1", "二": "2", "三": "3", "四": "4",
    "五": "5", "六": "6", "七": "7", "八": "8", "九": "9",
    "十": "10", "廿": "20", "卅": "30",
    # Formal variants
    "壱": "1", "弐": "2", "参": "3",
}

# Compiled patterns (priority order: most specific first)
_DATE_FULL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 令和六年三月一日 (kanji year+month+day)
    (re.compile(
        r"(令和|平成|昭和|大正|明治)"
        r"\s*([〇一二三四五六七八九十百千壱弐参拾]+)\s*年"
        r"\s*([〇一二三四五六七八九十壱弐参拾]+)\s*月"
        r"\s*([〇一二三四五六七八九十壱弐参拾]+)\s*日"
    ), "era_kanji_full"),
    # 令和7年3月15日 (era + arabic)
    (re.compile(
        r"(令和|平成|昭和|大正|明治)\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
    ), "era_arabic_full"),
    # R7/3/15  R7.3.15  R7年3月15日
    (re.compile(
        r"([RHSTMrhstm])\s*(\d{1,2})\s*[./年]\s*(\d{1,2})\s*[./月]\s*(\d{1,2})(?:\s*日)?"
    ), "era_short_full"),
    # 2025年3月15日
    (re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"), "western_kanji_full"),
    # 2025/03/15  2025-03-15  2025.03.15
    (re.compile(r"(\d{4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})"), "western_slash_full"),
    # 25年12月24日 (2-digit year, western assumed)
    (re.compile(r"(\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"), "two_digit_year_full"),
]

_DATE_MONTH_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 令和七年三月 (kanji)
    (re.compile(
        r"(令和|平成|昭和|大正|明治)"
        r"\s*([〇一二三四五六七八九十百千壱弐参拾]+)\s*年"
        r"\s*([〇一二三四五六七八九十壱弐参拾]+)\s*月"
    ), "era_kanji_month"),
    # 令和7年3月
    (re.compile(
        r"(令和|平成|昭和|大正|明治)\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月"
    ), "era_arabic_month"),
    # R7/3  R7.3
    (re.compile(r"([RHSTMrhstm])\s*(\d{1,2})\s*[./]\s*(\d{1,2})"), "era_short_month"),
    # 2025年3月
    (re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月"), "western_kanji_month"),
    # 2025/03  2025.03  2026.3
    (re.compile(r"(\d{4})\s*[/.\-]\s*(\d{1,2})$"), "western_slash_month"),
]

_DATE_YEAR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 令和七年
    (re.compile(
        r"(令和|平成|昭和|大正|明治)\s*([〇一二三四五六七八九十百千壱弐参拾]+)\s*年"
    ), "era_kanji_year"),
    # 令和7年
    (re.compile(
        r"(令和|平成|昭和|大正|明治)\s*(\d{1,2})\s*年"
    ), "era_arabic_year"),
    # 2025年
    (re.compile(r"(\d{4})\s*年"), "western_year"),
]


def _kanji_year_to_int(kanji_str: str) -> int | None:
    """Convert kanji string like '六' or '三十一' to integer."""
    text = normalize_chars(kanji_str).strip()
    # If already digits
    if text.isdigit():
        return int(text)
    # Kanji parse (simple: handles up to 千)
    val = kanji_to_int(text)
    return val


def _era_to_year(era_key: str, era_year: int) -> int | None:
    """Convert era + era-year to western year. Returns None if invalid."""
    if era_key not in ERA_TABLE:
        return None
    offset, era_code = ERA_TABLE[era_key]
    year = offset + era_year

    # Validate against known era ranges
    lo, hi = _ERA_VALID_RANGES.get(era_code, (1, 9999))
    if year < lo or year > hi:
        return None  # e.g., 平成36年 is invalid (Heisei ended 31)
    return year


def parse_date(text: str) -> DateField:
    """Parse date with precision tag.

    Handles:
    - 令和六年三月一日 → full, era=R
    - R6/3/1, R6.3.1 → full, era=R
    - 2024年3月1日 → full
    - 2024/03/01, 2024-03-01 → full
    - 令和6年3月 → year_month, era=R
    - 2024年3月 → year_month
    - 2024年 → year
    - 令和元年 handling: 元 → 1
    - Era overflow validation: 平成36年 → None (invalid)
    """
    if not text:
        return DateField(raw=text, value=None, confidence=0.0,
                         provenance=["空文字列"])

    provenance: list[str] = []
    normalized = normalize_chars(text.strip())
    # Handle 元年 (first year of era) → 1
    normalized = normalized.replace("元年", "1年")

    # Track whether text contains an explicit Japanese era name.
    # When true, skip two_digit_year_full fallback — an overflowed era year
    # (e.g., 平成36年 where 平成 ended at 31) should produce None, not "2036-xx-xx".
    has_explicit_era: bool = bool(
        re.search(r"令和|平成|昭和|大正|明治", normalized)
    )

    # ---- Full date patterns ----
    for pattern, pat_name in _DATE_FULL_PATTERNS:
        m = pattern.search(normalized)
        if not m:
            continue

        groups = m.groups()
        era_code: str | None = None

        if pat_name in ("era_kanji_full", "era_arabic_full"):
            era_key = groups[0]
            y_raw = groups[1]
            mo_raw = groups[2]
            d_raw = groups[3]

            y_int = _kanji_year_to_int(y_raw) if pat_name == "era_kanji_full" else int(y_raw)
            mo_int = _kanji_year_to_int(mo_raw) if pat_name == "era_kanji_full" else int(mo_raw)
            d_int = _kanji_year_to_int(d_raw) if pat_name == "era_kanji_full" else int(d_raw)

            if y_int is None or mo_int is None or d_int is None:
                continue

            year = _era_to_year(era_key, y_int)
            if year is None:
                provenance.append(f"元号オーバーフロー: {era_key}{y_int}年")
                continue
            _, era_code = ERA_TABLE[era_key]

        elif pat_name == "era_short_full":
            era_key = groups[0]
            year = _era_to_year(era_key, int(groups[1]))
            if year is None:
                continue
            mo_int = int(groups[2])
            d_int = int(groups[3])
            _, era_code = ERA_TABLE.get(era_key, (0, era_key.upper()))

        elif pat_name == "western_kanji_full":
            year = int(groups[0])
            mo_int = int(groups[1])
            d_int = int(groups[2])

        elif pat_name == "western_slash_full":
            year = int(groups[0])
            mo_int = int(groups[1])
            d_int = int(groups[2])

        elif pat_name == "two_digit_year_full":
            # Skip this pattern when text contains an explicit era name.
            # e.g., "平成36年1月1日" overflowed era → should yield None, not "2036-01-01"
            if has_explicit_era:
                continue
            y2 = int(groups[0])
            year = 2000 + y2 if y2 < 50 else 1900 + y2
            mo_int = int(groups[1])
            d_int = int(groups[2])
            provenance.append("2桁年号→西暦推定")

        else:
            continue

        try:
            from datetime import date as _date
            d_obj = _date(year, mo_int, d_int)
            provenance.append(f"パターン:{pat_name}")
            return DateField(
                raw=text,
                value=d_obj.isoformat(),
                confidence=1.0,
                provenance=provenance,
                precision="full",
                era=era_code,
            )
        except (ValueError, TypeError):
            continue

    # ---- Year-month patterns ----
    for pattern, pat_name in _DATE_MONTH_PATTERNS:
        m = pattern.search(normalized)
        if not m:
            continue

        groups = m.groups()
        era_code = None

        if pat_name in ("era_kanji_month", "era_arabic_month"):
            era_key = groups[0]
            y_raw = groups[1]
            mo_raw = groups[2]
            y_int = _kanji_year_to_int(y_raw) if pat_name == "era_kanji_month" else int(y_raw)
            mo_int = _kanji_year_to_int(mo_raw) if pat_name == "era_kanji_month" else int(mo_raw)
            if y_int is None or mo_int is None:
                continue
            year = _era_to_year(era_key, y_int)
            if year is None:
                continue
            _, era_code = ERA_TABLE[era_key]

        elif pat_name == "era_short_month":
            era_key = groups[0]
            year = _era_to_year(era_key, int(groups[1]))
            if year is None:
                continue
            mo_int = int(groups[2])
            _, era_code = ERA_TABLE.get(era_key, (0, era_key.upper()))

        elif pat_name == "western_kanji_month":
            year = int(groups[0])
            mo_int = int(groups[1])

        elif pat_name == "western_slash_month":
            year = int(groups[0])
            mo_int = int(groups[1])

        else:
            continue

        try:
            from datetime import date as _date
            _date(year, mo_int, 1)  # validate
            value = f"{year:04d}-{mo_int:02d}"
            provenance.append(f"パターン:{pat_name}")
            return DateField(
                raw=text,
                value=value,
                confidence=0.9,
                provenance=provenance,
                precision="year_month",
                era=era_code,
            )
        except (ValueError, TypeError):
            continue

    # ---- Year-only patterns ----
    for pattern, pat_name in _DATE_YEAR_PATTERNS:
        m = pattern.search(normalized)
        if not m:
            continue

        groups = m.groups()
        era_code = None

        if pat_name in ("era_kanji_year", "era_arabic_year"):
            era_key = groups[0]
            y_raw = groups[1]
            y_int = _kanji_year_to_int(y_raw) if pat_name == "era_kanji_year" else int(y_raw)
            if y_int is None:
                continue
            year = _era_to_year(era_key, y_int)
            if year is None:
                continue
            _, era_code = ERA_TABLE[era_key]

        elif pat_name == "western_year":
            year = int(groups[0])

        else:
            continue

        provenance.append(f"パターン:{pat_name}")
        return DateField(
            raw=text,
            value=str(year),
            confidence=0.7,
            provenance=provenance,
            precision="year",
            era=era_code,
        )

    return DateField(
        raw=text,
        value=None,
        confidence=0.0,
        provenance=["日付パターン未一致"],
    )


# ---------------------------------------------------------------------------
# 4. Company Name Normalization
# ---------------------------------------------------------------------------

COMPANY_ABBREVS: dict[str, str] = {
    "㈱": "株式会社",
    "(株)": "株式会社",
    "（株）": "株式会社",
    "㈲": "有限会社",
    "(有)": "有限会社",
    "（有）": "有限会社",
    "㈳": "一般社団法人",
    "(社)": "一般社団法人",
    "（社）": "一般社団法人",
    "㈵": "特定非営利活動法人",
    "(合)": "合同会社",
    "（合）": "合同会社",
    "(名)": "合名会社",
    "（名）": "合名会社",
    "(資)": "合資会社",
    "（資）": "合資会社",
}

# Sort by length descending so longer abbreviations match first
_SORTED_ABBREVS = sorted(COMPANY_ABBREVS.items(), key=lambda x: -len(x[0]))


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein distance between two strings."""
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    # Use two-row dynamic programming
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            sub_cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + sub_cost)
        prev = curr
    return prev[lb]


def _fuzzy_candidates(
    name: str,
    known_companies: list[str],
    top_n: int = 3,
    max_distance: int = 3,
) -> list[str]:
    """Return top-N fuzzy matches from known_companies."""
    try:
        import rapidfuzz.distance as _rfd  # type: ignore[import]
        scored = [
            (c, _rfd.Levenshtein.distance(name, c))
            for c in known_companies
        ]
    except ImportError:
        scored = [
            (c, _levenshtein(name, c))
            for c in known_companies
        ]
    scored.sort(key=lambda x: x[1])
    return [c for c, dist in scored[:top_n] if dist <= max_distance]


def normalize_company(
    text: str,
    known_companies: list[str] | None = None,
) -> CompanyField:
    """Normalize company name with provenance tracking.

    Steps:
    1. Character normalization (NFKC + zen/han)
    2. Abbreviation expansion (㈱ → 株式会社, etc.)
    3. Whitespace compression (consecutive spaces → removed)
    4. Fuzzy match against known_companies (if provided)
    5. Record all applied rules in provenance
    """
    if not text:
        return CompanyField(raw=text, value=None, confidence=0.0,
                            provenance=["空文字列"])

    provenance: list[str] = []
    normalized = normalize_chars(text.strip())

    # Step 2: abbreviation expansion
    for abbr, full in _SORTED_ABBREVS:
        if abbr in normalized:
            normalized = normalized.replace(abbr, full)
            provenance.append(f"{abbr}→{full}")

    # Step 3: whitespace compression
    # Remove spaces between Japanese characters (e.g., "テスト　ホールディングス" → "テストホールディングス")
    # But preserve spaces between ASCII words
    before_ws = normalized
    # Remove all whitespace between non-ASCII characters
    normalized = re.sub(r"(?<=[\u3000-\u9fff\uff00-\uffef])\s+(?=[\u3000-\u9fff\uff00-\uffef])", "", normalized)
    # Remove leading/trailing whitespace
    normalized = normalized.strip()
    # Compress remaining multiple spaces to single
    normalized = re.sub(r"\s{2,}", " ", normalized)
    if normalized != before_ws.strip():
        provenance.append("連続スペース圧縮")

    similar_candidates: list[str] = []

    # Step 4: fuzzy match
    if known_companies:
        similar_candidates = _fuzzy_candidates(normalized, known_companies)
        if similar_candidates:
            # If exact match exists, set confidence to 1.0
            if similar_candidates[0] == normalized:
                provenance.append("既知企業完全一致")
            else:
                provenance.append(f"類似候補: {similar_candidates[0]}")

    return CompanyField(
        raw=text,
        value=normalized if normalized else None,
        confidence=1.0 if normalized else 0.0,
        provenance=provenance,
        similar_candidates=similar_candidates,
    )


# ---------------------------------------------------------------------------
# 5. Invoice Number
# ---------------------------------------------------------------------------

_RE_T_NUMBER = re.compile(r"T\d{13}")
_RE_ALPHANUM = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*")


def validate_invoice_no(text: str) -> InvoiceNoField:
    """Normalize and validate invoice number.

    - Remove: 第, 号, spaces
    - T-number format: T + 13 digits (Japanese qualified invoice issuer number)
    - Generic: alphanumeric + hyphens
    - Record format_type
    """
    if not text:
        return InvoiceNoField(raw=text, value=None, confidence=0.0,
                              format_valid=False, provenance=["空文字列"])

    provenance: list[str] = []
    normalized = normalize_chars(text.strip())

    # Remove common prefixes/suffixes
    for token in ["第", "号", "No.", "NO.", "No ", "番号", "インボイス番号", "登録番号"]:
        if token in normalized:
            normalized = normalized.replace(token, "")
            provenance.append(f"'{token}'除去")

    # Remove all whitespace
    normalized = re.sub(r"\s+", "", normalized)

    if not normalized:
        return InvoiceNoField(raw=text, value=None, confidence=0.0,
                              format_valid=False, provenance=provenance + ["空白のみ"])

    # Check T-number (qualified invoice issuer number in Japan)
    if _RE_T_NUMBER.fullmatch(normalized):
        provenance.append("T番号形式(適格請求書発行事業者)")
        return InvoiceNoField(
            raw=text,
            value=normalized,
            confidence=1.0,
            provenance=provenance,
            format_valid=True,
            format_type="t_number",
        )

    # Check if T-number with prefix noise
    t_match = _RE_T_NUMBER.search(normalized)
    if t_match:
        clean = t_match.group(0)
        provenance.append("T番号抽出")
        return InvoiceNoField(
            raw=text,
            value=clean,
            confidence=0.9,
            provenance=provenance,
            format_valid=True,
            format_type="t_number",
        )

    # Generic alphanumeric + hyphens
    alnum_match = _RE_ALPHANUM.fullmatch(normalized)
    if alnum_match:
        provenance.append("英数字形式")
        return InvoiceNoField(
            raw=text,
            value=normalized,
            confidence=1.0,
            provenance=provenance,
            format_valid=True,
            format_type="custom",
        )

    # Digits only (after stripping)
    if normalized.isdigit():
        provenance.append("数値のみ形式")
        return InvoiceNoField(
            raw=text,
            value=normalized,
            confidence=0.9,
            provenance=provenance,
            format_valid=True,
            format_type="custom",
        )

    # Unknown format but has some content
    provenance.append("未知形式")
    return InvoiceNoField(
        raw=text,
        value=normalized,
        confidence=0.5,
        provenance=provenance,
        format_valid=False,
        format_type=None,
    )


# ---------------------------------------------------------------------------
# 6. Convenience: Process All Fields
# ---------------------------------------------------------------------------

def normalize_ocr_fields(
    raw_text: str,
    field_hints: dict[str, str] | None = None,
) -> dict[str, NormalizedField]:
    """Process raw OCR text and extract all recognizable fields.

    Args:
        raw_text: Raw OCR output text.
        field_hints: Optional dict of {field_type: hint_text} to override
                     auto-extraction with specific sub-strings.

    Returns:
        Dict of NormalizedField subclasses keyed by field type:
        {
            "amount": AmountField,
            "date": DateField,
            "company": CompanyField,
            "invoice_no": InvoiceNoField,
        }
    """
    hints = field_hints or {}
    result: dict[str, NormalizedField] = {}

    # Amount
    amount_text = hints.get("amount", raw_text)
    result["amount"] = parse_amount(amount_text, context=raw_text)

    # Date
    date_text = hints.get("date", raw_text)
    result["date"] = parse_date(date_text)

    # Company
    company_text = hints.get("company", raw_text)
    result["company"] = normalize_company(company_text)

    # Invoice number
    invoice_text = hints.get("invoice_no", raw_text)
    result["invoice_no"] = validate_invoice_no(invoice_text)

    return result
