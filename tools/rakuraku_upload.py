# -*- coding: utf-8 -*-
"""
楽楽精算 領収書/請求書アップロードモジュール

PDFをアップロードしてOCR自動入力後、内容を確認・確定する

Usage:
    python rakuraku_upload.py --pdf "取引先名_20251107_22803.pdf"
"""
import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass

# 共通モジュールをインポートできるようにパス追加
sys.path.insert(0, str(Path(__file__).parent))

from common.config_loader import load_config, get_env
from common.credential_manager import get_credential, get_credential_value
from common.logger import setup_logger, get_logger, LogContext

# Playwrightインポート
try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: playwright not installed. Run: pip install playwright && playwright install chromium")


@dataclass
class ReceiptData:
    """領収書/請求書データ"""
    pdf_path: str
    document_type: str = "請求書"  # 領収書 or 請求書
    storage_type: str = "スキャナ保存"  # 電子取引 or スキャナ保存 or 未指定
    trading_date: str = ""  # 取引日 YYYY/MM/DD
    receiving_date: str = ""  # 受領日 YYYY/MM/DD
    invoice_number: str = ""  # 事業者登録番号 T+13桁
    vendor_name: str = ""  # 取引先名
    amount: int = 0  # 金額


class RakurakuUploader:
    """楽楽精算アップローダー"""

    def __init__(self, config: dict):
        """
        Args:
            config: 設定辞書
        """
        self.config = config
        self.base_url = config.get("RAKURAKU_URL", "https://rsatonality.rakurakuseisan.jp/")
        self.credential_name = config.get("CREDENTIAL_RAKURAKU", "RK10_RakurakuSeisan")
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.logger = get_logger()

    def _get_credentials(self) -> tuple:
        """資格情報を取得"""
        # 方法1: 統合資格情報
        try:
            return get_credential(self.credential_name)
        except ValueError:
            pass

        # 方法2: 個別資格情報
        try:
            login_id = get_credential_value("ログインID　楽楽精算")
            password = get_credential_value("パスワード　楽楽精算")
            if login_id and password:
                return (login_id, password)
        except ValueError:
            pass

        raise ValueError(
            f"楽楽精算のログイン情報が見つかりません。\n"
            f"Windows資格情報マネージャーに登録してください。"
        )

    def start_browser(self, headless: bool = False):
        """ブラウザを起動"""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("playwright is not installed")

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            args=["--start-maximized"]
        )
        self.context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        self.page = self.context.new_page()
        self.logger.info("ブラウザ起動完了")

    def close_browser(self):
        """ブラウザを閉じる"""
        if self.browser:
            self.browser.close()
            self.logger.info("ブラウザ終了")
        if hasattr(self, 'playwright'):
            self.playwright.stop()

    def login(self):
        """楽楽精算にログイン"""
        if not self.page:
            raise RuntimeError("Browser not started")

        with LogContext("楽楽精算ログイン"):
            login_id, password = self._get_credentials()

            self.logger.info(f"アクセス: {self.base_url}")
            self.page.goto(self.base_url)
            self.page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

            self.logger.info("ログイン情報入力...")

            # ログインID入力
            login_input = self.page.locator("input[name='loginId']")
            if login_input.count() == 0:
                login_input = self.page.locator("input[type='text']").first
            login_input.fill(login_id)

            # パスワード入力
            pw_input = self.page.locator("input[type='password']")
            pw_input.fill(password)

            # ログインボタン
            login_btn = self.page.locator("input[type='submit'], button[type='submit']").first
            login_btn.click()

            # ログイン完了待機
            self.logger.info("ログイン待機中...")
            for i in range(15):
                time.sleep(1)
                current_url = self.page.url

                if "mainView" in current_url or "Top" in current_url:
                    self.logger.info("ログイン成功")
                    break

                login_form = self.page.locator("input[name='loginId']")
                if login_form.count() == 0:
                    self.logger.info("ログイン成功")
                    break

            time.sleep(3)

    def navigate_to_receipt_form(self):
        """領収書/請求書新規登録画面へ移動"""
        with LogContext("領収書/請求書登録画面へ移動"):
            receipt_url = self.base_url.rstrip('/') + "/sapEbookFile/initializeView"
            self.logger.info(f"アクセス: {receipt_url}")
            self.page.goto(receipt_url, timeout=90000)
            self.page.wait_for_load_state("domcontentloaded")
            time.sleep(3)
            self.logger.info(f"現在URL: {self.page.url}")

    def upload_pdf(self, pdf_path: str) -> bool:
        """PDFをアップロード

        Args:
            pdf_path: PDFファイルパス

        Returns:
            成功/失敗
        """
        with LogContext("PDFアップロード"):
            abs_path = os.path.abspath(pdf_path)
            if not os.path.exists(abs_path):
                self.logger.error(f"ファイルが存在しません: {abs_path}")
                return False

            self.logger.info(f"アップロード: {abs_path}")

            # 方法1: filechooserイベント
            try:
                with self.page.expect_file_chooser(timeout=10000) as fc_info:
                    # ファイル選択ボタンをクリック
                    upload_btn = self.page.locator("input[type='file'], button:has-text('ファイル選択')").first
                    if upload_btn.count() == 0:
                        upload_btn = self.page.locator("xpath=//input").first
                    upload_btn.click()

                file_chooser = fc_info.value
                file_chooser.set_files(abs_path)
                self.logger.info("アップロード完了（filechooser方式）")

                # OCR処理待機
                self.logger.info("OCR処理待機中（20秒）...")
                time.sleep(20)
                return True

            except Exception as e:
                self.logger.warning(f"filechooser方式失敗: {e}")

            # 方法2: input[type='file']に直接設定
            try:
                file_input = self.page.locator("input[type='file']")
                if file_input.count() > 0:
                    file_input.first.set_input_files(abs_path)
                    self.logger.info("アップロード完了（input[type='file']方式）")
                    time.sleep(20)
                    return True
            except Exception as e:
                self.logger.warning(f"input[type='file']方式失敗: {e}")

            self.logger.error("アップロード失敗")
            return False

    def fill_form(self, data: ReceiptData):
        """フォームに入力

        Args:
            data: 領収書/請求書データ
        """
        with LogContext("フォーム入力"):
            # 書類区分（領収書/請求書）
            if data.document_type:
                self.logger.info(f"書類区分: {data.document_type}")
                try:
                    radio = self.page.locator(f"input[type='radio'][value='{data.document_type}']")
                    if radio.count() > 0:
                        radio.click()
                except Exception as e:
                    self.logger.warning(f"書類区分選択失敗: {e}")

            # 保存形式
            if data.storage_type:
                self.logger.info(f"保存形式: {data.storage_type}")
                try:
                    radio = self.page.locator(f"input[type='radio'][value*='{data.storage_type}']")
                    if radio.count() > 0:
                        radio.click()
                except Exception as e:
                    self.logger.warning(f"保存形式選択失敗: {e}")

            # 取引日入力
            if data.trading_date:
                self._fill_date_fields("trading", data.trading_date)

            # 受領日入力
            if data.receiving_date:
                self._fill_date_fields("receiving", data.receiving_date)

            # 事業者登録番号
            if data.invoice_number:
                self.logger.info(f"事業者登録番号: {data.invoice_number}")
                try:
                    invoice_input = self.page.locator("input[name='invoiceBusinessNumber(0)']")
                    if invoice_input.count() > 0:
                        invoice_input.fill(data.invoice_number)
                except Exception as e:
                    self.logger.warning(f"事業者登録番号入力失敗: {e}")

            # 取引先名
            if data.vendor_name:
                self.logger.info(f"取引先名: {data.vendor_name}")
                try:
                    vendor_input = self.page.locator("input[name='supplierName(0)']")
                    if vendor_input.count() > 0:
                        vendor_input.fill(data.vendor_name)
                except Exception as e:
                    self.logger.warning(f"取引先名入力失敗: {e}")

            # 金額
            if data.amount > 0:
                self.logger.info(f"金額: {data.amount:,}円")
                try:
                    amount_input = self.page.locator("input[name='saimokuKingaku(0_1)']")
                    if amount_input.count() > 0:
                        amount_input.fill(str(data.amount))
                except Exception as e:
                    self.logger.warning(f"金額入力失敗: {e}")

            time.sleep(2)

    def _fill_date_fields(self, prefix: str, date_str: str):
        """日付フィールドに入力

        Args:
            prefix: "trading" or "receiving"
            date_str: 日付 YYYY/MM/DD or YYYYMMDD
        """
        # 日付を分解
        date_str = date_str.replace("/", "").replace("-", "")
        if len(date_str) != 8:
            return

        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]

        self.logger.info(f"{prefix}日: {year}/{month}/{day}")

        try:
            if prefix == "trading":
                self.page.locator("input[name='tradingDateYear(0)']").fill(year)
                self.page.locator("input[name='tradingDateMonth(0)']").fill(month)
                self.page.locator("input[name='tradingDateDay(0)']").fill(day)
            elif prefix == "receiving":
                self.page.locator("input[name='receivingDateYear(0)']").fill(year)
                self.page.locator("input[name='receivingDateMonth(0)']").fill(month)
                self.page.locator("input[name='receivingDateDay(0)']").fill(day)
        except Exception as e:
            self.logger.warning(f"{prefix}日入力失敗: {e}")

    def submit(self, dry_run: bool = False, pause_before_submit: bool = False) -> bool:
        """確定ボタンをクリック

        Args:
            dry_run: Trueの場合は確定しない
            pause_before_submit: Trueの場合、確定前に一時停止

        Returns:
            成功/失敗
        """
        with LogContext("確定処理"):
            if dry_run:
                self.logger.info("ドライラン: 確定をスキップ")
                return True

            if pause_before_submit:
                self.logger.info("=" * 50)
                self.logger.info("確定ボタンを押す前で停止しています")
                self.logger.info("ブラウザで内容を確認してください")
                self.logger.info("30秒後に自動で確定します...")
                self.logger.info("=" * 50)
                time.sleep(30)

            try:
                # 確定ボタンをクリック（classにkakuteiを含むボタン）
                confirm_btn = self.page.locator("button.accesskeyOk, button:has-text('確定')").first
                if confirm_btn.count() > 0:
                    confirm_btn.scroll_into_view_if_needed()
                    time.sleep(1)
                    confirm_btn.click()
                    self.logger.info("確定ボタンクリック")
                else:
                    self.logger.warning("確定ボタンが見つかりません")
                    return False

                # 確認ダイアログ対応（事業者登録番号未入力時など）
                time.sleep(3)

                # デバッグ: 確定後のスクリーンショット
                try:
                    self.page.screenshot(path="C:/ProgramData/RK10/Robots/44PDF一般経費楽楽精算申請/docs/screenshots/after_confirm.png")
                    self.logger.info("確定後スクリーンショット保存")
                except:
                    pass

                # ダイアログのOKボタンを探してクリック（事業者登録番号未入力時など）
                dialog_clicked = False
                for attempt in range(10):
                    try:
                        # get_by_roleでOKボタンを探す
                        ok_btn = self.page.get_by_role("button", name="OK")
                        if ok_btn.count() > 0 and ok_btn.is_visible():
                            ok_btn.click()
                            self.logger.info("ダイアログOKクリック成功")
                            dialog_clicked = True
                            time.sleep(2)
                            break
                        time.sleep(1)
                    except Exception as e:
                        self.logger.debug(f"ダイアログ対応試行{attempt+1}: {e}")
                        time.sleep(1)

                if not dialog_clicked:
                    self.logger.info("ダイアログなし、または既に閉じている")

                # 処理完了待機
                self.logger.info("処理待機中（最大30秒）...")
                time.sleep(30)

                return True

            except Exception as e:
                self.logger.error(f"確定処理失敗: {e}")
                return False

    def run(
        self,
        pdf_path: str,
        data: Optional[ReceiptData] = None,
        headless: bool = False,
        dry_run: bool = False
    ) -> bool:
        """メイン処理

        Args:
            pdf_path: PDFファイルパス
            data: 入力データ（省略時はOCR結果を使用）
            headless: ヘッドレスモード
            dry_run: ドライラン

        Returns:
            成功/失敗
        """
        try:
            self.start_browser(headless=headless)
            self.login()
            self.navigate_to_receipt_form()

            if not self.upload_pdf(pdf_path):
                return False

            if data:
                self.fill_form(data)

            return self.submit(dry_run=dry_run)

        except Exception as e:
            self.logger.error(f"エラー: {e}", exc_info=True)
            return False

        finally:
            self.close_browser()


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="楽楽精算 領収書/請求書アップロード")
    parser.add_argument("--pdf", required=True, help="PDFファイルパス")
    parser.add_argument("--vendor", help="取引先名")
    parser.add_argument("--date", help="取引日 (YYYYMMDD)")
    parser.add_argument("--amount", type=int, help="金額")
    parser.add_argument("--invoice-no", help="事業者登録番号")
    parser.add_argument("--doc-type", default="請求書", choices=["領収書", "請求書"], help="書類区分")
    parser.add_argument("--env", choices=["LOCAL", "PROD"], help="環境")
    parser.add_argument("--headless", action="store_true", help="ヘッドレスモード")
    parser.add_argument("--dry-run", action="store_true", help="ドライラン")

    args = parser.parse_args()

    # ロガー設定
    setup_logger("rakuraku_upload")
    logger = get_logger()

    # 設定読み込み
    config = load_config(args.env)
    logger.info(f"環境: {config.get('ENV', 'UNKNOWN')}")

    # データ作成
    data = None
    if args.vendor or args.date or args.amount or args.invoice_no:
        data = ReceiptData(
            pdf_path=args.pdf,
            vendor_name=args.vendor or "",
            trading_date=args.date or "",
            amount=args.amount or 0,
            invoice_number=args.invoice_no or "",
            document_type=args.doc_type
        )

    # アップロード実行
    uploader = RakurakuUploader(config)
    success = uploader.run(
        pdf_path=args.pdf,
        data=data,
        headless=args.headless,
        dry_run=args.dry_run
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
