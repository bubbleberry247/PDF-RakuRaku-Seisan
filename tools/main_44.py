# -*- coding: utf-8 -*-
"""
44PDF一般経費楽楽精算申請 メイン処理（SmartOCR統合版）

FAXで受信したPDFを楽楽精算に登録する

処理フロー:
1. FAX受信フォルダからPDFを取得
2. SmartOCR前処理（回転・傾き・影除去）
3. ローカルOCR（YomiToku）で信頼度判定
4. 高信頼度: 楽楽精算にアップロード・登録
5. 低信頼度: 手動キューに振り分け

Updated: 2026-01-14 - Document AI廃止対応

Usage:
    # 対話形式で実行
    python main_44.py

    # 特定PDFのみ処理
    python main_44.py --pdf "取引先名_20251107_22803.pdf"

    # ドライラン（確定しない）
    python main_44.py --dry-run

    # SmartOCRをスキップ（楽楽精算のOCRのみ使用）
    python main_44.py --skip-smart-ocr
"""
import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

# 共通モジュールをインポートできるようにパス追加
sys.path.insert(0, str(Path(__file__).parent))

from common.config_loader import load_config, get_env
from common.logger import setup_logger, get_logger, LogContext

from pdf_renamer import PDFRenamer, PDFInfo, interactive_rename
from rakuraku_upload import RakurakuUploader, ReceiptData

# SmartOCR（Document AI廃止後のメインOCR）
try:
    from pdf_ocr_smart import SmartOCRProcessor, SmartOCRResult, CONFIDENCE_THRESHOLD
    SMART_OCR_AVAILABLE = True
except ImportError:
    SMART_OCR_AVAILABLE = False


def process_single_pdf(
    uploader: RakurakuUploader,
    pdf_path: Path,
    info: Optional[PDFInfo] = None,
    headless: bool = False,
    dry_run: bool = False,
    skip_smart_ocr: bool = False,
    smart_ocr_processor: Optional['SmartOCRProcessor'] = None
) -> dict:
    """単一PDFを処理

    Args:
        uploader: RakurakuUploaderインスタンス
        pdf_path: PDFファイルパス
        info: PDF情報（リネーム後のデータ）
        headless: ヘッドレスモード
        dry_run: ドライラン
        skip_smart_ocr: SmartOCRをスキップするか
        smart_ocr_processor: SmartOCRProcessorインスタンス

    Returns:
        処理結果 {'success': bool, 'requires_manual': bool, 'confidence': float}
    """
    logger = get_logger()
    result = {'success': False, 'requires_manual': False, 'confidence': 0.0}

    with LogContext(f"PDF処理: {pdf_path.name}"):
        # SmartOCR処理（前処理＋ローカルOCR＋信頼度判定）
        ocr_result = None
        upload_path = pdf_path  # アップロードするPDFのパス

        if SMART_OCR_AVAILABLE and not skip_smart_ocr and smart_ocr_processor:
            logger.info("SmartOCR処理開始...")
            ocr_result = smart_ocr_processor.process(
                pdf_path,
                output_dir=pdf_path.parent,
                auto_queue=True  # 低信頼度は自動的にキューに追加
            )

            result['confidence'] = ocr_result.confidence

            # 低信頼度の場合は手動対応
            if ocr_result.requires_manual:
                logger.warning(
                    f"低信頼度({ocr_result.confidence:.2f}) → 手動キューに追加"
                )
                result['requires_manual'] = True
                return result

            # 前処理済みPDFを使用
            if ocr_result.preprocess_info:
                preproc_path = pdf_path.parent / f"_preproc_{pdf_path.name}"
                if preproc_path.exists():
                    upload_path = preproc_path
                    logger.info(f"前処理済みPDFを使用: {upload_path.name}")

        # ReceiptDataを作成
        data = None
        if info:
            # リネーム情報から作成
            data = ReceiptData(
                pdf_path=str(upload_path),
                vendor_name=info.vendor_name,
                trading_date=info.issue_date,
                amount=info.amount,
                invoice_number=info.invoice_number
            )
        elif ocr_result and ocr_result.success:
            # SmartOCR結果から作成
            data = ReceiptData(
                pdf_path=str(upload_path),
                vendor_name=ocr_result.vendor_name,
                trading_date=ocr_result.issue_date,
                amount=ocr_result.amount,
                invoice_number=ocr_result.invoice_number
            )
            logger.info(
                f"SmartOCR結果を使用: vendor={ocr_result.vendor_name}, "
                f"date={ocr_result.issue_date}, amount={ocr_result.amount}"
            )

        # アップロード実行
        success = uploader.run(
            pdf_path=str(upload_path),
            data=data,
            headless=headless,
            dry_run=dry_run
        )

        result['success'] = success
        return result


