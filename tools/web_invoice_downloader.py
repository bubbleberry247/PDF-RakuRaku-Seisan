# -*- coding: utf-8 -*-
"""
Web Invoice Portal PDF Downloader
Playwright-based download for 楽楽明細, BtoB Infomart, ダイオーHS Newfile portals.
Integrates with outlook_save_pdf_and_batch_print.py via dispatch_web_download().

Usage:
    from web_invoice_downloader import (
        WebDownloadConfig, VendorWebConfig, dispatch_web_download, cleanup_web_sessions,
    )

Tested flows:
    - 楽楽明細: C:\\tmp\\kyowa_pdf_flow.py
    - BtoB Infomart: C:\\tmp\\btob_pdf_v2.py
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import re
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VendorWebConfig:
    """Configuration for a single web invoice vendor."""
    handler_id: str           # "rakuraku_meisai" | "btob_infomart" | "daiohs_newfile"
    target_name: str          # Credential Manager target name
    sender_pattern: str       # regex for sender email matching
    url_pattern: str          # regex for URL matching in email body
    options: dict = field(default_factory=dict)  # vendor-specific (login_url, etc.)


@dataclass(frozen=True)
class WebDownloadConfig:
    """Top-level config for web invoice downloading."""
    enabled: bool = False
    headless: bool = True
    download_timeout_ms: int = 30000
    vendors: tuple = ()       # tuple[VendorWebConfig, ...]


@dataclass
class WebDownloadResult:
    """Result of a web download attempt."""
    pdfs: list = field(default_factory=list)    # list[Path]
    errors: list = field(default_factory=list)  # list[str]


# ---------------------------------------------------------------------------
# Credential helper (Windows Credential Manager via ctypes)
# ---------------------------------------------------------------------------

_advapi32 = ctypes.windll.advapi32
_CRED_TYPE_GENERIC = 1


class _CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.wintypes.DWORD),
        ("Type", ctypes.wintypes.DWORD),
        ("TargetName", ctypes.wintypes.LPWSTR),
        ("Comment", ctypes.wintypes.LPWSTR),
        ("LastWritten", ctypes.wintypes.FILETIME),
        ("CredentialBlobSize", ctypes.wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", ctypes.wintypes.DWORD),
        ("AttributeCount", ctypes.wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", ctypes.wintypes.LPWSTR),
        ("UserName", ctypes.wintypes.LPWSTR),
    ]


_PCREDENTIAL = ctypes.POINTER(_CREDENTIAL)


def _get_credential(target_name: str) -> tuple[str, str]:
    """Read username/password from Windows Credential Manager.

    Returns:
        (username, password) tuple.

    Raises:
        RuntimeError: If CredReadW fails (target not found, etc.).
    """
    cred_ptr = _PCREDENTIAL()
    ok = _advapi32.CredReadW(target_name, _CRED_TYPE_GENERIC, 0, ctypes.byref(cred_ptr))
    if not ok:
        raise RuntimeError(f"CredReadW failed for '{target_name}'")
    c = cred_ptr.contents
    u = c.UserName or ""
    p = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize).decode(
        "utf-16-le", errors="replace"
    )
    _advapi32.CredFree(cred_ptr)
    return u, p


# ---------------------------------------------------------------------------
# Browser session cache
# ---------------------------------------------------------------------------

_pw_instance = None  # Single shared Playwright instance
_browser_cache: dict[str, dict] = {}  # cache_key (target_name) -> {"browser", "context", "page"}


def _get_or_create_session(cache_key: str, headless: bool) -> dict:
    """Get or create a Playwright browser session.

    Sessions are cached by cache_key (typically vendor.target_name) so each
    vendor gets its own isolated browser instance. This prevents cookie/login
    state leaking between tenants that share the same handler_id.
    A single shared Playwright instance is used across all sessions.
    """
    global _pw_instance

    if cache_key in _browser_cache:
        return _browser_cache[cache_key]

    if _pw_instance is None:
        from playwright.sync_api import sync_playwright
        _pw_instance = sync_playwright().start()

    browser = _pw_instance.chromium.launch(headless=headless)
    ctx = browser.new_context(
        accept_downloads=True,
        viewport={"width": 1920, "height": 1080},
    )
    page = ctx.new_page()
    _browser_cache[cache_key] = {
        "browser": browser,
        "context": ctx,
        "page": page,
    }
    return _browser_cache[cache_key]


def cleanup_web_sessions() -> None:
    """Close all cached browser sessions. Call after mail loop ends."""
    global _pw_instance
    for hid, session in list(_browser_cache.items()):
        try:
            session["browser"].close()
        except Exception:
            pass
    _browser_cache.clear()
    if _pw_instance is not None:
        try:
            _pw_instance.stop()
        except Exception:
            pass
        _pw_instance = None


# ---------------------------------------------------------------------------
# Vendor matching
# ---------------------------------------------------------------------------

def _match_vendor(
    cfg: WebDownloadConfig, sender: str, urls: list[str]
) -> VendorWebConfig | None:
    """Match sender AND URLs against vendor patterns. Return first match or None.

    Both sender_pattern and url_pattern must match for a vendor to be selected.
    """
    for v in cfg.vendors:
        sender_match = bool(re.search(v.sender_pattern, sender, re.IGNORECASE))
        url_match = any(re.search(v.url_pattern, u, re.IGNORECASE) for u in urls)
        if sender_match and url_match:
            return v
    return None


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------

def _append_log(log_path: Path, msg: str) -> None:
    """Append a timestamped log line."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


