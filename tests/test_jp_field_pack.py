"""Tests for tools/common/jp_field_pack.py

Covers:
- normalize_chars
- kanji_to_int
- parse_amount (with tax mode)
- parse_date (with precision + era)
- normalize_company (with provenance)
- validate_invoice_no
- normalize_ocr_fields (convenience)
- hard_negative_store (save/load/run_regression)
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module under test
# ---------------------------------------------------------------------------
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.jp_field_pack import (
    AmountField,
    CompanyField,
    DateField,
    InvoiceNoField,
    NormalizedField,
    kanji_to_int,
    normalize_chars,
    normalize_company,
    normalize_ocr_fields,
    parse_amount,
    parse_date,
    validate_invoice_no,
)
from tools.common.hard_negative_store import (
    _get_store_dir,
    delete_hard_negative,
    load_hard_negatives,
    run_regression,
    save_hard_negative,
    summarize_store,
)


# ===========================================================================
# normalize_chars
# ===========================================================================

class TestNormalizeChars:
    def test_fullwidth_alphanumeric_to_halfwidth(self):
        assert normalize_chars("１２３ＡＢＣ") == "123ABC"

    def test_halfwidth_katakana_to_fullwidth(self):
        result = normalize_chars("ｱｲｳｴｵ")
        assert result == "アイウエオ"

    def test_wave_dash_unification(self):
        # Various wave dash / tilde variants → half-width ~
        result = normalize_chars("〜")
        assert result == "~"

    def test_minus_sign_unification(self):
        # MINUS SIGN (U+2212) → hyphen-minus
        result = normalize_chars("−10000")
        assert result == "-10000"

    def test_zero_width_removed(self):
        # ZWSP between characters
        result = normalize_chars("テ\u200bスト")
        assert result == "テスト"

    def test_idempotent(self):
        text = "株式会社テスト"
        assert normalize_chars(normalize_chars(text)) == normalize_chars(text)


# ===========================================================================
# kanji_to_int
# ===========================================================================

class TestKanjiToInt:
    def test_simple_digits(self):
        assert kanji_to_int("一") == 1
        assert kanji_to_int("九") == 9

    def test_tens(self):
        assert kanji_to_int("十") == 10
        assert kanji_to_int("二十") == 20
        assert kanji_to_int("三十六") == 36

    def test_hundreds(self):
        assert kanji_to_int("百") == 100
        assert kanji_to_int("三百") == 300
        assert kanji_to_int("三百六十五") == 365

    def test_thousands(self):
        assert kanji_to_int("千") == 1000
        assert kanji_to_int("三千") == 3000
        assert kanji_to_int("六千五百") == 6500

    def test_man(self):
        assert kanji_to_int("一万") == 10000
        assert kanji_to_int("三万六千五百") == 36500
        assert kanji_to_int("参萬六千五百") == 36500  # formal kanji

    def test_formal_kanji(self):
        assert kanji_to_int("壱") == 1
        assert kanji_to_int("弐") == 2
        assert kanji_to_int("参") == 3

    def test_arabic_digits_passthrough(self):
        assert kanji_to_int("12345") == 12345
        assert kanji_to_int("1,234") == 1234

    def test_unrecognized_returns_none(self):
        assert kanji_to_int("abc") is None

    def test_empty_returns_none(self):
        assert kanji_to_int("") is None


# ===========================================================================
# parse_amount
# ===========================================================================

class TestParseAmount:
    def test_basic_amount_with_yen(self):
        result = parse_amount("¥12,345")
        assert result.value == 12345
        assert result.currency == "JPY"

    def test_fullwidth_yen_with_tax_included(self):
        result = parse_amount("￥ 12,345.-（税込）")
        assert result.value == 12345
        assert result.price_mode == "tax_included"

    def test_tax_excluded(self):
        result = parse_amount("1,000円（税別）")
        assert result.value == 1000
        assert result.price_mode == "tax_excluded"

    def test_kanji_amount(self):
        result = parse_amount("参萬六千五百円")
        assert result.value == 36500

    def test_fullwidth_digits(self):
        result = parse_amount("１２，３４５")
        assert result.value == 12345

    def test_trailing_dash(self):
        result = parse_amount("¥108,278-")
        assert result.value == 108278

    def test_tax_rate_10_percent(self):
        result = parse_amount("10,000円（税込・10%）")
        assert result.value == 10000
        assert result.price_mode == "tax_included"
        assert result.tax_rate == 0.10

    def test_tax_rate_8_percent(self):
        result = parse_amount("1,080円（軽減税率8%）")
        assert result.value == 1080
        assert result.tax_rate == 0.08

    def test_negative_amount(self):
        result = parse_amount("△5,000円")
        assert result.value == -5000

    def test_context_tax_mode(self):
        result = parse_amount("50,000", context="税込合計")
        assert result.price_mode == "tax_included"

    def test_no_tax_mode(self):
        result = parse_amount("50,000円")
        assert result.price_mode is None

    def test_provenance_recorded(self):
        result = parse_amount("参萬六千五百円")
        assert any("漢数字" in p for p in result.provenance)

    def test_zero_amount(self):
        result = parse_amount("0円")
        assert result.value == 0

    def test_invalid_returns_none(self):
        result = parse_amount("ABC")
        assert result.value is None
        assert result.confidence == 0.0


# ===========================================================================
# parse_date
# ===========================================================================

class TestParseDate:
    def test_reiwa_arabic_full(self):
        result = parse_date("令和6年3月1日")
        assert result.value == "2024-03-01"
        assert result.precision == "full"
        assert result.era == "R"

    def test_reiwa_short_slash(self):
        result = parse_date("R6/3/1")
        assert result.value == "2024-03-01"
        assert result.precision == "full"
        assert result.era == "R"

    def test_reiwa_short_dot(self):
        result = parse_date("R6.3.1")
        assert result.value == "2024-03-01"
        assert result.precision == "full"
        assert result.era == "R"

    def test_reiwa_kanji_year_month_day(self):
        result = parse_date("令和六年三月一日")
        assert result.value == "2024-03-01"
        assert result.precision == "full"
        assert result.era == "R"

    def test_reiwa_year_month_only(self):
        result = parse_date("令和六年三月")
        assert result.value == "2024-03"
        assert result.precision == "year_month"
        assert result.era == "R"

    def test_reiwa_arabic_year_month(self):
        result = parse_date("令和6年3月")
        assert result.value == "2024-03"
        assert result.precision == "year_month"
        assert result.era == "R"

    def test_western_dot_year_month(self):
        result = parse_date("2026.3")
        assert result.value == "2026-03"
        assert result.precision == "year_month"

    def test_western_full(self):
        result = parse_date("2024/03/01")
        assert result.value == "2024-03-01"
        assert result.precision == "full"

    def test_western_hyphen(self):
        result = parse_date("2024-03-01")
        assert result.value == "2024-03-01"
        assert result.precision == "full"

    def test_western_kanji_full(self):
        result = parse_date("2024年3月1日")
        assert result.value == "2024-03-01"
        assert result.precision == "full"

    def test_gannen(self):
        """令和元年 = 令和1年 = 2019"""
        result = parse_date("令和元年5月1日")
        assert result.value == "2019-05-01"
        assert result.era == "R"

    def test_heisei_last_day(self):
        """平成31年4月30日 (last day of Heisei)"""
        result = parse_date("平成31年4月30日")
        assert result.value == "2019-04-30"
        assert result.era == "H"

    def test_heisei_overflow_invalid(self):
        """平成36年 is invalid (Heisei ended at 31)"""
        result = parse_date("平成36年1月1日")
        assert result.value is None

    def test_showa(self):
        result = parse_date("昭和64年1月7日")
        assert result.value == "1989-01-07"
        assert result.era == "S"

    def test_year_only(self):
        result = parse_date("2025年")
        assert result.value == "2025"
        assert result.precision == "year"

    def test_empty_returns_none(self):
        result = parse_date("")
        assert result.value is None
        assert result.confidence == 0.0

    def test_unparseable_returns_none(self):
        result = parse_date("テキストのみ")
        assert result.value is None

    def test_confidence_full_date(self):
        result = parse_date("2024/03/01")
        assert result.confidence == 1.0

    def test_confidence_year_month(self):
        result = parse_date("2024年3月")
        assert result.confidence == pytest.approx(0.9)


# ===========================================================================
# normalize_company
# ===========================================================================

class TestNormalizeCompany:
    def test_kabushiki_abbrev(self):
        result = normalize_company("㈱テスト")
        assert result.value == "株式会社テスト"
        # NFKC converts ㈱ → (株) before abbreviation expansion,
        # so provenance contains "(株)→株式会社"
        assert any("株式会社" in p for p in result.provenance)

    def test_fullwidth_paren_kabushiki(self):
        result = normalize_company("（株）テスト")
        assert result.value == "株式会社テスト"

    def test_yuugen_abbrev(self):
        result = normalize_company("（有）ヤマダ工業")
        assert result.value == "有限会社ヤマダ工業"
        # NFKC converts （有） → (有) before expansion → provenance has "(有)→有限会社"
        assert any("有限会社" in p for p in result.provenance)

    def test_space_compression_katakana(self):
        result = normalize_company("㈱テスト　ホールディングス")
        assert result.value == "株式会社テストホールディングス"
        assert any("スペース" in p for p in result.provenance)

    def test_halfwidth_space_removal(self):
        result = normalize_company("（有）ヤマダ 工業")
        assert result.value == "有限会社ヤマダ工業"
        assert any("スペース" in p for p in result.provenance)

    def test_no_abbrev_passthrough(self):
        result = normalize_company("株式会社テスト")
        assert result.value == "株式会社テスト"

    def test_empty_returns_none(self):
        result = normalize_company("")
        assert result.value is None

    def test_known_companies_fuzzy(self):
        known = ["株式会社テスト", "テスト株式会社", "有限会社サンプル"]
        result = normalize_company("㈱テスト", known_companies=known)
        assert result.value == "株式会社テスト"
        # Should find "株式会社テスト" as top candidate
        assert "株式会社テスト" in result.similar_candidates

    def test_gouodou_company(self):
        result = normalize_company("（合）テスト商事")
        assert result.value == "合同会社テスト商事"

    def test_provenance_recorded_for_all_rules(self):
        result = normalize_company("㈱テスト　ホールディングス")
        # At least abbreviation and space rules should be recorded
        assert len(result.provenance) >= 2


# ===========================================================================
# validate_invoice_no
# ===========================================================================

class TestValidateInvoiceNo:
    def test_t_number_exact(self):
        result = validate_invoice_no("T1234567890123")
        assert result.value == "T1234567890123"
        assert result.format_type == "t_number"
        assert result.format_valid is True

    def test_fullwidth_alphanum(self):
        result = validate_invoice_no("INV-００１２３")
        assert result.value == "INV-00123"
        assert result.format_valid is True
        assert result.format_type == "custom"

    def test_prefix_removal(self):
        result = validate_invoice_no("第 12345 号")
        assert result.value == "12345"
        assert result.format_valid is True

    def test_no_prefix_removal(self):
        result = validate_invoice_no("INV-12345")
        assert result.value == "INV-12345"

    def test_empty_returns_none(self):
        result = validate_invoice_no("")
        assert result.value is None
        assert result.format_valid is False

    def test_t_number_with_noise(self):
        # T-number embedded in text
        result = validate_invoice_no("登録番号T1234567890123")
        assert result.value == "T1234567890123"
        assert result.format_type == "t_number"

    def test_confidence_t_number(self):
        result = validate_invoice_no("T1234567890123")
        assert result.confidence == 1.0

    def test_t_number_wrong_length_not_t_format(self):
        # T + 12 digits (not 13) → not t_number format
        result = validate_invoice_no("T123456789012")
        assert result.format_type != "t_number"


# ===========================================================================
# normalize_ocr_fields (convenience)
# ===========================================================================

class TestNormalizeOcrFields:
    def test_basic(self):
        raw = "2024年3月1日 ¥12,345 株式会社テスト"
        result = normalize_ocr_fields(raw)
        assert "amount" in result
        assert "date" in result
        assert "company" in result
        assert "invoice_no" in result

    def test_with_hints(self):
        hints = {
            "amount": "¥50,000（税込）",
            "date": "令和6年3月1日",
        }
        result = normalize_ocr_fields("", field_hints=hints)
        assert result["amount"].value == 50000
        assert result["amount"].price_mode == "tax_included"
        assert result["date"].value == "2024-03-01"


# ===========================================================================
# hard_negative_store
# ===========================================================================

class TestHardNegativeStore:
    """Tests for save/load/run_regression with isolated temp directory."""

    @pytest.fixture(autouse=True)
    def use_temp_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Override store directory to use tmp_path for each test."""
        monkeypatch.setenv("HARD_NEGATIVE_DIR", str(tmp_path))
        self.store_dir = tmp_path
        yield

    def test_save_creates_file(self):
        path = save_hard_negative(
            field_type="amount",
            raw_input="参萬六千五百円",
            wrong_output="0",
            correct_output="36500",
            rule_context="kanji 万 path",
            source_file="test.pdf",
        )
        assert Path(path).exists()
        assert path.endswith(".json")

    def test_save_content_roundtrip(self):
        save_hard_negative(
            field_type="amount",
            raw_input="参萬六千五百円",
            wrong_output="0",
            correct_output="36500",
        )
        cases = load_hard_negatives(field_type="amount")
        assert len(cases) == 1
        assert cases[0]["raw_input"] == "参萬六千五百円"
        assert cases[0]["correct_output"] == "36500"

    def test_load_all_field_types(self):
        save_hard_negative("amount", "1,000円", "0", "1000")
        save_hard_negative("date", "R6/3/1", "", "2024-03-01")
        save_hard_negative("company", "㈱テスト", "㈱テスト", "株式会社テスト")

        all_cases = load_hard_negatives()
        assert len(all_cases) == 3

        amount_cases = load_hard_negatives(field_type="amount")
        assert len(amount_cases) == 1

    def test_load_returns_empty_if_no_store(self):
        # Fresh temp dir with no files
        cases = load_hard_negatives()
        assert cases == []

    def test_run_regression_all_pass(self):
        save_hard_negative("amount", "1,000円", "0", "1000")
        save_hard_negative("amount", "¥5,000", "0", "5000")

        def mock_normalize(raw: str) -> str:
            return str(parse_amount(raw).value)

        report = run_regression(mock_normalize, field_type="amount")
        assert report["total"] == 2
        assert report["passed"] == 2
        assert report["failed"] == 0
        assert report["pass_rate"] == 1.0

    def test_run_regression_with_failure(self):
        save_hard_negative("amount", "invalid_text", "", "999")

        def always_wrong(raw: str) -> str:
            return "0"

        report = run_regression(always_wrong, field_type="amount")
        assert report["failed"] == 1
        assert len(report["failures"]) == 1
        assert report["failures"][0]["expected"] == "999"
        assert report["failures"][0]["got"] == "0"

    def test_run_regression_handles_exception(self):
        save_hard_negative("amount", "crash_input", "", "100")

        def raises_always(raw: str) -> str:
            raise ValueError("Deliberate crash")

        report = run_regression(raises_always, field_type="amount")
        assert report["failed"] == 1
        assert "ERROR" in report["failures"][0]["got"]

    def test_run_regression_empty_store(self):
        report = run_regression(lambda x: x)
        assert report["total"] == 0
        assert report["passed"] == 0
        assert report["pass_rate"] == 1.0  # vacuously true

    def test_invalid_field_type_raises(self):
        with pytest.raises(ValueError, match="Invalid field_type"):
            save_hard_negative("invalid_type", "raw", "wrong", "correct")

    def test_delete_hard_negative(self):
        save_hard_negative("amount", "1,000円", "0", "1000")
        save_hard_negative("amount", "2,000円", "0", "2000")

        deleted = delete_hard_negative("1,000円", field_type="amount")
        assert deleted == 1

        cases = load_hard_negatives(field_type="amount")
        assert len(cases) == 1
        assert cases[0]["raw_input"] == "2,000円"

    def test_summarize_store(self):
        save_hard_negative("amount", "1,000円", "0", "1000")
        save_hard_negative("date", "R6/3/1", "", "2024-03-01")

        summary = summarize_store()
        assert summary["total"] == 2
        assert summary["by_field_type"]["amount"] == 1
        assert summary["by_field_type"]["date"] == 1

    def test_save_multiple_same_input(self):
        """Multiple saves for same raw_input are allowed (different timestamps)."""
        save_hard_negative("amount", "1,000円", "0", "1000")
        save_hard_negative("amount", "1,000円", "None", "1000")

        cases = load_hard_negatives(field_type="amount")
        assert len(cases) == 2


