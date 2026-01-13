# -*- coding: utf-8 -*-
"""
PDFリネーム処理モジュール

FAX受信フォルダのPDFファイル名を以下の形式にリネーム:
    元: 20251117183719075.pdf（タイムスタンプ形式）
    後: {取引先名}_{発行日}_{金額}.pdf

Usage:
    # OCR自動モード（推奨）
    python pdf_renamer.py --auto

    # 手動入力モード
    python pdf_renamer.py --interactive

    # 単体リネーム
    python pdf_renamer.py --file 20251117183719075.pdf --vendor ソニービズネットワークス --date 20251107 --amount 22803
"""
import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass

# 共通モジュールをインポートできるようにパス追加
sys.path.insert(0, str(Path(__file__).parent))

from common.config_loader import load_config, get_env
from common.logger import setup_logger, get_logger, LogContext


@dataclass
class PDFInfo:
    """PDF情報"""
    original_path: Path
    vendor_name: str = ""
    issue_date: str = ""  # YYYYMMDD
    amount: int = 0
    invoice_number: str = ""  # 事業者登録番号（T+13桁）
    document_type: str = ""  # 領収書 or 請求書

    @property
    def new_filename(self) -> str:
        """リネーム後のファイル名を生成"""
        if not self.vendor_name:
            return self.original_path.name

        # ファイル名に使えない文字を置換
        safe_vendor = re.sub(r'[\\/:*?"<>|]', '_', self.vendor_name)

        # 金額をカンマなしで
        amount_str = str(self.amount) if self.amount > 0 else "0"

        return f"{safe_vendor}_{self.issue_date}_{amount_str}.pdf"


class PDFRenamer:
    """PDFリネームクラス"""

    def __init__(self, config: dict):
        """
        Args:
            config: 設定辞書
        """
        self.config = config
        self.fax_folder = Path(config.get("FAX_FOLDER", ""))
        self.processed_folder = Path(config.get("PROCESSED_FOLDER", ""))
        self.logger = get_logger()

    def get_pdf_list(self) -> List[Path]:
        """FAXフォルダからPDFファイルリストを取得

        Returns:
            PDFファイルパスのリスト（タイムスタンプ順）
        """
        if not self.fax_folder.exists():
            self.logger.warning(f"FAXフォルダが存在しません: {self.fax_folder}")
            return []

        pdfs = list(self.fax_folder.glob("*.pdf"))

        # タイムスタンプ形式のファイルを優先（数字のみのファイル名）
        def sort_key(p: Path) -> tuple:
            name = p.stem
            if name.isdigit():
                return (0, name)  # タイムスタンプ形式を先頭に
            return (1, name)

        pdfs.sort(key=sort_key)

        self.logger.info(f"PDFファイル数: {len(pdfs)}")
        return pdfs

    def rename_pdf(self, pdf_path: Path, info: PDFInfo) -> Optional[Path]:
        """PDFファイルをリネーム

        Args:
            pdf_path: 元のPDFパス
            info: PDF情報

        Returns:
            リネーム後のパス（失敗時はNone）
        """
        if not info.vendor_name:
            self.logger.warning(f"取引先名が未設定: {pdf_path.name}")
            return None

        new_name = info.new_filename
        new_path = pdf_path.parent / new_name

        # 同名ファイルが存在する場合は連番を付ける
        counter = 1
        while new_path.exists():
            stem = new_path.stem
            new_path = pdf_path.parent / f"{stem}_{counter:03d}.pdf"
            counter += 1

        try:
            pdf_path.rename(new_path)
            self.logger.info(f"リネーム: {pdf_path.name} -> {new_path.name}")
            return new_path
        except Exception as e:
            self.logger.error(f"リネーム失敗: {pdf_path.name} - {e}")
            return None

    def move_to_processed(self, pdf_path: Path) -> Optional[Path]:
        """処理済みフォルダに移動

        Args:
            pdf_path: PDFパス

        Returns:
            移動後のパス（失敗時はNone）
        """
        if not self.processed_folder:
            return pdf_path

        # 処理済みフォルダを作成
        self.processed_folder.mkdir(parents=True, exist_ok=True)

        dest_path = self.processed_folder / pdf_path.name

        # 同名ファイルが存在する場合は連番を付ける
        counter = 1
        while dest_path.exists():
            stem = pdf_path.stem
            dest_path = self.processed_folder / f"{stem}_{counter:03d}.pdf"
            counter += 1

        try:
            import shutil
            shutil.move(str(pdf_path), str(dest_path))
            self.logger.info(f"移動: {pdf_path.name} -> {dest_path}")
            return dest_path
        except Exception as e:
            self.logger.error(f"移動失敗: {pdf_path.name} - {e}")
            return None