# ---------------------------------------------------------------------------
# Duplicate prevention
# ---------------------------------------------------------------------------

def _marker_path(download_dir: Path, target_name: str, dt: datetime) -> Path:
    """Return marker file path for target_name + year-month."""
    ym = dt.strftime("%Y%m")
    return download_dir / f"{target_name}_{ym}.marker"


def _is_already_downloaded(download_dir: Path, target_name: str, dt: datetime) -> bool:
    """Check if a marker file exists for this vendor/month."""
    return _marker_path(download_dir, target_name, dt).exists()


def _write_marker(download_dir: Path, target_name: str, dt: datetime, pdf_paths: list[Path]) -> None:
    """Write a marker file recording downloaded PDFs."""
    mp = _marker_path(download_dir, target_name, dt)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"downloaded_at={ts}"]
    for p in pdf_paths:
        lines.append(str(p))
    mp.write_text("\n".join(lines), encoding="utf-8")


def _extract_pdfs_from_zip(zip_path: Path, extract_dir: Path, log_path: Path) -> list[Path]:
    """Extract PDF files from a ZIP archive. Returns list of extracted PDF paths."""
    pdfs = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.lower().endswith('.pdf'):
                    extracted = extract_dir / Path(name).name
                    with zf.open(name) as src, open(extracted, 'wb') as dst:
                        dst.write(src.read())
                    pdfs.append(extracted)
                    _append_log(log_path, f"[zip] Extracted: {extracted}")
        if pdfs:
            zip_path.unlink(missing_ok=True)
            _append_log(log_path, f"[zip] Removed source ZIP: {zip_path}")
    except zipfile.BadZipFile:
        _append_log(log_path, f"[zip] Not a valid ZIP, treating as-is: {zip_path}")
        if zip_path.suffix.lower() == '.zip':
            pdf_path = zip_path.with_suffix('.pdf')
            zip_path.rename(pdf_path)
            pdfs.append(pdf_path)
    return pdfs


# ---------------------------------------------------------------------------
# Handler: 楽楽明細 (rakuraku_meisai)
# ---------------------------------------------------------------------------

