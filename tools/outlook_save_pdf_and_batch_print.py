# -*- coding: utf-8 -*-
"""
Scenario 12/13: 受信メールのPDFを保存・一括印刷（Outlook COM）

目的:
- Outlook受信メールからPDF添付（請求書）を漏れなく保存する
- 必要ならPDFを結合し、一括印刷する
- 例外（暗号化PDFのパスワード不明、URLのみで未対応など）は処理を止めて通知する（TPS: 自働化/アンドン）

安全:
- 既定はドライラン（--execute を付けない限り保存/印刷しない）
- 上書き禁止（ファイル名衝突は自動で退避名にする）

Usage examples:
    python outlook_save_pdf_and_batch_print.py --config C:\\...\\tool_config.json --dry-run --dry-run-mail
    python outlook_save_pdf_and_batch_print.py --config C:\\...\\tool_config.json --execute
    python outlook_save_pdf_and_batch_print.py --config C:\\...\\tool_config.json --execute --print
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence, TypeVar
from unicodedata import normalize

sys.path.insert(0, str(Path(__file__).parent))

from common.email_notifier import (
    OutlookEmail,
    build_simple_html,
    html_link_to_path,
    send_outlook,
)

try:
    import win32com.client as win32  # type: ignore

    _OUTLOOK_AVAILABLE = True
except Exception:
    _OUTLOOK_AVAILABLE = False

try:
    import pythoncom  # type: ignore
    import pywintypes  # type: ignore

    _PYWIN32_COM_AVAILABLE = True
except Exception:
    _PYWIN32_COM_AVAILABLE = False


T = TypeVar("T")


_COM_MESSAGE_FILTER_INSTALLED = False


class _RetryMessageFilter:
    """
    COM message filter to automatically retry when Outlook is busy.

    This prevents sporadic failures like:
      (-2147418111, '呼び出し先が呼び出しを拒否しました。', None, None)
    """

    def HandleInComingCall(  # noqa: N802 - required COM interface name
        self, htaskCaller: Any, dwTickCount: int, dwCallType: int
    ) -> int:
        return pythoncom.SERVERCALL_ISHANDLED  # type: ignore[name-defined]

    def RetryRejectedCall(  # noqa: N802 - required COM interface name
        self, htaskCaller: Any, dwTickCount: int, dwRejectType: int
    ) -> int:
        # Retry later: return a delay in milliseconds.
        if dwRejectType == pythoncom.SERVERCALL_RETRYLATER:  # type: ignore[name-defined]
            return 250
        return -1

    def MessagePending(  # noqa: N802 - required COM interface name
        self, htaskCaller: Any, dwTickCount: int, dwPendingType: int
    ) -> int:
        return pythoncom.PENDINGMSG_WAITDEFPROCESS  # type: ignore[name-defined]


def _install_com_message_filter() -> None:
    global _COM_MESSAGE_FILTER_INSTALLED
    if _COM_MESSAGE_FILTER_INSTALLED:
        return
    if not _PYWIN32_COM_AVAILABLE:
        return
    try:
        # Make sure COM is initialized for this thread.
        pythoncom.CoInitialize()  # type: ignore[name-defined]
    except Exception:
        pass
    try:
        pythoncom.CoRegisterMessageFilter(_RetryMessageFilter())  # type: ignore[name-defined]
        _COM_MESSAGE_FILTER_INSTALLED = True
    except Exception:
        # Best-effort: tool can still work, but may hit RPC_E_CALL_REJECTED occasionally.
        pass


def _is_call_rejected_error(err: BaseException) -> bool:
    if not _PYWIN32_COM_AVAILABLE:
        return False
    if not isinstance(err, pywintypes.com_error):  # type: ignore[name-defined]
        return False
    if not err.args:
        return False
    hresult = err.args[0]
    # RPC_E_CALL_REJECTED / RPC_E_SERVERCALL_RETRYLATER
    return hresult in (-2147418111, -2147417846)


def _com_retry(fn: Callable[[], T], *, retries: int = 30) -> T:
    """
    Retry a COM call when Outlook is busy.

    The message filter handles many cases, but some calls still surface
    RPC_E_CALL_REJECTED. This keeps the automation stable.
    """

    delay = 0.2
    for _ in range(retries):
        try:
            return fn()
        except Exception as e:
            if _is_call_rejected_error(e):
                time.sleep(delay)
                delay = min(2.0, delay * 1.5)
                continue
            raise
    return fn()

try:
    from pypdf import PdfReader, PdfWriter  # type: ignore

    _PYPDF_AVAILABLE = True
except Exception:
    _PYPDF_AVAILABLE = False

try:
    import win32api  # type: ignore
    import win32print  # type: ignore

    _WIN32_PRINT_AVAILABLE = True
except Exception:
    _WIN32_PRINT_AVAILABLE = False

try:
    import fitz  # type: ignore  # PyMuPDF

    _PYMUPDF_AVAILABLE = True
except Exception:
    _PYMUPDF_AVAILABLE = False

# easyocr is optional and loaded lazily (heavy).
_EASYOCR_AVAILABLE = importlib.util.find_spec("easyocr") is not None

# Do not import yomitoku at module import time (it can be heavy / slow).
_YOMITOKU_AVAILABLE = importlib.util.find_spec("yomitoku") is not None

try:
    import pyzipper  # type: ignore

    _PYZIPPER_AVAILABLE = True
except Exception:
    _PYZIPPER_AVAILABLE = False


def _find_tesseract_exe() -> Path | None:
    env = os.environ.get("TESSERACT_EXE")
    if env:
        p = Path(env)
        if p.exists():
            return p

    candidates = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]
    for c in candidates:
        if c.exists():
            return c

    which = shutil.which("tesseract")
    return Path(which) if which else None


_TESSERACT_EXE = _find_tesseract_exe()
_TESSERACT_AVAILABLE = _TESSERACT_EXE is not None


DEFAULT_ARTIFACT_DIR = (
    r"C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\artifacts"
)

URL_RE = re.compile(r"https?://[^\s<>\"]+")
PASSWORD_RE = re.compile(r"(?:パスワード|Password)\s*[:：]?\s*([^\s]+)", re.IGNORECASE)

INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\\\|?*]+')
VENDOR_HINT_RE = re.compile(
    r"(株式会社|有限会社|合同会社|一般社団法人|一般財団法人|税理士法人|社会保険労務士法人|（株）|\(株\)|（有）|\(有\))"
)
DATE_YMD_RE = re.compile(
    r"(?P<y>20\d{2})[./\\年-](?P<m>\d{1,2})[./\\月-](?P<d>\d{1,2})"
)
DATE_LABEL_RE = re.compile(
    r"(請求(?:年月)?日|発行(?:年月)?日|作成(?:年月)?日|日付)\s*[:：]?\s*([0-9]{4}[^0-9]{0,2}[0-9]{1,2}[^0-9]{0,2}[0-9]{1,2})"
)
AMOUNT_LABEL_RE = re.compile(
    r"(支払決定金額|支払決定額|お支払い金額|支払金額|ご?請求金額|ご?請求額|請求金額|請求額|総合計|合計金額|合計)"
    r"(?:\s*[（(][^)）]*[)）])?"
    r"\s*[:：]?\s*[¥￥]?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)"
)
INVOICE_NO_RE = re.compile(
    r"(請求書番号|請求書No\.?|請求No\.?|Invoice\s*No\.?|INV\.?)[^0-9A-Za-z]*([0-9A-Za-z\-_/]{3,})"
)

ZIP_MAX_MEMBERS = 80
ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES = 80 * 1024 * 1024
ZIP_PASSWORD_MAX_CANDIDATES = 20


@dataclass(frozen=True)
class OutlookSelection:
    folder_path: str
    # Optional Outlook profile name (e.g. "RKM"). Useful when the default profile is not the target mailbox.
    profile_name: str | None = None
    unread_only: bool = True
    max_messages: int = 200
    received_within_days: int | None = 14
    subject_allow_regex: str | None = None
    subject_deny_regex: str | None = None
    mark_as_read_on_success: bool = False


@dataclass(frozen=True)
class MergeConfig:
    enabled: bool = True
    output_name: str = "merged.pdf"


@dataclass(frozen=True)
class PrintConfig:
    enabled: bool = False
    printer_name: str | None = None
    method: str = "shell"  # shell | (future) acrobat


@dataclass(frozen=True)
class MailConfig:
    send_success: bool = True
    success_to: Sequence[str] = tuple()
    error_to: Sequence[str] = tuple()
    error_cc: Sequence[str] = tuple()


@dataclass(frozen=True)
class RenameConfig:
    enabled: bool = True
    # If true, create a sub-directory per vendor under save_dir.
    create_vendor_subdir: bool = True
    vendor_subdir_template: str = "{vendor_short}"
    file_name_template: str = "{vendor_short}__{issue_date}__{amount}.pdf"
    # Regex to exclude recipient company names from vendor extraction (optional).
    company_deny_regex: str | None = None
    max_pages: int = 2


@dataclass(frozen=True)
class ToolConfig:
    artifact_dir: str = DEFAULT_ARTIFACT_DIR
    save_dir: str | None = None
    outlook: OutlookSelection | None = None
    merge: MergeConfig = MergeConfig()
    print: PrintConfig = PrintConfig()
    mail: MailConfig = MailConfig()
    rename: RenameConfig = RenameConfig()
    fail_on_url_only_mail: bool = True
    decrypt_password_window_minutes: int = 20


@dataclass(frozen=True)
class PasswordNote:
    received_time: datetime
    subject: str
    password: str


@dataclass(frozen=True)
class SavedAttachment:
    message_entry_id: str
    message_subject: str
    sender: str
    received_time: str
    attachment_name: str
    # Final saved path (after rename/move). Prefer decrypted output when applicable.
    saved_path: str
    original_saved_path: str
    vendor: str | None
    issue_date: str | None
    amount: int | None
    invoice_no: str | None
    sha256: str
    was_encrypted: bool
    decrypted_path: str | None
    encrypted_original_path: str | None


@dataclass(frozen=True)
class ExtractedPdfFields:
    vendor: str
    issue_date: str  # YYYYMMDD
    amount: int
    invoice_no: str | None


@dataclass(frozen=True)
class UrlOnlyTask:
    message_entry_id: str
    subject: str
    sender: str
    received_time: str
    urls: Sequence[str]


@dataclass(frozen=True)
class RunReport:
    run_id: str
    started_at: str
    finished_at: str
    dry_run: bool
    save_dir: str | None
    outlook_folder_path: str | None
    scanned_messages: int
    saved_attachments: Sequence[SavedAttachment]
    url_only_tasks: Sequence[UrlOnlyTask]
    merged_pdf_path: str | None
    printed_paths: Sequence[str]
    unresolved: Sequence[str]


def _now_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _recreate_dir(p: Path) -> None:
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
    p.mkdir(parents=True, exist_ok=True)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sanitize_filename(name: str, max_len: int = 180) -> str:
    name = name.strip().replace("\u0000", "")
    name = INVALID_FILENAME_CHARS_RE.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > max_len:
        root, ext = os.path.splitext(name)
        keep = max_len - len(ext)
        name = root[:keep] + ext
    if not name:
        return "unnamed"
    return name


def _slug_subject(subject: str, max_len: int = 60) -> str:
    s = subject.strip()
    s = re.sub(r"\s+", " ", s)
    s = INVALID_FILENAME_CHARS_RE.sub("_", s)
    s = s.replace("【", "[").replace("】", "]")
    s = s.replace("／", "/")
    s = s.replace("/", "_")
    s = s.replace("\\", "_")
    s = s.strip(" ._")
    if len(s) > max_len:
        s = s[:max_len].rstrip(" ._")
    return s if s else "no_subject"


def _normalize_text(text: str) -> str:
    # Normalize full-width digits/punctuation -> ASCII where possible.
    text = normalize("NFKC", text)
    return text.replace("\u3000", " ")


def _is_ascii_path(path: Path) -> bool:
    try:
        str(path).encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _vendor_short(vendor: str) -> str:
    v = vendor.strip()
    # Common Japanese corporate markers (prefix/suffix style).
    for token in [
        "株式会社",
        "有限会社",
        "合同会社",
        "一般社団法人",
        "一般財団法人",
        "税理士法人",
        "社会保険労務士法人",
    ]:
        v = v.replace(token, "")
    for token in ["（株）", "(株)", "（有）", "(有)"]:
        v = v.replace(token, "")
    return v.strip() or vendor.strip()


def _parse_ymd(value: str) -> str | None:
    s = _normalize_text(value)
    m = DATE_YMD_RE.search(s)
    if not m:
        return None
    y = int(m.group("y"))
    mo = int(m.group("m"))
    d = int(m.group("d"))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04}{mo:02}{d:02}"


def _extract_pdf_text_pypdf(path: Path, max_pages: int) -> str:
    if not _PYPDF_AVAILABLE:
        raise RuntimeError("pypdf が利用できません。PDF抽出/復号のために必要です。")
    reader = PdfReader(str(path))
    texts: list[str] = []
    for i, page in enumerate(reader.pages):
        if i >= max_pages:
            break
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t:
            texts.append(t)
    return _normalize_text("\n".join(texts))


def _extract_pdf_text_pymupdf(path: Path, max_pages: int) -> str:
    if not _PYMUPDF_AVAILABLE:
        raise RuntimeError("PyMuPDF (fitz) が利用できません。")
    tmp_dir: tempfile.TemporaryDirectory[str] | None = None
    open_path = path
    # Some native libraries have trouble with non-ASCII paths on Windows; use a temp ASCII path if needed.
    if not _is_ascii_path(path):
        tmp_dir = tempfile.TemporaryDirectory(prefix="s12_13_pymupdf_")
        open_path = Path(tmp_dir.name) / "input.pdf"
        shutil.copy2(path, open_path)

    doc = fitz.open(str(open_path))
    try:
        texts: list[str] = []
        for i in range(min(max_pages, int(doc.page_count))):
            try:
                page = doc.load_page(i)
                t = page.get_text("text") or ""
            except Exception:
                t = ""
            if t:
                texts.append(t)
        return _normalize_text("\n".join(texts))
    finally:
        try:
            doc.close()
        finally:
            if tmp_dir is not None:
                try:
                    tmp_dir.cleanup()
                except Exception:
                    pass


def _render_pdf_first_page_png(pdf_path: Path, out_path: Path, dpi: int = 200) -> None:
    if not _PYMUPDF_AVAILABLE:
        raise RuntimeError("PyMuPDF (fitz) が利用できません。")
    tmp_dir: tempfile.TemporaryDirectory[str] | None = None
    open_path = pdf_path
    if not _is_ascii_path(pdf_path):
        tmp_dir = tempfile.TemporaryDirectory(prefix="s12_13_render_")
        open_path = Path(tmp_dir.name) / "input.pdf"
        shutil.copy2(pdf_path, open_path)

    doc = fitz.open(str(open_path))
    try:
        page = doc.load_page(0)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(str(out_path))
    finally:
        try:
            doc.close()
        finally:
            if tmp_dir is not None:
                try:
                    tmp_dir.cleanup()
                except Exception:
                    pass


_EASYOCR_READERS: dict[tuple[tuple[str, ...], bool], Any] = {}


def _get_easyocr_reader(
    *,
    languages: Sequence[str] = ("ja", "en"),
    use_gpu: bool = False,
) -> Any:
    key = (tuple(languages), use_gpu)
    cached = _EASYOCR_READERS.get(key)
    if cached is not None:
        return cached

    if not _EASYOCR_AVAILABLE:
        raise RuntimeError("easyocr が利用できません。")
    try:
        import easyocr  # type: ignore
    except Exception as e:
        raise RuntimeError("easyocr が利用できません。") from e

    # Reader initialization can be heavy; keep it cached per (langs, gpu).
    reader = easyocr.Reader(list(languages), gpu=use_gpu, verbose=False)
    _EASYOCR_READERS[key] = reader
    return reader


def _extract_pdf_text_easyocr_ocr(pdf_path: Path, *, run_dir: Path) -> str:
    """
    OCR the first page using easyocr (fallback for PDFs where text extraction
    produces garbled characters due to font mappings).

    Returns the extracted text (best-effort) or raises on total failure.
    """

    if not (_EASYOCR_AVAILABLE and _PYMUPDF_AVAILABLE):
        raise RuntimeError("easyocr / PyMuPDF が利用できません。")

    # Use an ASCII temp directory to avoid native path issues on Windows.
    tmp_obj = tempfile.TemporaryDirectory(prefix="s12_13_easyocr_")
    tmp_dir = Path(tmp_obj.name)
    try:
        attempts: list[int] = [120, 150, 200]
        best = ""
        best_dpi: int | None = None

        reader = _get_easyocr_reader(languages=("ja", "en"), use_gpu=False)

        for dpi in attempts:
            tmp_img = tmp_dir / f"p1_{dpi}.png"
            try:
                _render_pdf_first_page_png(pdf_path, tmp_img, dpi=dpi)
            except Exception:
                continue

            try:
                # detail=0 returns list[str]. Keep as lines to preserve signals.
                lines = reader.readtext(str(tmp_img), detail=0)
            except Exception:
                continue

            text = _normalize_text(
                "\n".join([str(ln).strip() for ln in lines if str(ln).strip()])
            )
            if len(text) > len(best):
                best = text
                best_dpi = dpi

            # If it already looks usable, stop early to save time.
            if VENDOR_HINT_RE.search(best) and DATE_YMD_RE.search(best) and (
                AMOUNT_LABEL_RE.search(best)
                or re.search(r"[0-9]{1,3}(?:,[0-9]{3})+", best)
            ):
                break

        if not best:
            raise RuntimeError("easyocr OCR でテキスト抽出できませんでした。")

        # Persist the chosen render for post-mortem debugging (best-effort).
        if best_dpi is not None:
            try:
                ocr_dir = run_dir / "ocr"
                _ensure_dir(ocr_dir)
                img_out = (
                    ocr_dir
                    / f"{_sanitize_filename(pdf_path.stem)}__easyocr_p1_{best_dpi}.png"
                )
                _render_pdf_first_page_png(pdf_path, img_out, dpi=best_dpi)
            except Exception:
                pass

        return best
    finally:
        try:
            tmp_obj.cleanup()
        except Exception:
            pass


def _get_tesseract_tessdata_dir() -> Path | None:
    """
    Determine tessdata directory.

    Priority:
    1) Adjacent directory next to this script: ./tessdata
    2) Environment variable TESSDATA_PREFIX (direct or +/tessdata)
    3) Tesseract install dir (exe_dir/tessdata)
    """

    local = Path(__file__).parent / "tessdata"
    if local.exists():
        return local

    env = os.environ.get("TESSDATA_PREFIX")
    if env:
        base = Path(env)
        if base.exists():
            if (base / "tessdata").exists():
                return base / "tessdata"
            return base

    if _TESSERACT_EXE is not None:
        guess = Path(_TESSERACT_EXE).parent / "tessdata"
        if guess.exists():
            return guess

    return None


def _tesseract_image_to_text(
    image_path: Path,
    *,
    languages: str,
    tessdata_dir: Path | None,
    timeout_s: int,
) -> str:
    if not _TESSERACT_AVAILABLE or _TESSERACT_EXE is None:
        raise RuntimeError("tesseract が利用できません。")

    cmd = [
        str(_TESSERACT_EXE),
        str(image_path),
        "stdout",
        "-l",
        languages,
        "--psm",
        "6",
    ]
    if tessdata_dir is not None:
        cmd.extend(["--tessdata-dir", str(tessdata_dir)])

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        raise RuntimeError(f"tesseract failed: rc={proc.returncode} stderr={err}")
    return proc.stdout or ""


def _extract_pdf_text_tesseract_ocr(pdf_path: Path, *, run_dir: Path) -> str:
    """
    OCR the first page using tesseract (no Torch dependency).

    Returns extracted text or raises on total failure.
    """

    if not (_TESSERACT_AVAILABLE and _PYMUPDF_AVAILABLE):
        raise RuntimeError("tesseract / PyMuPDF が利用できません。")

    tessdata_dir = _get_tesseract_tessdata_dir()
    # Prefer jpn+eng, but be robust if tessdata_dir does not contain eng.
    languages = "jpn+eng"
    if tessdata_dir is not None:
        if (tessdata_dir / "jpn.traineddata").exists() and not (
            tessdata_dir / "eng.traineddata"
        ).exists():
            languages = "jpn"

    # Use an ASCII temp directory to avoid native path issues on Windows.
    tmp_obj = tempfile.TemporaryDirectory(prefix="s12_13_tess_")
    tmp_dir = Path(tmp_obj.name)
    try:
        attempts: list[int] = [120, 150, 200]
        best = ""
        best_dpi: int | None = None
        last_error: BaseException | None = None

        for dpi in attempts:
            tmp_img = tmp_dir / f"p1_{dpi}.png"
            try:
                _render_pdf_first_page_png(pdf_path, tmp_img, dpi=dpi)
            except Exception as e:
                last_error = e
                continue

            try:
                raw = _tesseract_image_to_text(
                    tmp_img,
                    languages=languages,
                    tessdata_dir=tessdata_dir,
                    timeout_s=60,
                )
            except Exception as e:
                last_error = e
                continue

            text = _normalize_text(raw)
            if len(text) > len(best):
                best = text
                best_dpi = dpi

            if VENDOR_HINT_RE.search(best) and DATE_YMD_RE.search(best) and (
                AMOUNT_LABEL_RE.search(best)
                or re.search(r"[0-9]{1,3}(?:,[0-9]{3})+", best)
            ):
                break

        if not best:
            hints: list[str] = []
            if tessdata_dir is None:
                hints.append("tessdata_dir=not_found")
            else:
                # When --tessdata-dir is specified, all languages must exist there.
                if not (tessdata_dir / "jpn.traineddata").exists():
                    hints.append(f"jpn.traineddata=missing ({tessdata_dir})")
                if languages == "jpn+eng" and not (tessdata_dir / "eng.traineddata").exists():
                    hints.append(f"eng.traineddata=missing ({tessdata_dir})")
            if last_error is not None:
                hints.append(f"last_error={type(last_error).__name__}: {last_error}")
            hint = (" " + "; ".join(hints)) if hints else ""
            raise RuntimeError(f"tesseract OCR でテキスト抽出できませんでした。{hint}".strip())

        # Persist the chosen render for post-mortem debugging (best-effort).
        if best_dpi is not None:
            try:
                ocr_dir = run_dir / "ocr"
                _ensure_dir(ocr_dir)
                img_out = (
                    ocr_dir
                    / f"{_sanitize_filename(pdf_path.stem)}__tesseract_p1_{best_dpi}.png"
                )
                _render_pdf_first_page_png(pdf_path, img_out, dpi=best_dpi)
            except Exception:
                pass

        return best
    finally:
        try:
            tmp_obj.cleanup()
        except Exception:
            pass


_YOMITOKU_ANALYZERS: dict[tuple[bool, bool], Any] = {}


def _get_yomitoku_analyzer(*, use_gpu: bool = False, lite_mode: bool = True) -> Any:
    key = (use_gpu, lite_mode)
    cached = _YOMITOKU_ANALYZERS.get(key)
    if cached is not None:
        return cached

    if not _YOMITOKU_AVAILABLE:
        raise RuntimeError("yomitoku が利用できません。")
    try:
        from yomitoku import DocumentAnalyzer  # type: ignore
    except Exception as e:
        raise RuntimeError("yomitoku が利用できません。") from e
    device = "cuda" if use_gpu else "cpu"
    configs: dict[str, Any] = {}
    if lite_mode:
        configs = {
            "ocr": {"model_name": "lite"},
            "layout_analyzer": {"model_name": "lite"},
        }
    analyzer = DocumentAnalyzer(configs=configs, device=device)
    _YOMITOKU_ANALYZERS[key] = analyzer
    return analyzer


def _yomitoku_content_to_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        s = str(value)
    except Exception:
        return ""
    # YomiToku sometimes inserts '\n' between each character. Remove them.
    s = s.replace("\r", "").replace("\n", "")
    s = _normalize_text(s).strip()
    if not s or s == "None":
        return ""
    return s


def _extract_text_from_yomitoku_result(result: Any) -> str:
    parts: list[str] = []

    # paragraphs
    for p in getattr(result, "paragraphs", []) or []:
        txt = _yomitoku_content_to_text(getattr(p, "contents", None))
        if txt:
            parts.append(txt)

    # figures (some PDFs embed key info as figure-like blocks)
    for fig in getattr(result, "figures", []) or []:
        txt = _yomitoku_content_to_text(getattr(fig, "contents", None))
        if txt:
            parts.append(txt)
        cap = _yomitoku_content_to_text(getattr(fig, "caption", None))
        if cap:
            parts.append(cap)
        for p in getattr(fig, "paragraphs", []) or []:
            txt = _yomitoku_content_to_text(getattr(p, "contents", None))
            if txt:
                parts.append(txt)

    # tables (invoice key fields are often in tables)
    for tbl in getattr(result, "tables", []) or []:
        # Most common: tbl.cells -> list of cell objects with .contents
        cells = getattr(tbl, "cells", None)
        if cells:
            for cell in cells:
                txt = _yomitoku_content_to_text(getattr(cell, "contents", None))
                if txt:
                    parts.append(txt)
            continue

        # Fallback: tbl.data can be nested (rows/cols)
        data = getattr(tbl, "data", None)
        if isinstance(data, list):
            for row in data:
                if not isinstance(row, list):
                    continue
                for cell in row:
                    txt = _yomitoku_content_to_text(getattr(cell, "contents", None))
                    if txt:
                        parts.append(txt)

    return _normalize_text("\n".join([p for p in parts if p]))


def _extract_pdf_text_yomitoku_ocr(pdf_path: Path, *, run_dir: Path) -> str:
    if not (_YOMITOKU_AVAILABLE and _PYMUPDF_AVAILABLE):
        raise RuntimeError("yomitoku / PyMuPDF が利用できません。")
    try:
        from yomitoku.data.functions import load_image  # type: ignore
    except Exception as e:
        raise RuntimeError("yomitoku が利用できません。") from e
    # Use an ASCII temp directory to avoid native path issues on Windows.
    tmp_obj = tempfile.TemporaryDirectory(prefix="s12_13_ocr_")
    tmp_dir = Path(tmp_obj.name)
    try:
        attempts: list[tuple[int, bool]] = [
            (150, True),
            (200, True),
            (200, False),
        ]
        best = ""
        for dpi, lite_mode in attempts:
            tmp_img = tmp_dir / f"p1_{dpi}_{'lite' if lite_mode else 'full'}.png"
            _render_pdf_first_page_png(pdf_path, tmp_img, dpi=dpi)
            analyzer = _get_yomitoku_analyzer(use_gpu=False, lite_mode=lite_mode)
            img = load_image(str(tmp_img))
            result, _, _ = analyzer(img)
            text = _extract_text_from_yomitoku_result(result)
            if len(text) > len(best):
                best = text

            # If it already looks usable, stop early to save time.
            if VENDOR_HINT_RE.search(best) and DATE_YMD_RE.search(best) and (
                AMOUNT_LABEL_RE.search(best)
                or re.search(r"[0-9]{1,3}(?:,[0-9]{3})+", best)
            ):
                break

        return best
    finally:
        try:
            tmp_obj.cleanup()
        except Exception:
            pass


def _extract_invoice_fields_from_pdf(
    pdf_path: Path,
    *,
    company_deny_regex: str | None,
    max_pages: int,
    run_dir: Path,
    log_path: Path,
) -> ExtractedPdfFields | None:
    # 1) pypdf
    try:
        if _PYPDF_AVAILABLE:
            text = _extract_pdf_text_pypdf(pdf_path, max_pages=max_pages)
            fields = _extract_invoice_fields(text=text, company_deny_regex=company_deny_regex)
            if fields:
                return fields
    except Exception as e:
        _append_log(log_path, f"[WARN] pypdf text extract failed: {pdf_path.name} error={e}")

    # 2) PyMuPDF
    try:
        if _PYMUPDF_AVAILABLE:
            text = _extract_pdf_text_pymupdf(pdf_path, max_pages=max_pages)
            fields = _extract_invoice_fields(text=text, company_deny_regex=company_deny_regex)
            if fields:
                return fields
    except Exception as e:
        _append_log(log_path, f"[WARN] pymupdf text extract failed: {pdf_path.name} error={e}")

    # 3) tesseract OCR
    try:
        if _TESSERACT_AVAILABLE and _PYMUPDF_AVAILABLE:
            text = _extract_pdf_text_tesseract_ocr(pdf_path, run_dir=run_dir)
            fields = _extract_invoice_fields(text=text, company_deny_regex=company_deny_regex)
            if fields:
                return fields
    except Exception as e:
        _append_log(log_path, f"[WARN] tesseract ocr failed: {pdf_path.name} error={e}")

    # 4) YomiToku OCR (optional)
    try:
        if _YOMITOKU_AVAILABLE and _PYMUPDF_AVAILABLE:
            text = _extract_pdf_text_yomitoku_ocr(pdf_path, run_dir=run_dir)
            fields = _extract_invoice_fields(text=text, company_deny_regex=company_deny_regex)
            if fields:
                return fields
    except Exception as e:
        _append_log(log_path, f"[WARN] yomitoku ocr failed: {pdf_path.name} error={e}")

    return None


def _expand_pdf_paths_for_debug(raw_paths: Sequence[str]) -> list[Path]:
    expanded: list[Path] = []
    for raw in raw_paths:
        p = Path(str(raw).strip())
        if p.is_dir():
            expanded.extend(sorted(p.rglob("*.pdf")))
        else:
            expanded.append(p)

    seen: set[str] = set()
    uniq: list[Path] = []
    for p in expanded:
        try:
            key = str(p.resolve())
        except Exception:
            key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def _write_debug_text(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except Exception:
        # Best-effort: do not break debug flow on encoding issues.
        path.write_text(text, encoding="utf-8", errors="replace")


def _debug_extract_invoice_fields_from_pdf(
    pdf_path: Path,
    *,
    company_deny_regex: str | None,
    max_pages: int,
    debug_run_dir: Path,
    log_path: Path,
) -> ExtractedPdfFields | None:
    """
    Debug helper: extract invoice fields from a PDF and write intermediate
    extraction artifacts (texts + page1 image).

    This function does not move files and does not send emails.
    """

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF: {pdf_path}")

    # Avoid clobbering debug outputs when multiple PDFs share the same file name.
    path_hash = hashlib.sha1(str(pdf_path).encode("utf-8", errors="ignore")).hexdigest()[:8]
    per_pdf_dir = debug_run_dir / f"{_sanitize_filename(pdf_path.stem)}__{path_hash}"
    _ensure_dir(per_pdf_dir)

    # Render the first page for manual inspection.
    if _PYMUPDF_AVAILABLE:
        try:
            _render_pdf_first_page_png(
                pdf_path, per_pdf_dir / "page1_200dpi.png", dpi=200
            )
        except Exception as e:
            _append_log(log_path, f"[WARN] render page1 failed: {pdf_path.name} error={e}")

    def _try_extract(method: str, extractor: Callable[[], str]) -> ExtractedPdfFields | None:
        try:
            text = extractor()
            _write_debug_text(per_pdf_dir / f"{method}.txt", text)
            fields = _extract_invoice_fields(text=text, company_deny_regex=company_deny_regex)
            _append_log(
                log_path,
                f"debug_extract {method}: pdf={pdf_path.name} text_len={len(text)} fields={'OK' if fields else 'NG'}",
            )
            if fields:
                _write_debug_text(per_pdf_dir / "picked_method.txt", method)
                return fields
        except Exception as e:
            _append_log(log_path, f"[WARN] debug_extract {method} failed: {pdf_path.name} error={e}")
        return None

    # 1) pypdf
    if _PYPDF_AVAILABLE:
        fields = _try_extract(
            "pypdf", lambda: _extract_pdf_text_pypdf(pdf_path, max_pages=max_pages)
        )
        if fields:
            return fields

    # 2) PyMuPDF
    if _PYMUPDF_AVAILABLE:
        fields = _try_extract(
            "pymupdf", lambda: _extract_pdf_text_pymupdf(pdf_path, max_pages=max_pages)
        )
        if fields:
            return fields

    # 3) tesseract OCR
    if _TESSERACT_AVAILABLE and _PYMUPDF_AVAILABLE:
        fields = _try_extract(
            "tesseract",
            lambda: _extract_pdf_text_tesseract_ocr(pdf_path, run_dir=per_pdf_dir),
        )
        if fields:
            return fields

    # 4) YomiToku OCR
    if _YOMITOKU_AVAILABLE and _PYMUPDF_AVAILABLE:
        fields = _try_extract(
            "yomitoku",
            lambda: _extract_pdf_text_yomitoku_ocr(pdf_path, run_dir=per_pdf_dir),
        )
        if fields:
            return fields

    return None


def _extract_invoice_fields(text: str, company_deny_regex: str | None) -> ExtractedPdfFields | None:
    text = _normalize_text(text)
    deny_re = re.compile(company_deny_regex) if company_deny_regex else None

    # Vendor candidate lines (prefer early, exclude recipient markers).
    vendor_candidates: list[str] = []
    for line in [ln.strip() for ln in text.splitlines() if ln.strip()]:
        if len(vendor_candidates) >= 30:
            break
        if ("様" in line) or ("御中" in line):
            continue

        # If both recipient and vendor appear in the same line, remove the recipient and re-check.
        candidate = line
        if deny_re and deny_re.search(candidate):
            candidate = deny_re.sub(" ", candidate).strip()
            if not candidate:
                continue

        # Remove common prefixes like "発行元:" / "会社名:" etc.
        candidate = re.sub(
            r"^(発行元|会社名|請求元|取引先|支払先|相手先|販売元|納入元)\s*[:：]?\s*",
            "",
            candidate,
        ).strip()

        if not VENDOR_HINT_RE.search(candidate):
            continue
        vendor_candidates.append(candidate)
    vendor = vendor_candidates[0] if vendor_candidates else None

    # Issue date (prefer labeled).
    issue_date: str | None = None
    for m in DATE_LABEL_RE.finditer(text):
        parsed = _parse_ymd(m.group(2))
        if parsed:
            issue_date = parsed
            break
    if not issue_date:
        dates = []
        for m in DATE_YMD_RE.finditer(text):
            parsed = _parse_ymd(m.group(0))
            if parsed:
                dates.append(parsed)
        uniq = sorted(set(dates))
        if len(uniq) == 1:
            issue_date = uniq[0]

    # Amount (prefer labeled by priority; fallback to numbers with comma + 円).
    #
    # Priority matters because invoices can contain multiple amounts such as:
    # - ご請求金額(税込)
    # - 支払決定金額 (actual payable amount)
    def _amount_label_priority(label: str) -> int:
        if "支払決定" in label:
            return 0
        if ("支払" in label) or ("お支払" in label) or ("お支払い" in label):
            return 1
        if "請求" in label:
            return 2
        return 3

    candidates: list[tuple[int, int]] = []
    for m in AMOUNT_LABEL_RE.finditer(text):
        label = m.group(1)
        raw = m.group(2).replace(",", "").strip()
        if raw.isdigit():
            candidates.append((_amount_label_priority(label), int(raw)))

    if candidates:
        candidates.sort(key=lambda x: (x[0], -x[1]))
        amount = candidates[0][1]
    else:
        amounts: list[int] = []
        # Currency symbol.
        for m in re.finditer(r"[¥￥]\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)", text):
            raw = m.group(1).replace(",", "")
            if raw.isdigit():
                amounts.append(int(raw))
        # Comma + 円.
        for m in re.finditer(r"([0-9]{1,3}(?:,[0-9]{3})+)\s*円", text):
            raw = m.group(1).replace(",", "")
            if raw.isdigit():
                amounts.append(int(raw))
        # Comma numbers without 円 (last resort).
        if not amounts:
            for m in re.finditer(r"([0-9]{1,3}(?:,[0-9]{3})+)", text):
                raw = m.group(1).replace(",", "")
                if raw.isdigit():
                    v = int(raw)
                    if v >= 1000:
                        amounts.append(v)
        amount = max(amounts) if amounts else None

    invoice_no: str | None = None
    m_no = INVOICE_NO_RE.search(text)
    if m_no:
        invoice_no = m_no.group(2).strip() or None

    if not vendor or not issue_date or amount is None:
        return None
    return ExtractedPdfFields(vendor=vendor, issue_date=issue_date, amount=amount, invoice_no=invoice_no)


def _render_template(template: str, values: dict[str, str]) -> str:
    try:
        return template.format(**values)
    except KeyError as e:
        raise ValueError(f"rename template has unknown key: {e}") from e


def _move_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


def _load_config(path: Path) -> ToolConfig:
    # PowerShell's Set-Content can emit UTF-8 BOM; accept it.
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    outlook_raw = raw.get("outlook") if isinstance(raw, dict) else None
    outlook = None
    if isinstance(outlook_raw, dict):
        outlook = OutlookSelection(
            folder_path=str(outlook_raw.get("folder_path", "")).strip(),
            profile_name=(
                str(outlook_raw["profile_name"]).strip()
                if outlook_raw.get("profile_name") is not None
                else None
            ),
            unread_only=bool(outlook_raw.get("unread_only", True)),
            max_messages=int(outlook_raw.get("max_messages", 200)),
            received_within_days=(
                int(outlook_raw["received_within_days"])
                if outlook_raw.get("received_within_days") is not None
                else None
            ),
            subject_allow_regex=(
                str(outlook_raw["subject_allow_regex"]).strip()
                if outlook_raw.get("subject_allow_regex")
                else None
            ),
            subject_deny_regex=(
                str(outlook_raw["subject_deny_regex"]).strip()
                if outlook_raw.get("subject_deny_regex")
                else None
            ),
            mark_as_read_on_success=bool(outlook_raw.get("mark_as_read_on_success", False)),
        )
        if not outlook.folder_path:
            raise ValueError("config.outlook.folder_path が空です。")

    merge_raw = raw.get("merge") if isinstance(raw, dict) else None
    merge = MergeConfig()
    if isinstance(merge_raw, dict):
        merge = MergeConfig(
            enabled=bool(merge_raw.get("enabled", True)),
            output_name=str(merge_raw.get("output_name", "merged.pdf")).strip()
            or "merged.pdf",
        )

    print_raw = raw.get("print") if isinstance(raw, dict) else None
    prn = PrintConfig()
    if isinstance(print_raw, dict):
        prn = PrintConfig(
            enabled=bool(print_raw.get("enabled", False)),
            printer_name=(
                str(print_raw["printer_name"]).strip()
                if print_raw.get("printer_name")
                else None
            ),
            method=str(print_raw.get("method", "shell")).strip() or "shell",
        )

    mail_raw = raw.get("mail") if isinstance(raw, dict) else None
    mail = MailConfig()
    if isinstance(mail_raw, dict):
        mail = MailConfig(
            send_success=bool(mail_raw.get("send_success", True)),
            success_to=tuple(mail_raw.get("success_to") or ()),
            error_to=tuple(mail_raw.get("error_to") or ()),
            error_cc=tuple(mail_raw.get("error_cc") or ()),
        )

    rename_raw = raw.get("rename") if isinstance(raw, dict) else None
    ren = RenameConfig()
    if isinstance(rename_raw, dict):
        ren = RenameConfig(
            enabled=bool(rename_raw.get("enabled", True)),
            create_vendor_subdir=bool(rename_raw.get("create_vendor_subdir", True)),
            vendor_subdir_template=str(
                rename_raw.get("vendor_subdir_template", "{vendor_short}")
            ).strip()
            or "{vendor_short}",
            file_name_template=str(
                rename_raw.get(
                    "file_name_template", "{vendor_short}__{issue_date}__{amount}.pdf"
                )
            ).strip()
            or "{vendor_short}__{issue_date}__{amount}.pdf",
            company_deny_regex=(
                str(rename_raw["company_deny_regex"]).strip()
                if rename_raw.get("company_deny_regex")
                else None
            ),
            max_pages=int(rename_raw.get("max_pages", 2)),
        )

    cfg = ToolConfig(
        artifact_dir=str(raw.get("artifact_dir", DEFAULT_ARTIFACT_DIR)).strip()
        or DEFAULT_ARTIFACT_DIR,
        save_dir=(str(raw["save_dir"]).strip() if raw.get("save_dir") else None),
        outlook=outlook,
        merge=merge,
        print=prn,
        mail=mail,
        rename=ren,
        fail_on_url_only_mail=bool(raw.get("fail_on_url_only_mail", True)),
        decrypt_password_window_minutes=int(raw.get("decrypt_password_window_minutes", 20)),
    )

    return cfg


def _is_unc_path(path: Path) -> bool:
    return str(path).startswith("\\\\")


def _ps_single_quote(value: str) -> str:
    # Escape single quotes for PowerShell single-quoted string literal.
    return "'" + value.replace("'", "''") + "'"


def _test_path_with_timeout(path: Path, timeout_seconds: float) -> bool | None:
    """
    Return True/False if the existence check succeeded, or None if it timed out/failed.
    Use PowerShell Test-Path for UNC paths to avoid long hangs.
    """

    if not _is_unc_path(path):
        try:
            return path.exists()
        except Exception:
            return None

    cmd = f"Test-Path -LiteralPath {_ps_single_quote(str(path))}"
    try:
        cp = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None

    if cp.returncode != 0:
        return None
    out = (cp.stdout or "").strip().lower()
    if out == "true":
        return True
    if out == "false":
        return False
    return None


def _outlook_namespace(profile_name: str | None = None) -> Any:
    if not _OUTLOOK_AVAILABLE:
        raise RuntimeError("Outlook COM が利用できません (pywin32/win32com が必要です)。")
    _install_com_message_filter()
    try:
        # Prefer an existing Outlook session (already logged-in, correct profile).
        outlook = win32.GetActiveObject("Outlook.Application")
    except Exception:
        outlook = win32.Dispatch("Outlook.Application")
    mapi = _com_retry(lambda: outlook.GetNamespace("MAPI"))
    if profile_name:
        profile = profile_name.strip()
        if profile:
            try:
                # ShowDialog=False to avoid UI; NewSession=True to ensure the profile is loaded.
                _com_retry(lambda: mapi.Logon(profile, "", False, True))
            except Exception as e:
                raise RuntimeError(
                    "Outlook プロファイルにログオンできませんでした。\n"
                    f"profile_name={profile_name}"
                ) from e
    return mapi


def _resolve_outlook_folder(mapi: Any, folder_path: str) -> Any:
    # folder_path example: "\\RK用の経理\\受信トレイ\\サブフォルダ"
    s = folder_path.strip()
    if not s.startswith("\\\\"):
        raise ValueError(
            f"outlook.folder_path は \\\\ から始まる必要があります: {folder_path}"
        )
    parts = [p for p in s.strip("\\").split("\\") if p]
    if len(parts) < 1:
        raise ValueError(f"outlook.folder_path の形式が不正です: {folder_path}")

    store_name = parts[0]
    store = None
    folders = _com_retry(lambda: mapi.Folders)
    count = _com_retry(lambda: int(folders.Count))
    for i in range(1, count + 1):
        f = _com_retry(lambda i=i: folders.Item(i))
        if (f.Name or "").strip() == store_name:
            store = f
            break
    if store is None:
        available = []
        for i in range(1, count + 1):
            try:
                available.append(str(_com_retry(lambda i=i: folders.Item(i).Name)))
            except Exception:
                continue
        raise ValueError(
            "Outlookストアが見つかりません。\n"
            f"指定: {store_name}\n"
            f"利用可能: {available}"
        )

    if len(parts) == 1:
        return store

    cur = store
    for name in parts[1:]:
        try:
            cur = _com_retry(lambda name=name: cur.Folders.Item(name))
        except Exception as e:
            raise ValueError(
                f"Outlookフォルダが見つかりません: {folder_path}\n"
                f"見つからない要素: {name}"
            ) from e
    return cur


def _safe_sender(item: Any) -> str:
    # SenderEmailAddress is often an Exchange X500 string. Prefer SenderName when needed.
    try:
        addr = (item.SenderEmailAddress or "").strip()
    except Exception:
        addr = ""
    try:
        name = (item.SenderName or "").strip()
    except Exception:
        name = ""
    if addr and "@" in addr:
        return addr
    return name or addr or "(unknown)"


def _safe_received_time(item: Any) -> datetime | None:
    try:
        rt = item.ReceivedTime
        if isinstance(rt, datetime):
            if rt.tzinfo is not None:
                # Normalize to naive local time to avoid mixing aware/naive datetimes.
                return rt.astimezone().replace(tzinfo=None)
            return rt
    except Exception:
        return None
    return None


def _iter_mail_items(folder: Any, unread_only: bool, max_messages: int) -> list[Any]:
    items = _com_retry(lambda: folder.Items)
    try:
        _com_retry(lambda: items.Sort("[ReceivedTime]", True), retries=5)
    except Exception:
        pass

    res: list[Any] = []
    count = _com_retry(lambda: int(items.Count))
    for i in range(1, count + 1):
        if len(res) >= max_messages:
            break
        try:
            item = _com_retry(lambda i=i: items.Item(i), retries=10)
        except Exception:
            continue
        # MailItem Class=43
        try:
            if int(getattr(item, "Class", 0)) != 43:
                continue
        except Exception:
            continue
        if unread_only:
            try:
                if not bool(item.UnRead):
                    continue
            except Exception:
                continue
        res.append(item)
    return res


def _is_password_mail(subject: str) -> bool:
    s = subject.lower()
    return ("パスワード" in subject) or ("hennge" in s) or ("password" in s)


def _clean_password_token(token: str) -> str:
    t = _normalize_text(token or "").strip()
    # Strip common wrappers (quotes/brackets/punctuation) but keep symbols like '+' that are valid in passwords.
    t = t.strip(" \t\r\n\"'“”‘’()[]{}<>「」『』")
    t = t.strip(" \t\r\n,.;:：。．、")
    return t


def _is_plausible_password(token: str) -> bool:
    t = token.strip()
    if len(t) < 4:
        return False
    # Avoid obvious masks
    if set(t) <= {"*", "・", "●"}:
        return False
    # Require at least one alnum (PPAP passwords are typically mixed)
    if not re.search(r"[A-Za-z0-9]", t):
        return False
    return True


def _extract_password(body: str) -> str | None:
    body = _normalize_text(body or "")
    m = PASSWORD_RE.search(body)
    if m:
        cand = _clean_password_token(m.group(1))
        return cand if _is_plausible_password(cand) else None
    # fallback: find a plausible token on a line containing パスワード
    for line in body.splitlines():
        if "パスワード" not in line and "password" not in line.lower():
            continue
        tokens = re.findall(r"[^\s]{4,}", line)
        for tok in reversed(tokens):
            cand = _clean_password_token(tok)
            if _is_plausible_password(cand):
                return cand
    return None


def _extract_urls(text: str) -> list[str]:
    urls = []
    for m in URL_RE.finditer(text or ""):
        u = m.group(0).strip().rstrip(").,>")
        if u not in urls:
            urls.append(u)
    return urls


def _subject_allowed(subject: str, allow_re: re.Pattern[str] | None) -> bool:
    if allow_re is None:
        return True
    return bool(allow_re.search(subject))


def _subject_denied(subject: str, deny_re: re.Pattern[str] | None) -> bool:
    if deny_re is None:
        return False
    return bool(deny_re.search(subject))


def _unique_path(base: Path) -> Path:
    if not base.exists():
        return base
    stem = base.stem
    suffix = base.suffix
    for i in range(1, 999):
        cand = base.with_name(f"{stem}__dup{i:03d}{suffix}")
        if not cand.exists():
            return cand
    raise RuntimeError(f"同名ファイルが多すぎます: {base}")


def _is_pdf_encrypted(path: Path) -> bool:
    if not _PYPDF_AVAILABLE:
        return False
    try:
        r = PdfReader(str(path))
        return bool(getattr(r, "is_encrypted", False))
    except Exception:
        # treat as non-encrypted here; parse errors will be handled later
        return False


def _decrypt_pdf(src: Path, dst: Path, password: str) -> None:
    if not _PYPDF_AVAILABLE:
        raise RuntimeError("pypdf が利用できません。")
    reader = PdfReader(str(src))
    if not reader.is_encrypted:
        raise ValueError("PDFは暗号化されていません。")
    ok = reader.decrypt(password)
    if ok == 0:
        raise ValueError("PDF復号に失敗しました（パスワード不一致）。")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    with dst.open("wb") as f:
        writer.write(f)


def _candidate_passwords_for_time(
    target_time: datetime,
    notes: Sequence[PasswordNote],
    window_minutes: int,
) -> list[str]:
    win = timedelta(minutes=window_minutes)
    scored: list[tuple[float, str]] = []
    for n in notes:
        dt = abs((n.received_time - target_time).total_seconds())
        if dt <= win.total_seconds():
            scored.append((dt, n.password))
    scored.sort(key=lambda x: (x[0], x[1]))
    uniq: list[str] = []
    seen: set[str] = set()
    for _, pw in scored:
        if not pw:
            continue
        if pw in seen:
            continue
        uniq.append(pw)
        seen.add(pw)
        if len(uniq) >= ZIP_PASSWORD_MAX_CANDIDATES:
            break
    return uniq


def _unique_dir(base: Path) -> Path:
    if not base.exists():
        return base
    for i in range(1, 999):
        cand = base.with_name(f"{base.name}__dup{i:03d}")
        if not cand.exists():
            return cand
    raise RuntimeError(f"同名ディレクトリが多すぎます: {base}")


def _sanitize_zip_member_relpath(member_name: str) -> Path:
    # Zip entries are usually POSIX-style paths even on Windows.
    raw = member_name.replace("\\", "/").strip()
    rel = Path(raw)
    if rel.is_absolute() or (len(rel.parts) > 0 and rel.parts[0].endswith(":")):
        raise ValueError(f"zip member has absolute path: {member_name}")
    parts: list[str] = []
    for p in rel.parts:
        if p in ("", "."):
            continue
        if p == "..":
            raise ValueError(f"zip member has parent traversal: {member_name}")
        parts.append(_sanitize_filename(p))
    if not parts:
        raise ValueError(f"zip member path is empty: {member_name}")
    return Path(*parts)


def _is_wrong_zip_password_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return ("password" in msg) or ("crc" in msg)


def _extract_pdf_members_from_zip(
    zip_path: Path,
    *,
    password: str | None,
    out_dir: Path,
    log_path: Path,
) -> list[Path]:
    pwd_bytes = password.encode("utf-8") if password else None
    extracted: list[Path] = []

    def _extract_with_open(zf: Any) -> list[Path]:
        infos = [i for i in zf.infolist() if not getattr(i, "is_dir", lambda: False)()]
        pdf_infos = [i for i in infos if str(i.filename).lower().endswith(".pdf")]
        if not pdf_infos:
            return []
        if len(pdf_infos) > ZIP_MAX_MEMBERS:
            raise ValueError(
                f"zip内PDFが多すぎます: {zip_path.name} pdf_members={len(pdf_infos)}"
            )
        total = 0
        for info in pdf_infos:
            size = int(getattr(info, "file_size", 0))
            if size <= 0:
                continue
            if size > ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"zip内PDFが大きすぎます: {zip_path.name} member={info.filename} size={size}"
                )
            total += size
            if total > ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"zip展開サイズが上限超過: {zip_path.name} total={total} limit={ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES}"
                )

        for info in pdf_infos:
            rel = _sanitize_zip_member_relpath(str(info.filename))
            dest = out_dir / rel
            dest = _unique_path(dest)
            _ensure_dir(dest.parent)
            _append_log(log_path, f"extract zip member: {zip_path.name}::{info.filename} -> {dest}")
            # zipfile/pyzipper both accept pwd=...
            with zf.open(info, pwd=pwd_bytes) as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(dest)
        return extracted

    # Prefer pyzipper (AES対応) when available; fallback to stdlib zipfile.
    if _PYZIPPER_AVAILABLE:
        try:
            with pyzipper.AESZipFile(str(zip_path), "r") as zf:
                return _extract_with_open(zf)
        except Exception as e:
            # If pyzipper fails, fallback to stdlib as a second attempt for non-AES zips.
            _append_log(log_path, f"[WARN] pyzipper failed, fallback to zipfile: {zip_path.name} error={e}")

    with zipfile.ZipFile(str(zip_path), "r") as zf:
        return _extract_with_open(zf)


def _merge_pdfs(input_paths: Sequence[Path], output_path: Path) -> None:
    if not _PYPDF_AVAILABLE:
        raise RuntimeError("pypdf が利用できません。")
    writer = PdfWriter()
    for p in input_paths:
        reader = PdfReader(str(p))
        for page in reader.pages:
            writer.add_page(page)
    with output_path.open("wb") as f:
        writer.write(f)


def _default_printer() -> str | None:
    if not _WIN32_PRINT_AVAILABLE:
        return None
    try:
        return str(win32print.GetDefaultPrinter())
    except Exception:
        return None


def _print_via_shell(pdf_path: Path, printer_name: str | None) -> None:
    if not _WIN32_PRINT_AVAILABLE:
        raise RuntimeError("印刷には pywin32 (win32api/win32print) が必要です。")
    verb = "printto" if printer_name else "print"
    params = f"\"{printer_name}\"" if printer_name else None
    win32api.ShellExecute(0, verb, str(pdf_path), params, str(pdf_path.parent), 0)


def _write_report_json(path: Path, report: RunReport) -> None:
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_report_csv(path: Path, saved: Sequence[SavedAttachment]) -> None:
    fields = [
        "message_entry_id",
        "message_subject",
        "sender",
        "received_time",
        "attachment_name",
        "saved_path",
        "original_saved_path",
        "vendor",
        "issue_date",
        "amount",
        "invoice_no",
        "sha256",
        "was_encrypted",
        "decrypted_path",
        "encrypted_original_path",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in saved:
            w.writerow(asdict(r))


def _process_saved_pdf_file(
    *,
    cfg: ToolConfig,
    pdf_path: Path,
    attachment_name: str,
    entry_id: str,
    subject: str,
    sender: str,
    received_dt: datetime,
    received_time_s: str,
    password_notes: Sequence[PasswordNote],
    save_dir: Path,
    run_dir: Path,
    log_path: Path,
    unresolved: list[str],
) -> SavedAttachment:
    sha = _sha256_file(pdf_path)

    was_encrypted = _is_pdf_encrypted(pdf_path)
    decrypted_path: Path | None = None
    encrypted_original_path: str | None = str(pdf_path) if was_encrypted else None

    primary_path = pdf_path
    if was_encrypted:
        passwords = _candidate_passwords_for_time(
            target_time=received_dt,
            notes=password_notes,
            window_minutes=cfg.decrypt_password_window_minutes,
        )
        if not passwords:
            unresolved.append(
                f"暗号化PDFのパスワードが見つかりません: {pdf_path.name} (subject={subject})"
            )
        else:
            out_base = pdf_path.with_name(pdf_path.stem + "__decrypted.pdf")
            ok = False
            for pw in passwords:
                out = _unique_path(out_base)
                try:
                    _append_log(log_path, f"decrypt pdf: {pdf_path.name} -> {out.name}")
                    _decrypt_pdf(pdf_path, out, pw)
                    decrypted_path = out
                    primary_path = out
                    ok = True
                    break
                except Exception as e:
                    try:
                        out.unlink()
                    except Exception:
                        pass
                    # wrong password is common; avoid logging secrets
                    _append_log(
                        log_path,
                        f"[WARN] decrypt failed (try next): {pdf_path.name} error={e}",
                    )
            if not ok:
                unresolved.append(
                    f"PDF復号に失敗しました（候補パスワードで開けない）: {pdf_path.name} (subject={subject})"
                )

    final_path = primary_path
    vendor: str | None = None
    issue_date: str | None = None
    amount: int | None = None
    invoice_no: str | None = None

    # Rename/move based on PDF values (source of truth).
    if cfg.rename.enabled and (not was_encrypted or decrypted_path is not None):
        fields = _extract_invoice_fields_from_pdf(
            primary_path,
            company_deny_regex=cfg.rename.company_deny_regex,
            max_pages=cfg.rename.max_pages,
            run_dir=run_dir,
            log_path=log_path,
        )
        if fields is None:
            unresolved.append(
                f"PDFからリネーム用の値（会社名/日付/金額）を確定できません: {primary_path.name} (subject={subject})"
            )
        else:
            vendor = fields.vendor
            issue_date = fields.issue_date
            amount = fields.amount
            invoice_no = fields.invoice_no
            values = {
                "vendor": vendor,
                "vendor_short": _vendor_short(vendor),
                "issue_date": issue_date,
                "amount": str(amount),
                "amount_comma": f"{amount:,}",
                "invoice_no": invoice_no or "",
            }

            subdir = (
                _sanitize_filename(_render_template(cfg.rename.vendor_subdir_template, values))
                if cfg.rename.create_vendor_subdir
                else ""
            )
            filename = _sanitize_filename(_render_template(cfg.rename.file_name_template, values))
            dest_dir = (save_dir / subdir) if subdir else save_dir
            final_path = _unique_path(dest_dir / filename)
            _append_log(log_path, f"rename/move: {primary_path.name} -> {final_path}")
            try:
                _move_file(primary_path, final_path)
            except Exception:
                unresolved.append(
                    f"保存先への移動/リネームに失敗: {primary_path.name} -> {final_path}"
                )
                final_path = primary_path
    elif not cfg.rename.enabled:
        # Rename disabled: move the raw attachment name into save_dir.
        final_path = _unique_path(save_dir / primary_path.name)
        _append_log(log_path, f"move (rename disabled): {primary_path.name} -> {final_path}")
        try:
            _move_file(primary_path, final_path)
        except Exception:
            unresolved.append(f"保存先への移動に失敗: {primary_path.name} -> {final_path}")
            final_path = primary_path

    return SavedAttachment(
        message_entry_id=entry_id,
        message_subject=subject,
        sender=sender,
        received_time=received_time_s,
        attachment_name=attachment_name,
        saved_path=str(final_path),
        original_saved_path=str(pdf_path),
        vendor=vendor,
        issue_date=issue_date,
        amount=amount,
        invoice_no=invoice_no,
        sha256=sha,
        was_encrypted=was_encrypted,
        decrypted_path=str(final_path) if (was_encrypted and decrypted_path is not None) else None,
        encrypted_original_path=encrypted_original_path,
    )


def _validate_mail_config(cfg: ToolConfig, dry_run: bool, scan_only: bool) -> None:
    if scan_only or dry_run:
        return
    if not cfg.mail.error_to:
        raise ValueError("config.mail.error_to が空です（エラー通知先が必要です）。")
    if cfg.mail.send_success and (not cfg.mail.success_to):
        raise ValueError(
            "config.mail.success_to が空です（send_success=true のため通知先が必要です）。"
        )


def _send_success_mail(cfg: ToolConfig, report: RunReport, run_dir: Path, dry_run: bool) -> None:
    if not cfg.mail.send_success:
        return
    if report.dry_run:
        return

    save_dir_html = (
        html_link_to_path(Path(report.save_dir)) if report.save_dir else "(未指定)"
    )
    merged_html = (
        html_link_to_path(Path(report.merged_pdf_path))
        if report.merged_pdf_path
        else "(なし)"
    )
    paragraphs = [
        f"シナリオ12・13（受信メールPDF保存・一括印刷）が完了しました。",
        f"Run ID: {report.run_id}",
        f"ドライラン: {report.dry_run}",
        f"保存先: {save_dir_html}",
        f"Outlookフォルダ: {report.outlook_folder_path or '(未指定)'}",
        f"保存PDF数: {len(report.saved_attachments)}",
        f"URLのみタスク数: {len(report.url_only_tasks)}",
        f"結合PDF: {merged_html}",
        f"印刷ジョブ: {len(report.printed_paths)}",
        f"レポート: {html_link_to_path(run_dir)}",
    ]
    bullets: list[str] = []
    max_details = 30
    for a in report.saved_attachments[:max_details]:
        p = Path(a.saved_path)
        link = html_link_to_path(p, label=p.name)
        vendor = _vendor_short(a.vendor) if a.vendor else "(vendor不明)"
        issue = a.issue_date or "(日付不明)"
        amount = f"{a.amount:,}円" if a.amount is not None else "(金額不明)"
        # Avoid shadowing the imported `html` module below.
        inv = f" / {html.escape(a.invoice_no)}" if a.invoice_no else ""
        bullets.append(f"{link} / {vendor} / {issue} / {amount}{inv}")
    if len(report.saved_attachments) > max_details:
        bullets.append(f"... 他{len(report.saved_attachments) - max_details}件")
    if report.url_only_tasks:
        bullets.append("URLのみメールが検知されています（ダウンロード工程が未実装/未設定の場合は停止対象）")

    html_body = build_simple_html(
        title="【完了】シナリオ12・13 受信メールPDF保存・一括印刷",
        paragraphs=paragraphs,
        bullets=bullets or None,
    )
    send_outlook(
        OutlookEmail(
            to=cfg.mail.success_to,
            subject=f"【完了】受信メールPDF保存・一括印刷 Run={report.run_id}",
            html_body=html_body,
            attachments=[run_dir / "report.csv", run_dir / "report.json"],
        ),
        dry_run=dry_run,
    )


def _send_error_mail(
    cfg: ToolConfig,
    run_id: str,
    run_dir: Path,
    summary: str,
    details: Sequence[str],
    dry_run: bool,
) -> None:
    paragraphs = [
        "シナリオ12・13（受信メールPDF保存・一括印刷）でエラー/未解決が発生しました。",
        f"Run ID: {run_id}",
        summary,
        f"レポート/ログ: {html_link_to_path(run_dir)}",
    ]
    base = build_simple_html(
        title="★エラー発生★ 受信メールPDF保存・一括印刷",
        paragraphs=paragraphs,
        bullets=list(details) if details else None,
    )
    # Preserve traceback formatting in HTML mail body.
    tb_text = "\n\n".join([d for d in details if d]) if details else ""
    tb_html = (
        f"<h4>Traceback</h4><pre>{html.escape(tb_text)}</pre>" if tb_text else ""
    )
    html_body = base.replace("</body>", f"{tb_html}\n  </body>")
    send_outlook(
        OutlookEmail(
            to=cfg.mail.error_to,
            cc=cfg.mail.error_cc,
            subject=f"★エラー発生★ 受信メールPDF保存・一括印刷 Run={run_id}",
            html_body=html_body,
            attachments=[p for p in [run_dir / "run.log", run_dir / "report.json"] if p.exists()],
        ),
        dry_run=dry_run,
    )


def _append_log(log_path: Path, line: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path.write_text("", encoding="utf-8") if not log_path.exists() else None
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")


def _list_outlook_stores(mapi: Any) -> list[str]:
    stores: list[str] = []
    folders = _com_retry(lambda: mapi.Folders)
    count = _com_retry(lambda: int(folders.Count))
    for i in range(1, count + 1):
        try:
            stores.append(str(_com_retry(lambda i=i: folders.Item(i).Name)))
        except Exception:
            continue
    return stores


def _list_outlook_child_folders(mapi: Any, folder_path: str) -> list[str]:
    folder = _resolve_outlook_folder(mapi, folder_path)
    names: list[str] = []
    subfolders = _com_retry(lambda: folder.Folders)
    count = _com_retry(lambda: int(subfolders.Count))
    for i in range(1, count + 1):
        try:
            names.append(str(_com_retry(lambda i=i: subfolders.Item(i).Name)))
        except Exception:
            continue
    return names


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=str, required=False, help="JSON config path")
    ap.add_argument(
        "--scan-only",
        action="store_true",
        help="Scan candidate mails/attachments only (no save/print, no email send)",
    )
    ap.add_argument(
        "--outlook-profile",
        type=str,
        default=None,
        help="Outlook profile name to log on (optional). Example: RKM",
    )
    ap.add_argument(
        "--list-outlook-stores",
        action="store_true",
        help="List Outlook stores (top-level mailboxes) and exit",
    )
    ap.add_argument(
        "--list-outlook-folders",
        type=str,
        default=None,
        help="List child folders under the given Outlook folder path and exit (e.g. \\\\Store\\\\受信トレイ)",
    )
    ap.add_argument(
        "--debug-extract-pdf",
        type=str,
        nargs="+",
        default=None,
        help="Debug: extract invoice fields from given PDF file(s) or directory(ies) and exit (no Outlook).",
    )
    ap.add_argument(
        "--outlook-folder-path",
        type=str,
        default=None,
        help="Override config.outlook.folder_path (e.g. \\\\Store\\\\受信トレイ)",
    )
    ap.add_argument(
        "--include-read",
        action="store_true",
        help="Include read mails (override config.outlook.unread_only=false)",
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Actually save/decrypt (default: dry-run)",
    )
    ap.add_argument(
        "--print",
        action="store_true",
        help="Actually print (requires --execute and config.print.enabled=true)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Force dry-run (ignores --execute)",
    )
    ap.add_argument(
        "--dry-run-mail",
        action="store_true",
        help="Do not send emails; print email content instead",
    )
    ap.add_argument(
        "--max-messages",
        type=int,
        default=None,
        help="Override config.outlook.max_messages",
    )
    ap.add_argument(
        "--save-dir",
        type=str,
        default=None,
        help="Override config.save_dir (save destination directory)",
    )
    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.list_outlook_stores:
        mapi = _outlook_namespace(profile_name=args.outlook_profile)
        for s in _list_outlook_stores(mapi):
            print(s)
        return 0

    if args.list_outlook_folders:
        mapi = _outlook_namespace(profile_name=args.outlook_profile)
        parent = str(args.list_outlook_folders)
        for name in _list_outlook_child_folders(mapi, parent):
            # Print both name and the full path for copy/paste.
            print(f"{name}\t{parent.rstrip('\\\\')}\\{name}")
        return 0

    if args.debug_extract_pdf:
        cfg = _load_config(Path(args.config)) if args.config else ToolConfig()
        run_id = _now_run_id()
        debug_run_dir = Path(cfg.artifact_dir) / f"debug_extract_{run_id}"
        _ensure_dir(debug_run_dir)
        log_path = debug_run_dir / "run.log"
        _append_log(
            log_path,
            f"start debug_extract run_id={run_id} config={args.config or '(none)'}",
        )

        pdf_paths = _expand_pdf_paths_for_debug(args.debug_extract_pdf)
        if not pdf_paths:
            ap.error("--debug-extract-pdf: no PDFs found in given paths")

        ok = 0
        ng = 0
        for pdf_path in pdf_paths:
            try:
                fields = _debug_extract_invoice_fields_from_pdf(
                    pdf_path,
                    company_deny_regex=cfg.rename.company_deny_regex,
                    max_pages=int(cfg.rename.max_pages),
                    debug_run_dir=debug_run_dir,
                    log_path=log_path,
                )
                if fields:
                    ok += 1
                    invoice_no = fields.invoice_no or ""
                    print(
                        f"OK\t{pdf_path}\tvendor={fields.vendor}\tissue_date={fields.issue_date}\tamount={fields.amount}\tinvoice_no={invoice_no}"
                    )
                else:
                    ng += 1
                    print(f"NG\t{pdf_path}")
            except Exception as e:
                ng += 1
                _append_log(log_path, f"[ERROR] debug_extract failed: pdf={pdf_path} error={e}")
                print(f"NG\t{pdf_path}\terror={e}")

        print(f"summary: ok={ok} ng={ng} total={len(pdf_paths)}")
        print(f"debug artifacts: {debug_run_dir}")
        return 0 if ng == 0 else 2

    if not args.config:
        ap.error(
            "--config is required unless using --list-outlook-stores/--list-outlook-folders/--debug-extract-pdf"
        )

    cfg = _load_config(Path(args.config))
    scan_only = bool(args.scan_only)
    dry_run = True if scan_only else (bool(args.dry_run) or (not args.execute))
    mail_enabled = not scan_only
    # Two-key safety for printing: config.print.enabled AND CLI --print must be true.
    do_print = bool(args.print) and (not dry_run) and bool(cfg.print.enabled)
    mail_dry_run = True if scan_only else (bool(args.dry_run_mail) or dry_run)
    _validate_mail_config(cfg, dry_run=dry_run, scan_only=scan_only)

    run_id = _now_run_id()
    run_dir = Path(cfg.artifact_dir) / f"run_{run_id}"
    _ensure_dir(run_dir)
    log_path = run_dir / "run.log"
    _append_log(log_path, f"start run_id={run_id} dry_run={dry_run} config={args.config}")

    started_at = datetime.now()
    merged_pdf_path: str | None = None
    printed_paths: list[str] = []
    unresolved: list[str] = []

    try:
        save_dir: Path | None = None
        effective_save_dir = (str(args.save_dir).strip() if args.save_dir else None) or cfg.save_dir
        if effective_save_dir is None:
            if not dry_run:
                raise ValueError("config.save_dir が未設定です（保存先フォルダを指定してください）。")
        else:
            save_dir = Path(effective_save_dir)
            # Existence check can hang on UNC paths; use timeout-based probing.
            if not dry_run:
                exists = _test_path_with_timeout(save_dir, timeout_seconds=8.0)
                if exists is not True:
                    raise ValueError(f"保存先フォルダが存在しません/到達できません: {save_dir}")
            else:
                # In dry-run/scan-only, do not block on network paths.
                if _is_unc_path(save_dir):
                    exists = _test_path_with_timeout(save_dir, timeout_seconds=2.0)
                    if exists is False:
                        _append_log(
                            log_path, f"[WARN] save_dir unreachable (dry-run): {save_dir}"
                        )
                    elif exists is None:
                        _append_log(
                            log_path,
                            f"[WARN] save_dir check timed out/failed (dry-run): {save_dir}",
                        )
                else:
                    if not save_dir.exists():
                        _append_log(
                            log_path, f"[WARN] save_dir does not exist (dry-run): {save_dir}"
                        )

        if cfg.outlook is None:
            raise ValueError("config.outlook が未設定です。")

        outlook_cfg = cfg.outlook
        max_messages = args.max_messages if args.max_messages is not None else outlook_cfg.max_messages

        allow_re = re.compile(outlook_cfg.subject_allow_regex) if outlook_cfg.subject_allow_regex else None
        deny_re = re.compile(outlook_cfg.subject_deny_regex) if outlook_cfg.subject_deny_regex else None

        outlook_profile = (
            str(args.outlook_profile).strip()
            if args.outlook_profile
            else (outlook_cfg.profile_name or None)
        )
        folder_path = (
            str(args.outlook_folder_path).strip()
            if args.outlook_folder_path
            else outlook_cfg.folder_path
        )
        if outlook_profile:
            src = "cli" if args.outlook_profile else "config"
            _append_log(log_path, f"using outlook profile ({src}): {outlook_profile}")
        if args.outlook_folder_path:
            _append_log(log_path, f"using outlook folder_path (cli): {folder_path}")

        mapi = _outlook_namespace(profile_name=outlook_profile)
        folder = _resolve_outlook_folder(mapi, folder_path)
        _append_log(log_path, f"resolved outlook folder: {folder_path}")

        effective_unread_only = False if bool(args.include_read) else bool(outlook_cfg.unread_only)
        if args.include_read:
            _append_log(log_path, "override: include_read=true -> unread_only=false")

        items = _iter_mail_items(folder, effective_unread_only, max_messages=max_messages)
        _append_log(log_path, f"loaded messages: {len(items)} (unread_only={effective_unread_only})")

        # Restrict by received time if configured.
        if outlook_cfg.received_within_days is not None:
            cutoff = datetime.now() - timedelta(days=outlook_cfg.received_within_days)
            kept = []
            for it in items:
                rt = _safe_received_time(it)
                if rt and rt >= cutoff:
                    kept.append(it)
            items = kept
            _append_log(log_path, f"filtered by received_within_days: {len(items)}")

        password_notes: list[PasswordNote] = []
        candidates: list[Any] = []
        scanned = 0
        for it in items:
            scanned += 1
            try:
                subject = str(it.Subject or "")
            except Exception:
                subject = ""

            if not _subject_allowed(subject, allow_re) or _subject_denied(subject, deny_re):
                continue

            if _is_password_mail(subject):
                try:
                    body = str(it.Body or "")
                except Exception:
                    body = ""
                pw = _extract_password(body)
                rt = _safe_received_time(it)
                if pw and rt:
                    password_notes.append(
                        PasswordNote(received_time=rt, subject=subject, password=pw)
                    )
            candidates.append(it)

        _append_log(
            log_path,
            f"candidates={len(candidates)} password_notes={len(password_notes)}",
        )

        saved_rows: list[SavedAttachment] = []
        url_only_tasks: list[UrlOnlyTask] = []

        for it in candidates:
            try:
                subject = str(it.Subject or "")
            except Exception:
                subject = ""

            sender = _safe_sender(it)
            rt_dt = _safe_received_time(it) or datetime.now()
            rt_s = rt_dt.strftime("%Y-%m-%d %H:%M:%S")

            try:
                entry_id = str(it.EntryID)
            except Exception:
                entry_id = f"(no_entry_id:{rt_s})"

            unresolved_before_mail = len(unresolved)

            # URL-only detection (body) for later; avoid logging sensitive bodies.
            try:
                body = str(it.Body or "")
            except Exception:
                body = ""
            urls = _extract_urls(body)

            # Save PDF attachments.
            attachments_saved = 0
            try:
                atts = it.Attachments
                att_count = int(atts.Count)
            except Exception:
                att_count = 0
                atts = None

            if att_count <= 0:
                if urls:
                    url_only_tasks.append(
                        UrlOnlyTask(
                            message_entry_id=entry_id,
                            subject=subject,
                            sender=sender,
                            received_time=rt_s,
                            urls=tuple(urls),
                        )
                    )
                continue

            for j in range(1, att_count + 1):
                try:
                    att = atts.Item(j)
                    att_name = str(att.FileName or "")
                except Exception:
                    continue
                att_name_l = att_name.lower().strip()
                is_pdf = att_name_l.endswith(".pdf")
                is_zip = att_name_l.endswith(".zip")
                if not (is_pdf or is_zip):
                    continue

                received_ymd = rt_dt.strftime("%Y%m%d")
                subj_slug = _slug_subject(subject)
                att_slug = _sanitize_filename(att_name)
                tmp_name = f"{received_ymd}__{subj_slug}__{att_slug}"
                tmp_name = _sanitize_filename(tmp_name)

                if dry_run:
                    dest_preview = (save_dir / tmp_name) if save_dir else Path(tmp_name)
                    kind = "zip" if is_zip else "pdf"
                    _append_log(
                        log_path,
                        f"[DRY] save attachment({kind}): {att_name} -> {dest_preview}",
                    )
                    if is_pdf:
                        # fake sha for report
                        saved_rows.append(
                            SavedAttachment(
                                message_entry_id=entry_id,
                                message_subject=subject,
                                sender=sender,
                                received_time=rt_s,
                                attachment_name=att_name,
                                saved_path=str(dest_preview),
                                original_saved_path=str(dest_preview),
                                vendor=None,
                                issue_date=None,
                                amount=None,
                                invoice_no=None,
                                sha256="(dry-run)",
                                was_encrypted=False,
                                decrypted_path=None,
                                encrypted_original_path=None,
                            )
                        )
                        attachments_saved += 1
                    continue

                if save_dir is None:
                    raise RuntimeError("save_dir must be set in execute mode")
                attachments_dir = run_dir / "attachments"
                _ensure_dir(attachments_dir)

                if is_pdf:
                    dest_path = _unique_path(attachments_dir / tmp_name)
                    _append_log(
                        log_path, f"save attachment(pdf): {att_name} -> {dest_path}"
                    )
                    att.SaveAsFile(str(dest_path))
                    saved_rows.append(
                        _process_saved_pdf_file(
                            cfg=cfg,
                            pdf_path=dest_path,
                            attachment_name=att_name,
                            entry_id=entry_id,
                            subject=subject,
                            sender=sender,
                            received_dt=rt_dt,
                            received_time_s=rt_s,
                            password_notes=password_notes,
                            save_dir=save_dir,
                            run_dir=run_dir,
                            log_path=log_path,
                            unresolved=unresolved,
                        )
                    )
                    attachments_saved += 1
                    continue

                # ZIP attachment: extract PDFs and process each.
                zip_path = _unique_path(attachments_dir / tmp_name)
                _append_log(log_path, f"save attachment(zip): {att_name} -> {zip_path}")
                att.SaveAsFile(str(zip_path))

                extracted_parent = attachments_dir / "extracted"
                _ensure_dir(extracted_parent)
                extracted_dir = _unique_dir(
                    extracted_parent / _sanitize_filename(zip_path.stem)
                )
                _ensure_dir(extracted_dir)

                pw_candidates = _candidate_passwords_for_time(
                    target_time=rt_dt,
                    notes=password_notes,
                    window_minutes=cfg.decrypt_password_window_minutes,
                )
                attempts: list[str | None] = [None] + list(pw_candidates)
                extracted_pdfs: list[Path] = []
                last_error: Exception | None = None
                for pw in attempts:
                    _recreate_dir(extracted_dir)
                    try:
                        extracted_pdfs = _extract_pdf_members_from_zip(
                            zip_path,
                            password=pw,
                            out_dir=extracted_dir,
                            log_path=log_path,
                        )
                        last_error = None
                        break
                    except Exception as e:
                        last_error = e
                        if _is_wrong_zip_password_error(e) and pw is not attempts[-1]:
                            _append_log(
                                log_path,
                                f"[WARN] zip extract failed (try next password): {zip_path.name} error={e}",
                            )
                            continue
                        break

                if last_error is not None:
                    hint = ""
                    if isinstance(last_error, NotImplementedError) and (not _PYZIPPER_AVAILABLE):
                        hint = " / AES暗号ZIPの可能性があります（pyzipperが必要）。"
                    unresolved.append(
                        f"ZIP展開に失敗: {zip_path.name} (subject={subject}) error={last_error}{hint}"
                    )
                    continue

                if not extracted_pdfs:
                    unresolved.append(
                        f"ZIP内にPDFが見つかりません: {zip_path.name} (subject={subject})"
                    )
                    continue

                for pdf_path in extracted_pdfs:
                    try:
                        rel = str(pdf_path.relative_to(extracted_dir))
                    except Exception:
                        rel = pdf_path.name
                    display_name = f"{att_name}::{rel}"
                    saved_rows.append(
                        _process_saved_pdf_file(
                            cfg=cfg,
                            pdf_path=pdf_path,
                            attachment_name=display_name,
                            entry_id=entry_id,
                            subject=subject,
                            sender=sender,
                            received_dt=rt_dt,
                            received_time_s=rt_s,
                            password_notes=password_notes,
                            save_dir=save_dir,
                            run_dir=run_dir,
                            log_path=log_path,
                            unresolved=unresolved,
                        )
                    )
                    attachments_saved += 1

            if attachments_saved == 0 and urls:
                url_only_tasks.append(
                    UrlOnlyTask(
                        message_entry_id=entry_id,
                        subject=subject,
                        sender=sender,
                        received_time=rt_s,
                        urls=tuple(urls),
                    )
                )

            # Mimic the human workflow: reading/handling a mail marks it as processed.
            # This is intentionally best-effort to avoid blocking invoice collection.
            if (
                (not dry_run)
                and bool(outlook_cfg.mark_as_read_on_success)
                and attachments_saved > 0
                and len(unresolved) == unresolved_before_mail
            ):
                try:
                    it.UnRead = False
                    it.Save()
                    _append_log(log_path, f"marked as read: entry_id={entry_id}")
                except Exception as e:
                    _append_log(
                        log_path,
                        f"[WARN] failed to mark as read: entry_id={entry_id} error={e}",
                    )

        # Merge/Print targets (prefer decrypted if exists). Skip existence checks in dry-run/scan.
        printable: list[Path] = []
        if not dry_run:
            for r in saved_rows:
                p = Path(r.decrypted_path) if r.decrypted_path else Path(r.saved_path)
                if p.exists():
                    printable.append(p)

        if not dry_run and cfg.merge.enabled and printable:
            merged = run_dir / cfg.merge.output_name
            _append_log(log_path, f"merge pdfs: {len(printable)} -> {merged}")
            _merge_pdfs(printable, merged)
            merged_pdf_path = str(merged)

        # Print (jidoka: do not print in dry-run)
        if do_print and printable:
            printer = cfg.print.printer_name or _default_printer()
            if cfg.print.method != "shell":
                raise ValueError(f"未対応のprint.methodです: {cfg.print.method}")

            targets = [Path(merged_pdf_path)] if merged_pdf_path else printable
            for p in targets:
                _append_log(log_path, f"print: {p} -> printer={printer or '(default)'}")
                _print_via_shell(p, printer_name=printer)
                printed_paths.append(str(p))
                time.sleep(1.0)  # small gap to avoid overwhelming the print spooler

        # URL-only tasks are unresolved by default (unless fail_on_url_only_mail is false)
        if (not scan_only) and cfg.fail_on_url_only_mail and url_only_tasks:
            unresolved.append(f"URLのみメールが{len(url_only_tasks)}件あります（Web請求の自動DL未対応/未設定）。")

        finished_at = datetime.now()
        report = RunReport(
            run_id=run_id,
            started_at=started_at.isoformat(timespec="seconds"),
            finished_at=finished_at.isoformat(timespec="seconds"),
            dry_run=dry_run,
            save_dir=str(save_dir) if save_dir else None,
            outlook_folder_path=folder_path,
            scanned_messages=scanned,
            saved_attachments=tuple(saved_rows),
            url_only_tasks=tuple(url_only_tasks),
            merged_pdf_path=merged_pdf_path,
            printed_paths=tuple(printed_paths),
            unresolved=tuple(unresolved),
        )
        _write_report_json(run_dir / "report.json", report)
        _write_report_csv(run_dir / "report.csv", saved_rows)

        if unresolved:
            _append_log(log_path, f"unresolved_count={len(unresolved)}")
            if mail_enabled:
                _send_error_mail(
                    cfg=cfg,
                    run_id=run_id,
                    run_dir=run_dir,
                    summary="未解決項目があるため処理を停止しました。",
                    details=unresolved,
                    dry_run=mail_dry_run,
                )
            return 2

        if scan_only:
            _append_log(log_path, "scan_only done")
            return 0

        if mail_enabled:
            _send_success_mail(
                cfg=cfg, report=report, run_dir=run_dir, dry_run=mail_dry_run
            )
        _append_log(log_path, "success")
        return 0

    except Exception as e:
        tb = traceback.format_exc()
        _append_log(log_path, f"exception: {e}\n{tb}")
        if mail_enabled:
            try:
                _send_error_mail(
                    cfg=cfg,
                    run_id=run_id,
                    run_dir=run_dir,
                    summary=str(e),
                    details=[tb],
                    dry_run=mail_dry_run,
                )
            except Exception:
                # last resort: do not hide the original failure; still return non-zero.
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