# ===========================================================================
# Integration: real-world OCR patterns (practical test cases)
# ===========================================================================

class TestRealWorldPatterns:
    """Practical test cases based on actual OCR failure patterns from Japanese invoices."""

    @pytest.mark.parametrize("raw,expected_value,expected_mode", [
        ("￥ 12,345.-（税込）", 12345, "tax_included"),
        ("1,000円（税別）", 1000, "tax_excluded"),
        ("参萬六千五百円", 36500, None),
        ("１２，３４５", 12345, None),
        ("¥108,278-", 108278, None),
    ])
    def test_amount_real_patterns(self, raw: str, expected_value: int, expected_mode: str | None):
        result = parse_amount(raw)
        assert result.value == expected_value, f"Input: {raw!r}, got {result.value}"
        assert result.price_mode == expected_mode, f"Input: {raw!r}, mode={result.price_mode}"

    @pytest.mark.parametrize("raw,expected_value,expected_precision,expected_era", [
        ("令和6年3月1日", "2024-03-01", "full", "R"),
        ("R6/3/1", "2024-03-01", "full", "R"),
        ("令和六年三月", "2024-03", "year_month", "R"),
        ("2026.3", "2026-03", "year_month", None),
        ("令和元年5月1日", "2019-05-01", "full", "R"),
        ("平成31年4月30日", "2019-04-30", "full", "H"),
    ])
    def test_date_real_patterns(
        self,
        raw: str,
        expected_value: str,
        expected_precision: str,
        expected_era: str | None,
    ):
        result = parse_date(raw)
        assert result.value == expected_value, f"Input: {raw!r}, got {result.value}"
        assert result.precision == expected_precision, f"Input: {raw!r}, precision={result.precision}"
        assert result.era == expected_era, f"Input: {raw!r}, era={result.era}"

    @pytest.mark.parametrize("raw,expected_value,expected_provenance_keywords", [
        ("㈱テスト　ホールディングス", "株式会社テストホールディングス", ["株式会社", "スペース"]),
        ("（有）ヤマダ 工業", "有限会社ヤマダ工業", ["有限会社", "スペース"]),
    ])
    def test_company_real_patterns(
        self,
        raw: str,
        expected_value: str,
        expected_provenance_keywords: list[str],
    ):
        result = normalize_company(raw)
        assert result.value == expected_value, f"Input: {raw!r}, got {result.value}"
        for keyword in expected_provenance_keywords:
            assert any(keyword in p for p in result.provenance), (
                f"Expected '{keyword}' in provenance {result.provenance}"
            )

    @pytest.mark.parametrize("raw,expected_value,expected_format_type,expected_valid", [
        ("T1234567890123", "T1234567890123", "t_number", True),
        ("INV-００１２３", "INV-00123", "custom", True),
        ("第 12345 号", "12345", "custom", True),
    ])
    def test_invoice_no_real_patterns(
        self,
        raw: str,
        expected_value: str,
        expected_format_type: str | None,
        expected_valid: bool,
    ):
        result = validate_invoice_no(raw)
        assert result.value == expected_value, f"Input: {raw!r}, got {result.value}"
        assert result.format_type == expected_format_type, f"Input: {raw!r}, type={result.format_type}"
        assert result.format_valid == expected_valid


# ===========================================================================
# NormalizedField dataclass
# ===========================================================================

class TestNormalizedField:
    def test_default_confidence(self):
        f = NormalizedField(raw="test", value="test")
        assert f.confidence == 1.0

    def test_provenance_empty_by_default(self):
        f = NormalizedField(raw="test", value="test")
        assert f.provenance == []

    def test_amount_field_defaults(self):
        f = AmountField(raw="¥100", value=100)
        assert f.currency == "JPY"
        assert f.price_mode is None
        assert f.tax_rate is None

    def test_date_field_defaults(self):
        f = DateField(raw="2024/01/01", value="2024-01-01")
        assert f.precision == "full"
        assert f.era is None

    def test_invoice_no_field_defaults(self):
        f = InvoiceNoField(raw="INV-001", value="INV-001")
        assert f.format_valid is True
        assert f.format_type is None
