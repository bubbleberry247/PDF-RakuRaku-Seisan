"""Vision API OCR module for Japanese invoice extraction."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF (fitz) is required. Install: pip install PyMuPDF")

from vendor_matching import (
    canonicalize_vendor,
    classify_vendor_category,
    infer_vendor_from_sender_context,
)

logger = logging.getLogger(__name__)

NON_INVOICE_SIGNAL_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("contract_docs", ("契約書類", "契約書")),
    ("checklist", ("チェックリスト", "回収チェックリスト")),
    ("delivery_note", ("納品書",)),
    ("electronic_payment", ("電子決済サービス",)),
    ("assessment_sheet", ("査定表",)),
)
DATE_YMD_RE = re.compile(r"(?P<y>20\d{2})[./\\年-](?P<m>\d{1,2})[./\\月-](?P<d>\d{1,2})")
DATE_LABEL_RE = re.compile(
    r"(請求(?:年月)?日|発行(?:年月)?日|作成(?:年月)?日|日付)\s*[:：]?\s*([0-9]{4}[^0-9]{0,2}[0-9]{1,2}[^0-9]{0,2}[0-9]{1,2})"
)
AMOUNT_LABEL_RE = re.compile(
    r"(支払決定金額|支払決定額|お支払い金額|支払金額|ご?請求金額|ご?請求額|請求金額|請求額|総合計|合計金額|合計)"
    r"(?:\s*[（(][^)）]*[)）])?"
    r"\s*[:：]?\s*[¥￥]?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)"
)
AMOUNT_LABEL_KEYWORDS: tuple[str, ...] = (
    "支払決定金額",
    "支払決定額",
    "お支払い金額",
    "支払金額",
    "ご請求金額",
    "ご請求額",
    "請求金額",
    "請求額",
    "総合計",
    "合計金額",
    "合計",
)
VENDOR_AMOUNT_STRATEGY: dict[str, str] = {
    "アシタカ総建株式会社": "prefer_total",
    "ワーク": "prefer_total",
    "㈱モノタロウ": "prefer_due",
    "(冨田信行様邸共同住宅新築工事)_甲陽建設工業": "prefer_total",
    "甲陽建設工業": "prefer_total",
    "株式会社オカケン": "prefer_total",
    "YAMAJIパーティション": "prefer_due",
}
VENDOR_PREFER_LABELED_AMOUNT: set[str] = {
    "クレーンタル野田",
}


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------
def _retry_with_backoff(
    fn,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs,
) -> Any:
    """Call fn with exponential backoff retry on transient errors.

    Respects Retry-After header from Azure/OpenAI errors.
    Only retries on transient errors (HTTP 429, 500, 502, 503, 504).
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            err_str = str(e).lower()
            status_code = getattr(e, 'status_code', None) or getattr(e, 'code', None)

            # Check if this is a transient/retryable error
            is_transient = False
            if status_code in (429, 500, 502, 503, 504):
                is_transient = True
            elif any(k in err_str for k in ('timeout', 'rate limit', 'throttl', '429', '500', '502', '503', '504', 'connection', 'temporary')):
                is_transient = True

            if not is_transient or attempt >= max_retries:
                raise

            # Calculate delay: check Retry-After header first
            delay = base_delay * (2 ** attempt)
            retry_after = getattr(e, 'retry_after', None)
            if retry_after and isinstance(retry_after, (int, float)):
                delay = max(delay, float(retry_after))
            delay = min(delay, max_delay)

            logger.warning(
                "Transient error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1, max_retries, delay, e
            )
            time.sleep(delay)

    raise last_exc


# ---------------------------------------------------------------------------
# Gemini SDK detection
# ---------------------------------------------------------------------------
_GENAI_NEW = False
_GENAI_OLD = False

try:
    from google import genai as _genai_new  # noqa: F401

    _GENAI_NEW = True
except ImportError:
    pass

if not _GENAI_NEW:
    try:
        import google.generativeai as _genai_old  # noqa: F401

        _GENAI_OLD = True
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Azure Document Intelligence SDK detection
# ---------------------------------------------------------------------------
_AZURE_DI = False

try:
    from azure.ai.documentintelligence import DocumentIntelligenceClient  # noqa: F401
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest  # noqa: F401
    from azure.core.credentials import AzureKeyCredential  # noqa: F401

    _AZURE_DI = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
PROMPT = """\
この画像は日本の請求書（invoice）です。以下の情報を抽出してJSON形式で返してください。

{
  "vendor": "請求書を発行した会社（差出人・発行者）の正式名称。株式会社等を含む。不明なら null",
  "issue_date": "発行日（YYYYMMDD形式、例: 20260125。不明なら null）",
  "amount_subtotal": "税抜小計（数字のみカンマなし。不明なら null）",
  "amount_tax": "消費税額（数字のみカンマなし。不明なら null）",
  "amount_total": "税込合計金額（数字のみカンマなし。不明なら null）",
  "amount_due": "差引請求額・ご請求額（数字のみカンマなし。不明なら null）",
  "invoice_no": "請求書番号（あれば。不明なら null）"
}

重要:
- JSONオブジェクトのみを返してください。説明文は不要です。
- 金額フィールドは見つかったものだけ記入。不明なフィールドはnull。
- amount_due（差引請求額）が最優先。次にamount_total（税込合計）。
- 日付は和暦の場合、西暦に変換してください（令和7年=2025年、令和8年=2026年）。
- issue_date は「発行日」「請求日」「請求書日付」を優先し、「支払期限」「お支払期限」「入金予定日」は絶対に選ばないこと。
- amount は「差引請求額」「ご請求額」「今回請求額」「請求金額」を優先し、「前回請求額」「累計」「出来高」「入金額」は選ばないこと。
- vendorは「請求元」＝この請求書を作成・発行した会社です。
  ※「御中」「殿」「様」が付いた会社名は宛先（受取人）なので除外すること。
  ※ 宛先と請求元を間違えないこと。
  ※ 住所・電話番号・登録番号（T+13桁）の近くにある会社名を優先すること。
  ※ 「東海インプル建設株式会社」は宛先（受取会社）です。vendorには入れないでください。
"""