def auto_rename_with_ocr(renamer: PDFRenamer) -> List[PDFInfo]:
    """OCRを使用して自動リネーム

    Args:
        renamer: PDFRenamerインスタンス

    Returns:
        処理したPDF情報のリスト
    """
    # Document AI版を優先、なければAdobe OCR版にフォールバック
    try:
        from pdf_ocr_documentai import DocumentAIOCRProcessor as PDFOCRProcessor
        print("  [OCRエンジン: Document AI]")
    except ImportError:
        from pdf_ocr import PDFOCRProcessor
        print("  [OCRエンジン: Adobe PDF Services]")

    logger = get_logger()
    pdfs = renamer.get_pdf_list()

    if not pdfs:
        logger.info("処理対象のPDFがありません")
        return []

    results = []
    processor = PDFOCRProcessor()

    print("\n" + "=" * 60)
    print("PDFリネーム処理（OCR自動モード）")
    print("=" * 60)
    print(f"対象フォルダ: {renamer.fax_folder}")
    print(f"ファイル数: {len(pdfs)}")
    print("-" * 60)

    for i, pdf_path in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] {pdf_path.name}")
        print("  OCR処理中...")

        # OCR処理
        ocr_result = processor.process_pdf(pdf_path)

        if not ocr_result.success:
            print(f"  OCR失敗: {ocr_result.error}")
            print("  -> スキップ（手動で処理してください）")
            continue

        # 抽出結果を表示
        print(f"  取引先: {ocr_result.vendor_name}")
        print(f"  日付: {ocr_result.issue_date}")
        print(f"  金額: {ocr_result.amount:,}円" if ocr_result.amount else "  金額: -")
        print(f"  事業者登録番号: {ocr_result.invoice_number}")

        # 確認
        confirm = input("  この内容でリネーム? [y/n/edit]: ").strip().lower()

        if confirm == 'n':
            print("  -> スキップ")
            continue
        elif confirm == 'edit':
            # 手動修正
            vendor = input(f"  取引先名 [{ocr_result.vendor_name}]: ").strip()
            if not vendor:
                vendor = ocr_result.vendor_name

            date_str = input(f"  発行日 [{ocr_result.issue_date}]: ").strip()
            if not date_str:
                date_str = ocr_result.issue_date

            amount_str = input(f"  金額 [{ocr_result.amount}]: ").strip()
            if amount_str:
                amount = int(re.sub(r'[,¥\\]', '', amount_str))
            else:
                amount = ocr_result.amount

            invoice_no = input(f"  事業者登録番号 [{ocr_result.invoice_number}]: ").strip()
            if not invoice_no:
                invoice_no = ocr_result.invoice_number
        else:
            # OCR結果をそのまま使用
            vendor = ocr_result.vendor_name
            date_str = ocr_result.issue_date
            amount = ocr_result.amount
            invoice_no = ocr_result.invoice_number

        # PDF情報を作成
        info = PDFInfo(
            original_path=pdf_path,
            vendor_name=vendor,
            issue_date=date_str,
            amount=amount,
            invoice_number=invoice_no
        )

        # リネーム実行
        new_path = renamer.rename_pdf(pdf_path, info)
        if new_path:
            info.original_path = new_path
            results.append(info)
            print(f"  -> リネーム完了: {new_path.name}")

    return results


