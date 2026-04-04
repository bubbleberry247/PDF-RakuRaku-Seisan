# -*- coding: utf-8 -*-
"""
Scenario 70: 楽楽精算「支払確定（支払先）」自動化（Playwright / Edge）

重要:
- 支払確定は金銭に直結します。
- `--execute` を付けない限り、確認ダイアログの OK は押しません（ドライラン）。

Usage examples:
    python rakuraku_payment_confirm.py --payment-date 2025/12/30 --execute
    python rakuraku_payment_confirm.py --payment-date 2025/12/30 --dry-run-mail
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import traceback
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence

sys.path.insert(0, str(Path(__file__).parent))

from common.credential_manager import get_credential, get_credential_value
from common.email_notifier import (
    OutlookEmail,
    build_simple_html,
    html_link_to_path,
    send_outlook,
)
from common.scenario70_config import (
    DEFAULT_CONFIG_DIR,
    get_env as get_scenario70_env,
    load_config as load_scenario70_config,
    split_mail_list,
)

try:
    from playwright.sync_api import (
        Browser,
        BrowserContext,
        Frame,
        Locator,
        Page,
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )

    _PLAYWRIGHT_AVAILABLE = True
except Exception:
    _PLAYWRIGHT_AVAILABLE = False


DEFAULT_BASE_URL = "https://rsatonality.rakurakuseisan.jp/rHqny3DOsIa/"
DEFAULT_ARTIFACT_DIR = r"C:\ProgramData\RK10\Robots\70楽楽精算支払い確定\artifacts"
DEFAULT_DEPARTMENT_CODE = "300"
DEFAULT_TRANSFER_SOURCE = "三菱UFJ銀行（当座）/110"

MAIL_TO_SUCCESS = ["kanri.tic@tokai-ic.co.jp"]
MAIL_TO_ERROR = ["kanri.tic@tokai-ic.co.jp"]
MAIL_CC_ERROR = ["kalimistk@gmail.com"]

PAYMENT_SLIP_NO_RE = re.compile(r"\b\d{8}\b")
DATE_RE = re.compile(r"\b\d{4}/\d{2}/\d{2}\b")
YEN_AMOUNT_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")
KNOWN_PAYMENT_METHODS = ("総合振込", "都度振込", "口座振替")
RESULT_RANGE_RE = re.compile(r"(\d+)件中\s*(\d+)件.*?(\d+)件目")
DISPLAY_COUNT_RE = re.compile(r"表示件数\s*(\d+)件")
SELECTED_COUNT_RE = re.compile(r"(\d+)件中\s*(\d+)件\s*が選択されています")
CREDENTIAL_TARGET_ALIASES = (
    "RK10_RakurakuSeisan",
    "楽楽精算",
)


def _normalize_payment_date(s: str) -> str:
    s = s.strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[0:4]}/{s[4:6]}/{s[6:8]}"
    if re.fullmatch(r"\d{4}/\d{1,2}/\d{1,2}", s):
        y, m, d = s.split("/")
        return f"{y}/{int(m):02d}/{int(d):02d}"
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", s):
        y, m, d = s.split("-")
        return f"{y}/{int(m):02d}/{int(d):02d}"
    raise ValueError(f"支払日形式が不正です: {s} (expected YYYY/MM/DD)")


def _split_ymd(date_yyyy_mm_dd: str) -> tuple[str, str, str]:
    y, m, d = date_yyyy_mm_dd.split("/")
    return y, m, d


def _mask_login_id(login_id: str) -> str:
    login_id = login_id.strip()
    if len(login_id) <= 2:
        return "**"
    return login_id[:2] + "*" * (len(login_id) - 2)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _now_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _read_text(locator: Locator) -> str:
    try:
        return (locator.text_content() or "").strip()
    except Exception:
        return ""


def _parse_int_yen(s: str) -> int:
    # "1,508,256円" or "1,508,256" -> 1508256
    s = s.replace("円", "").replace(",", "").strip()
    return int(s)


@dataclass(frozen=True)
class SlipRecord:
    page_no: int
    row_group_index: int
    slip_no: str
    request_date: str | None
    approval_date: str | None
    payment_date: str
    payment_method: str | None
    payment_method_source: str
    amount_yen: int | None
    vendor: str | None
    applicant: str | None
    note: str | None
    fee_burden: str | None
    original_save: str | None
    checkbox_name: str | None
    decision: str
    decision_reason: str
    raw_text: str


@dataclass
class RunResult:
    run_id: str
    started_at: str
    env_name: str
    base_url: str
    department_code: str
    payment_date: str
    transfer_source: str
    artifact_root: str
    run_dir: str
    selected_records: int = 0
    inventory_records: int = 0
    total_amount_yen: int | None = None
    payment_no: str | None = None
    summary_path: str | None = None
    report_json_path: str | None = None
    report_path: str | None = None
    selected_report_path: str | None = None
    anomaly_records: int = 0
    anomaly_report_path: str | None = None
    preflight_path: str | None = None
    ledger_path: str | None = None
    ledger_excerpt_path: str | None = None
    status: str = "started"  # started/success/failed/dry_run
    error: str | None = None
    ended_at: str | None = None


@dataclass
class SlipSelectionResult:
    inventory: list[SlipRecord]
    selected: list[SlipRecord]
    anomalies: list[SlipRecord]


@dataclass(frozen=True)
class SearchResultSummary:
    total_count: int
    range_start: int
    range_end: int
    display_count: int | None


@dataclass(frozen=True)
class SelectedCountSummary:
    total_count: int
    selected_count: int


def _detect_payment_method(text: str) -> str | None:
    matches = [method for method in KNOWN_PAYMENT_METHODS if method in text]
    if len(matches) == 1:
        return matches[0]
    return None


def parse_slip_row_text(row_text: str, payment_date: str) -> SlipRecord:
    text = " ".join([t for t in (row_text or "").split() if t])
    slip_match = PAYMENT_SLIP_NO_RE.search(text)
    if not slip_match:
        raise ValueError(f"伝票Noが抽出できません: {text[:120]}")
    slip_no = slip_match.group(0)

    dates = DATE_RE.findall(text)
    # Preserve order; payment_date should appear as one of them.
    request_date: str | None = None
    approval_date: str | None = None
    remaining_dates = [d for d in dates if d != payment_date]
    if len(remaining_dates) >= 2:
        request_date = remaining_dates[0]
        approval_date = remaining_dates[1]

    amounts = YEN_AMOUNT_RE.findall(text)
    amount_yen: int | None = None
    if amounts:
        # In this screen, the per-slip amount is typically the only comma-number in the row.
        # Choose the last one to reduce risk of picking vendor codes earlier in the row.
        amount_yen = _parse_int_yen(amounts[-1])
    payment_method = _detect_payment_method(text)

    return SlipRecord(
        page_no=1,
        row_group_index=1,
        slip_no=slip_no,
        request_date=request_date,
        approval_date=approval_date,
        payment_date=payment_date,
        payment_method=payment_method,
        payment_method_source="row_text" if payment_method else "unresolved",
        amount_yen=amount_yen,
        vendor=None,
        applicant=None,
        note=None,
        fee_burden=None,
        original_save=None,
        checkbox_name=None,
        decision="unclassified",
        decision_reason="fallback_row_text_parse",
        raw_text=text,
    )


def _first_non_empty_line(text: str) -> str | None:
    for line in text.splitlines():
        value = line.strip()
        if value:
            return value
    return None


def _extract_original_save(text: str) -> str | None:
    if "保存不要" in text:
        return "保存不要"
    if "保存要" in text:
        return "保存要"
    return None


def _extract_fee_burden(text: str) -> str | None:
    if "先方負担" in text:
        return "先方負担"
    if "当方負担" in text:
        return "当方負担"
    return None


def _clean_note_text(text: str) -> str | None:
    cleaned = text.replace("先方負担", "").replace("当方負担", "").strip()
    return cleaned or None


def _parse_result_summary_text(text: str) -> SearchResultSummary:
    range_match = RESULT_RANGE_RE.search(text)
    if not range_match:
        raise RuntimeError("検索結果件数を画面から読み取れませんでした")
    display_match = DISPLAY_COUNT_RE.search(text)
    return SearchResultSummary(
        total_count=int(range_match.group(1)),
        range_start=int(range_match.group(2)),
        range_end=int(range_match.group(3)),
        display_count=int(display_match.group(1)) if display_match else None,
    )


def _parse_selected_count_text(text: str) -> SelectedCountSummary:
    match = SELECTED_COUNT_RE.search(text)
    if not match:
        raise RuntimeError("選択件数表示を画面から読み取れませんでした")
    return SelectedCountSummary(
        total_count=int(match.group(1)),
        selected_count=int(match.group(2)),
    )


def parse_slip_block_texts(
    *,
    row1_text: str,
    row2_text: str,
    row3_text: str,
    checkbox_name: str | None,
    page_no: int,
    row_group_index: int,
) -> SlipRecord:
    row1_text = row1_text.strip()
    row2_text = row2_text.strip()
    row3_text = row3_text.strip()
    raw_text = "\n".join([t for t in (row1_text, row2_text, row3_text) if t])
    slip_match = PAYMENT_SLIP_NO_RE.search(row1_text or raw_text)
    if not slip_match:
        raise ValueError(f"伝票Noを抽出できません: {raw_text[:120]}")

    dates = DATE_RE.findall(row1_text)
    request_date = dates[0] if len(dates) >= 1 else None
    approval_date = dates[1] if len(dates) >= 2 else None
    requested_payment_date = dates[2] if len(dates) >= 3 else ""

    amounts = YEN_AMOUNT_RE.findall(row1_text)
    amount_yen = _parse_int_yen(amounts[-1]) if amounts else None
    payment_method = _detect_payment_method(raw_text)
    row1_lines = [line.strip() for line in row1_text.splitlines() if line.strip()]
    applicant = row1_lines[1] if len(row1_lines) >= 2 else None

    return SlipRecord(
        page_no=page_no,
        row_group_index=row_group_index,
        slip_no=slip_match.group(0),
        request_date=request_date,
        approval_date=approval_date,
        payment_date=requested_payment_date,
        payment_method=payment_method,
        payment_method_source="row_text" if payment_method else "unresolved",
        amount_yen=amount_yen,
        vendor=_first_non_empty_line(row2_text),
        applicant=applicant,
        note=_clean_note_text(row3_text),
        fee_burden=_extract_fee_burden(row3_text),
        original_save=_extract_original_save(row1_text),
        checkbox_name=checkbox_name,
        decision="unclassified",
        decision_reason="unclassified",
        raw_text=raw_text,
    )


def classify_slip_record(record: SlipRecord, payment_date: str) -> SlipRecord:
    if record.payment_date != payment_date:
        return replace(record, decision="skipped", decision_reason="payment_date_mismatch")
    if not record.fee_burden:
        return replace(record, decision="anomaly", decision_reason="missing_fee_burden")
    if record.fee_burden != "当方負担":
        return replace(record, decision="anomaly", decision_reason="non_company_fee_burden")
    return replace(record, decision="selected", decision_reason="payment_date_match_and_company_fee")


class RakurakuPaymentConfirmer:
    def __init__(
        self,
        base_url: str,
        artifact_dir: Path,
        credential_name: str = "RK10_RakurakuSeisan",
        headless: bool = False,
    ) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright is not available. Install playwright first.")
        self.base_url = base_url
        self.artifact_dir = artifact_dir
        self.credential_name = credential_name
        self.headless = headless

        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def _get_credentials(self) -> tuple[str, str]:
        # 方法1: 統合資格情報
        for target_name in (self.credential_name, *CREDENTIAL_TARGET_ALIASES):
            try:
                return get_credential(target_name)
            except ValueError:
                pass

        # 方法2: 個別資格情報
        login_id = ""
        password = ""
        try:
            login_id = get_credential_value("ログインID　楽楽精算")
        except ValueError:
            pass
        try:
            password = get_credential_value("パスワード　楽楽精算")
        except ValueError:
            pass
        if login_id and password:
            return (login_id, password)

        raise ValueError(
            "楽楽精算のログイン情報が見つかりません。Windows資格情報マネージャーに登録してください。"
        )

    def _get_main_frame(self) -> Frame | None:
        if not self.page:
            return None
        try:
            main = self.page.frame("main")
            if main:
                return main
            for frame in self.page.frames:
                if "main" in (frame.name or "").lower():
                    return frame
        except Exception:
            return None
        return None

    def start(self) -> None:
        self.playwright = sync_playwright().start()
        # Use Microsoft Edge as required.
        self.browser = self.playwright.chromium.launch(
            channel="msedge",
            headless=self.headless,
            args=["--start-maximized"],
        )
        self.context = self.browser.new_context(viewport={"width": 1920, "height": 1080})
        self.page = self.context.new_page()

    def close(self) -> None:
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def screenshot(self, name: str, full_page: bool = True) -> Path:
        if not self.page:
            raise RuntimeError("page not started")
        shots_dir = self.artifact_dir / "screenshots"
        _ensure_dir(shots_dir)
        path = shots_dir / name
        self.page.screenshot(path=str(path), full_page=full_page)
        return path

    def login(self) -> None:
        if not self.page:
            raise RuntimeError("page not started")

        login_id, password = self._get_credentials()
        self.page.goto(self.base_url, timeout=90_000)
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(2)

        login_input = self.page.locator("input[name='loginId']")
        if login_input.count() == 0:
            login_input = self.page.locator("input[type='text']").first
        login_input.fill(login_id)

        pw_input = self.page.locator("input[type='password']")
        pw_input.fill(password)

        self.page.locator("input[type='submit'], button[type='submit']").first.click()

        # Wait until login form disappears or mainView is reached.
        for _ in range(30):
            time.sleep(1)
            if "mainView" in self.page.url or "Top" in self.page.url:
                break
            if self.page.locator("input[name='loginId']").count() == 0:
                break

    def goto_search_screen(self) -> None:
        if not self.page:
            raise RuntimeError("page not started")
        url = self.base_url.rstrip("/") + "/sapShihaShiharaiKakuteiKensaku/initializeView"
        self.page.goto(url, timeout=90_000)
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        if "sapShihaShiharaiKakuteiKensaku" not in self.page.url:
            raise RuntimeError(f"支払確定（支払先）画面に遷移できませんでした: {self.page.url}")

    def search_by_department(self, department_code: str) -> None:
        if not self.page:
            raise RuntimeError("page not started")

        dept_input = self.page.locator("input[name='bumonCd']").first
        if dept_input.count() == 0:
            dept_input = self.page.locator("input[name='shozokuBumon']").first
        if dept_input.count() == 0:
            dept_input = self.page.locator(
                "xpath=//*[normalize-space()='所属部門']/following::input[1]"
            ).first
        dept_input.wait_for(state="visible", timeout=30_000)
        dept_input.fill(department_code)
        time.sleep(0.5)
        try:
            dept_input.press("Tab")
        except Exception:
            pass

        # 検索
        search_btn = self.page.locator("button:has-text('検索'), input[value='検索']").first
        search_btn.click()
        for _ in range(30):
            time.sleep(1)
            body_text = _read_text(self.page.locator("body").first)
            if "検索条件に一致するデータは見つかりませんでした" in body_text:
                raise RuntimeError("所属部門検索の結果が0件でした")
            if self.page.locator("input[name^='kakutei(']").count() > 0:
                return
        raise RuntimeError("所属部門検索後の一覧表示を確認できませんでした")

    def read_result_summary(self) -> SearchResultSummary:
        if not self.page:
            raise RuntimeError("page not started")
        return _parse_result_summary_text(_read_text(self.page.locator("body").first))

    def read_selected_count_summary(self) -> SelectedCountSummary:
        if not self.page:
            raise RuntimeError("page not started")
        return _parse_selected_count_text(_read_text(self.page.locator("body").first))

    def iter_slip_blocks(self) -> list[tuple[Locator, Locator, Locator, Locator]]:
        if not self.page:
            raise RuntimeError("page not started")
        blocks: list[tuple[Locator, Locator, Locator, Locator]] = []
        for checkbox in self.page.locator("input[name^='kakutei(']").all():
            row1 = checkbox.locator("xpath=ancestor::tr[1]").first
            row2 = row1.locator("xpath=following-sibling::tr[1]").first
            row3 = row1.locator("xpath=following-sibling::tr[2]").first
            if row2.count() == 0 or row3.count() == 0:
                raise RuntimeError("1伝票3行ブロックを特定できませんでした")
            blocks.append((checkbox, row1, row2, row3))
        return blocks

    def parse_slip_block(
        self,
        *,
        checkbox: Locator,
        row1: Locator,
        row2: Locator,
        row3: Locator,
        page_no: int,
        row_group_index: int,
    ) -> SlipRecord:
        checkbox_name = checkbox.get_attribute("name")
        record = parse_slip_block_texts(
            row1_text=_read_text(row1),
            row2_text=_read_text(row2),
            row3_text=_read_text(row3),
            checkbox_name=checkbox_name,
            page_no=page_no,
            row_group_index=row_group_index,
        )
        fee_select = row3.locator("select[name^='tesuryoKbn(']").first
        if fee_select.count() > 0:
            fee_value = (fee_select.input_value() or "").strip()
            fee_burden = {"0": "当方負担", "1": "先方負担"}.get(fee_value, fee_value or None)
            if fee_burden:
                record = replace(record, fee_burden=fee_burden)
        return record

    def select_slips_by_payment_date(self, payment_date: str) -> SlipSelectionResult:
        if not self.page:
            raise RuntimeError("page not started")
        self.page.locator("text=伝票No").first.wait_for(state="visible", timeout=60_000)
        summary = self.read_result_summary()
        if summary.range_start != 1 or summary.range_end != summary.total_count:
            raise RuntimeError(
                f"複数ページまたは表示範囲不足を検知しました: {summary.range_start}-{summary.range_end}/{summary.total_count}"
            )

        inventory: list[SlipRecord] = []
        selected: list[SlipRecord] = []
        anomalies: list[SlipRecord] = []
        matching_count = 0

        for row_group_index, (checkbox, row1, row2, row3) in enumerate(self.iter_slip_blocks(), start=1):
            record = self.parse_slip_block(
                checkbox=checkbox,
                row1=row1,
                row2=row2,
                row3=row3,
                page_no=1,
                row_group_index=row_group_index,
            )
            classified = classify_slip_record(record, payment_date)
            inventory.append(classified)
            if classified.payment_date == payment_date:
                matching_count += 1
                if classified.decision == "selected":
                    selected.append(classified)
                elif classified.decision == "anomaly":
                    anomalies.append(classified)

        expected_count = summary.range_end - summary.range_start + 1
        if len(inventory) != expected_count:
            raise RuntimeError(
                f"表示件数と抽出件数が一致しません: summary={expected_count}, parsed={len(inventory)}"
            )
        if matching_count == 0:
            raise RuntimeError(f"対象なし: (申請)支払日={payment_date} の行が見つかりません")

        return SlipSelectionResult(inventory=inventory, selected=selected, anomalies=anomalies)

    def check_selected_slips(self, records: Sequence[SlipRecord]) -> None:
        if not self.page:
            raise RuntimeError("page not started")
        for record in records:
            if not record.checkbox_name:
                raise RuntimeError(f"checkbox 名を取得できていません: {record.slip_no}")
            checkbox = self.page.locator(f"input[name='{record.checkbox_name}']").first
            checkbox.wait_for(state="visible", timeout=30_000)
            checkbox.scroll_into_view_if_needed()
            try:
                checkbox.check()
            except Exception:
                checkbox.click(force=True)

    def export_report(
        self,
        run_id: str,
        records: Sequence[SlipRecord],
        *,
        kind: str = "selected",
    ) -> Path:
        reports_dir = self.artifact_dir / "reports"
        _ensure_dir(reports_dir)
        path = reports_dir / f"raku_payment_confirm_{kind}_{run_id}.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "page_no",
                    "row_group_index",
                    "slip_no",
                    "request_date",
                    "approval_date",
                    "requested_payment_date",
                    "payment_method",
                    "payment_method_source",
                    "amount_yen",
                    "vendor",
                    "applicant",
                    "note",
                    "fee_burden",
                    "original_save",
                    "checkbox_name",
                    "decision",
                    "decision_reason",
                    "raw_text",
                ]
            )
            for r in records:
                w.writerow(
                    [
                        r.page_no,
                        r.row_group_index,
                        r.slip_no,
                        r.request_date or "",
                        r.approval_date or "",
                        r.payment_date,
                        r.payment_method or "",
                        r.payment_method_source,
                        r.amount_yen if r.amount_yen is not None else "",
                        r.vendor or "",
                        r.applicant or "",
                        r.note or "",
                        r.fee_burden or "",
                        r.original_save or "",
                        r.checkbox_name or "",
                        r.decision,
                        r.decision_reason,
                        r.raw_text,
                    ]
                )
        return path

    def set_footer_conditions(self, transfer_source: str, payment_date: str) -> None:
        if not self.page:
            raise RuntimeError("page not started")
        footer = self.page.locator(
            "xpath=//*[.//*[normalize-space()='振込元'] and .//*[normalize-space()='支払日'] and (.//button[normalize-space()='確定'] or .//input[@value='確定'])]"
        ).first
        footer.wait_for(state="visible", timeout=60_000)

        # 振込元
        select_loc = footer.locator("select").first
        if select_loc.count() > 0:
            try:
                select_loc.select_option(label=transfer_source)
            except Exception:
                # Some UIs need exact value; fallback to clicking options by text.
                select_loc.select_option(value=transfer_source)
        else:
            raise RuntimeError("振込元のドロップダウンが見つかりません")

        # 支払日（年/月/日）
        y, m, d = _split_ymd(payment_date)
        year_in = footer.locator("xpath=.//*[normalize-space()='支払日']/following::input[1]").first
        month_in = footer.locator("xpath=.//*[normalize-space()='支払日']/following::input[2]").first
        day_in = footer.locator("xpath=.//*[normalize-space()='支払日']/following::input[3]").first
        year_in.fill(y)
        month_in.fill(m)
        day_in.fill(d)

    def click_confirm(self) -> None:
        if not self.page:
            raise RuntimeError("page not started")
        selected_count = self.page.locator("input[name^='kakutei(']:checked").count()
        if selected_count == 0:
            raise RuntimeError("選択済み伝票が0件のため、確定処理へ進めません")
        btn = self.page.locator("button:has-text('確定'), input[value='確定']").first
        btn.scroll_into_view_if_needed()
        time.sleep(0.2)
        btn.click()

    def read_confirmation_modal(self) -> dict:
        if not self.page:
            raise RuntimeError("page not started")

        modal = self.page.locator(
            "xpath=//*[contains(@class,'modal') or @role='dialog' or contains(@class,'ui-dialog')][.//*[normalize-space()='確認']]"
        ).first
        modal.wait_for(state="visible", timeout=60_000)

        def read_row(label: str) -> str:
            loc = modal.locator(
                f"xpath=.//tr[.//*[normalize-space()='{label}']]/*[self::td or self::th][last()]"
            ).first
            if loc.count() == 0:
                return ""
            return _read_text(loc)

        transfer_source = read_row("振込元")
        payment_date = read_row("支払日")
        total_amount = read_row("支払額の合計")

        return {
            "transfer_source": transfer_source,
            "payment_date": payment_date,
            "total_amount_raw": total_amount,
            "modal": modal,
        }

    def click_modal_ok(self, modal_locator: Locator) -> None:
        ok_btn = modal_locator.locator("button:has-text('OK'), input[value='OK']").first
        ok_btn.wait_for(state="visible", timeout=30_000)
        ok_btn.click()

    def read_success_screen(self) -> dict:
        if not self.page:
            raise RuntimeError("page not started")

        # Wait for success area (支払No.)
        self.page.locator("text=支払No.").first.wait_for(state="visible", timeout=90_000)

        def read_value(label: str) -> str:
            loc = self.page.locator(
                f"xpath=//*[normalize-space()='{label}']/following::*[1]"
            ).first
            return _read_text(loc)

        # Use more specific extraction if possible
        payment_no = ""
        pay_no_loc = self.page.locator(
            "xpath=//*[normalize-space()='支払No.']/following::td[1]"
        ).first
        if pay_no_loc.count() > 0:
            payment_no = _read_text(pay_no_loc)

        transfer_source = ""
        ts_loc = self.page.locator(
            "xpath=//*[normalize-space()='振込元']/following::td[1]"
        ).first
        if ts_loc.count() > 0:
            transfer_source = _read_text(ts_loc)

        payment_date = ""
        pd_loc = self.page.locator(
            "xpath=//*[normalize-space()='支払日']/following::td[1]"
        ).first
        if pd_loc.count() > 0:
            payment_date = _read_text(pd_loc)

        total_amount = ""
        ta_loc = self.page.locator(
            "xpath=//*[normalize-space()='支払額の合計']/following::td[1]"
        ).first
        if ta_loc.count() > 0:
            total_amount = _read_text(ta_loc)

        return {
            "payment_no": payment_no,
            "transfer_source": transfer_source,
            "payment_date": payment_date,
            "total_amount_raw": total_amount,
        }

    def click_close_on_success(self) -> None:
        if not self.page:
            raise RuntimeError("page not started")
        btn = self.page.locator("button:has-text('閉じる'), input[value='閉じる']").first
        if btn.count() == 0:
            return
        btn.click()


def _write_json(path: Path, payload: dict) -> None:
    _ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict) -> None:
    _ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    return items


def _prepare_run_dirs(artifact_root: Path, run_id: str) -> dict[str, Path]:
    run_dir = artifact_root / f"run_{run_id}"
    paths = {
        "artifact_root": artifact_root,
        "run_dir": run_dir,
        "logs_dir": run_dir / "logs",
        "reports_dir": run_dir / "reports",
        "screenshots_dir": run_dir / "screenshots",
    }
    for path in paths.values():
        _ensure_dir(path)
    return paths


def _write_preflight_json(path: Path, payload: dict) -> None:
    _write_json(path, payload)


def _make_run_key(payment_date: str, transfer_source: str, slip_nos: Sequence[str]) -> str:
    # Deterministic key for rerun-safety checks.
    slips = ",".join(sorted(set(slip_nos)))
    return f"{payment_date}|{transfer_source}|{slips}"


def run_payment_confirm(
    *,
    env_name: str,
    base_url: str,
    department_code: str,
    payment_date: str,
    transfer_source: str,
    artifact_root: Path,
    execute: bool,
    headless: bool,
    dry_run_mail: bool,
) -> RunResult:
    run_id = _now_run_id()
    artifact_root = artifact_root.resolve()
    _ensure_dir(artifact_root)
    run_paths = _prepare_run_dirs(artifact_root, run_id)
    run_dir = run_paths["run_dir"]
    result_json_path = run_paths["reports_dir"] / "report.json"
    summary_json_path = run_dir / "summary.json"
    preflight_path = run_dir / "reports" / "preflight.json"
    ledger_path = artifact_root / "state" / "scenario70" / env_name.upper() / "ledger.jsonl"
    ledger_excerpt_path = run_paths["logs_dir"] / "ledger_excerpt.jsonl"
    _ensure_dir(ledger_path.parent)

    result = RunResult(
        run_id=run_id,
        started_at=datetime.now().isoformat(timespec="seconds"),
        env_name=env_name.upper(),
        base_url=base_url,
        department_code=department_code,
        payment_date=payment_date,
        transfer_source=transfer_source,
        artifact_root=str(artifact_root),
        run_dir=str(run_dir),
        summary_path=str(summary_json_path),
        report_json_path=str(result_json_path),
        preflight_path=str(preflight_path),
        ledger_path=str(ledger_path),
        ledger_excerpt_path=str(ledger_excerpt_path),
    )

    _write_preflight_json(
        preflight_path,
        {
            "run_id": run_id,
            "env_name": env_name.upper(),
            "base_url": base_url,
            "department_code": department_code,
            "payment_date": payment_date,
            "transfer_source": transfer_source,
            "artifact_root": str(artifact_root),
            "execute": execute,
            "headless": headless,
            "dry_run_mail": dry_run_mail,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        },
    )

    confirmer = RakurakuPaymentConfirmer(
        base_url=base_url,
        artifact_dir=run_dir,
        headless=headless,
    )

    screenshot_paths: list[Path] = []

    try:
        confirmer.start()
        confirmer.login()
        screenshot_paths.append(confirmer.screenshot(f"{run_id}_after_login.png"))

        confirmer.goto_search_screen()
        screenshot_paths.append(confirmer.screenshot(f"{run_id}_search_screen.png"))

        confirmer.search_by_department(department_code)
        screenshot_paths.append(confirmer.screenshot(f"{run_id}_list_screen.png"))

        selection = confirmer.select_slips_by_payment_date(payment_date)
        inventory = selection.inventory
        records = selection.selected
        anomalies = selection.anomalies
        result.inventory_records = len(inventory)
        result.selected_records = len(records)
        result.anomaly_records = len(anomalies)

        # Export report before any irreversible action.
        report_path = confirmer.export_report(run_id, inventory, kind="full_inventory")
        result.report_path = str(report_path)
        if records:
            selected_report_path = confirmer.export_report(run_id, records, kind="selected_candidates")
            result.selected_report_path = str(selected_report_path)
        if anomalies:
            anomaly_report_path = confirmer.export_report(run_id, anomalies, kind="anomalies")
            result.anomaly_report_path = str(anomaly_report_path)

        screenshot_paths.append(confirmer.screenshot(f"{run_id}_inventory.png"))

        # Rerun safety: if same exact selection was already confirmed, stop.
        run_key = _make_run_key(payment_date, transfer_source, [r.slip_no for r in records])
        for past in _load_jsonl(ledger_path):
            if past.get("status") == "success" and past.get("run_key") == run_key:
                raise RuntimeError(
                    "リラン安全: 同一の伝票セットで支払確定済みの実行履歴があります。"
                )

        if not execute:
            result.status = "dry_run"
            result.ended_at = datetime.now().isoformat(timespec="seconds")
            report_payload = {
                **asdict(result),
                "selected_slip_nos": [r.slip_no for r in records],
                "anomaly_slip_nos": [r.slip_no for r in anomalies],
                "screenshot_paths": [str(p) for p in screenshot_paths],
            }
            _write_json(result_json_path, report_payload)
            _write_json(summary_json_path, asdict(result))
            ledger_entry = {
                "schema_version": 1,
                "environment": env_name.upper(),
                "run_id": run_id,
                "run_key": run_key,
                "status": "dry_run",
                "inventory_records": result.inventory_records,
                "selected_records": result.selected_records,
                "anomaly_records": result.anomaly_records,
                "at": datetime.now().isoformat(timespec="seconds"),
            }
            _append_jsonl(ledger_path, ledger_entry)
            _append_jsonl(ledger_excerpt_path, ledger_entry)
            return result

        if anomalies:
            raise RuntimeError(
                "確認ゲート: 自動実行対象外の異常候補が "
                f"{len(anomalies)}件あります。"
                f"異常候補CSVを確認してから再実行してください: {result.anomaly_report_path}"
            )
        if len(records) == 0:
            raise RuntimeError("確認ゲート: 自動選択候補が0件のため execute は実行しません")

        confirmer.check_selected_slips(records)
        screenshot_paths.append(confirmer.screenshot(f"{run_id}_selected.png"))

        selected_summary = confirmer.read_selected_count_summary()
        if selected_summary.selected_count != len(records):
            raise RuntimeError(
                "選択件数不一致: "
                f"UI={selected_summary.selected_count}件, "
                f"RPA={len(records)}件"
            )
        if selected_summary.total_count != result.inventory_records:
            raise RuntimeError(
                "総件数不一致: "
                f"UI={selected_summary.total_count}件, "
                f"RPA={result.inventory_records}件"
            )

        confirmer.set_footer_conditions(transfer_source, payment_date)
        screenshot_paths.append(confirmer.screenshot(f"{run_id}_footer_set.png"))

        confirmer.click_confirm()

        modal_info = confirmer.read_confirmation_modal()
        modal = modal_info["modal"]
        screenshot_paths.append(confirmer.screenshot(f"{run_id}_confirm_modal.png"))

        # Poka-yoke: validate modal values match expected.
        modal_transfer = (modal_info.get("transfer_source") or "").strip()
        modal_date = (modal_info.get("payment_date") or "").strip()
        if modal_transfer and modal_transfer != transfer_source:
            raise RuntimeError(
                f"確認ダイアログ不一致: 振込元 expected='{transfer_source}' actual='{modal_transfer}'"
            )
        if modal_date and modal_date != payment_date:
            raise RuntimeError(
                f"確認ダイアログ不一致: 支払日 expected='{payment_date}' actual='{modal_date}'"
            )

        expected_total_amount = sum(r.amount_yen or 0 for r in records)
        total_amount_raw = (modal_info.get("total_amount_raw") or "").strip()
        if not total_amount_raw:
            raise RuntimeError("確認ダイアログから支払額の合計を取得できません")
        result.total_amount_yen = _parse_int_yen(total_amount_raw)
        if result.total_amount_yen != expected_total_amount:
            raise RuntimeError(
                "確認ダイアログ不一致: "
                f"支払額の合計 expected='{expected_total_amount}' actual='{result.total_amount_yen}'"
            )

        confirmer.click_modal_ok(modal)

        # Success screen
        success = confirmer.read_success_screen()
        screenshot_paths.append(confirmer.screenshot(f"{run_id}_success.png"))

        payment_no = (success.get("payment_no") or "").strip()
        if not payment_no:
            raise RuntimeError("成功画面から支払Noを取得できません")
        result.payment_no = payment_no

        success_total_raw = (success.get("total_amount_raw") or "").strip()
        if success_total_raw:
            result.total_amount_yen = _parse_int_yen(success_total_raw)

        confirmer.click_close_on_success()
        screenshot_paths.append(confirmer.screenshot(f"{run_id}_after_close.png"))

        result.status = "success"
        result.ended_at = datetime.now().isoformat(timespec="seconds")
        report_payload = {
            **asdict(result),
            "selected_slip_nos": [r.slip_no for r in records],
            "anomaly_slip_nos": [r.slip_no for r in anomalies],
            "screenshot_paths": [str(p) for p in screenshot_paths],
        }
        _write_json(result_json_path, report_payload)
        _write_json(summary_json_path, asdict(result))
        ledger_entry = {
            "schema_version": 1,
            "environment": env_name.upper(),
            "run_id": run_id,
            "run_key": run_key,
            "status": "success",
            "payment_no": result.payment_no,
            "total_amount_yen": result.total_amount_yen,
            "selected_records": result.selected_records,
            "at": result.ended_at,
            "report_path": result.report_path,
        }
        _append_jsonl(ledger_path, ledger_entry)
        _append_jsonl(ledger_excerpt_path, ledger_entry)

        return result

    except Exception as e:
        result.status = "failed"
        result.error = f"{type(e).__name__}: {e}"
        result.ended_at = datetime.now().isoformat(timespec="seconds")
        try:
            if confirmer.page:
                screenshot_paths.append(confirmer.screenshot(f"{run_id}_error.png"))
        except Exception:
            pass
        report_payload = {
            **asdict(result),
            "screenshot_paths": [str(p) for p in screenshot_paths],
        }
        _write_json(result_json_path, report_payload)
        _write_json(summary_json_path, asdict(result))
        ledger_entry = {
            "schema_version": 1,
            "environment": env_name.upper(),
            "run_id": run_id,
            "status": "failed",
            "error": result.error,
            "at": result.ended_at,
        }
        _append_jsonl(ledger_path, ledger_entry)
        _append_jsonl(ledger_excerpt_path, ledger_entry)
        raise

    finally:
        try:
            confirmer.close()
        except Exception:
            pass


def send_result_email(
    *,
    result: RunResult,
    slip_nos: Sequence[str] | None,
    screenshot_paths: Sequence[Path] | None,
    dry_run_mail: bool,
) -> None:
    if result.status == "dry_run":
        if result.anomaly_records <= 0:
            return

        subject = (
            f"[scenario70] dry-run anomaly detected "
            f"{result.payment_date} {result.transfer_source}"
        )
        paragraphs = [
            f"run_id: {result.run_id}",
            f"payment_date: {result.payment_date}",
            f"department_code: {result.department_code}",
            f"transfer_source: {result.transfer_source}",
            f"inventory_records: {result.inventory_records}",
            f"selected_records: {result.selected_records}",
            f"anomaly_records: {result.anomaly_records}",
            "dry-run detected anomalies before confirmation. "
            "Please review the anomaly CSV and correct Rakuraku data before rerun.",
        ]
        if result.report_path:
            paragraphs.append(
                f"full_inventory: {html_link_to_path(Path(result.report_path), label=result.report_path)}"
            )
        if result.selected_report_path:
            paragraphs.append(
                "selected_candidates: "
                f"{html_link_to_path(Path(result.selected_report_path), label=result.selected_report_path)}"
            )
        if result.anomaly_report_path:
            paragraphs.append(
                f"anomaly_csv: {html_link_to_path(Path(result.anomaly_report_path), label=result.anomaly_report_path)}"
            )
        if screenshot_paths:
            paragraphs.append("screenshots:")
            paragraphs.append("<pre>" + "\n".join([str(p) for p in screenshot_paths]) + "</pre>")

        html = build_simple_html(
            title="scenario70 dry-run anomaly detected",
            paragraphs=paragraphs,
        )
        send_outlook(
            OutlookEmail(
                to=MAIL_TO_ERROR,
                cc=MAIL_CC_ERROR,
                subject=subject,
                html_body=html,
            ),
            dry_run=dry_run_mail,
        )
        return

    if result.status == "success":
        subject = (
            f"【完了】楽楽精算 支払確定（支払先） {result.payment_date} "
            f"{result.transfer_source} 支払No={result.payment_no}"
        )
        report_link = ""
        if result.report_path:
            report_link = html_link_to_path(Path(result.report_path), label=result.report_path)

        bullets: list[str] = []
        if slip_nos:
            bullets.append("伝票No:")
            bullets.append("<pre>" + "\n".join(slip_nos) + "</pre>")

        html = build_simple_html(
            title="楽楽精算 支払確定（支払先） 処理完了",
            paragraphs=[
                f"支払日(申請): {result.payment_date}",
                f"所属部門: {result.department_code}",
                f"振込元: {result.transfer_source}",
                f"支払No: {result.payment_no}",
                f"支払額合計: {result.total_amount_yen:,}円"
                if result.total_amount_yen is not None
                else "支払額合計: (取得失敗)",
                f"inventory件数: {result.inventory_records}",
                f"選択件数: {result.selected_records}",
                f"異常候補件数: {result.anomaly_records}",
                f"レポート: {report_link}" if report_link else "レポート: (未出力)",
                (
                    f"選択候補CSV: {html_link_to_path(Path(result.selected_report_path), label=result.selected_report_path)}"
                    if result.selected_report_path
                    else "選択候補CSV: なし"
                ),
                (
                    f"異常候補CSV: {html_link_to_path(Path(result.anomaly_report_path), label=result.anomaly_report_path)}"
                    if result.anomaly_report_path
                    else "異常候補CSV: なし"
                ),
            ],
            bullets=bullets or None,
        )
        send_outlook(
            OutlookEmail(
                to=MAIL_TO_SUCCESS,
                subject=subject,
                html_body=html,
            ),
            dry_run=dry_run_mail,
        )
        return

    # failed
    subject = (
        f"★エラー発生★【楽楽精算 支払確定（支払先）】{result.payment_date} {result.transfer_source}"
    )
    paragraphs = [
        f"run_id: {result.run_id}",
        f"支払日(申請): {result.payment_date}",
        f"所属部門: {result.department_code}",
        f"振込元: {result.transfer_source}",
        f"エラー: {result.error}",
    ]
    if result.report_path:
        paragraphs.append(f"レポート: {html_link_to_path(Path(result.report_path), label=result.report_path)}")
    if result.selected_report_path:
        paragraphs.append(
            f"選択候補CSV: {html_link_to_path(Path(result.selected_report_path), label=result.selected_report_path)}"
        )
    if result.anomaly_report_path:
        paragraphs.append(
            f"異常候補CSV: {html_link_to_path(Path(result.anomaly_report_path), label=result.anomaly_report_path)}"
        )
    if screenshot_paths:
        paragraphs.append("スクショ:")
        paragraphs.append("<pre>" + "\n".join([str(p) for p in screenshot_paths]) + "</pre>")

    html = build_simple_html(
        title="楽楽精算 支払確定（支払先） エラー通知",
        paragraphs=paragraphs,
    )
    send_outlook(
        OutlookEmail(
            to=MAIL_TO_ERROR,
            cc=MAIL_CC_ERROR,
            subject=subject,
            html_body=html,
        ),
        dry_run=dry_run_mail,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="楽楽精算 支払確定（支払先） 自動化（Scenario 70）")
    parser.add_argument("--env", default=None, help="LOCAL or PROD")
    parser.add_argument("--config-dir", default=str(DEFAULT_CONFIG_DIR), help="scenario70 config directory")
    parser.add_argument("--base-url", default=None, help="楽楽精算URL")
    parser.add_argument("--department-code", default=None, help="所属部門コード（例: 300）")
    parser.add_argument("--payment-date", required=True, help="対象の(申請)支払日（YYYY/MM/DD）")
    parser.add_argument("--transfer-source", default=None, help="振込元（ドロップダウン表示名）")
    parser.add_argument("--artifact-dir", default=None, help="成果物出力先ディレクトリ（フルパス）")
    parser.add_argument("--headless", action="store_true", help="ヘッドレス（非推奨）")
    parser.add_argument("--execute", action="store_true", help="確認ダイアログのOKを押して支払確定まで実行する")
    parser.add_argument("--dry-run-mail", action="store_true", help="メール送信をドライラン（プレビューのみ）")

    args = parser.parse_args()

    if not _PLAYWRIGHT_AVAILABLE:
        print("Error: playwright is not installed.")
        return 2

    config_dir = Path(args.config_dir)
    env_name = get_scenario70_env(config_dir, args.env)
    config: dict[str, str] = {}
    if config_dir.exists():
        try:
            config = load_scenario70_config(config_dir, env_name)
        except FileNotFoundError:
            config = {"ENV": env_name, "CONFIG_DIR": str(config_dir)}

    global MAIL_TO_SUCCESS, MAIL_TO_ERROR, MAIL_CC_ERROR
    if config.get("MAIL_TO_SUCCESS"):
        MAIL_TO_SUCCESS = split_mail_list(config["MAIL_TO_SUCCESS"])
    if config.get("MAIL_TO_ERROR"):
        MAIL_TO_ERROR = split_mail_list(config["MAIL_TO_ERROR"])
    if config.get("MAIL_CC_ERROR"):
        MAIL_CC_ERROR = split_mail_list(config["MAIL_CC_ERROR"])

    payment_date = _normalize_payment_date(args.payment_date)
    base_url = (args.base_url or config.get("BASE_URL") or DEFAULT_BASE_URL).strip()
    artifact_root = Path(args.artifact_dir or config.get("ARTIFACT_ROOT") or DEFAULT_ARTIFACT_DIR)
    department_code = str(args.department_code or config.get("DEPARTMENT_CODE") or DEFAULT_DEPARTMENT_CODE).strip()
    transfer_source = str(args.transfer_source or config.get("TRANSFER_SOURCE") or DEFAULT_TRANSFER_SOURCE).strip()

    # Ensure artifact dir exists early.
    _ensure_dir(artifact_root)

    slip_nos: list[str] = []
    screenshots: list[Path] = []
    result: RunResult | None = None

    try:
        result = run_payment_confirm(
            env_name=env_name,
            base_url=base_url,
            department_code=department_code,
            payment_date=payment_date,
            transfer_source=transfer_source,
            artifact_root=artifact_root,
            execute=bool(args.execute),
            headless=bool(args.headless),
            dry_run_mail=bool(args.dry_run_mail),
        )
        if result.status == "dry_run" and result.anomaly_records > 0:
            try:
                send_result_email(
                    result=result,
                    slip_nos=slip_nos,
                    screenshot_paths=screenshots,
                    dry_run_mail=bool(args.dry_run_mail),
                )
            except Exception:
                print("Warning: dry-run anomaly email failed to send.")
        # In current implementation, slip list is saved in CSV; email slip_nos list is optional.
        # If needed, we can re-read CSV here.
        return 0 if result.status in ("success", "dry_run") else 1

    except Exception:
        # Send error email with traceback summary.
        if result is None:
            result = RunResult(
                run_id=_now_run_id(),
                started_at=datetime.now().isoformat(timespec="seconds"),
                env_name=env_name.upper(),
                base_url=base_url,
                department_code=department_code,
                payment_date=payment_date,
                transfer_source=transfer_source,
                artifact_root=str(artifact_root.resolve()),
                run_dir="",
                status="failed",
                error="Unhandled error before result initialization",
                ended_at=datetime.now().isoformat(timespec="seconds"),
            )
        result.error = result.error or traceback.format_exc()
        try:
            send_result_email(
                result=result,
                slip_nos=slip_nos,
                screenshot_paths=screenshots,
                dry_run_mail=bool(args.dry_run_mail),
            )
        except Exception:
            pass
        print(traceback.format_exc())
        return 1

    finally:
        # Success email is intentionally not sent here because the run already includes all artifacts.
        # Sending success email is a policy decision; enable it in operational wrapper if needed.
        if result and result.status == "success":
            try:
                send_result_email(
                    result=result,
                    slip_nos=slip_nos,
                    screenshot_paths=screenshots,
                    dry_run_mail=bool(args.dry_run_mail),
                )
            except Exception:
                # If mail fails, treat as failure in ops; here we only log to console.
                print("Warning: success email failed to send.")


if __name__ == "__main__":
    sys.exit(main())