# OpenAI Structured Output schema
_OPENAI_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "invoice_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "vendor": {"type": ["string", "null"]},
                "issue_date": {"type": ["string", "null"]},
                "amount_subtotal": {"type": ["string", "null"]},
                "amount_tax": {"type": ["string", "null"]},
                "amount_total": {"type": ["string", "null"]},
                "amount_due": {"type": ["string", "null"]},
                "invoice_no": {"type": ["string", "null"]},
            },
            "required": ["vendor", "issue_date", "amount_subtotal", "amount_tax", "amount_total", "amount_due", "invoice_no"],
            "additionalProperties": False,
        },
    },
}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------
@dataclass
class VisionOcrResult:
    """Result of Vision API OCR extraction."""

    text: str = ""
    vendor: str | None = None
    issue_date: str | None = None
    amount: str | None = None
    amount_subtotal: str | None = None
    amount_tax: str | None = None
    amount_total: str | None = None
    amount_due: str | None = None
    invoice_no: str | None = None
    provider: str = ""
    elapsed_s: float = 0.0
    error: str | None = None
    confidence: str = "low"
    fallback_used: bool = False
    fallback_from: str | None = None
    vendor_category: str | None = None
    requires_manual: bool = True
    review_reasons: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# PDF -> images
# ---------------------------------------------------------------------------
def _pdf_to_images(pdf_path: Path, max_pages: int = 3, dpi: int = 200) -> list[bytes]:
    """Convert PDF pages to PNG byte arrays."""
    doc = fitz.open(str(pdf_path))
    images: list[bytes] = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        pix = page.get_pixmap(dpi=dpi)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


def _extract_pdf_text(pdf_path: Path, max_pages: int = 3) -> str:
    """Extract text from PDF using PyMuPDF. Returns concatenated text."""
    doc = fitz.open(str(pdf_path))
    texts = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        texts.append(page.get_text())
    doc.close()
    return "\n".join(texts)


def _clean_positive_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return None
    number = int(digits)
    return number if number > 0 else None


def _is_valid_issue_date(value: str | None) -> bool:
    if not value:
        return False
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 8 or not digits.startswith("20"):
        return False
    try:
        parsed = datetime.strptime(digits, "%Y%m%d").date()
    except ValueError:
        return False
    return parsed <= (datetime.now().date() + timedelta(days=60))


def _normalize_yyyymmdd_candidate(value: str) -> str | None:
    digits = re.sub(r"\D", "", unicodedata.normalize("NFKC", value or ""))

    def _validate(y: int, mo: int, d: int) -> bool:
        if not (2000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
            return False
        try:
            datetime(y, mo, d)
            return True
        except ValueError:
            return False

    if len(digits) == 8:
        y, mo, d = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
        if _validate(y, mo, d):
            return f"{y:04d}{mo:02d}{d:02d}"
        return None
    if len(digits) == 7:
        y, mo, d = int(digits[0:4]), int(digits[4:5]), int(digits[5:7])
        if _validate(y, mo, d):
            return f"{y:04d}{mo:02d}{d:02d}"
        return None
    if len(digits) == 6:
        y, mo, d = 2000 + int(digits[0:2]), int(digits[2:4]), int(digits[4:6])
        if _validate(y, mo, d):
            return f"{y:04d}{mo:02d}{d:02d}"
        return None
    if len(digits) == 9:
        today = datetime.now().date()
        candidates: list[tuple[int, int, str]] = []
        for idx in range(9):
            parsed = _normalize_yyyymmdd_candidate(digits[:idx] + digits[idx + 1 :])
            if not parsed:
                continue
            cand_date = datetime.strptime(parsed, "%Y%m%d").date()
            future_penalty = 0 if cand_date <= today else 1
            candidates.append((future_penalty, abs((today - cand_date).days), parsed))
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1], item[2]))
            return candidates[0][2]
    return None


def _parse_date_fragment(value: str | None) -> str | None:
    normalized = unicodedata.normalize("NFKC", value or "")
    reiwa_match = re.search(r"(?:令和|R)\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?", normalized, re.IGNORECASE)
    if reiwa_match:
        year = 2018 + int(reiwa_match.group(1))
        month = int(reiwa_match.group(2))
        day = int(reiwa_match.group(3))
        return _normalize_yyyymmdd_candidate(f"{year:04d}{month:02d}{day:02d}")

    ymd_match = re.search(r"(20\d{2})\s*[./\-年 ]\s*(\d{1,2})\s*[./\-月 ]\s*(\d{1,2})\s*日?", normalized)
    if ymd_match:
        year = int(ymd_match.group(1))
        month = int(ymd_match.group(2))
        day = int(ymd_match.group(3))
        return _normalize_yyyymmdd_candidate(f"{year:04d}{month:02d}{day:02d}")

    return _normalize_yyyymmdd_candidate(normalized)


def _cleanup_filename_vendor_hint(value: str | None) -> str | None:
    if not value:
        return None
    normalized = unicodedata.normalize("NFKC", value)
    vendor = normalized.strip().strip("_-[]{}【】　 ")
    vendor = re.sub(r"^[✖×・]+", "", vendor).strip()
    vendor = re.sub(r"^[\d０-９]+", "", vendor).strip()
    vendor = re.sub(r"^(?:再|再送|請求書|御請求書|請求明細|請求書明細|請求書鑑)\s*", "", vendor).strip()
    vendor = re.sub(r"\s*(?:請求書|御請求書|請求明細|請求書明細|請求書鑑)\s*$", "", vendor).strip()
    vendor = vendor.strip("_-[]{}【】　 ")
    return vendor or None


def _extract_amount_hint(value: str | None) -> str | None:
    if not value:
        return None
    normalized = unicodedata.normalize("NFKC", value)
    for match in re.finditer(r"(?<!\d)([¥￥]?\s*[\d,，.．]+\s*円?)(?!\d)", normalized):
        digits = re.sub(r"\D", "", match.group(1))
        if not digits:
            continue
        amount = int(digits)
        if 0 < amount < 1_000_000_000:
            # Guard: do not mistake YYYYMMDD-like tokens for amount.
            if _normalize_yyyymmdd_candidate(digits):
                continue
            return digits
    return None


def _get_vendor_amount_strategy(vendor: str | None) -> str | None:
    normalized = str(vendor or "").strip()
    if not normalized:
        return None
    strategy = VENDOR_AMOUNT_STRATEGY.get(normalized)
    if strategy:
        return strategy
    if normalized.endswith("甲陽建設工業"):
        return "prefer_total"
    return None


