# -*- coding: utf-8 -*-
"""
44PDF一般経費楽楽精算申請 RK10連携CLI

RK10シナリオから呼び出すための非対話CLIインターフェース

Usage:
    # Phase 1: 前処理（FAX取得→SmartOCR→data.json出力）
    python main_44_rk10.py --pre

    # Phase 2: 一括処理（ログイン→全PDF登録→終了）
    python main_44_rk10.py --run-all

    # Phase 3: 後処理（PDF移動→結果出力）
    python main_44_rk10.py --post

    # その他
    python main_44_rk10.py --get-count    # データ件数取得
    python main_44_rk10.py --reset        # インデックスリセット

Options:
    --dry-run    確定ボタンを押さない（テスト用）
    --headless   ヘッドレスモードで実行
    --env        環境指定（LOCAL/PROD）

Created: 2026-01-26
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

TOOLS_OCR_CORE = Path(r"C:\ProgramData\RK10\Tools\ocr\core")
if TOOLS_OCR_CORE.exists():
    sys.path.insert(0, str(TOOLS_OCR_CORE))
ROBOT_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("RK10_ROBOT_DIR", str(ROBOT_DIR))


from typing import List, Optional, Dict

# 共通モジュールをインポートできるようにパス追加
sys.path.insert(0, str(Path(__file__).parent))

from common.config_loader import load_config, get_env
from common.logger import setup_logger, get_logger, LogContext

from pdf_renamer import PDFRenamer
from rakuraku_upload import RakurakuUploader, ReceiptData

# SmartOCR
try:
    from pdf_ocr_smart import SmartOCRProcessor, SmartOCRResult, CONFIDENCE_THRESHOLD
    SMART_OCR_AVAILABLE = True
except ImportError:
    SMART_OCR_AVAILABLE = False

# メール送信モジュール
try:
    from mail_sender import send_mail, save_result
    MAIL_AVAILABLE = True
except ImportError:
    MAIL_AVAILABLE = False

# 中間データディレクトリ
WORK_OUTPUT_DIR = Path(__file__).parent.parent / "work" / "output"
DATA_JSON_PATH = WORK_OUTPUT_DIR / "data.json"
RESULT_JSON_PATH = WORK_OUTPUT_DIR / "result.json"
INDEX_FILE_PATH = WORK_OUTPUT_DIR / "current_index.txt"

# OCR失敗フォルダ
OCR_FAILED_BASE_DIR = Path(__file__).parent.parent / "work" / "ocr_failed"


def ensure_work_dir():
    """作業ディレクトリを作成"""
    WORK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_ocr_failed_dir() -> Path:
    """本日のOCR失敗フォルダを取得（なければ作成）"""
    today = datetime.now().strftime("%Y%m%d")
    failed_dir = OCR_FAILED_BASE_DIR / today
    failed_dir.mkdir(parents=True, exist_ok=True)
    return failed_dir


def move_to_ocr_failed(pdf_path: Path, confidence: float = 0.0, reason: str = "OCR失敗") -> Optional[Path]:
    """PDFをOCR失敗フォルダに移動"""
    logger = get_logger()
    try:
        failed_dir = get_ocr_failed_dir()
        dest_path = failed_dir / pdf_path.name

        if dest_path.exists():
            base = pdf_path.stem
            ext = pdf_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = failed_dir / f"{base}_{counter}{ext}"
                counter += 1

        shutil.move(str(pdf_path), str(dest_path))
        logger.info(f"OCR失敗フォルダに移動: {dest_path}")
        return dest_path
    except Exception as e:
        logger.error(f"OCR失敗フォルダへの移動エラー: {e}")
        return None


# =============================================================================
# コマンド: --pre（前処理）
# =============================================================================
def rename_pdf_with_ocr(pdf_path: Path, vendor_name: str, issue_date: str, amount: int) -> Optional[Path]:
    """PDFをOCR結果でリネーム

    フォーマット: {会社名}_{請求書発行年月}_{請求金額}.pdf
    例: ソニービズネットワークス_202511_22803.pdf

    Args:
        pdf_path: 元のPDFパス
        vendor_name: 会社名
        issue_date: 発行日（YYYYMMDD）
        amount: 請求金額

    Returns:
        リネーム後のパス（失敗時はNone）
    """
    import re
    logger = get_logger()

    if not vendor_name:
        logger.warning(f"会社名が未設定のためリネームスキップ: {pdf_path.name}")
        return pdf_path

    # ファイル名に使えない文字を置換
    safe_vendor = re.sub(r'[\\/:*?"<>|]', '_', vendor_name)

    # 発行年月（YYYYMM形式）
    issue_yearmonth = issue_date[:6] if issue_date and len(issue_date) >= 6 else ""

    # 新しいファイル名を生成
    if issue_yearmonth and amount > 0:
        new_name = f"{safe_vendor}_{issue_yearmonth}_{amount}.pdf"
    elif issue_yearmonth:
        new_name = f"{safe_vendor}_{issue_yearmonth}.pdf"
    else:
        new_name = f"{safe_vendor}_{amount}.pdf"

    new_path = pdf_path.parent / new_name

    # 同名ファイルが存在する場合は連番を付ける
    counter = 1
    base_stem = new_path.stem
    while new_path.exists() and new_path != pdf_path:
        new_path = pdf_path.parent / f"{base_stem}_{counter:03d}.pdf"
        counter += 1

    # 元のファイルと同じ名前なら何もしない
    if new_path == pdf_path:
        return pdf_path

    if not pdf_path.exists():
        logger.error(f"リネーム元が見つかりません: {pdf_path}")
        return None

    try:
        pdf_path.rename(new_path)
        logger.info(f"リネーム: {pdf_path.name} → {new_path.name}")
        return new_path
    except Exception as e:
        logger.error(f"リネーム失敗: {pdf_path.name} - {e}")
        return pdf_path


def cmd_pre(config: dict) -> int:
    """前処理: FAXフォルダからPDF取得→SmartOCR→リネーム→output/error移動→data.json出力

    処理内容:
    1. FAXフォルダからPDFを取得
    2. SmartOCRで会社名・発行年月・金額を抽出
    3. PDFを「会社名_請求書発行年月_請求金額.pdf」形式にリネーム
    4. 成功→output/フォルダ、エラー→error/フォルダに移動
    5. data.jsonに出力

    Returns:
        0: 成功, 1: 失敗
    """
    logger = get_logger()
    ensure_work_dir()

    # 出力フォルダとエラーフォルダを設定（inputフォルダの兄弟として）
    fax_folder = Path(config.get("FAX_FOLDER", ""))
    output_folder = fax_folder.parent / "output"
    error_folder = fax_folder.parent / "error"
    output_folder.mkdir(parents=True, exist_ok=True)
    error_folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"出力フォルダ: {output_folder}")
    logger.info(f"エラーフォルダ: {error_folder}")

    logger.info("=== Phase 1: 前処理開始 ===")

    # tmp_preprocディレクトリ（inputフォルダの兄弟として作成）
    tmp_preproc_dir = fax_folder.parent / "tmp_preproc"
    tmp_preproc_dir.mkdir(parents=True, exist_ok=True)

    # inputフォルダの_preproc_残骸を掃除
    for stale in fax_folder.glob("_preproc_*.pdf"):
        try:
            stale.unlink()
            logger.info(f"残骸削除: {stale.name}")
        except Exception:
            pass

    # SmartOCRプロセッサを初期化
    smart_ocr = None
    if SMART_OCR_AVAILABLE:
        try:
            smart_ocr = SmartOCRProcessor(use_gpu=False, lite_mode=True)
            logger.info("SmartOCRプロセッサ初期化完了（CPU lite_mode）")
        except Exception as e:
            logger.warning(f"SmartOCR初期化失敗: {e}")

    # PDFリストを取得
    renamer = PDFRenamer(config)
    pdfs = renamer.get_pdf_list()

    if not pdfs:
        logger.info("処理対象のPDFがありません")
        # 空のdata.jsonを作成
        data = {
            "scenario_id": "44",
            "scenario_name": "【44】PDF一般経費楽楽精算申請",
            "created_at": datetime.now().isoformat(),
            "config": {
                "env": config.get("ENV", "LOCAL"),
                "fax_folder": config.get("FAX_FOLDER", "")
            },
            "total_count": 0,
            "manual_count": 0,
            "data": [],
            "manual_queue": []
        }
        DATA_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    logger.info(f"PDF件数: {len(pdfs)}")

    # OCR処理 + リネーム
    data_list = []
    manual_queue = []

    for i, pdf_path in enumerate(pdfs):
        logger.info(f"処理中 [{i+1}/{len(pdfs)}]: {pdf_path.name}")

        item = {
            "_index": i,
            "_pdf_path": str(pdf_path),
            "_pdf_name": pdf_path.name,
            "_original_name": pdf_path.name,  # リネーム前の名前を保持
            "_preprocessed_path": "",
            "_confidence": 0.0,
            "_requires_manual": False,
            "vendor_name": "",
            "issue_date": "",
            "amount": 0,
            "invoice_number": "",
            "document_type": "請求書",
            "storage_type": "スキャナ保存"
        }

        if smart_ocr:
            try:
                ocr_result = smart_ocr.process(
                    pdf_path,
                    output_dir=tmp_preproc_dir,
                    auto_queue=False  # 手動で振り分け
                )

                item["_confidence"] = ocr_result.confidence
                item["vendor_name"] = ocr_result.vendor_name or ""
                item["issue_date"] = ocr_result.issue_date or ""
                item["amount"] = ocr_result.amount or 0
                item["invoice_number"] = ocr_result.invoice_number or ""

                # 前処理済みPDFパス（tmp_preproc_dir配下）
                preproc_path = tmp_preproc_dir / f"_preproc_{pdf_path.name}"
                if preproc_path.exists():
                    item["_preprocessed_path"] = str(preproc_path)

                # 信頼度判定
                if ocr_result.requires_manual:
                    item["_requires_manual"] = True
                    # エラーファイルをerrorフォルダに移動
                    try:
                        dest_error = error_folder / pdf_path.name
                        if dest_error.exists():
                            counter = 1
                            base_stem = dest_error.stem
                            while dest_error.exists():
                                dest_error = error_folder / f"{base_stem}_{counter:03d}.pdf"
                                counter += 1
                        shutil.move(str(pdf_path), str(dest_error))
                        item["_pdf_path"] = str(dest_error)
                        item["_pdf_name"] = dest_error.name
                        # 前処理済みPDFは削除
                        if preproc_path.exists():
                            preproc_path.unlink()
                        logger.warning(f"  → 低信頼度({ocr_result.confidence:.2%}) → errorに移動: {dest_error.name}")
                    except Exception as e:
                        logger.warning(f"  → 低信頼度({ocr_result.confidence:.2%}) → 移動失敗: {e}")
                    manual_queue.append(item)
                else:
                    # ★ リネーム処理（会社名_請求書発行年月_請求金額.pdf）
                    new_path = rename_pdf_with_ocr(
                        pdf_path,
                        ocr_result.vendor_name,
                        ocr_result.issue_date,
                        ocr_result.amount
                    )
                    if new_path:
                        item["_pdf_path"] = str(new_path)
                        item["_pdf_name"] = new_path.name
                        # 前処理済みPDFもリネーム
                        if preproc_path.exists():
                            new_preproc = preproc_path.parent / f"_preproc_{new_path.name}"
                            try:
                                preproc_path.rename(new_preproc)
                                item["_preprocessed_path"] = str(new_preproc)
                            except:
                                pass

                    # 成功したファイルをoutputフォルダに移動
                    if new_path and new_path.exists():
                        dest_path = output_folder / new_path.name
                        if dest_path.exists():
                            # 同名ファイルが存在する場合は連番
                            counter = 1
                            base_stem = dest_path.stem
                            while dest_path.exists():
                                dest_path = output_folder / f"{base_stem}_{counter:03d}.pdf"
                                counter += 1
                        try:
                            shutil.move(str(new_path), str(dest_path))
                            item["_pdf_path"] = str(dest_path)
                            item["_pdf_name"] = dest_path.name
                            logger.info(f"  → outputに移動: {dest_path.name}")
                            # 前処理済みPDFは削除（tmp_preproc_dir配下）
                            preproc_new = tmp_preproc_dir / f"_preproc_{new_path.name}"
                            if preproc_new.exists():
                                preproc_new.unlink()
                        except Exception as e:
                            logger.warning(f"  → 移動失敗: {e}")

                    data_list.append(item)
                    logger.info(f"  → 成功: vendor={ocr_result.vendor_name}, amount={ocr_result.amount}")

            except Exception as e:
                logger.error(f"OCRエラー: {e}")
                item["_requires_manual"] = True
                # OCRエラーファイルもerrorフォルダに移動
                try:
                    dest_error = error_folder / pdf_path.name
                    if dest_error.exists():
                        counter = 1
                        base_stem = dest_error.stem
                        while dest_error.exists():
                            dest_error = error_folder / f"{base_stem}_{counter:03d}.pdf"
                            counter += 1
                    shutil.move(str(pdf_path), str(dest_error))
                    item["_pdf_path"] = str(dest_error)
                    item["_pdf_name"] = dest_error.name
                    # 前処理済みPDFがあれば削除（tmp_preproc_dir配下）
                    preproc_path = tmp_preproc_dir / f"_preproc_{pdf_path.name}"
                    if preproc_path.exists():
                        preproc_path.unlink()
                    logger.info(f"  → errorに移動: {dest_error.name}")
                except Exception as move_e:
                    logger.warning(f"  → 移動失敗: {move_e}")
                manual_queue.append(item)
        else:
            # SmartOCRなしの場合はerrorフォルダに移動
            item["_requires_manual"] = True
            try:
                dest_error = error_folder / pdf_path.name
                if dest_error.exists():
                    counter = 1
                    base_stem = dest_error.stem
                    while dest_error.exists():
                        dest_error = error_folder / f"{base_stem}_{counter:03d}.pdf"
                        counter += 1
                shutil.move(str(pdf_path), str(dest_error))
                item["_pdf_path"] = str(dest_error)
                item["_pdf_name"] = dest_error.name
                logger.info(f"  → SmartOCRなし → errorに移動: {dest_error.name}")
            except Exception as e:
                logger.warning(f"  → 移動失敗: {e}")
            manual_queue.append(item)

    # data.json出力
    data = {
        "scenario_id": "44",
        "scenario_name": "【44】PDF一般経費楽楽精算申請",
        "created_at": datetime.now().isoformat(),
        "config": {
            "env": config.get("ENV", "LOCAL"),
            "fax_folder": config.get("FAX_FOLDER", ""),
            "output_folder": str(output_folder),
            "error_folder": str(error_folder)
        },
        "total_count": len(data_list),
        "manual_count": len(manual_queue),
        "data": data_list,
        "manual_queue": manual_queue
    }

    DATA_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"data.json出力完了: {DATA_JSON_PATH}")
    logger.info(f"  自動処理対象: {len(data_list)}件")
    logger.info(f"  手動対応必要: {len(manual_queue)}件")

    # tmp_preprocフォルダの残骸を掃除
    for stale in tmp_preproc_dir.glob("_preproc_*.pdf"):
        try:
            stale.unlink()
        except Exception:
            pass

    # インデックスリセット
    INDEX_FILE_PATH.write_text("0", encoding="utf-8")

    return 0


# =============================================================================
# コマンド: --run-all（一括処理）
# =============================================================================
def cmd_run_all(config: dict, headless: bool = False, dry_run: bool = False) -> int:
    """一括処理: ログイン→全PDF登録→終了

    Returns:
        0: 成功, 1: 失敗
    """
    logger = get_logger()

    logger.info("=== Phase 2: 一括処理開始 ===")

    # data.json読み込み
    if not DATA_JSON_PATH.exists():
        logger.error("data.jsonが見つかりません。先に --pre を実行してください")
        return 1

    data = json.loads(DATA_JSON_PATH.read_text(encoding="utf-8"))
    data_list = data.get("data", [])

    if not data_list:
        logger.info("処理対象のPDFがありません")
        return 0

    logger.info(f"処理対象: {len(data_list)}件")

    # 結果初期化
    results = {
        "scenario_id": "44",
        "executed_at": datetime.now().isoformat(),
        "completed_at": "",
        "summary": {
            "total": len(data_list),
            "success": 0,
            "failed": 0
        },
        "results": []
    }

    # アップローダー初期化
    uploader = RakurakuUploader(config)

    # 全件処理
    for item in data_list:
        pdf_path = Path(item["_pdf_path"])
        # _preprocessed_pathは一時ファイルで削除済みの場合があるため、_pdf_path（出力フォルダ）を使用
        upload_path = item["_pdf_path"]

        # ファイル存在チェック
        if not Path(upload_path).exists():
            logger.error(f"ファイルが存在しません: {upload_path}")
            results["summary"]["failed"] += 1
            results["results"].append({
                "index": item["_index"],
                "pdf_name": item["_pdf_name"],
                "pdf_path": item["_pdf_path"],
                "status": "エラー",
                "message": f"ファイルが存在しません: {upload_path}",
                "vendor_name": item.get("vendor_name", ""),
                "amount": item.get("amount", 0),
                "timestamp": datetime.now().isoformat()
            })
            continue

        logger.info(f"処理中: {item['_pdf_name']}")

        # ReceiptData作成
        receipt_data = ReceiptData(
            pdf_path=upload_path,
            vendor_name=item.get("vendor_name", ""),
            trading_date=item.get("issue_date", ""),
            amount=item.get("amount", 0),
            invoice_number=item.get("invoice_number", "")
        )

        # アップロード実行
        try:
            success = uploader.run(
                pdf_path=upload_path,
                data=receipt_data,
                headless=headless,
                dry_run=dry_run
            )

            result_item = {
                "index": item["_index"],
                "pdf_name": item["_pdf_name"],
                "pdf_path": item["_pdf_path"],
                "status": "成功" if success else "失敗",
                "message": "登録完了" if success else "登録失敗",
                "vendor_name": item.get("vendor_name", ""),
                "amount": item.get("amount", 0),
                "timestamp": datetime.now().isoformat()
            }
            results["results"].append(result_item)

            if success:
                results["summary"]["success"] += 1
                logger.info(f"  → 成功")
            else:
                results["summary"]["failed"] += 1
                logger.error(f"  → 失敗")

        except Exception as e:
            logger.error(f"アップロードエラー: {e}")
            results["summary"]["failed"] += 1
            results["results"].append({
                "index": item["_index"],
                "pdf_name": item["_pdf_name"],
                "pdf_path": item["_pdf_path"],
                "status": "エラー",
                "message": str(e),
                "vendor_name": item.get("vendor_name", ""),
                "amount": item.get("amount", 0),
                "timestamp": datetime.now().isoformat()
            })

    # 結果出力
    results["completed_at"] = datetime.now().isoformat()
    RESULT_JSON_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"result.json出力完了: {RESULT_JSON_PATH}")

    logger.info("=== 一括処理完了 ===")
    logger.info(f"  成功: {results['summary']['success']}件")
    logger.info(f"  失敗: {results['summary']['failed']}件")

    return 0 if results["summary"]["failed"] == 0 else 1


# =============================================================================
# コマンド: --post（後処理）
# =============================================================================
def cmd_post(config: dict, send_mail_flag: bool = False, test_mode: bool = False) -> int:
    """後処理: 成功PDFをアーカイブへ移動、結果レポート出力

    Returns:
        0: 成功, 1: 失敗
    """
    logger = get_logger()

    logger.info("=== Phase 3: 後処理開始 ===")

    # result.json読み込み
    if not RESULT_JSON_PATH.exists():
        logger.error("result.jsonが見つかりません。先に --run-all を実行してください")
        return 1

    results = json.loads(RESULT_JSON_PATH.read_text(encoding="utf-8"))

    # 成功したPDFをprocessedフォルダに移動
    renamer = PDFRenamer(config)
    moved_count = 0

    for item in results.get("results", []):
        if item.get("status") == "成功":
            pdf_path = Path(item["pdf_path"])
            if pdf_path.exists():
                try:
                    renamer.move_to_processed(pdf_path)
                    moved_count += 1
                    logger.info(f"アーカイブ移動: {pdf_path.name}")
                except Exception as e:
                    logger.error(f"移動失敗: {pdf_path.name} - {e}")

    logger.info(f"アーカイブ移動完了: {moved_count}件")

    # 失敗したPDFをOCR失敗フォルダに移動
    for item in results.get("results", []):
        if item.get("status") != "成功":
            pdf_path = Path(item["pdf_path"])
            if pdf_path.exists():
                move_to_ocr_failed(pdf_path, reason=item.get("message", "失敗"))

    # メール送信
    if send_mail_flag and MAIL_AVAILABLE:
        mail_results = {
            'timestamp': results.get("completed_at", ""),
            'total': results["summary"]["total"],
            'success': results["summary"]["success"],
            'failed': results["summary"]["failed"],
            'skipped': 0,
            'manual': 0,
            'success_files': [],
            'failed_files': [],
            'failed_dir': str(get_ocr_failed_dir()) if results["summary"]["failed"] > 0 else ""
        }

        for item in results.get("results", []):
            if item.get("status") == "成功":
                mail_results['success_files'].append({
                    'name': item['pdf_name'],
                    'vendor': item.get('vendor_name', ''),
                    'amount': item.get('amount', 0)
                })
            else:
                mail_results['failed_files'].append({
                    'name': item['pdf_name'],
                    'confidence': 0,
                    'reason': item.get('message', '失敗')
                })

        send_mail(mail_results, test_mode=test_mode, config=config)
        logger.info("メール送信完了")

    logger.info("=== 後処理完了 ===")
    return 0


# =============================================================================
# その他コマンド
# =============================================================================
def cmd_get_count() -> int:
    """データ件数を出力"""
    if not DATA_JSON_PATH.exists():
        print("0")
        return 0

    data = json.loads(DATA_JSON_PATH.read_text(encoding="utf-8"))
    print(data.get("total_count", 0))
    return 0


def cmd_reset() -> int:
    """インデックスリセット"""
    ensure_work_dir()
    INDEX_FILE_PATH.write_text("0", encoding="utf-8")
    print("OK")
    return 0


def cmd_init_result() -> int:
    """結果ファイル初期化"""
    ensure_work_dir()
    results = {
        "scenario_id": "44",
        "executed_at": datetime.now().isoformat(),
        "completed_at": "",
        "summary": {"total": 0, "success": 0, "failed": 0},
        "results": []
    }
    RESULT_JSON_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK")
    return 0


# =============================================================================
# メイン
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="44PDF一般経費楽楽精算申請 RK10連携CLI")

    # コマンド
    parser.add_argument("--pre", action="store_true", help="前処理（FAX取得→OCR→data.json）")
    parser.add_argument("--run-all", action="store_true", help="一括処理（ログイン→全PDF登録）")
    parser.add_argument("--post", action="store_true", help="後処理（PDF移動→結果出力）")
    parser.add_argument("--get-count", action="store_true", help="データ件数取得")
    parser.add_argument("--reset", action="store_true", help="インデックスリセット")
    parser.add_argument("--init-result", action="store_true", help="結果ファイル初期化")

    # オプション
    parser.add_argument("--env", choices=["LOCAL", "PROD"], help="環境")
    parser.add_argument("--headless", action="store_true", help="ヘッドレスモード")
    parser.add_argument("--dry-run", action="store_true", help="ドライラン（確定しない）")
    parser.add_argument("--send-mail", action="store_true", help="メール送信（--postで使用）")
    parser.add_argument("--test-mode", action="store_true", help="テストアドレスにメール送信")

    args = parser.parse_args()

    # ロガー設定
    setup_logger("main_44_rk10")
    logger = get_logger()

    # コマンド実行
    if args.get_count:
        return cmd_get_count()

    if args.reset:
        return cmd_reset()

    if args.init_result:
        return cmd_init_result()

    # 設定読み込み（pre, run-all, postで必要）
    config = load_config(args.env)
    logger.info(f"環境: {config.get('ENV', 'UNKNOWN')}")

    if args.pre:
        return cmd_pre(config)

    if args.run_all:
        return cmd_run_all(config, headless=args.headless, dry_run=args.dry_run)

    if args.post:
        return cmd_post(config, send_mail_flag=args.send_mail, test_mode=args.test_mode)

    # コマンドなしの場合はヘルプ表示
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