def _handle_rakuraku_meisai(
    *,
    session: dict,
    vendor: VendorWebConfig,
    username: str,
    password: str,
    subject: str,
    received_dt: datetime,
    download_dir: Path,
    download_timeout_ms: int,
    log_path: Path,
) -> list[Path]:
    """Download PDF from 楽楽明細 portal.

    Flow (from tested kyowa_pdf_flow.py):
        Login (#loginId, #password, button[type="submit"])
        → Top page → Find links with invoice keywords
        → Navigate to invoice list
        → Find PDF download link/button
        → expect_download → save to download_dir

    Returns:
        List of downloaded PDF paths.
    """
    page = session["page"]
    downloaded: list[Path] = []

    login_url = vendor.options.get("login_url", "")
    if not login_url:
        raise ValueError("rakuraku_meisai requires options.login_url")

    # Step 1: Login
    _append_log(log_path, f"[rakuraku] Navigating to login: {login_url}")
    page.goto(login_url, wait_until="networkidle", timeout=30000)
    page.fill("#loginId", username)
    page.fill("#password", password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=30000)
    time.sleep(2)
    _append_log(log_path, f"[rakuraku] Logged in. URL: {page.url}")

    # Step 2: Find invoice list links
    invoice_kw = ["請求", "明細", "PDF", "ダウンロード", "帳票", "書類", "一覧"]
    links = page.evaluate(
        """() => Array.from(document.querySelectorAll('a')).map(a => ({
            text: a.innerText.trim().substring(0, 80),
            href: a.href
        }))"""
    )

    invoice_links = [
        l for l in links if any(kw in l["text"] for kw in invoice_kw)
    ]
    if not invoice_links:
        # Fallback: check href patterns
        href_kw = ["invoice", "bill", "pdf", "download", "meisai", "list"]
        invoice_links = [
            l for l in links
            if any(kw in l["href"].lower() for kw in href_kw)
        ]

    if not invoice_links:
        raise RuntimeError(
            f"rakuraku: No invoice links found on top page ({page.url}). "
            f"Total links: {len(links)}"
        )

    target = invoice_links[0]
    _append_log(log_path, f"[rakuraku] Navigating to invoice list: {target['text']} -> {target['href']}")
    page.goto(target["href"], wait_until="networkidle", timeout=30000)
    time.sleep(2)

    # Step 3: Find PDF download candidates
    dl_candidates = page.evaluate(
        """() => {
            const r = [];
            document.querySelectorAll('a').forEach(a => {
                const t = (a.innerText||'').trim(), h = a.href||'',
                      oc = a.getAttribute('onclick')||'';
                if (h.match(/pdf|download/i) || oc.match(/pdf|download/i)
                    || t.match(/ダウンロード|PDF|表示|閲覧/))
                    r.push({tag:'a', text:t.substring(0,80), href:h,
                            onclick:oc.substring(0,100)});
            });
            document.querySelectorAll('button').forEach(b => {
                const t = (b.innerText||'').trim(),
                      oc = b.getAttribute('onclick')||'';
                if (t.match(/ダウンロード|PDF|表示|閲覧/) || oc.match(/pdf|download/i))
                    r.push({tag:'button', text:t.substring(0,80),
                            onclick:oc.substring(0,100)});
            });
            return r;
        }"""
    )

    if not dl_candidates:
        raise RuntimeError(
            f"rakuraku: No download candidates on invoice list page ({page.url})"
        )

    _append_log(
        log_path,
        f"[rakuraku] Found {len(dl_candidates)} download candidates. "
        f"Trying first: {dl_candidates[0]['text']}",
    )

    c = dl_candidates[0]
    with page.expect_download(timeout=download_timeout_ms) as dl_info:
        if c["tag"] == "a":
            page.click(f"text={c['text'][:30]}")
        else:
            page.click(f"button:has-text('{c['text'][:30]}')")

    dl = dl_info.value
    save_path = download_dir / dl.suggested_filename
    dl.save_as(str(save_path))
    _append_log(log_path, f"[rakuraku] Downloaded: {save_path}")

    # Handle ZIP files (楽楽明細 returns ZIP from 一括ダウンロード)
    if save_path.suffix.lower() == '.zip':
        extracted = _extract_pdfs_from_zip(save_path, download_dir, log_path)
        if extracted:
            downloaded.extend(extracted)
        else:
            _append_log(log_path, f"[rakuraku] WARN: ZIP contained no PDFs: {save_path}")
            downloaded.append(save_path)
    else:
        downloaded.append(save_path)

    return downloaded