def interactive_rename(renamer: PDFRenamer) -> List[PDFInfo]:
    """対話形式でPDFをリネーム（手動入力）

    Args:
        renamer: PDFRenamerインスタンス

    Returns:
        処理したPDF情報のリスト
    """
    logger = get_logger()
    pdfs = renamer.get_pdf_list()

    if not pdfs:
        logger.info("処理対象のPDFがありません")
        return []

    results = []

    print("\n" + "=" * 60)
    print("PDFリネーム処理（手動入力モード）")
    print("=" * 60)
    print(f"対象フォルダ: {renamer.fax_folder}")
    print(f"ファイル数: {len(pdfs)}")
    print("-" * 60)
    print("各PDFを確認して、取引先名・発行日・金額を入力してください")
    print("スキップ: 空Enter / 終了: q")
    print("-" * 60)

    for i, pdf_path in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] {pdf_path.name}")

        # 取引先名
        vendor = input("  取引先名: ").strip()
        if vendor.lower() == 'q':
            print("終了します")
            break
        if not vendor:
            print("  -> スキップ")
            continue

        # 発行日
        date_str = input("  発行日 (YYYYMMDD): ").strip()
        if not date_str:
            date_str = pdf_path.stem[:8] if pdf_path.stem.isdigit() else ""

        # 金額
        amount_str = input("  金額: ").strip()
        amount = int(re.sub(r'[,¥\\]', '', amount_str)) if amount_str else 0

        # 事業者登録番号（オプション）
        invoice_no = input("  事業者登録番号 (省略可): ").strip()

        # PDF情報を作成
        info = PDFInfo(
            original_path=pdf_path,
            vendor_name=vendor,
            issue_date=date_str,
            amount=amount,
            invoice_number=invoice_no
        )

        # リネーム実行
        new_path = renamer.rename_pdf(pdf_path, info)
        if new_path:
            info.original_path = new_path
            results.append(info)

    return results


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="PDFリネーム処理")
    parser.add_argument("--env", choices=["LOCAL", "PROD"], help="環境")
    parser.add_argument("--file", help="対象PDFファイル名")
    parser.add_argument("--vendor", help="取引先名")
    parser.add_argument("--date", help="発行日 (YYYYMMDD)")
    parser.add_argument("--amount", type=int, help="金額")
    parser.add_argument("--invoice-no", help="事業者登録番号")
    parser.add_argument("--list", action="store_true", help="PDFリストを表示")
    parser.add_argument("--interactive", action="store_true", help="手動入力モード")
    parser.add_argument("--auto", action="store_true", help="OCR自動モード（推奨）")

    args = parser.parse_args()

    # ロガー設定
    setup_logger("pdf_renamer")
    logger = get_logger()

    # 設定読み込み
    config = load_config(args.env)
    logger.info(f"環境: {config.get('ENV', 'UNKNOWN')}")

    renamer = PDFRenamer(config)

    # リスト表示モード
    if args.list:
        pdfs = renamer.get_pdf_list()
        print(f"\nPDFファイル一覧 ({len(pdfs)}件):")
        for i, pdf in enumerate(pdfs, 1):
            print(f"  {i}. {pdf.name}")
        return 0

    # OCR自動モード
    if args.auto:
        results = auto_rename_with_ocr(renamer)
        print(f"\n処理完了: {len(results)}件")
        return 0

    # 手動入力モード
    if args.interactive:
        results = interactive_rename(renamer)
        print(f"\n処理完了: {len(results)}件")
        return 0

    # 単体リネームモード
    if args.file and args.vendor:
        pdf_path = renamer.fax_folder / args.file
        if not pdf_path.exists():
            logger.error(f"ファイルが見つかりません: {pdf_path}")
            return 1

        info = PDFInfo(
            original_path=pdf_path,
            vendor_name=args.vendor,
            issue_date=args.date or "",
            amount=args.amount or 0,
            invoice_number=args.invoice_no or ""
        )

        new_path = renamer.rename_pdf(pdf_path, info)
        if new_path:
            logger.info(f"リネーム完了: {new_path}")
            return 0
        return 1

    # 引数なしの場合はヘルプを表示
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