def _extract_filename_hint_fields(filename: str | None) -> dict[str, str]:
    """Extract conservative vendor/date/amount hints from filename patterns."""
    if not filename:
        return {}

    normalized = unicodedata.normalize("NFKC", str(filename)).removesuffix(".pdf").strip()
    normalized = normalized.replace("＿", "_")

    patterns = (
        re.compile(
            r"^(?P<vendor>.+?)_(?P<date>\d{6,9})_(?P<amount>[\d,，,.]+)(?:[_（【([](?P<project>.+))?$"
        ),
        re.compile(
            r"^(?P<vendor>.+?)-(?P<date>\d{8})-(?P<amount>[\d,，,.]+)(?:-(?P<project>.+))?$"
        ),
        re.compile(
            r"^(?P<vendor>.+?)_(?P<year>\d{4})\.(?P<month>\d{1,2})\.(?P<day>\d{1,2})_(?P<amount>[\d,，,.]+)(?:_(?P<project>.+))?$"
        ),
    )

    for pattern in patterns:
        match = pattern.match(normalized)
        if not match:
            continue

        vendor = _cleanup_filename_vendor_hint(match.groupdict().get("vendor"))
        amount = re.sub(r"\D", "", match.groupdict().get("amount") or "")
        date_value = match.groupdict().get("date")
        if not date_value and match.groupdict().get("year"):
            date_value = (
                f"{match.group('year')}{match.group('month').zfill(2)}{match.group('day').zfill(2)}"
            )
        issue_date = _normalize_yyyymmdd_candidate(date_value or "")

        payload: dict[str, str] = {}
        if vendor:
            payload["vendor"] = vendor
        if issue_date:
            payload["issue_date"] = issue_date
        if amount:
            payload["amount"] = amount
        if payload:
            return payload

    stem = normalized.strip()
    date_spans: list[tuple[int, int, str]] = []
    date_patterns = (
        re.compile(r"(?:令和|R)\s*\d{1,2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?", re.IGNORECASE),
        re.compile(r"20\d{2}\s*[./\-年 ]\s*\d{1,2}\s*[./\-月 ]\s*\d{1,2}\s*日?"),
        re.compile(r"(?<!\d)\d{6,9}(?!\d)"),
    )
    for pattern in date_patterns:
        for match in pattern.finditer(stem):
            parsed = _parse_date_fragment(match.group(0))
            if parsed:
                date_spans.append((match.start(), match.end(), parsed))
    date_spans.sort(key=lambda item: (item[0], item[1]))

    issue_date = date_spans[0][2] if date_spans else None
    date_start = date_spans[0][0] if date_spans else None
    date_end = date_spans[0][1] if date_spans else None

    vendor = _cleanup_filename_vendor_hint(stem[:date_start] if date_start is not None else stem)
    amount = _extract_amount_hint(stem[date_end:] if date_end is not None else stem)

    payload: dict[str, str] = {}
    if vendor:
        payload["vendor"] = vendor
    if issue_date:
        payload["issue_date"] = issue_date
    if amount:
        payload["amount"] = amount
    if payload:
        return payload

    return {}


def _detect_non_invoice_signals(
    *,
    filename_hint: str | None = None,
    context_text: str | None = None,
) -> tuple[str, ...]:
    haystacks: list[str] = []
    if filename_hint:
        haystacks.append(unicodedata.normalize("NFKC", str(filename_hint)).lower())
    if context_text:
        haystacks.append(unicodedata.normalize("NFKC", str(context_text))[:4000].lower())

    if not haystacks:
        return ()

    found: list[str] = []
    for label, keywords in NON_INVOICE_SIGNAL_PATTERNS:
        if any(keyword.lower() in haystack for haystack in haystacks for keyword in keywords):
            found.append(label)
    return tuple(found)


def _parse_labeled_issue_date(text: str | None) -> str | None:
    if not text:
        return None
    normalized = unicodedata.normalize("NFKC", text)
    for match in DATE_LABEL_RE.finditer(normalized):
        value = match.group(2)
        labeled_match = DATE_YMD_RE.search(value)
        if not labeled_match:
            digits = re.sub(r"\D", "", value)
            if len(digits) == 8 and digits.startswith("20"):
                try:
                    datetime.strptime(digits, "%Y%m%d")
                    return digits
                except ValueError:
                    continue
            continue
        year = int(labeled_match.group("y"))
        month = int(labeled_match.group("m"))
        day = int(labeled_match.group("d"))
        try:
            datetime(year, month, day)
        except ValueError:
            continue
        return f"{year:04d}{month:02d}{day:02d}"
    return None


def _select_labeled_amount(text: str | None) -> str | None:
    if not text:
        return None

    def _label_priority(label: str) -> int:
        if "支払決定" in label:
            return 0
        if ("支払" in label) or ("お支払" in label) or ("お支払い" in label):
            return 1
        if "請求" in label:
            return 2
        return 3

    normalized = unicodedata.normalize("NFKC", text)
    candidates: list[tuple[int, int]] = []

    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        compact = re.sub(r"\s+", "", line)
        label = next((keyword for keyword in AMOUNT_LABEL_KEYWORDS if keyword in compact), None)
        if not label:
            continue
        for look_ahead in range(idx, min(len(lines), idx + 6)):
            raw = re.sub(r"\D", "", lines[look_ahead])
            if not raw:
                continue
            value = int(raw)
            if value <= 0:
                continue
            candidates.append((_label_priority(label), value))
            break

    for match in AMOUNT_LABEL_RE.finditer(normalized):
        raw = re.sub(r"\D", "", match.group(2))
        if not raw:
            continue
        value = int(raw)
        if value <= 0:
            continue
        candidates.append((_label_priority(match.group(1)), value))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], -item[1]))
    return str(candidates[0][1])


def _select_tax_inclusive_invoice_amount(text: str | None) -> str | None:
    if not text:
        return None
    normalized = unicodedata.normalize("NFKC", text)
    patterns = (
        re.compile(r"請求金額\s*[（(]税込[)）]\s*[:：]?\s*[¥￥]?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)"),
        re.compile(r"請求金額\s*[（(]税込[)）][^0-9]{0,40}([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)", re.DOTALL),
    )
    for pattern in patterns:
        match = pattern.search(normalized)
        if not match:
            continue
        digits = re.sub(r"\D", "", match.group(1))
        if digits:
            return digits
    return None


