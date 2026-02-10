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
from dataclasses import asdict, dataclass
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
    slip_no: str
    request_date: str | None
    approval_date: str | None
    payment_date: str
    amount_yen: int | None
    raw_text: str


@dataclass
class RunResult:
    run_id: str
    started_at: str
    base_url: str
    department_code: str
    payment_date: str
    transfer_source: str
    selected_records: int = 0
    total_amount_yen: int | None = None
    payment_no: str | None = None
    report_path: str | None = None
    status: str = "started"  # started/success/failed/dry_run
    error: str | None = None
    ended_at: str | None = None


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

    return SlipRecord(
        slip_no=slip_no,
        request_date=request_date,
        approval_date=approval_date,
        payment_date=payment_date,
        amount_yen=amount_yen,
        raw_text=text,
    )


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
        try:
            return get_credential(self.credential_name)
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

    def search_by_department(self, department_code: str) -> None:
        if not self.page:
            raise RuntimeError("page not started")

        target: Page | Frame = self._get_main_frame() or self.page

        # 所属部門入力（オートコンプリートがあるためTabで確定）
        dept_input = target.locator(
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
        search_btn = target.locator("button:has-text('検索'), input[value='検索']").first
        search_btn.click()
        time.sleep(2)

        # 一覧の「確定」ボタンが出るまで待機
        confirm_btn = target.locator("button:has-text('確定'), input[value='確定']").first
        confirm_btn.wait_for(state="visible", timeout=90_000)

    def select_slips_by_payment_date(self, payment_date: str) -> list[SlipRecord]:
        if not self.page:
            raise RuntimeError("page not started")

        target: Page | Frame = self._get_main_frame() or self.page

        # ヘッダが見えることを確認
        target.locator("text=伝票No").first.wait_for(state="visible", timeout=60_000)

        rows = target.locator("table tbody tr, table tr").all()
        records: list[SlipRecord] = []
        seen: set[str] = set()

        for row in rows:
            try:
                cb = row.locator("input[type='checkbox']")
                if cb.count() == 0:
                    continue
                row_text = (row.text_content() or "").strip()
                if payment_date not in row_text:
                    continue
                rec = parse_slip_row_text(row_text, payment_date)
                if rec.slip_no in seen:
                    continue
                # Avoid selecting header checkbox etc.
                cb_first = cb.first
                if not cb_first.is_visible():
                    continue
                try:
                    cb_first.scroll_into_view_if_needed()
                    time.sleep(0.05)
                except Exception:
                    pass
                try:
                    cb_first.check()
                except Exception:
                    cb_first.click(force=True)

                records.append(rec)
                seen.add(rec.slip_no)
            except Exception:
                continue

        # Selected count text: "526件中 23件 が選択されています"
        selected_info = ""
        info_loc = target.locator(
            "xpath=//*[contains(normalize-space(),'件が選択されています')]"
        ).first
        if info_loc.count() > 0:
            selected_info = _read_text(info_loc)
        m = re.search(r"(\d+)件\s*が選択されています", selected_info)
        if m:
            selected_count = int(m.group(1))
            if selected_count != len(records):
                raise RuntimeError(
                    f"選択件数不一致: 画面表示={selected_count}, 抽出/選択={len(records)}. "
                    f"支払日混在やDOM未取得の可能性。"
                )
        if len(records) == 0:
            raise RuntimeError(f"対象なし: (申請)支払日={payment_date} の行が見つかりません")

        return records

    def export_report(self, run_id: str, records: Sequence[SlipRecord]) -> Path:
        reports_dir = self.artifact_dir / "reports"
        _ensure_dir(reports_dir)
        path = reports_dir / f"raku_payment_confirm_selected_{run_id}.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "slip_no",
                    "request_date",
                    "approval_date",
                    "payment_date",
                    "amount_yen",
                    "raw_text",
                ]
            )
            for r in records:
                w.writerow(
                    [
                        r.slip_no,
                        r.request_date or "",
                        r.approval_date or "",
                        r.payment_date,
                        r.amount_yen if r.amount_yen is not None else "",
                        r.raw_text,
                    ]
                )
        return path

    def set_footer_conditions(self, transfer_source: str, payment_date: str) -> None:
        if not self.page:
            raise RuntimeError("page not started")
        target: Page | Frame = self._get_main_frame() or self.page

        footer = target.locator(
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
        target: Page | Frame = self._get_main_frame() or self.page
        btn = target.locator("button:has-text('確定'), input[value='確定']").first
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
                f"xpath=.//tr[.//*[normalize-space()='{label}']]//td"
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


def _make_run_key(payment_date: str, transfer_source: str, slip_nos: Sequence[str]) -> str:
    # Deterministic key for rerun-safety checks.
    slips = ",".join(sorted(set(slip_nos)))
    return f"{payment_date}|{transfer_source}|{slips}"


def run_payment_confirm(
    *,
    base_url: str,
    department_code: str,
    payment_date: str,
    transfer_source: str,
    artifact_dir: Path,
    execute: bool,
    headless: bool,
    dry_run_mail: bool,
) -> RunResult:
    run_id = _now_run_id()
    result = RunResult(
        run_id=run_id,
        started_at=datetime.now().isoformat(timespec="seconds"),
        base_url=base_url,
        department_code=department_code,
        payment_date=payment_date,
        transfer_source=transfer_source,
    )

    artifact_dir = artifact_dir.resolve()
    _ensure_dir(artifact_dir)
    result_json_path = artifact_dir / "logs" / f"run_{run_id}.json"
    ledger_path = artifact_dir / "logs" / "ledger.jsonl"

    confirmer = RakurakuPaymentConfirmer(
        base_url=base_url,
        artifact_dir=artifact_dir,
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

        records = confirmer.select_slips_by_payment_date(payment_date)
        result.selected_records = len(records)

        # Export report before any irreversible action.
        report_path = confirmer.export_report(run_id, records)
        result.report_path = str(report_path)

        screenshot_paths.append(confirmer.screenshot(f"{run_id}_selected.png"))

        # Rerun safety: if same exact selection was already confirmed, stop.
        run_key = _make_run_key(payment_date, transfer_source, [r.slip_no for r in records])
        for past in _load_jsonl(ledger_path):
            if past.get("status") == "success" and past.get("run_key") == run_key:
                raise RuntimeError(
                    "リラン安全: 同一の伝票セットで支払確定済みの実行履歴があります。"
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

        total_amount_raw = (modal_info.get("total_amount_raw") or "").strip()
        if total_amount_raw:
            result.total_amount_yen = _parse_int_yen(total_amount_raw)

        if not execute:
            result.status = "dry_run"
            # Do not click OK.
            _write_json(result_json_path, asdict(result))
            _append_jsonl(
                ledger_path,
                {
                    "run_id": run_id,
                    "run_key": run_key,
                    "status": "dry_run",
                    "at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            return result

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
        _write_json(result_json_path, asdict(result))
        _append_jsonl(
            ledger_path,
            {
                "run_id": run_id,
                "run_key": run_key,
                "status": "success",
                "payment_no": result.payment_no,
                "total_amount_yen": result.total_amount_yen,
                "selected_records": result.selected_records,
                "at": result.ended_at,
                "report_path": result.report_path,
            },
        )

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
        _write_json(result_json_path, asdict(result))
        _append_jsonl(
            ledger_path,
            {
                "run_id": run_id,
                "status": "failed",
                "error": result.error,
                "at": result.ended_at,
            },
        )
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
                f"選択件数: {result.selected_records}",
                f"レポート: {report_link}" if report_link else "レポート: (未出力)",
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
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="楽楽精算URL")
    parser.add_argument("--department-code", default=DEFAULT_DEPARTMENT_CODE, help="所属部門コード（例: 300）")
    parser.add_argument("--payment-date", required=True, help="対象の(申請)支払日（YYYY/MM/DD）")
    parser.add_argument("--transfer-source", default=DEFAULT_TRANSFER_SOURCE, help="振込元（ドロップダウン表示名）")
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR, help="成果物出力先ディレクトリ（フルパス）")
    parser.add_argument("--headless", action="store_true", help="ヘッドレス（非推奨）")
    parser.add_argument("--execute", action="store_true", help="確認ダイアログのOKを押して支払確定まで実行する")
    parser.add_argument("--dry-run-mail", action="store_true", help="メール送信をドライラン（プレビューのみ）")

    args = parser.parse_args()

    if not _PLAYWRIGHT_AVAILABLE:
        print("Error: playwright is not installed.")
        return 2

    payment_date = _normalize_payment_date(args.payment_date)
    base_url = args.base_url.strip()
    artifact_dir = Path(args.artifact_dir)

    # Ensure artifact dir exists early.
    _ensure_dir(artifact_dir)

    slip_nos: list[str] = []
    screenshots: list[Path] = []
    result: RunResult | None = None

    try:
        result = run_payment_confirm(
            base_url=base_url,
            department_code=str(args.department_code).strip(),
            payment_date=payment_date,
            transfer_source=str(args.transfer_source).strip(),
            artifact_dir=artifact_dir,
            execute=bool(args.execute),
            headless=bool(args.headless),
            dry_run_mail=bool(args.dry_run_mail),
        )
        # In current implementation, slip list is saved in CSV; email slip_nos list is optional.
        # If needed, we can re-read CSV here.
        return 0 if result.status in ("success", "dry_run") else 1

    except Exception:
        # Send error email with traceback summary.
        if result is None:
            result = RunResult(
                run_id=_now_run_id(),
                started_at=datetime.now().isoformat(timespec="seconds"),
                base_url=base_url,
                department_code=str(args.department_code).strip(),
                payment_date=payment_date,
                transfer_source=str(args.transfer_source).strip(),
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