# ---------------------------------------------------------------------------
# Handler: BtoB Infomart (btob_infomart)
# ---------------------------------------------------------------------------

def _handle_btob_infomart(
    *,
    session: dict,
    vendor: VendorWebConfig,
    username: str,
    password: str,
    subject: str,
    received_dt: datetime,
    download_dir: Path,
    download_timeout_ms: int,
    log_path: Path,
) -> list[Path]:
    """Download PDF from BtoB Infomart portal.

    Flow (from tested btob_pdf_v2.py):
        Login (input[name="UID"], input[name="PWD"], input[name="Logon"])
        → /buyer/invoicelist/every/list.page
        → Click amount link (金額リンク: regex /^[0-9,]+$/ and length > 3)
        → Detail page
        → Click #aPrint (dropdown opens)
        → Wait for dropdown #bt-opt-nv-print-box to become visible
        → Click #subLayoutPrintTop with expect_download → save PDF

    CRITICAL: Use expect_download, NOT expect_popup.

    Returns:
        List of downloaded PDF paths.
    """
    page = session["page"]
    downloaded: list[Path] = []

    login_url = vendor.options.get(
        "login_url", "https://www.infomart.co.jp/scripts/logon.asp"
    )
    list_url = vendor.options.get(
        "list_url", "https://wi.infomart.co.jp/buyer/invoicelist/every/list.page"
    )

    # Step 1: Login
    _append_log(log_path, f"[btob] Navigating to login: {login_url}")
    page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    page.fill('input[name="UID"]', username)
    page.fill('input[name="PWD"]', password)
    page.click('input[name="Logon"]')
    page.wait_for_load_state("domcontentloaded", timeout=30000)
    time.sleep(3)
    _append_log(log_path, f"[btob] Logged in. URL: {page.url}")

    # Step 2: Navigate to invoice list
    _append_log(log_path, f"[btob] Navigating to invoice list: {list_url}")
    page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    # Find amount links in the invoice list
    amount_links = page.evaluate(
        """() => {
            const r = [];
            document.querySelectorAll('a').forEach(a => {
                const t = (a.innerText || '').trim();
                if (t.match(/^[0-9,]+$/) && t.length > 3)
                    r.push({text: t});
            });
            return r;
        }"""
    )

    if not amount_links:
        raise RuntimeError(
            f"btob: No amount links found on invoice list ({page.url})"
        )

    _append_log(
        log_path,
        f"[btob] Found {len(amount_links)} amount links on invoice list.",
    )

    # Invoice matching: extract amount from email subject, match against list
    target_link = _btob_match_invoice(subject, amount_links)
    target_text = target_link["text"]

    _append_log(log_path, f"[btob] Clicking amount link: {target_text}")
    page.click(f"a:has-text('{target_text}')")
    page.wait_for_load_state("domcontentloaded", timeout=30000)
    time.sleep(3)
    _append_log(log_path, f"[btob] Detail page: {page.url}")

    # Step 3: Open print dropdown and download PDF
    page.click("#aPrint")
    time.sleep(1)

    # Verify dropdown is open
    disp = page.evaluate(
        "window.getComputedStyle(document.getElementById('bt-opt-nv-print-box')).display"
    )
    _append_log(log_path, f"[btob] Print dropdown display: {disp}")

    # CRITICAL: Use expect_download, NOT expect_popup
    _append_log(log_path, "[btob] Clicking #subLayoutPrintTop with expect_download...")
    with page.expect_download(timeout=download_timeout_ms) as dl_info:
        page.click("#subLayoutPrintTop", timeout=5000)

    dl = dl_info.value
    save_path = download_dir / dl.suggested_filename
    dl.save_as(str(save_path))
    downloaded.append(save_path)
    _append_log(log_path, f"[btob] Downloaded: {save_path}")

    return downloaded