def evaluate_auto_pass(
    *,
    vendor: str | None,
    issue_date: str | None,
    amount: str | int | None,
    amount_subtotal: str | int | None = None,
    amount_tax: str | int | None = None,
    amount_total: str | int | None = None,
    amount_due: str | int | None = None,
    confidence: str = "low",
    fallback_used: bool = False,
    filename_hint: str | None = None,
    context_text: str | None = None,
) -> tuple[str | None, bool, tuple[str, ...]]:
    """Return (vendor_category, requires_manual, review_reasons)."""
    review_reasons: list[str] = []
    vendor_category = classify_vendor_category(vendor)

    if not vendor:
        review_reasons.append("missing_vendor")
    if vendor_category != "fixed":
        review_reasons.append(f"vendor_category:{vendor_category or 'unknown'}")
    forced_manual_reason = None
    if forced_manual_reason:
        review_reasons.append(forced_manual_reason)
    if not _is_valid_issue_date(issue_date):
        review_reasons.append("invalid_issue_date")

    resolved_amount = _clean_positive_int(amount)
    subtotal = _clean_positive_int(amount_subtotal)
    tax = _clean_positive_int(amount_tax)
    total = _clean_positive_int(amount_total)
    due = _clean_positive_int(amount_due)

    if resolved_amount is None:
        review_reasons.append("invalid_amount")
    if confidence != "high":
        review_reasons.append(f"confidence:{confidence}")
    if fallback_used:
        review_reasons.append("provider_fallback")
    for signal in _detect_non_invoice_signals(
        filename_hint=filename_hint,
        context_text=context_text,
    ):
        review_reasons.append(f"non_invoice_signal:{signal}")

    candidate_amounts = {v for v in (due, total, subtotal) if v is not None}
    if subtotal is not None and tax is not None:
        candidate_amounts.add(subtotal + tax)
    if resolved_amount is not None and candidate_amounts and resolved_amount not in candidate_amounts:
        review_reasons.append("amount_mismatch:resolved_amount")
    if (
        subtotal is not None
        and tax is not None
        and total is not None
        and (subtotal + tax) != total
        and resolved_amount not in {due, total}
    ):
        review_reasons.append("amount_mismatch:subtotal+tax!=total")
    if due is not None and total is not None and due > total:
        review_reasons.append("amount_mismatch:due>total")

    deduped: list[str] = []
    seen: set[str] = set()
    for reason in review_reasons:
        if reason in seen:
            continue
        seen.add(reason)
        deduped.append(reason)
    return vendor_category, bool(deduped), tuple(deduped)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _validate_result(
    data: dict[str, Any],
    *,
    context_text: str = "",
    sender_hint: str | None = None,
    subject_hint: str | None = None,
    filename_hint: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Validate and clean extracted data. Returns (cleaned_data, confidence)."""
    confidence = "high"
    filename_fields = _extract_filename_hint_fields(filename_hint)
    non_invoice_signals = _detect_non_invoice_signals(
        filename_hint=filename_hint,
        context_text=context_text,
    )
    used_filename_hint = False
    used_sender_hint = False
    labeled_issue_date = _parse_labeled_issue_date(context_text)
    labeled_amount = _select_labeled_amount(context_text)

    # issue_date: 8-digit number starting with 20
    if data.get("issue_date"):
        d = re.sub(r"\D", "", str(data["issue_date"]))
        if len(d) == 8 and d[:2] == "20":
            data["issue_date"] = d
        else:
            confidence = "low"
            data["issue_date"] = None
    if labeled_issue_date and data.get("issue_date") != labeled_issue_date:
        if data.get("issue_date"):
            confidence = "medium" if confidence == "high" else confidence
        data["issue_date"] = labeled_issue_date

    # amount: resolve from decomposed fields, then validate
    resolved_amount = _resolve_amount(data)
    if resolved_amount:
        data["amount"] = resolved_amount
    else:
        # Fallback: try legacy single "amount" field if present
        if data.get("amount"):
            a = re.sub(r"\D", "", str(data["amount"]))
            if a and int(a) > 0:
                data["amount"] = a
            else:
                confidence = "low"
                data["amount"] = None
        else:
            confidence = "low"
            data["amount"] = None
    if labeled_amount:
        current_amount = _clean_positive_int(data.get("amount"))
        labeled_amount_int = _clean_positive_int(labeled_amount)
        if current_amount is None and labeled_amount_int is not None:
            data["amount"] = labeled_amount
        elif (
            current_amount is not None
            and labeled_amount_int is not None
            and labeled_amount_int > current_amount
        ):
            ratio = labeled_amount_int / current_amount if current_amount else 0.0
            if 1.08 <= ratio <= 1.12:
                data["amount"] = str(labeled_amount_int)
                confidence = "medium" if confidence == "high" else confidence

    # vendor: minimum length
    if data.get("vendor") and len(str(data["vendor"]).strip()) < 2:
        data["vendor"] = None
        if confidence == "high":
            confidence = "medium"

    # vendor: apply shared vendor matching / hint rules
    if data.get("vendor"):
        data["vendor"] = canonicalize_vendor(
            str(data["vendor"]),
            sender=sender_hint,
            context_text=context_text,
            drop_non_vendor=True,
        )

    if str(data.get("vendor") or "") in VENDOR_PREFER_LABELED_AMOUNT:
        preferred_amount = _select_tax_inclusive_invoice_amount(context_text) or labeled_amount
        labeled_amount_int = _clean_positive_int(preferred_amount)
        if labeled_amount_int is not None:
            data["amount"] = str(labeled_amount_int)

    if not data.get("vendor"):
        sender_match = infer_vendor_from_sender_context(
            sender=sender_hint,
            subject=subject_hint,
            attachment_name=filename_hint,
            context_text=context_text,
        )
        if sender_match.canonical:
            data["vendor"] = sender_match.canonical
            used_sender_hint = True

    for key in ("vendor", "issue_date", "amount"):
        if data.get(key) or not filename_fields.get(key):
            continue
        data[key] = filename_fields[key]
        used_filename_hint = True

    if data.get("vendor"):
        data["vendor"] = canonicalize_vendor(
            str(data["vendor"]),
            sender=sender_hint,
            context_text=context_text,
            drop_non_vendor=True,
        )

    if used_filename_hint and confidence == "high":
        confidence = "medium"
    if used_sender_hint and confidence == "high":
        confidence = "medium"

    strategy = _get_vendor_amount_strategy(str(data.get("vendor") or ""))
    _apply_vendor_amount_override(data)

    preserve_amount_from_ocr = (
        (strategy in {"prefer_due", "prefer_total"} or str(data.get("vendor") or "") in VENDOR_PREFER_LABELED_AMOUNT)
        and bool(data.get("amount"))
    )

    if filename_fields:
        filename_vendor = filename_fields.get("vendor")
        if filename_vendor:
            data["vendor"] = canonicalize_vendor(
                str(filename_vendor),
                sender=sender_hint,
                context_text=context_text,
                drop_non_vendor=True,
            ) or filename_vendor
        for field_name in ("issue_date", "amount"):
            if field_name == "amount" and preserve_amount_from_ocr:
                continue
            filename_value = filename_fields.get(field_name)
            if filename_value:
                data[field_name] = filename_value

    # Hard-hide clearly non-invoice documents, but keep delivery-note values visible for review.
    if non_invoice_signals:
        suppress_fields = any(signal != "delivery_note" for signal in non_invoice_signals)
        if suppress_fields:
            data["vendor"] = None
            data["issue_date"] = None
            data["amount"] = None
        confidence = "low"

    # 2+ nulls among key fields -> low
    nulls = sum(1 for k in ["vendor", "issue_date", "amount"] if not data.get(k))
    if nulls >= 2:
        confidence = "low"

    return data, confidence


def _resolve_amount(parsed: dict[str, Any]) -> str | None:
    """Resolve final amount from decomposed fields.

    Priority: amount_due > amount_total > (amount_subtotal + amount_tax) > amount_subtotal
    """
    def _clean_int(v: Any) -> int | None:
        if not v:
            return None
        digits = re.sub(r"\D", "", str(v))
        return int(digits) if digits and int(digits) > 0 else None

    due = _clean_int(parsed.get("amount_due"))
    total = _clean_int(parsed.get("amount_total"))
    subtotal = _clean_int(parsed.get("amount_subtotal"))
    tax = _clean_int(parsed.get("amount_tax"))
    subtotal_plus_tax = (subtotal + tax) if (subtotal and tax) else None

    # Reject clearly implausible "due" values when better totals exist.
    if due and total and due > int(total * 1.2):
        due = None
    if due and subtotal_plus_tax and due > int(subtotal_plus_tax * 1.2):
        due = None

    # Priority 1: amount_due (差引請求額) — the actual amount to pay
    if due:
        return str(due)

    # Priority 2: amount_total (税込合計)
    if total:
        return str(total)

    # Priority 3: subtotal + tax (if both available, compute total)
    if subtotal_plus_tax:
        return str(subtotal_plus_tax)

    # Priority 4: subtotal only (better than nothing)
    if subtotal:
        return str(subtotal)

    return None


def _apply_vendor_amount_override(data: dict[str, Any]) -> None:
    vendor = str(data.get("vendor") or "")
    strategy = _get_vendor_amount_strategy(vendor)
    if strategy == "prefer_due":
        due = _clean_positive_int(data.get("amount_due"))
        if due is not None:
            data["amount"] = str(due)
    elif strategy == "prefer_total":
        total = _clean_positive_int(data.get("amount_total"))
        if total is not None:
            data["amount"] = str(total)

    # YAMAJI invoices sometimes oscillate between subtotal and total.
    # If tax is missing but a clean 10% tax pattern is plausible, prefer税込.
    if vendor == "YAMAJIパーティション":
        total = _clean_positive_int(data.get("amount_total"))
        due = _clean_positive_int(data.get("amount_due"))
        subtotal = _clean_positive_int(data.get("amount_subtotal"))
        tax = _clean_positive_int(data.get("amount_tax"))
        if total is not None:
            data["amount"] = str(total)
        elif due is not None:
            data["amount"] = str(due)
        elif subtotal is not None:
            if tax is not None:
                data["amount"] = str(subtotal + tax)
            else:
                inferred_total = int(round(subtotal * 1.1))
                data["amount"] = str(inferred_total)


def _parse_json_from_text(text: str) -> dict[str, Any]:
    """Extract JSON object from potentially wrapped text."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find JSON block in markdown code fence
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # Try to find first { ... }
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise json.JSONDecodeError("No JSON object found", text, 0)


def _build_adi_request_bytes(
    pdf_path: Path,
    *,
    max_pages: int = 3,
    max_bytes: int = 7_500_000,
) -> bytes:
    """Build compact bytes for Azure DI from the first few PDF pages."""
    source = fitz.open(str(pdf_path))
    try:
        max_page_index = min(max_pages, source.page_count) - 1
        for page_count in range(max_page_index + 1, 0, -1):
            subset = fitz.open()
            try:
                subset.insert_pdf(source, from_page=0, to_page=page_count - 1)
                pdf_bytes = subset.tobytes(garbage=4, deflate=True)
            finally:
                subset.close()
            if len(pdf_bytes) <= max_bytes:
                return pdf_bytes

        # Last resort: render first page to PNG. One-page invoices are usually enough.
        page = source.load_page(0)
        for dpi in (150, 120, 96):
            pix = page.get_pixmap(dpi=dpi)
            png_bytes = pix.tobytes("png")
            if len(png_bytes) <= max_bytes:
                return png_bytes
        return png_bytes
    finally:
        source.close()


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------
def _call_claude(
    page_images_b64: list[str], timeout_s: float, model: str = "claude-sonnet-4-20250514",
    prompt: str = PROMPT, **kwargs,
) -> tuple[str, dict[str, Any]]:
    """Call Claude Vision API. Returns (raw_text, parsed_dict)."""
    import httpx
    import anthropic

    client = anthropic.Anthropic(timeout=httpx.Timeout(timeout_s))
    content: list[dict[str, Any]] = []
    for b64 in page_images_b64:
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": b64},
            }
        )
    content.append({"type": "text", "text": prompt})

    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )
    raw_text = message.content[0].text
    parsed = _parse_json_from_text(raw_text)
    return raw_text, parsed


