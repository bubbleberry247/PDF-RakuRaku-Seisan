# -*- coding: utf-8 -*-
"""
Email notification utilities (Outlook COM).

Design goals:
- HTML email with clickable file hyperlinks (Outlook HTMLBody).
- Works without SMTP dependencies (corporate environment friendly).
- Dry-run mode for safe testing.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


try:
    import win32com.client as win32  # type: ignore

    _OUTLOOK_AVAILABLE = True
except Exception:
    _OUTLOOK_AVAILABLE = False


def file_uri(path: Path) -> str:
    # Outlook recognizes file:/// links. Use forward slashes.
    p = path.resolve()
    return "file:///" + p.as_posix()


def html_link_to_path(path: Path, label: str | None = None) -> str:
    display = label if label is not None else str(path)
    # Escape label to avoid breaking HTML mail (paths may contain '&', '<', etc).
    return f"<a href=\"{file_uri(path)}\">{html.escape(display)}</a>"


def _join_addresses(addrs: Sequence[str] | None) -> str:
    if not addrs:
        return ""
    return ";".join([a.strip() for a in addrs if a and a.strip()])


@dataclass(frozen=True)
class OutlookEmail:
    to: Sequence[str]
    subject: str
    html_body: str
    cc: Sequence[str] | None = None
    attachments: Sequence[Path] | None = None


def send_outlook(email: OutlookEmail, dry_run: bool = False) -> None:
    if dry_run:
        print("=== [DRY-RUN] Outlook email ===")
        print(f"To: {_join_addresses(email.to)}")
        print(f"CC: {_join_addresses(email.cc)}")
        print(f"Subject: {email.subject}")
        print("HTMLBody:")
        print(email.html_body)
        if email.attachments:
            print("Attachments:")
            for p in email.attachments:
                print(f"- {p}")
        print("=== [/DRY-RUN] ===")
        return

    if not _OUTLOOK_AVAILABLE:
        raise RuntimeError("Outlook COM is not available (pywin32/win32com is required).")

    outlook = win32.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)
    mail.To = _join_addresses(email.to)
    mail.Subject = email.subject
    mail.HTMLBody = email.html_body
    if email.cc:
        mail.CC = _join_addresses(email.cc)
    if email.attachments:
        for p in email.attachments:
            mail.Attachments.Add(str(p.resolve()))
    mail.Send()


def build_simple_html(
    title: str,
    paragraphs: Iterable[str],
    bullets: Iterable[str] | None = None,
) -> str:
    ps = "\n".join([f"<p>{p}</p>" for p in paragraphs])
    if bullets:
        lis = "\n".join([f"<li>{b}</li>" for b in bullets])
        ul = f"<ul>\n{lis}\n</ul>"
    else:
        ul = ""
    return f"""\
<html>
  <body>
    <h3>{title}</h3>
    {ps}
    {ul}
  </body>
</html>
"""
