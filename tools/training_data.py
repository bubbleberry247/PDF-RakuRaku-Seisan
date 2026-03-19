"""Teacher PDF / PST context helpers for scenario 12/13."""

from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path
from typing import Any

from vendor_matching import extract_sender_domain, resolve_preferred_canonical

ROOT_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
DEFAULT_TEACHER_PDF_DIR = ROOT_DIR / "samples" / "PDF教師データ"
DEFAULT_BACKUP_PST = Path(os.environ.get("USERPROFILE", "")) / "Downloads" / "backup.pst"
DEFAULT_PST_CONTEXT_CACHE = ARTIFACTS_DIR / "cache" / "backup_pst_attachment_context.json"

ATTACH_FILENAME_ENTRY = 0x3704
ATTACH_LONG_FILENAME_ENTRY = 0x3707
EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
LEADING_NOTE_RE = re.compile(r"^(?:\[[^\]]+\]|【[^】]+】|\([^)]*\)|（[^）]*）)\s*")
VENDOR_TRAILING_DOC_RE = re.compile(
    r"(請求書明細|請求書鑑|指定請求書|CP請求書|ＣＰ請求書|請求書|御請求書|インボイス)$"
)
PROJECT_STOPWORDS = {
    "請求書",
    "御請求書",
    "請求書明細",
    "請求書鑑",
    "指定請求書",
    "cp請求書",
    "c p請求書",
}
PROJECT_SPLIT_RE = re.compile(r"[\s_./\\\-:：;；,，'\"()（）\[\]【】<>＜＞]+")


@dataclass(frozen=True)
class TeacherPdfRecord:
    filename: str
    path: str
    source_month: str
    vendor: str | None = None
    canonical_vendor: str | None = None
    issue_date: str | None = None
    amount: str | None = None
    project: str | None = None
    senders: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    sender_domains: tuple[str, ...] = ()


def _normalize_text(value: str | None) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def normalize_attachment_name(value: str | None) -> str:
    return _normalize_text(value).casefold()


def _normalize_context_key(value: str | None) -> str:
    normalized = _normalize_text(value)
    normalized = re.sub(r"[\s_./\\\-:：;；,，'\"()（）\[\]【】<>＜＞]+", "", normalized)
    return normalized.casefold()