def _call_openai(
    page_images_b64: list[str], timeout_s: float, model: str = "gpt-4o",
    prompt: str = PROMPT, **kwargs,
) -> tuple[str, dict[str, Any]]:
    """Call OpenAI Vision API with Structured Output. Returns (raw_text, parsed_dict)."""
    import openai

    client = openai.OpenAI(timeout=timeout_s)
    content: list[dict[str, Any]] = []
    for b64 in page_images_b64:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )
    content.append({"type": "text", "text": prompt})

    # o3/o4 models: no Structured Output, use max_completion_tokens instead of max_tokens
    is_reasoning = any(k in model for k in ("o3", "o4"))
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
    }
    if is_reasoning:
        kwargs["max_completion_tokens"] = 1024
    else:
        kwargs["max_tokens"] = 1024
        kwargs["response_format"] = _OPENAI_JSON_SCHEMA

    response = client.chat.completions.create(**kwargs)
    raw_text = response.choices[0].message.content
    parsed = _parse_json_from_text(raw_text) if is_reasoning else json.loads(raw_text)
    return raw_text, parsed


def _call_gemini(
    page_images_b64: list[str], timeout_s: float, model: str = "gemini-2.0-flash",
    prompt: str = PROMPT, **kwargs,
) -> tuple[str, dict[str, Any]]:
    """Call Gemini Vision API. Returns (raw_text, parsed_dict)."""
    if _GENAI_NEW:
        return _call_gemini_new(page_images_b64, timeout_s, model=model, prompt=prompt)
    elif _GENAI_OLD:
        return _call_gemini_old(page_images_b64, timeout_s, model=model, prompt=prompt)
    else:
        raise ImportError("No Gemini SDK available (google-genai or google-generativeai)")