def _btob_match_invoice(
    subject: str, amount_links: list[dict]
) -> dict:
    """Match email subject amount against invoice list amounts.

    Strategy:
        1. Extract amount from email subject (regex for comma-separated numbers).
        2. If a matching amount exists in amount_links, return it.
        3. Otherwise, return the first (latest) amount link.
    """
    # Extract amounts from subject
    amounts_in_subject = re.findall(r"\d{1,3}(?:,\d{3})+", subject)

    if amounts_in_subject:
        for amt_str in amounts_in_subject:
            for link in amount_links:
                if link["text"] == amt_str:
                    return link

    # No match or no amount in subject → take first available (latest)
    return amount_links[0]


# ---------------------------------------------------------------------------
# Handler: ダイオーHS Newfile (daiohs_newfile)
# ---------------------------------------------------------------------------

def _handle_daiohs_newfile(
    *,
    session: dict,
    vendor: VendorWebConfig,
    username: str,
    password: str,
    subject: str,
    received_dt: datetime,
    download_dir: Path,
    download_timeout_ms: int,
    log_path: Path,
) -> list[Path]:
    """Download PDF from Newfile portal (newfile.jp).

    Flow:
        Login (#loginId, #password, button[name="doLogin"])
        → Navigate to invoice list: /upfile/mypage/eform/invoice.html
        → Find <a> links with href containing viewer.html?uri=mypage/eform/file/{ID}
        → Extract file URI, construct direct download URL: /upfile/mypage/eform/file/{ID}
        → page.expect_download() + page.goto(direct_url) → save PDF

    Returns:
        List of downloaded PDF paths (single latest invoice).
    """
    page = session["page"]
    downloaded: list[Path] = []

    login_url = vendor.options.get("login_url", "")
    if not login_url:
        raise ValueError("daiohs_newfile requires options.login_url")

    # Step 1: Login
    _append_log(log_path, f"[newfile] Navigating to login: {login_url}")
    page.goto(login_url, wait_until="networkidle", timeout=30000)
    page.fill("#loginId", username)
    page.fill("#password", password)
    page.click('button[name="doLogin"]')
    page.wait_for_load_state("networkidle", timeout=30000)
    time.sleep(2)
    _append_log(log_path, f"[newfile] Logged in. URL: {page.url}")

    # Step 2: Navigate to invoice list page
    invoice_list_url = "https://newfile.jp/upfile/mypage/eform/invoice.html"
    _append_log(log_path, f"[newfile] Navigating to invoice list: {invoice_list_url}")
    page.goto(invoice_list_url, wait_until="networkidle", timeout=30000)
    time.sleep(2)
    _append_log(log_path, f"[newfile] Invoice list loaded. URL: {page.url}")

    # Step 3: Find all links whose href contains viewer.html?uri=mypage/eform/file/
    file_links = page.evaluate(
        """() => {
            const r = [];
            document.querySelectorAll('a').forEach(a => {
                const h = a.href || '';
                if (h.includes('viewer.html?uri=mypage/eform/file/')) {
                    // Extract the uri query parameter value
                    const m = h.match(/[?&]uri=([^&]+)/);
                    const uri = m ? m[1] : '';
                    r.push({
                        text: (a.innerText || '').trim(),
                        href: h,
                        uri: uri
                    });
                }
            });
            return r;
        }"""
    )

    if not file_links:
        raise RuntimeError(
            f"newfile: No invoice file links found on invoice list page ({page.url}). "
            f"Expected links with href containing 'viewer.html?uri=mypage/eform/file/'"
        )

    _append_log(
        log_path,
        f"[newfile] Found {len(file_links)} invoice file link(s). "
        f"Latest: {file_links[0]['text']} (uri={file_links[0]['uri']})",
    )

    # Step 4: Download the FIRST (latest) invoice PDF via direct URL
    latest = file_links[0]
    # Direct download URL: https://newfile.jp/upfile/ + uri_value
    # uri_value is e.g. "mypage/eform/file/479735"
    direct_url = f"https://newfile.jp/upfile/{latest['uri']}"
    filename = latest["text"] if latest["text"] else "invoice.pdf"
    # Ensure filename ends with .pdf
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    _append_log(
        log_path,
        f"[newfile] Downloading latest invoice: {filename} from {direct_url}",
    )

    with page.expect_download(timeout=download_timeout_ms) as dl_info:
        # Use JavaScript to create and click a temporary link instead of page.goto(),
        # because goto() throws "Download is starting" error on direct PDF URLs.
        page.evaluate(
            f"""() => {{
                const a = document.createElement('a');
                a.href = '{direct_url}';
                a.download = '{filename}';
                document.body.appendChild(a);
                a.click();
                a.remove();
            }}"""
        )

    dl = dl_info.value
    save_path = download_dir / filename
    dl.save_as(str(save_path))
    downloaded.append(save_path)
    _append_log(log_path, f"[newfile] Downloaded: {save_path}")

    return downloaded


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