def process_all_pdfs(
    config: dict,
    headless: bool = False,
    dry_run: bool = False,
    skip_smart_ocr: bool = False
) -> dict:
    """全PDFを処理（対話形式）

    Args:
        config: 設定辞書
        headless: ヘッドレスモード
        dry_run: ドライラン
        skip_smart_ocr: SmartOCRをスキップするか

    Returns:
        処理結果 {'success': count, 'failed': count, 'skipped': count, 'manual': count}
    """
    logger = get_logger()
    renamer = PDFRenamer(config)
    uploader = RakurakuUploader(config)

    # SmartOCRプロセッサを初期化
    smart_ocr = None
    if SMART_OCR_AVAILABLE and not skip_smart_ocr:
        try:
            smart_ocr = SmartOCRProcessor(use_gpu=False, lite_mode=True)
            logger.info("SmartOCRプロセッサ初期化完了（CPU lite_mode）")
        except Exception as e:
            logger.warning(f"SmartOCR初期化失敗: {e} → 楽楽精算OCRのみ使用")

    results = {
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'manual': 0
    }

    # PDFリストを取得
    pdfs = renamer.get_pdf_list()
    if not pdfs:
        logger.info("処理対象のPDFがありません")
        return results

    print("\n" + "=" * 60)
    print("44PDF一般経費楽楽精算申請")
    print("=" * 60)
    print(f"環境: {config.get('ENV', 'UNKNOWN')}")
    print(f"FAXフォルダ: {config.get('FAX_FOLDER', '')}")
    print(f"PDFファイル数: {len(pdfs)}")
    print("-" * 60)

    # 処理モードを選択
    print("\n処理モードを選択してください:")
    print("  1. 対話形式（各PDFを確認しながら処理）")
    print("  2. 一括処理（OCR自動入力のみで処理）")
    print("  q. 終了")
    mode = input("\n選択 [1/2/q]: ").strip()

    if mode.lower() == 'q':
        print("終了します")
        return results

    # 対話形式
    if mode == '1':
        # リネーム処理
        print("\n--- フェーズ1: PDFリネーム ---")
        renamed_pdfs = interactive_rename(renamer)

        if not renamed_pdfs:
            logger.info("リネームされたPDFがありません")
            return results

        # アップロード処理
        print("\n--- フェーズ2: 楽楽精算アップロード ---")
        print(f"アップロード対象: {len(renamed_pdfs)}件")
        confirm = input("アップロードを開始しますか？ [y/n]: ").strip().lower()

        if confirm != 'y':
            results['skipped'] = len(renamed_pdfs)
            return results

        for info in renamed_pdfs:
            proc_result = process_single_pdf(
                uploader=uploader,
                pdf_path=info.original_path,
                info=info,
                headless=headless,
                dry_run=dry_run,
                skip_smart_ocr=skip_smart_ocr,
                smart_ocr_processor=smart_ocr
            )
            if proc_result['requires_manual']:
                results['manual'] += 1
            elif proc_result['success']:
                results['success'] += 1
                # 処理済みフォルダに移動
                renamer.move_to_processed(info.original_path)
            else:
                results['failed'] += 1

    # 一括処理（SmartOCR使用）
    elif mode == '2':
        print("\n--- 一括処理モード（SmartOCR） ---")
        if smart_ocr:
            print(f"SmartOCRによる前処理＋ローカルOCRを使用")
            print(f"信頼度閾値: {CONFIDENCE_THRESHOLD}")
            print(f"低信頼度PDFは手動キューに振り分け")
        else:
            print("SmartOCRが利用できません → 楽楽精算OCRのみ使用")

        confirm = input("開始しますか？ [y/n]: ").strip().lower()

        if confirm != 'y':
            results['skipped'] = len(pdfs)
            return results

        for pdf_path in pdfs:
            proc_result = process_single_pdf(
                uploader=uploader,
                pdf_path=pdf_path,
                info=None,  # SmartOCR結果を使用
                headless=headless,
                dry_run=dry_run,
                skip_smart_ocr=skip_smart_ocr,
                smart_ocr_processor=smart_ocr
            )
            if proc_result['requires_manual']:
                results['manual'] += 1
                print(f"  → 手動キューへ: {pdf_path.name}")
            elif proc_result['success']:
                results['success'] += 1
                renamer.move_to_processed(pdf_path)
            else:
                results['failed'] += 1

    return results


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="44PDF一般経費楽楽精算申請（SmartOCR統合版）")
    parser.add_argument("--pdf", help="特定PDFファイルパス")
    parser.add_argument("--env", choices=["LOCAL", "PROD"], help="環境")
    parser.add_argument("--headless", action="store_true", help="ヘッドレスモード")
    parser.add_argument("--dry-run", action="store_true", help="ドライラン（確定しない）")
    parser.add_argument("--list", action="store_true", help="PDFリストを表示")
    parser.add_argument("--skip-smart-ocr", action="store_true", help="SmartOCRをスキップ")
    parser.add_argument("--show-queue", action="store_true", help="手動キューを表示")

    args = parser.parse_args()

    # ロガー設定
    setup_logger("main_44")
    logger = get_logger()

    # 設定読み込み
    config = load_config(args.env)
    logger.info(f"環境: {config.get('ENV', 'UNKNOWN')}")

    # 手動キュー表示モード
    if args.show_queue:
        from pdf_ocr_smart import MANUAL_QUEUE_DIR
        queue_file = MANUAL_QUEUE_DIR / "queue.json"
        if queue_file.exists():
            import json
            queue = json.loads(queue_file.read_text(encoding="utf-8"))
            print(f"\n手動キュー ({len(queue)}件):")
            print("-" * 60)
            for item in queue:
                print(f"  ファイル: {item['file']}")
                print(f"    登録日時: {item['timestamp']}")
                print(f"    信頼度: {item['confidence']:.2%}")
                partial = item.get('partial_result', {})
                if partial:
                    print(f"    部分結果: vendor={partial.get('vendor_name', '')}, "
                          f"amount={partial.get('amount', 0)}")
                print()
        else:
            print("\n手動キューは空です")
        return 0

    # リスト表示モード
    if args.list:
        renamer = PDFRenamer(config)
        pdfs = renamer.get_pdf_list()
        print(f"\nPDFファイル一覧 ({len(pdfs)}件):")
        for i, pdf in enumerate(pdfs, 1):
            print(f"  {i}. {pdf.name}")
        return 0

    # 特定PDF処理モード
    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            # FAXフォルダから探す
            fax_folder = Path(config.get("FAX_FOLDER", ""))
            pdf_path = fax_folder / args.pdf

        if not pdf_path.exists():
            logger.error(f"ファイルが見つかりません: {args.pdf}")
            return 1

        # SmartOCRプロセッサを初期化
        smart_ocr = None
        if SMART_OCR_AVAILABLE and not args.skip_smart_ocr:
            try:
                smart_ocr = SmartOCRProcessor(use_gpu=False, lite_mode=True)
            except Exception as e:
                logger.warning(f"SmartOCR初期化失敗: {e}")

        uploader = RakurakuUploader(config)
        proc_result = process_single_pdf(
            uploader=uploader,
            pdf_path=pdf_path,
            info=None,
            headless=args.headless,
            dry_run=args.dry_run,
            skip_smart_ocr=args.skip_smart_ocr,
            smart_ocr_processor=smart_ocr
        )

        if proc_result['requires_manual']:
            print(f"\n低信頼度({proc_result['confidence']:.2%}) → 手動キューに追加されました")
            return 1
        return 0 if proc_result['success'] else 1

    # 対話形式処理
    results = process_all_pdfs(
        config=config,
        headless=args.headless,
        dry_run=args.dry_run,
        skip_smart_ocr=args.skip_smart_ocr
    )

    # 結果表示
    print("\n" + "=" * 60)
    print("処理結果")
    print("=" * 60)
    print(f"  成功: {results['success']}件")
    print(f"  手動対応: {results['manual']}件")
    print(f"  失敗: {results['failed']}件")
    print(f"  スキップ: {results['skipped']}件")
    print("=" * 60)

    if results['manual'] > 0:
        print(f"\n※ 手動キュー確認: python main_44.py --show-queue")

    return 0 if results['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