def _call_gemini_new(
    page_images_b64: list[str], timeout_s: float, model: str = "gemini-2.0-flash",
    prompt: str = PROMPT, **kwargs,
) -> tuple[str, dict[str, Any]]:
    """Call Gemini via new google-genai SDK."""
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"),
        http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
    )
    parts: list[types.Part] = []
    for b64 in page_images_b64:
        parts.append(
            types.Part.from_bytes(data=base64.b64decode(b64), mime_type="image/png")
        )
    parts.append(types.Part.from_text(text=prompt))

    response = client.models.generate_content(
        model=model,
        contents=types.Content(role="user", parts=parts),
        config=types.GenerateContentConfig(max_output_tokens=1024),
    )
    raw_text = response.text
    parsed = _parse_json_from_text(raw_text)
    return raw_text, parsed


def _call_gemini_old(
    page_images_b64: list[str], timeout_s: float, model: str = "gemini-2.0-flash",
    prompt: str = PROMPT, **kwargs,
) -> tuple[str, dict[str, Any]]:
    """Call Gemini via deprecated google-generativeai SDK."""
    import google.generativeai as genai_old

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if api_key:
        genai_old.configure(api_key=api_key)

    gmodel = genai_old.GenerativeModel(model)
    parts: list[Any] = []
    for b64 in page_images_b64:
        parts.append({"mime_type": "image/png", "data": base64.b64decode(b64)})
    parts.append(prompt)

    response = gmodel.generate_content(
        parts,
        request_options={"timeout": timeout_s},
        generation_config=genai_old.GenerationConfig(max_output_tokens=1024),
    )
    raw_text = response.text
    parsed = _parse_json_from_text(raw_text)
    return raw_text, parsed


# ---------------------------------------------------------------------------
# Azure Document Intelligence providers
# ---------------------------------------------------------------------------
def _call_azure_di(
    page_images_b64: list[str], timeout_s: float, **kwargs,
) -> tuple[str, dict[str, Any]]:
    """Call Azure Document Intelligence prebuilt-invoice. Returns (raw_text, parsed_dict)."""
    if not _AZURE_DI:
        raise ImportError("azure-ai-documentintelligence is not installed")

    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
    from azure.core.credentials import AzureKeyCredential

    endpoint = os.environ.get("AZURE_DI_ENDPOINT")
    key = os.environ.get("AZURE_DI_KEY")
    if not endpoint or not key:
        raise ValueError("AZURE_DI_ENDPOINT and AZURE_DI_KEY must be set")

    pdf_path = kwargs.get("pdf_path")
    if not pdf_path:
        raise ValueError("pdf_path is required for azure_di provider")

    pdf_bytes = _build_adi_request_bytes(Path(pdf_path))

    client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    poller = client.begin_analyze_document(
        model_id="prebuilt-invoice",
        body=AnalyzeDocumentRequest(bytes_source=pdf_bytes),
        locale="ja-JP",
    )
    result = poller.result()

    raw_text = result.content or ""

    parsed: dict[str, Any] = {
        "vendor": None,
        "issue_date": None,
        "amount": None,
        "invoice_no": None,
    }

    if result.documents:
        fields = result.documents[0].fields or {}

        # VendorName
        if "VendorName" in fields and fields["VendorName"].content:
            parsed["vendor"] = fields["VendorName"].content

        # InvoiceDate -> YYYYMMDD
        if "InvoiceDate" in fields and fields["InvoiceDate"].content:
            date_str = fields["InvoiceDate"].content
            # Try to parse common date formats
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    parsed["issue_date"] = dt.strftime("%Y%m%d")
                    break
                except ValueError:
                    continue
            if not parsed["issue_date"]:
                # Fallback: extract digits
                digits = re.sub(r"\D", "", date_str)
                if len(digits) == 8 and digits[:2] == "20":
                    parsed["issue_date"] = digits

        # Amount: InvoiceTotal > SubTotal
        for amount_field in ("InvoiceTotal", "SubTotal"):
            if amount_field in fields and fields[amount_field].content:
                amount_str = re.sub(r"\D", "", fields[amount_field].content)
                if amount_str and int(amount_str) > 0:
                    parsed["amount"] = amount_str
                    break

        # InvoiceId
        if "InvoiceId" in fields and fields["InvoiceId"].content:
            parsed["invoice_no"] = fields["InvoiceId"].content

    return raw_text, parsed


def _call_azure_di_gpt4o(
    page_images_b64: list[str], timeout_s: float, **kwargs,
) -> tuple[str, dict[str, Any]]:
    """Azure DI layout OCR + GPT-4o Vision. Returns (raw_text, parsed_dict)."""
    if not _AZURE_DI:
        raise ImportError("azure-ai-documentintelligence is not installed")

    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
    from azure.core.credentials import AzureKeyCredential

    endpoint = os.environ.get("AZURE_DI_ENDPOINT")
    key = os.environ.get("AZURE_DI_KEY")
    if not endpoint or not key:
        raise ValueError("AZURE_DI_ENDPOINT and AZURE_DI_KEY must be set")

    pdf_path = kwargs.get("pdf_path")
    if not pdf_path:
        raise ValueError("pdf_path is required for azure_di_gpt4o provider")

    pdf_bytes = _build_adi_request_bytes(Path(pdf_path))

    # Step 1: ADI layout OCR for high-quality text extraction
    client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    poller = client.begin_analyze_document(
        model_id="prebuilt-layout",
        body=AnalyzeDocumentRequest(bytes_source=pdf_bytes),
        locale="ja-JP",
    )
    result = poller.result()
    adi_text = result.content or ""

    # Step 2: Build augmented prompt with ADI text (instead of PyMuPDF text)
    if adi_text.strip():
        augmented_prompt = (
            f"【OCR補助テキスト（Azure Document Intelligence抽出。画像と矛盾する場合は画像を優先）】\n"
            f"{adi_text[:2000]}\n\n"
            f"{PROMPT}"
        )
    else:
        augmented_prompt = PROMPT

    # Step 3: Call GPT-4o Vision with ADI text + page images
    model = kwargs.get("model", "gpt-4o")
    _, parsed = _call_openai(page_images_b64, timeout_s, model=model, prompt=augmented_prompt)
    return adi_text, parsed


