"""Shared vendor matching helpers for scenario 12/13."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
VENDOR_HINTS_PATH = CONFIG_DIR / "vendor_hints.json"
GOLDEN_DATASET_PATH = CONFIG_DIR / "golden_dataset_v4.json"

COMPANY_TOKEN_RE = re.compile(r"(株式会社|有限会社|合同会社|合資会社|合名会社)")
EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
HONORIFIC_SUFFIX_RE = re.compile(r"(御中|様|殿)$")
LEADING_LABEL_RE = re.compile(r"^(請求元|発行者|差出人|取引先|会社名|会社)\s*[:：]?\s*")
LEADING_DECORATION_RE = re.compile(r"^[✖×※★☆■□△▲▼▽◎○●◇◆]+")
TRAILING_DOC_RE = re.compile(
    r"(請求書明細|請求書鑑|指定請求書|CP請求書|ＣＰ請求書|請求書|御請求書|インボイス|作業報告書|作業報告)$"
)
NUMBERISH_RE = re.compile(r"^[\dA-Za-z._\-/()（）]+$")
COMPARE_NOISE_RE = re.compile(r"[・･·.．,，'\"()（）\\[\\]【】「」『』_\\-:/\\\\]")

COMPARE_CHAR_MAP = str.maketrans({
    "髙": "高",
    "﨑": "崎",
    "塚": "塚",
    "德": "徳",
    "冨": "富",
})

LEGACY_VENDOR_HINTS: dict[str, tuple[str, ...]] = {
    "髙田工業所": ("高田工業所", "髙田工業所", "タカダ工業所"),
    "㈱カイノス": ("カイノス",),
    "㈱タツノ開発": ("タツノ開発",),
    "㈱高橋組": ("高橋組",),
    "太田商事㈱": ("太田商事",),
    "㈱カネモト": ("カネモト",),
    "㈱真栄産業": ("真栄産業",),
    "ジャパンギャランティサービス㈱": ("ジャパンギャランティ", "JGS"),
    "㈱山西": ("山西",),
    "パルカンパニー渡辺": ("パルカンパニー",),
    "㈱拓土": ("拓土",),
    "丸井産業㈱": ("丸井産業",),
    "㈱八木商会": ("八木商会",),
    "伊藤鉄筋": ("伊藤鉄筋",),
    "㈱セーファ": ("セーファ",),
    "㈱谷野宮組": ("谷野宮組",),
    "堀章塗装": ("堀章塗装",),
    "㈱神谷業務店": ("神谷業務店",),
    "アシタカ総建株式会社": ("アシタカ総建",),
    "㈱サムシング": ("サムシング",),
    "東海工測㈱": ("東海工測",),
    "㈱ハジメサービス": ("ハジメサービス",),
    "ソラサポート": ("ソラサポート",),
    "㈱新美興業": ("新美興業",),
    "安成工業": ("安成工業",),
    "㈱レンタルのニッケン": ("レンタルのニッケン", "ニッケン"),
    "中村産業鉄板リース㈱": ("中村産業鉄板リース", "中村産業"),
    "衣浦イーテクト㈱": ("衣浦イーテクト",),
    "(有)前畑工務店": ("前畑工務店",),
    "大功建築": ("大功建築",),
    "三谷商事": ("三谷商事",),
    "中部建装": ("中部建装",),
    "㈱大嶽安城": ("大嶽安城",),
    "フォースター": ("フォースター",),
    "トーケン": ("トーケン",),
    "知多重機": ("知多重機",),
    "キョーワ㈱": ("キョーワ",),
    "㈱川口": ("川口",),
    "(株)鳥居工業": ("鳥居工業",),
    "(有)竹下建築": ("竹下建築",),
    "クレーンタル野田": ("クレーンタル野田",),
    "株式会社ZERQ": ("ZERQ",),
    "岩田硝子": ("岩田硝子",),
    "日建工業㈱": ("日建工業",),
    "㈲池本シート商会": ("池本シート商会",),
    "有長工業所": ("有長工業所",),
    "東警㈱": ("東警",),
    "株式会社インテルグロー": ("インテルグロー",),
    "株式会社メイゴー": ("メイゴー",),
    "近藤電工社": ("近藤電工社",),
    "吉田電気工事㈱": ("吉田電気工事",),
    "株式会社ハローコーポレーション": ("ハローコーポレーション",),
    "㈱モノタロウ": ("モノタロウ", "MonotaRO", "MonotaRo", "株式会社MonotaRO", "Mono talRo", "株式会社Mono talRo"),
    "㈱NJS": ("NJS", "エヌジェイエス", "株式会社エヌジェイエス"),
    "東海スマート企業グループ株式会社スマイルテクノロジー": (
        "TSCG ST",
        "スマイルテクノロジー",
        "TSKG㈱スマイルテクノロジー",
        "TSKGスマイルテクノロジー",
        "TSKG（㈱）スマイルテクノロジー",
        "TSGK（㈱）スマイルテクノロジー11.25",
    ),
    "三和シャッター工業株式会社": (
        "三和シヤッター工業株式会社",
        "三和シャッター工業",
        "三和シヤッター工業",
    ),
    "北恵㈱": ("北恵", "北恵株式会社", "北恵株式会社名古屋営業所"),
    "セキュリティースタッフ㈱": (
        "セキュリティースタッフ",
        "セキュリティースタッフ株式会社",
        "セキュリティスタッフ",
        "セキュリティスタッフ株式会社",
        "セキュリティスタッフ㈱",
    ),
    "カーテン工房マルナ刈谷店": ("丸奈", "株式会社丸奈"),
    "エヌエーガラス㈲": ("エヌエーガラス", "エヌエーガラス有限会社", "エヌ・エーガラス有限会社"),
    "(株)エム・エイチ・シー・ランバー": (
        "エム・エイチ・シー・ランバー",
        "株式会社エム・エイチ・シー・ランバー",
        "株式会社エム·エイチ·シー·ランバー",
    ),
    "㈱Gエース": ("G-ACE", "株式会社G-ACE", "GACE", "株式会社GACE"),
    "一般財団法人 日本品質保証機構": ("(財)日本品質保証機構", "財)日本品質保証機構", "日本品質保証機構"),
}

DEFAULT_BLOCKED_VENDOR_CANDIDATES = ("東海インプル建設株式会社",)
DEFAULT_NON_VENDOR_PATTERNS = (
    "請求書明細",
    "請求書鑑",
    "指定請求書",
    "CP請求書",
    "ＣＰ請求書",
    "請求書",
    "御請求書",
    "請求web",
    "請求Web",
    "パスワード通知",
    "パスワード",
    "見積書",
    "納品書",
    "作業報告書",
    "工事",
    "新築工事",
    "改修工事",
    "注文発注用",
    "原本改定",
)


@dataclass(frozen=True)
class VendorHint:
    canonical: str
    aliases: tuple[str, ...] = ()
    sender_domains: tuple[str, ...] = ()
    web_domains: tuple[str, ...] = ()
    address_keywords: tuple[str, ...] = ()
    registration_numbers: tuple[str, ...] = ()
    project_keywords: tuple[str, ...] = ()
    deny_patterns: tuple[str, ...] = ()
    category: str | None = None
    sources: tuple[str, ...] = ()
    match_keys: tuple[str, ...] = ()
    project_match_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class VendorMatch:
    original: str | None
    candidate: str | None
    canonical: str | None = None
    category: str | None = None
    matched_by: str | None = None
    score: int = 0
    sender_domain: str | None = None
    review_flags: tuple[str, ...] = ()


def clean_vendor_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = unicodedata.normalize("NFKC", str(value))
    cleaned = cleaned.replace("（", "(").replace("）", ")")
    cleaned = cleaned.replace("(株)", "株式会社").replace("㈱", "株式会社")
    cleaned = cleaned.replace("(有)", "有限会社").replace("㈲", "有限会社")
    cleaned = re.sub(r"[\s\u3000]+", "", cleaned)
    cleaned = cleaned.replace("シヤ", "シャ").replace("シユ", "シュ").replace("シヨ", "ショ")
    cleaned = cleaned.replace("チヤ", "チャ").replace("チユ", "チュ").replace("チヨ", "チョ")
    cleaned = cleaned.replace("ヤッ", "ャッ")
    return cleaned.strip("._-:/\\")


def normalize_vendor_key(value: str | None, *, strip_company_tokens: bool = True) -> str:
    cleaned = clean_vendor_text(value)
    if not cleaned:
        return ""
    normalized = cleaned.translate(COMPARE_CHAR_MAP)
    if strip_company_tokens:
        normalized = COMPANY_TOKEN_RE.sub("", normalized)
    normalized = COMPARE_NOISE_RE.sub("", normalized)
    normalized = normalized.replace("ー", "")
    return normalized.lower()


def normalize_context_key(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    if not normalized:
        return ""
    normalized = normalized.translate(COMPARE_CHAR_MAP)
    normalized = re.sub(r"[\s\u3000]+", "", normalized)
    normalized = COMPARE_NOISE_RE.sub("", normalized)
    return normalized.lower()


def _context_contains_key(context_key: str, candidate_keys: tuple[str, ...], *, min_length: int = 4) -> bool:
    if not context_key:
        return False
    return any(key and len(key) >= min_length and key in context_key for key in candidate_keys)


@lru_cache(maxsize=1)
def _legacy_alias_to_canonical() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for canonical, aliases in LEGACY_VENDOR_HINTS.items():
        candidates = {canonical, *aliases}
        for candidate in candidates:
            for strip_company_tokens in (False, True):
                key = normalize_vendor_key(candidate, strip_company_tokens=strip_company_tokens)
                if key:
                    mapping[key] = canonical
    return mapping


def resolve_preferred_canonical(value: str | None) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    for strip_company_tokens in (False, True):
        key = normalize_vendor_key(cleaned, strip_company_tokens=strip_company_tokens)
        if not key:
            continue
        preferred = _legacy_alias_to_canonical().get(key)
        if preferred:
            return preferred
    return cleaned


def extract_sender_domain(value: str | None) -> str | None:
    if not value:
        return None
    match = EMAIL_RE.search(str(value))
    if not match:
        return None
    return match.group(2).lower()


def clean_vendor_candidate(value: str | None) -> str | None:
    cleaned = clean_vendor_text(value)
    if not cleaned:
        return None
    cleaned = LEADING_LABEL_RE.sub("", cleaned)
    cleaned = LEADING_DECORATION_RE.sub("", cleaned)
    cleaned = HONORIFIC_SUFFIX_RE.sub("", cleaned)
    cleaned = TRAILING_DOC_RE.sub("", cleaned)
    cleaned = cleaned.strip("._-:/\\")
    return cleaned or None


def is_non_vendor_candidate(value: str | None) -> tuple[bool, tuple[str, ...]]:
    cleaned = clean_vendor_text(value)
    if not cleaned:
        return True, ("empty_candidate",)

    flags: list[str] = []
    if cleaned in _load_rules()["blocked_vendor_candidates"]:
        flags.append("blocked_vendor_candidate")
    if NUMBERISH_RE.fullmatch(cleaned) and len(re.sub(r"\W", "", cleaned)) >= 6:
        flags.append("numeric_or_doclike")
    if HONORIFIC_SUFFIX_RE.search(cleaned):
        flags.append("honorific_suffix")

    lowered = cleaned.lower()
    for pattern in _load_rules()["non_vendor_patterns"]:
        if pattern.lower() in lowered:
            flags.append(f"non_vendor_pattern:{pattern}")
            break

    compare_key = normalize_vendor_key(cleaned)
    if len(compare_key) < 2:
        flags.append("too_short")

    return bool(flags), tuple(flags)


def canonicalize_vendor(
    value: str | None,
    *,
    sender: str | None = None,
    context_text: str | None = None,
    drop_non_vendor: bool = False,
) -> str | None:
    match = match_vendor_candidate(value, sender=sender, context_text=context_text)
    if "blocked_vendor_candidate" in match.review_flags:
        return None
    if match.canonical:
        return match.canonical
    if drop_non_vendor and any(
        flag.startswith(("blocked_", "non_vendor_", "numeric_", "too_short"))
        for flag in match.review_flags
    ):
        return None
    return match.candidate


def classify_vendor_category(value: str | None) -> str | None:
    if not value:
        return None
    canonical = canonicalize_vendor(value)
    if canonical:
        match = match_vendor_candidate(canonical)
        if match.category:
            return match.category

    compare_key = normalize_vendor_key(value)
    if not compare_key:
        return None
    return _load_category_map().get(compare_key)


def match_vendor_candidate(
    value: str | None,
    *,
    sender: str | None = None,
    context_text: str | None = None,
) -> VendorMatch:
    sender_domain = extract_sender_domain(sender)
    candidate = clean_vendor_candidate(value)
    is_non_vendor, review_flags = is_non_vendor_candidate(value)
    if not candidate:
        return VendorMatch(
            original=value,
            candidate=None,
            sender_domain=sender_domain,
            review_flags=review_flags,
        )

    candidate_keys = {
        normalize_vendor_key(candidate, strip_company_tokens=False),
        normalize_vendor_key(candidate, strip_company_tokens=True),
    }
    candidate_keys.discard("")
    context_key = normalize_context_key(context_text)

    best_hint: VendorHint | None = None
    best_score = 0
    best_match_by: str | None = None

    for hint in _load_vendor_hints():
        local_score = 0
        local_match_by: str | None = None
        for alias_key in hint.match_keys:
            if not alias_key:
                continue
            if alias_key in candidate_keys:
                local_score = 100
                local_match_by = "exact"
                break
            if len(alias_key) >= 5 and any(
                alias_key in candidate_key or candidate_key in alias_key
                for candidate_key in candidate_keys
            ):
                local_score = max(local_score, 88)
                local_match_by = "substring"

        if local_score == 0:
            continue
        alias_context_match = _context_contains_key(context_key, hint.match_keys, min_length=5)
        project_context_match = _context_contains_key(context_key, hint.project_match_keys, min_length=4)
        match_by_parts = [local_match_by]
        if sender_domain and sender_domain in set(hint.sender_domains + hint.web_domains):
            local_score += 8
            match_by_parts.append("sender")
        if alias_context_match:
            local_score += 2
            match_by_parts.append("context")
        if project_context_match:
            local_score += 3
            match_by_parts.append("project")
        if is_non_vendor and local_match_by and local_match_by.startswith("substring"):
            local_score -= 6
        local_match_by = "+".join(part for part in match_by_parts if part)

        if local_score > best_score:
            best_hint = hint
            best_score = local_score
            best_match_by = local_match_by

    accepted = False
    if best_hint and best_match_by:
        if best_match_by.startswith("exact") and best_score >= 100:
            accepted = True
        elif "substring" in best_match_by and best_score >= 96:
            accepted = True

    canonical = best_hint.canonical if accepted and best_hint else None
    category = best_hint.category if best_hint and best_hint.category else _load_category_map().get(
        normalize_vendor_key(canonical or candidate)
    )
    if "blocked_vendor_candidate" in review_flags and canonical is None:
        category = None

    flags = list(review_flags)
    if best_hint is None:
        flags.append("no_hint_match")
    elif not accepted:
        flags.append("low_confidence_hint_match")

    return VendorMatch(
        original=value,
        candidate=candidate,
        canonical=canonical,
        category=category,
        matched_by=best_match_by,
        score=best_score,
        sender_domain=sender_domain,
        review_flags=tuple(_dedupe(flags)),
    )


def infer_vendor_from_sender_context(
    *,
    sender: str | None,
    subject: str | None = None,
    attachment_name: str | None = None,
    context_text: str | None = None,
) -> VendorMatch:
    sender_domain = extract_sender_domain(sender)
    if not sender_domain:
        return VendorMatch(
            original=sender,
            candidate=None,
            sender_domain=None,
            review_flags=("missing_sender_domain",),
        )

    combined_context = normalize_context_key(
        " ".join(v for v in (subject, attachment_name, context_text) if v)
    )
    candidates: list[tuple[int, VendorHint, str]] = []
    for hint in _load_vendor_hints():
        domains = set(hint.sender_domains + hint.web_domains)
        if sender_domain not in domains:
            continue
        score = 100
        matched_by_parts = ["sender_domain"]
        if _context_contains_key(combined_context, hint.match_keys, min_length=5):
            score += 5
            matched_by_parts.append("context")
        if _context_contains_key(combined_context, hint.project_match_keys, min_length=4):
            score += 5
            matched_by_parts.append("project")
        matched_by = "+".join(matched_by_parts)
        candidates.append((score, hint, matched_by))

    if not candidates:
        return VendorMatch(
            original=sender,
            candidate=None,
            sender_domain=sender_domain,
            review_flags=("no_sender_domain_match",),
        )

    candidates.sort(key=lambda item: (-item[0], item[1].canonical))
    best_score, best_hint, matched_by = candidates[0]
    second_score = candidates[1][0] if len(candidates) > 1 else None
    accepted = len(candidates) == 1 or (
        second_score is not None and best_score >= 105 and best_score > second_score
    )
    flags: list[str] = []
    if len(candidates) > 1 and not accepted:
        flags.append("ambiguous_sender_domain_match")

    return VendorMatch(
        original=sender,
        candidate=None,
        canonical=best_hint.canonical if accepted else None,
        category=best_hint.category,
        matched_by=matched_by if accepted else None,
        score=best_score,
        sender_domain=sender_domain,
        review_flags=tuple(flags),
    )


def vendor_match_equal(predicted: str | None, expected: str | None) -> tuple[bool, str]:
    if not predicted:
        return False, "missing"
    if not expected:
        return False, "missing_expected"
    if predicted == expected:
        return True, "exact"

    pred_key = normalize_vendor_key(predicted)
    exp_key = normalize_vendor_key(expected)
    if pred_key == exp_key:
        return True, "normalized"

    pred_match = match_vendor_candidate(predicted)
    exp_match = match_vendor_candidate(expected)
    pred_canonical = pred_match.canonical or pred_match.candidate
    exp_canonical = exp_match.canonical or exp_match.candidate
    if normalize_vendor_key(pred_canonical) == normalize_vendor_key(exp_canonical):
        return True, "canonical"
    if exp_key and pred_key and (exp_key in pred_key or pred_key in exp_key):
        return True, "substring"
    return False, "mismatch"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _basic_aliases(canonical: str) -> set[str]:
    aliases = {clean_vendor_text(canonical)}
    keyless = normalize_vendor_key(canonical)
    if keyless and len(keyless) >= 2:
        aliases.add(keyless)
    cleaned = clean_vendor_text(canonical)
    if cleaned.startswith("株式会社"):
        aliases.add(cleaned.removeprefix("株式会社"))
    if cleaned.endswith("株式会社"):
        aliases.add(cleaned.removesuffix("株式会社"))
    if cleaned.startswith("有限会社"):
        aliases.add(cleaned.removeprefix("有限会社"))
    if cleaned.endswith("有限会社"):
        aliases.add(cleaned.removesuffix("有限会社"))
    return {alias for alias in aliases if alias}


def _merge_entry(entries: dict[str, dict[str, Any]], payload: dict[str, Any]) -> None:
    canonical = resolve_preferred_canonical(payload.get("canonical"))
    if not canonical:
        return
    entry = entries.setdefault(
        canonical,
        {
            "canonical": canonical,
            "aliases": set(),
            "sender_domains": set(),
            "web_domains": set(),
            "address_keywords": set(),
            "registration_numbers": set(),
            "project_keywords": set(),
            "deny_patterns": set(),
            "sources": set(),
            "category": None,
        },
    )
    for alias in payload.get("aliases") or ():
        cleaned_alias = clean_vendor_text(alias)
        if cleaned_alias:
            entry["aliases"].add(cleaned_alias)
    for field_name in ("sender_domains", "web_domains", "address_keywords", "registration_numbers", "project_keywords", "deny_patterns", "sources"):
        for value in payload.get(field_name) or ():
            if value:
                entry[field_name].add(str(value).strip())
    category = str(payload.get("category") or "").strip().lower()
    if category:
        entry["category"] = _collapse_category(entry["category"], category)


def _collapse_category(current: str | None, incoming: str | None) -> str | None:
    priorities = {"variable": 3, "gray": 2, "fixed": 1}
    current_val = priorities.get((current or "").lower(), 0)
    incoming_val = priorities.get((incoming or "").lower(), 0)
    if incoming_val >= current_val:
        return incoming if incoming_val else current
    return current


@lru_cache(maxsize=1)
def _load_rules() -> dict[str, tuple[str, ...]]:
    blocked = set(DEFAULT_BLOCKED_VENDOR_CANDIDATES)
    patterns = set(DEFAULT_NON_VENDOR_PATTERNS)
    if VENDOR_HINTS_PATH.exists():
        try:
            data = json.loads(VENDOR_HINTS_PATH.read_text(encoding="utf-8"))
            rules = data.get("rules") or {}
            blocked.update(clean_vendor_text(v) for v in rules.get("blocked_vendor_candidates") or ())
            patterns.update(str(v).strip() for v in rules.get("non_vendor_patterns") or ())
        except Exception:
            pass
    return {
        "blocked_vendor_candidates": tuple(sorted(v for v in blocked if v)),
        "non_vendor_patterns": tuple(sorted(v for v in patterns if v)),
    }


@lru_cache(maxsize=1)
def _load_vendor_hints() -> tuple[VendorHint, ...]:
    entries: dict[str, dict[str, Any]] = {}

    for canonical, aliases in LEGACY_VENDOR_HINTS.items():
        _merge_entry(
            entries,
            {
                "canonical": canonical,
                "aliases": aliases,
                "sources": ("legacy_priority",),
            },
        )

    if VENDOR_HINTS_PATH.exists():
        data = json.loads(VENDOR_HINTS_PATH.read_text(encoding="utf-8"))
        for item in data.get("vendors") or ():
            is_noise, _ = is_non_vendor_candidate(item.get("canonical"))
            if is_noise and str(item.get("canonical") or "").strip() not in LEGACY_VENDOR_HINTS:
                continue
            _merge_entry(entries, item)

    if GOLDEN_DATASET_PATH.exists():
        rows = json.loads(GOLDEN_DATASET_PATH.read_text(encoding="utf-8"))
        for row in rows:
            category = str(row.get("category") or "").strip().lower()
            if category == "regression":
                continue
            is_noise, _ = is_non_vendor_candidate(row.get("vendor"))
            if is_noise and str(row.get("vendor") or "").strip() not in LEGACY_VENDOR_HINTS:
                continue
            _merge_entry(
                entries,
                {
                    "canonical": row.get("vendor"),
                    "category": category,
                    "sources": ("golden_dataset_v4",),
                },
            )

    hints: list[VendorHint] = []
    for canonical, entry in entries.items():
        flattened_aliases: set[str] = set(_basic_aliases(canonical))
        for alias in entry["aliases"]:
            flattened_aliases.update(_basic_aliases(alias))
        flattened_aliases.update(entry["aliases"])

        match_keys = {
            normalize_vendor_key(canonical, strip_company_tokens=False),
            normalize_vendor_key(canonical, strip_company_tokens=True),
        }
        for alias in flattened_aliases:
            match_keys.add(normalize_vendor_key(alias, strip_company_tokens=False))
            match_keys.add(normalize_vendor_key(alias, strip_company_tokens=True))
        match_keys.discard("")
        project_match_keys = set()
        for keyword in entry["project_keywords"]:
            normalized_keyword = normalize_context_key(keyword)
            if normalized_keyword:
                project_match_keys.add(normalized_keyword)

        hints.append(
            VendorHint(
                canonical=canonical,
                aliases=tuple(sorted(v for v in flattened_aliases if v and v != canonical)),
                sender_domains=tuple(sorted(entry["sender_domains"])),
                web_domains=tuple(sorted(entry["web_domains"])),
                address_keywords=tuple(sorted(entry["address_keywords"])),
                registration_numbers=tuple(sorted(entry["registration_numbers"])),
                project_keywords=tuple(sorted(entry["project_keywords"])),
                deny_patterns=tuple(sorted(entry["deny_patterns"])),
                category=entry["category"],
                sources=tuple(sorted(entry["sources"])),
                match_keys=tuple(sorted(match_keys)),
                project_match_keys=tuple(sorted(project_match_keys)),
            )
        )

    hints.sort(key=lambda hint: (hint.category or "zzz", hint.canonical))
    return tuple(hints)


@lru_cache(maxsize=1)
def _load_category_map() -> dict[str, str]:
    category_map: dict[str, str] = {}
    for hint in _load_vendor_hints():
        if not hint.category:
            continue
        for key in hint.match_keys:
            current = category_map.get(key)
            category_map[key] = _collapse_category(current, hint.category) or hint.category
    return category_map