def _normalize_yyyymmdd_candidate(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", _normalize_text(value))

    def _validate(year: int, month: int, day: int) -> bool:
        if not (2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
            return False
        try:
            datetime(year, month, day)
            return True
        except ValueError:
            return False

    if len(digits) == 8:
        year, month, day = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
        if _validate(year, month, day):
            return f"{year:04d}{month:02d}{day:02d}"
        return None
    if len(digits) == 7:
        year, month, day = int(digits[0:4]), int(digits[4:5]), int(digits[5:7])
        if _validate(year, month, day):
            return f"{year:04d}{month:02d}{day:02d}"
        return None
    if len(digits) == 6:
        year, month, day = 2000 + int(digits[0:2]), int(digits[2:4]), int(digits[4:6])
        if _validate(year, month, day):
            return f"{year:04d}{month:02d}{day:02d}"
    return None


def _parse_amount_token(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    digits = re.sub(r"\D", "", normalized)
    if not digits:
        return None
    if _normalize_yyyymmdd_candidate(digits):
        return None
    amount = int(digits)
    if amount <= 0 or amount >= 1_000_000_000:
        return None
    return digits


def _cleanup_vendor_hint(value: str | None) -> str | None:
    vendor = _normalize_text(value)
    if not vendor:
        return None
    vendor = vendor.replace("＿", "_").replace("－", "_")
    while True:
        next_vendor = LEADING_NOTE_RE.sub("", vendor).strip()
        if next_vendor == vendor:
            break
        vendor = next_vendor
    vendor = vendor.strip("_- ")
    vendor = re.sub(r"^[✖×※★☆■□△▲▼▽◎○●◇◆]+", "", vendor).strip()
    vendor = re.sub(r"^[\d０-９]+", "", vendor).strip()
    vendor = re.sub(r"^(?:再送?|請求書|御請求書)\s*", "", vendor).strip()
    vendor = VENDOR_TRAILING_DOC_RE.sub("", vendor).strip(" _-")
    return vendor or None


def _cleanup_project_hint(value: str | None) -> str | None:
    project = _normalize_text(value)
    if not project:
        return None
    project = project.strip("_- ")
    project = VENDOR_TRAILING_DOC_RE.sub("", project).strip(" _-")
    if _normalize_context_key(project) in PROJECT_STOPWORDS:
        return None
    return project or None


def parse_teacher_pdf_filename(filename: str) -> dict[str, str]:
    stem = _normalize_text(filename).removesuffix(".pdf").strip()
    stem = stem.replace("＿", "_")
    for sep in ("－", "–", "—"):
        stem = stem.replace(sep, "_")
    stem = re.sub(r"_+", "_", stem)
    parts = [part.strip() for part in stem.split("_") if part.strip()]

    date_idx: int | None = None
    issue_date: str | None = None
    for idx, part in enumerate(parts):
        parsed = _normalize_yyyymmdd_candidate(part)
        if parsed:
            date_idx = idx
            issue_date = parsed
            break

    amount_idx: int | None = None
    amount: str | None = None
    if date_idx is not None:
        for idx in range(date_idx + 1, len(parts)):
            parsed = _parse_amount_token(parts[idx])
            if parsed:
                amount_idx = idx
                amount = parsed
                break

    if amount is None:
        for idx, part in enumerate(parts):
            parsed = _parse_amount_token(part)
            if parsed:
                amount_idx = idx
                amount = parsed
                break

    vendor: str | None = None
    if date_idx is not None and date_idx > 0:
        vendor = _cleanup_vendor_hint("_".join(parts[:date_idx]))
    elif amount_idx is not None and amount_idx > 0:
        vendor = _cleanup_vendor_hint("_".join(parts[:amount_idx]))
    elif parts:
        vendor = _cleanup_vendor_hint(parts[0])

    project: str | None = None
    if amount_idx is not None and amount_idx + 1 < len(parts):
        project = _cleanup_project_hint("_".join(parts[amount_idx + 1 :]))
    elif date_idx is not None and date_idx + 1 < len(parts):
        project = _cleanup_project_hint("_".join(parts[date_idx + 1 :]))

    payload: dict[str, str] = {}
    if vendor:
        payload["vendor"] = vendor
    if issue_date:
        payload["issue_date"] = issue_date
    if amount:
        payload["amount"] = amount
    if project:
        payload["project"] = project
    return payload


def _pst_signature(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _load_cached_pst_context(cache_path: Path, signature: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    if not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if payload.get("signature") != signature:
        return {}
    raw_index = payload.get("index") or {}
    index: dict[str, list[dict[str, str]]] = {}
    for key, rows in raw_index.items():
        if not key or not isinstance(rows, list):
            continue
        cleaned_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            cleaned_rows.append(
                {
                    "attachment_name": str(row.get("attachment_name") or "").strip(),
                    "sender": str(row.get("sender") or "").strip(),
                    "subject": str(row.get("subject") or "").strip(),
                    "delivery_time": str(row.get("delivery_time") or "").strip(),
                }
            )
        if cleaned_rows:
            index[key] = cleaned_rows
    return index


def _write_cached_pst_context(
    cache_path: Path,
    signature: dict[str, Any],
    index: dict[str, list[dict[str, str]]],
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "signature": signature,
        "index": index,
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _decode_record_entry_data(data: Any) -> str | None:
    if data is None:
        return None
    if isinstance(data, str):
        return data.strip("\x00").strip()
    if not isinstance(data, (bytes, bytearray)):
        return str(data).strip()
    raw = bytes(data)
    for encoding in ("utf-8", "utf-16-le", "cp932"):
        try:
            return raw.decode(encoding).strip("\x00").strip()
        except Exception:
            continue
    return None


def _extract_attachment_name(attachment: Any) -> str | None:
    long_name: str | None = None
    short_name: str | None = None
    try:
        record_set_count = attachment.number_of_record_sets
    except Exception:
        return None
    for record_set_idx in range(record_set_count):
        try:
            record_set = attachment.get_record_set(record_set_idx)
            entry_count = record_set.number_of_entries
        except Exception:
            continue
        for entry_idx in range(entry_count):
            try:
                entry = record_set.get_entry(entry_idx)
                entry_type = getattr(entry, "entry_type", None)
                if entry_type not in (ATTACH_FILENAME_ENTRY, ATTACH_LONG_FILENAME_ENTRY):
                    continue
                value = _decode_record_entry_data(getattr(entry, "data", None))
            except Exception:
                continue
            if not value:
                continue
            if entry_type == ATTACH_LONG_FILENAME_ENTRY:
                long_name = value
            elif entry_type == ATTACH_FILENAME_ENTRY:
                short_name = value
    return long_name or short_name


def _sender_from_message(message: Any) -> str | None:
    headers = ""
    try:
        headers = getattr(message, "transport_headers", "") or ""
    except Exception:
        headers = ""
    if headers:
        match = EMAIL_RE.search(headers)
        if match:
            return match.group(1)
        _, email_addr = parseaddr(headers)
        if email_addr:
            return email_addr
    try:
        sender = getattr(message, "sender_name", None)
    except Exception:
        sender = None
    if sender:
        match = EMAIL_RE.search(str(sender))
        if match:
            return match.group(1)
        return str(sender).strip()
    return None


def build_pst_attachment_context_index(
    pst_path: Path = DEFAULT_BACKUP_PST,
    *,
    cache_path: Path = DEFAULT_PST_CONTEXT_CACHE,
    use_cache: bool = True,
) -> dict[str, list[dict[str, str]]]:
    pst_path = Path(pst_path)
    if not pst_path.exists():
        return {}

    signature = _pst_signature(pst_path)
    if use_cache:
        cached = _load_cached_pst_context(cache_path, signature)
        if cached:
            return cached

    try:
        import pypff  # type: ignore
    except ImportError:
        return {}

    pst = pypff.file()
    pst.open(str(pst_path))
    root = pst.get_root_folder()

    index: dict[str, list[dict[str, str]]] = {}
    seen: set[tuple[str, str, str, str]] = set()

    def walk(folder: Any) -> None:
        try:
            message_count = folder.number_of_sub_messages
        except Exception:
            message_count = 0
        for message_idx in range(message_count):
            try:
                message = folder.get_sub_message(message_idx)
            except Exception:
                continue
            sender = _sender_from_message(message) or ""
            subject = str(getattr(message, "subject", "") or "").strip()
            delivery_time = str(getattr(message, "delivery_time", "") or "").strip()
            try:
                attachment_count = message.number_of_attachments
            except Exception:
                continue
            for attachment_idx in range(attachment_count):
                try:
                    attachment = message.get_attachment(attachment_idx)
                    attachment_name = _extract_attachment_name(attachment)
                except Exception:
                    continue
                if not attachment_name:
                    continue
                normalized_name = normalize_attachment_name(attachment_name)
                if not normalized_name:
                    continue
                row = {
                    "attachment_name": _normalize_text(attachment_name),
                    "sender": sender,
                    "subject": subject,
                    "delivery_time": delivery_time,
                }
                dedupe_key = (
                    normalized_name,
                    row["sender"],
                    row["subject"],
                    row["delivery_time"],
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                index.setdefault(normalized_name, []).append(row)
        try:
            subfolder_count = folder.number_of_sub_folders
        except Exception:
            subfolder_count = 0
        for subfolder_idx in range(subfolder_count):
            try:
                walk(folder.get_sub_folder(subfolder_idx))
            except Exception:
                continue

    try:
        walk(root)
    finally:
        pst.close()

    if use_cache:
        _write_cached_pst_context(cache_path, signature, index)
    return index


def _select_primary_context(rows: list[dict[str, str]]) -> dict[str, str]:
    if not rows:
        return {}
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            row.get("sender", ""),
            row.get("subject", ""),
            row.get("delivery_time", ""),
        ),
    )
    score_map: dict[tuple[str, str], tuple[int, str]] = {}
    for row in sorted_rows:
        key = (row.get("sender", ""), row.get("subject", ""))
        current_count, current_delivery = score_map.get(key, (0, ""))
        delivery_time = row.get("delivery_time", "")
        score_map[key] = (current_count + 1, max(current_delivery, delivery_time))
    best_sender, best_subject = max(score_map, key=lambda key: (score_map[key][0], score_map[key][1], key[0], key[1]))
    return {
        "sender": best_sender,
        "subject": best_subject,
    }


def build_pst_attachment_context_map(
    pst_path: Path = DEFAULT_BACKUP_PST,
    *,
    cache_path: Path = DEFAULT_PST_CONTEXT_CACHE,
    use_cache: bool = True,
) -> dict[str, dict[str, str]]:
    index = build_pst_attachment_context_index(
        pst_path=pst_path,
        cache_path=cache_path,
        use_cache=use_cache,
    )
    return {key: _select_primary_context(rows) for key, rows in index.items() if rows}


def build_artifact_attachment_context_map(artifact_dir: Path = ARTIFACTS_DIR) -> dict[str, dict[str, str]]:
    context_map: dict[str, dict[str, str]] = {}
    artifact_dir = Path(artifact_dir)
    if not artifact_dir.exists():
        return context_map

    for csv_path in sorted(artifact_dir.rglob("report.csv")):
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    attachment_name = str(row.get("attachment_name") or "").strip()
                    if not attachment_name:
                        continue
                    sender = str(row.get("sender") or "").strip()
                    subject = str(row.get("message_subject") or "").strip()
                    key = normalize_attachment_name(attachment_name)
                    if key and (sender or subject):
                        context_map.setdefault(key, {"sender": sender, "subject": subject})
        except Exception:
            continue

    for json_path in sorted(artifact_dir.rglob("report.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in payload.get("saved_attachments") or ():
            attachment_name = str(row.get("attachment_name") or "").strip()
            if not attachment_name:
                continue
            sender = str(row.get("sender") or "").strip()
            subject = str(row.get("message_subject") or "").strip()
            key = normalize_attachment_name(attachment_name)
            if key and (sender or subject):
                context_map.setdefault(key, {"sender": sender, "subject": subject})

    return context_map


def build_combined_attachment_context_map(
    *,
    artifact_dir: Path = ARTIFACTS_DIR,
    pst_path: Path = DEFAULT_BACKUP_PST,
    use_pst_cache: bool = True,
) -> dict[str, dict[str, str]]:
    context_map = build_pst_attachment_context_map(
        pst_path=pst_path,
        use_cache=use_pst_cache,
    )
    context_map.update(build_artifact_attachment_context_map(artifact_dir=artifact_dir))
    return context_map


def build_teacher_pdf_records(
    pdf_root: Path = DEFAULT_TEACHER_PDF_DIR,
    *,
    pst_path: Path = DEFAULT_BACKUP_PST,
    use_pst_cache: bool = True,
) -> list[TeacherPdfRecord]:
    pdf_root = Path(pdf_root)
    if not pdf_root.exists():
        return []

    pst_index = build_pst_attachment_context_index(
        pst_path=pst_path,
        use_cache=use_pst_cache,
    )

    records: list[TeacherPdfRecord] = []
    for pdf_path in sorted(pdf_root.rglob("*.pdf")):
        filename = pdf_path.name
        fields = parse_teacher_pdf_filename(filename)
        contexts = pst_index.get(normalize_attachment_name(filename), [])
        senders = tuple(sorted({str(row.get("sender") or "").strip() for row in contexts if row.get("sender")}))
        subjects = tuple(sorted({str(row.get("subject") or "").strip() for row in contexts if row.get("subject")}))
        sender_domains = tuple(
            sorted(
                {
                    domain
                    for sender in senders
                    if (domain := extract_sender_domain(sender))
                }
            )
        )
        vendor = fields.get("vendor")
        canonical_vendor = resolve_preferred_canonical(vendor) if vendor else None
        records.append(
            TeacherPdfRecord(
                filename=filename,
                path=str(pdf_path),
                source_month=pdf_path.parent.name,
                vendor=vendor,
                canonical_vendor=canonical_vendor,
                issue_date=fields.get("issue_date"),
                amount=fields.get("amount"),
                project=fields.get("project"),
                senders=senders,
                subjects=subjects,
                sender_domains=sender_domains,
            )
        )
    return records


def project_keyword_candidates(project: str | None) -> tuple[str, ...]:
    cleaned = _cleanup_project_hint(project)
    if not cleaned:
        return ()
    candidates: list[str] = []
    full_normalized = _normalize_context_key(cleaned)
    if len(full_normalized) >= 4 and len(re.sub(r"\D", "", full_normalized)) <= 4:
        candidates.append(cleaned)

    for part in PROJECT_SPLIT_RE.split(cleaned):
        token = _cleanup_project_hint(part)
        if not token:
            continue
        token = re.sub(r"^[\d０-９]+", "", token).strip()
        token = re.sub(r"[\d０-９]+$", "", token).strip()
        if not token:
            continue
        normalized = _normalize_context_key(token)
        if len(normalized) < 4:
            continue
        if len(re.sub(r"\D", "", normalized)) > 2:
            continue
        if normalized in PROJECT_STOPWORDS:
            continue
        candidates.append(token)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_context_key(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(candidate)
    return tuple(deduped)


def teacher_pdf_records_as_json(records: list[TeacherPdfRecord]) -> str:
    return json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2)