def _call_hybrid_gpt4o(
    page_images_b64: list[str], timeout_s: float, **kwargs,
) -> tuple[str, dict[str, Any]]:
    """PyMuPDF text + ADI text + GPT-4o Vision hybrid. Returns (raw_text, parsed_dict)."""
    if not _AZURE_DI:
        raise ImportError("azure-ai-documentintelligence is not installed")

    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
    from azure.core.credentials import AzureKeyCredential

    endpoint = os.environ.get("AZURE_DI_ENDPOINT")
    key = os.environ.get("AZURE_DI_KEY")
    if not endpoint or not key:
        raise ValueError("AZURE_DI_ENDPOINT and AZURE_DI_KEY must be set")

    pdf_path = kwargs.get("pdf_path")
    if not pdf_path:
        raise ValueError("pdf_path is required for hybrid_gpt4o provider")

    # Source 1: PyMuPDF text (embedded text layer)
    pymupdf_text = _extract_pdf_text(Path(pdf_path), max_pages=3)

    # Source 2: ADI layout OCR text (image-based OCR)
    pdf_bytes = _build_adi_request_bytes(Path(pdf_path))
    client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    poller = client.begin_analyze_document(
        model_id="prebuilt-layout",
        body=AnalyzeDocumentRequest(bytes_source=pdf_bytes),
        locale="ja-JP",
    )
    result = poller.result()
    adi_text = result.content or ""

    # Build augmented prompt with both text sources
    text_parts = []
    if pymupdf_text.strip():
        text_parts.append(f"【テキスト抽出1: PDF埋め込みテキスト】\n{pymupdf_text[:1000]}")
    if adi_text.strip():
        text_parts.append(f"【テキスト抽出2: Azure Document Intelligence OCR】\n{adi_text[:1000]}")

    if text_parts:
        augmented_prompt = (
            "\n\n".join(text_parts)
            + "\n\n※上記は参考情報です。画像と矛盾する場合は画像を優先してください。\n\n"
            + PROMPT
        )
    else:
        augmented_prompt = PROMPT

    model = kwargs.get("model", "gpt-4o")
    _, parsed = _call_openai(page_images_b64, timeout_s, model=model, prompt=augmented_prompt)
    combined_text = "\n\n".join(part for part in (pymupdf_text, adi_text) if part.strip())
    return combined_text, parsed


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------
_PROVIDERS: dict[str, tuple[str, Any]] = {
    "claude": ("ANTHROPIC_API_KEY", _call_claude),
    "openai": ("OPENAI_API_KEY", _call_openai),
    "gemini": ("GOOGLE_API_KEY", _call_gemini),
    "azure_di": ("AZURE_DI_KEY", _call_azure_di),
    "azure_di_gpt4o": ("AZURE_DI_KEY", _call_azure_di_gpt4o),
    "hybrid_gpt4o": ("AZURE_DI_KEY", _call_hybrid_gpt4o),
}

# Gemini also checks GEMINI_API_KEY
_GEMINI_ALT_KEY = "GEMINI_API_KEY"


def _provider_available(name: str) -> bool:
    """Check if a provider's API key is set."""
    env_key = _PROVIDERS[name][0]
    if os.environ.get(env_key):
        return True
    if name == "gemini" and os.environ.get(_GEMINI_ALT_KEY):
        return True
    return False