_HANDLER_REGISTRY: dict[str, Callable] = {
    "rakuraku_meisai": _handle_rakuraku_meisai,
    "btob_infomart": _handle_btob_infomart,
    "daiohs_newfile": _handle_daiohs_newfile,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def dispatch_web_download(
    *,
    cfg: WebDownloadConfig,
    sender: str,
    urls: list[str],
    subject: str,
    received_dt: datetime,
    download_dir: Path,
    log_path: Path,
    dry_run: bool,
    scan_only: bool,
) -> WebDownloadResult:
    """Download PDFs from matched web vendor portal.

    Returns:
        WebDownloadResult with pdfs and errors.

    Never raises — all exceptions caught and added to result.errors.
    On dry_run or scan_only: log match info only, no browser launch.
    """
    result = WebDownloadResult()

    # Check if web download is enabled at config level
    if not cfg.enabled:
        return result

    try:
        # 1. Match vendor
        vendor = _match_vendor(cfg, sender, urls)
        if vendor is None:
            return result

        _append_log(
            log_path,
            f"[web] Vendor matched: handler={vendor.handler_id}, "
            f"sender={sender}, subject={subject[:60]}",
        )

        # 2. Dry run / scan only → log and return
        if dry_run or scan_only:
            _append_log(
                log_path,
                f"[DRY] Would download from {vendor.handler_id} "
                f"(target={vendor.target_name})",
            )
            return result

        # 3. Duplicate check
        if _is_already_downloaded(download_dir, vendor.target_name, received_dt):
            _append_log(
                log_path,
                f"[SKIP] Already downloaded: {vendor.handler_id} "
                f"for {received_dt.strftime('%Y-%m')}",
            )
            return result

        # 4. Get credential
        try:
            username, password = _get_credential(vendor.target_name)
        except RuntimeError as e:
            msg = f"[WARN] Credential failed for '{vendor.target_name}': {e}"
            _append_log(log_path, msg)
            result.errors.append(msg)
            return result

        # 5. Get/create browser session
        handler_fn = _HANDLER_REGISTRY.get(vendor.handler_id)
        if handler_fn is None:
            msg = f"[ERROR] Unknown handler_id: {vendor.handler_id}"
            _append_log(log_path, msg)
            result.errors.append(msg)
            return result

        session = _get_or_create_session(vendor.target_name, cfg.headless)

        # 6. Ensure download_dir exists
        download_dir.mkdir(parents=True, exist_ok=True)

        # 7. Dispatch to handler
        pdfs = handler_fn(
            session=session,
            vendor=vendor,
            username=username,
            password=password,
            subject=subject,
            received_dt=received_dt,
            download_dir=download_dir,
            download_timeout_ms=cfg.download_timeout_ms,
            log_path=log_path,
        )

        result.pdfs.extend(pdfs)

        # 8. Write marker to prevent re-download
        if pdfs:
            _write_marker(download_dir, vendor.target_name, received_dt, pdfs)
            _append_log(
                log_path,
                f"[web] Success: {vendor.handler_id} downloaded {len(pdfs)} PDF(s)",
            )

    except Exception as e:
        msg = f"[ERROR] Web download failed: {e}"
        _append_log(log_path, msg)
        result.errors.append(msg)

    return result