def _get_provider_order(requested: str) -> list[str]:
    """Return ordered list of providers to try.

    When a specific provider is requested, includes fallback providers:
    - azure_di_gpt4o -> fallback to openai (PyMuPDF+GPT-4o baseline)
    - hybrid_gpt4o -> fallback to openai
    - azure_di -> fallback to openai
    """
    all_names = ["claude", "openai", "gemini", "azure_di", "azure_di_gpt4o", "hybrid_gpt4o"]
    if requested == "auto":
        return [p for p in all_names if _provider_available(p)]

    # Fallback chains for ADI-based providers
    _FALLBACK_CHAINS = {
        "azure_di_gpt4o": ["azure_di_gpt4o", "openai"],
        "hybrid_gpt4o": ["hybrid_gpt4o", "openai"],
        "azure_di": ["azure_di", "openai"],
    }

    chain = _FALLBACK_CHAINS.get(requested, [requested])
    # Only include providers that have API keys available
    return [p for p in chain if _provider_available(p)]


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------
def extract(
    pdf_path: str | Path,
    provider: str = "auto",
    model: str | None = None,
    max_pages: int = 3,
    timeout_s: float = 30.0,
    sender_hint: str | None = None,
    subject_hint: str | None = None,
) -> VisionOcrResult:
    """Extract invoice data from PDF using Vision API.

    Args:
        pdf_path: Path to the PDF file.
        provider: "auto", "claude", "openai", or "gemini".
        model: Model name override (e.g. "gemini-2.5-pro", "o3-mini"). None uses provider default.
        max_pages: Maximum pages to process.
        timeout_s: Timeout per API call in seconds.
        sender_hint: Optional sender email/domain hint used for vendor matching.
        subject_hint: Optional mail subject hint used for sender-based rescue.

    Returns:
        VisionOcrResult with extracted data.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return VisionOcrResult(error=f"File not found: {pdf_path}", provider="none")

    # Convert PDF to base64 images
    try:
        raw_images = _pdf_to_images(pdf_path, max_pages=max_pages)
    except Exception as e:
        return VisionOcrResult(error=f"PDF conversion failed: {e}", provider="none")

    if not raw_images:
        return VisionOcrResult(error="No pages extracted from PDF", provider="none")

    page_images_b64 = [base64.b64encode(img).decode("ascii") for img in raw_images]
    logger.info("Converted %d page(s) from %s", len(page_images_b64), pdf_path.name)

    # 2-Stage: extract text from PDF for prompt augmentation
    # (skipped for azure_di / azure_di_gpt4o — they handle text extraction internally)
    _skip_pymupdf_providers = {"azure_di", "azure_di_gpt4o", "hybrid_gpt4o"}
    if provider not in _skip_pymupdf_providers:
        pdf_text = _extract_pdf_text(pdf_path, max_pages=max_pages)
        if pdf_text.strip():
            augmented_prompt = (
                f"【OCR補助テキスト（参考情報。画像と矛盾する場合は画像を優先）】\n"
                f"{pdf_text[:2000]}\n\n"
                f"{PROMPT}"
            )
        else:
            augmented_prompt = PROMPT
    else:
        augmented_prompt = PROMPT

    # Try providers in order
    providers = _get_provider_order(provider)
    if not providers:
        return VisionOcrResult(
            error="No providers available. Set API keys: ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY, AZURE_DI_KEY",
            provider="none",
        )

    errors: list[str] = []
    for prov_name in providers:
        _, call_fn = _PROVIDERS[prov_name]
        logger.info("Trying provider: %s", prov_name)
        t0 = time.perf_counter()
        try:
            call_kwargs: dict[str, Any] = {"prompt": augmented_prompt, "pdf_path": pdf_path}
            if model is not None:
                call_kwargs["model"] = model
            raw_text, parsed = _retry_with_backoff(
                call_fn, page_images_b64, timeout_s,
                max_retries=3, base_delay=2.0,
                **call_kwargs,
            )
            elapsed = time.perf_counter() - t0

            # Use model name as provider label when explicitly specified
            display_provider = model if model else prov_name
            cleaned, confidence = _validate_result(
                parsed,
                context_text=raw_text,
                sender_hint=sender_hint,
                subject_hint=subject_hint,
                filename_hint=pdf_path.name,
            )
            is_fallback = prov_name != providers[0]
            vendor_category, requires_manual, review_reasons = evaluate_auto_pass(
                vendor=cleaned.get("vendor"),
                issue_date=cleaned.get("issue_date"),
                amount=cleaned.get("amount"),
                amount_subtotal=cleaned.get("amount_subtotal"),
                amount_tax=cleaned.get("amount_tax"),
                amount_total=cleaned.get("amount_total"),
                amount_due=cleaned.get("amount_due"),
                confidence=confidence,
                fallback_used=is_fallback,
                filename_hint=pdf_path.name,
                context_text=raw_text,
            )
            return VisionOcrResult(
                text=raw_text,
                vendor=cleaned.get("vendor"),
                issue_date=cleaned.get("issue_date"),
                amount=cleaned.get("amount"),
                amount_subtotal=cleaned.get("amount_subtotal"),
                amount_tax=cleaned.get("amount_tax"),
                amount_total=cleaned.get("amount_total"),
                amount_due=cleaned.get("amount_due"),
                invoice_no=cleaned.get("invoice_no"),
                provider=display_provider,
                elapsed_s=round(elapsed, 2),
                confidence=confidence,
                fallback_used=is_fallback,
                fallback_from=providers[0] if is_fallback else None,
                vendor_category=vendor_category,
                requires_manual=requires_manual,
                review_reasons=review_reasons,
            )
        except Exception as e:
            elapsed = time.perf_counter() - t0
            err_msg = f"{prov_name}: {type(e).__name__}: {e}"
            logger.warning("Provider %s failed (%.1fs): %s", prov_name, elapsed, e)
            errors.append(err_msg)
            continue

    return VisionOcrResult(
        error=f"All providers failed: {'; '.join(errors)}", provider="none"
    )


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------
def _run_benchmark(
    pdf_dir: Path,
    provider: str,
    compare_all: bool,
    max_pages: int,
    timeout_s: float,
    model: str | None = None,
) -> str:
    """Run benchmark on all PDFs in directory. Returns markdown report."""
    pdfs = sorted(
        p for p in pdf_dir.rglob("*.pdf") if "merged" not in p.stem.lower()
    )
    if not pdfs:
        return f"No PDFs found in {pdf_dir}"

    providers_to_test = (
        ["claude", "openai", "gemini"] if compare_all else [provider]
    )

    rows: list[str] = []
    for i, pdf in enumerate(pdfs, 1):
        for prov in providers_to_test:
            if prov != "auto" and not _provider_available(prov):
                rows.append(
                    f"| {i} | {pdf.name} | {prov} | - | - | - | - | - | SKIP (no key) |"
                )
                continue
            result = extract(pdf, provider=prov, model=model, max_pages=max_pages, timeout_s=timeout_s)
            if result.error:
                rows.append(
                    f"| {i} | {pdf.name} | {result.provider or prov} | - | - | - | - | - | ERROR: {result.error[:40]} |"
                )
            else:
                rows.append(
                    f"| {i} | {pdf.name} | {result.provider} | {result.elapsed_s} "
                    f"| {result.vendor or '-'} | {result.issue_date or '-'} "
                    f"| {result.amount or '-'} | {result.invoice_no or '-'} "
                    f"| {result.confidence} |"
                )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = (
        f"# Vision OCR Benchmark Report\n"
        f"Date: {now}\n"
        f"Provider: {provider}{'(compare-all)' if compare_all else ''}\n"
        f"PDFs tested: {len(pdfs)}\n\n"
        f"| # | File | Provider | Time(s) | Vendor | Date | Amount | InvNo | Confidence |\n"
        f"|---|------|----------|---------|--------|------|--------|-------|------------|\n"
    )
    return header + "\n".join(rows) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    """CLI entry point."""
    import argparse

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    ap = argparse.ArgumentParser(description="Vision API OCR for Japanese invoices")
    ap.add_argument("--pdf", type=str, help="Single PDF path")
    ap.add_argument("--bench-dir", type=str, help="Directory of PDFs for benchmark")
    ap.add_argument(
        "--provider",
        default="auto",
        choices=["auto", "claude", "openai", "gemini", "azure_di", "azure_di_gpt4o", "hybrid_gpt4o"],
    )
    ap.add_argument(
        "--compare-all", action="store_true", help="Compare all providers"
    )
    ap.add_argument("--output", type=str, default=None, help="Output markdown path")
    ap.add_argument("--model", type=str, default=None, help="Model name override (e.g., gemini-2.5-pro, o3-mini)")
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    if not args.pdf and not args.bench_dir:
        ap.error("Either --pdf or --bench-dir is required")

    if args.bench_dir:
        report = _run_benchmark(
            pdf_dir=Path(args.bench_dir),
            provider=args.provider,
            compare_all=args.compare_all,
            max_pages=args.max_pages,
            timeout_s=args.timeout,
            model=args.model,
        )
        if args.output:
            Path(args.output).write_text(report, encoding="utf-8")
            logger.info("Report written to %s", args.output)
        else:
            print(report)
        return

    # Single PDF mode
    result = extract(
        pdf_path=args.pdf,
        provider=args.provider,
        model=args.model,
        max_pages=args.max_pages,
        timeout_s=args.timeout,
    )
    output = {
        "vendor": result.vendor,
        "issue_date": result.issue_date,
        "amount": result.amount,
        "amount_subtotal": result.amount_subtotal,
        "amount_tax": result.amount_tax,
        "amount_total": result.amount_total,
        "amount_due": result.amount_due,
        "invoice_no": result.invoice_no,
        "provider": result.provider,
        "elapsed_s": result.elapsed_s,
        "confidence": result.confidence,
        "error": result.error,
        "fallback_used": result.fallback_used,
        "fallback_from": result.fallback_from,
        "vendor_category": result.vendor_category,
        "requires_manual": result.requires_manual,
        "review_reasons": list(result.review_reasons),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
