# -*- coding: utf-8 -*-
"""
RK10シナリオ連携用 メイン処理

RK10シナリオからPythonを呼び出すためのCLIインターフェース

Usage:
    python main_44_rk10.py --pre          # 前処理（PDF検索→SmartOCR→JSON出力）
    python main_44_rk10.py --post         # 後処理（結果記録→PDF移動）
    python main_44_rk10.py --reset        # インデックスリセット
    python main_44_rk10.py --get-count    # データ件数取得
    python main_44_rk10.py --get-data     # 現在のPDFデータ取得
    python main_44_rk10.py --next         # 次のPDFへ
    python main_44_rk10.py --record ROW STATUS MSG  # 結果記録
    python main_44_rk10.py --login        # 楽楽精算ログイン
    python main_44_rk10.py --upload       # PDFアップロード・登録
    python main_44_rk10.py --close        # ブラウザ終了
    python main_44_rk10.py --run-all      # 一括処理（ログイン→全PDF登録→終了）★推奨

Options:
    --dry-run     確定ボタンを押さない（テスト用）
    --headless    ヘッドレスモードで実行

Created: 2026-01-14
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

# 共通モジュール
sys.path.insert(0, str(Path(__file__).parent))

from common.config_loader import load_config, get_env
from common.logger import setup_logger, get_logger

# OCRモジュール
from pdf_ocr_smart import SmartOCRProcessor, SmartOCRResult

# 楽楽精算アップロードモジュール
from rakuraku_upload import RakurakuUploader, ReceiptData


# ===========================================
# 定数
# ===========================================

BASE_DIR = Path(__file__).parent.parent
WORK_DIR = BASE_DIR / "work"
OUTPUT_DIR = WORK_DIR / "output"
MANUAL_QUEUE_DIR = WORK_DIR / "manual_queue"
PROCESSED_DIR = WORK_DIR / "processed"

DATA_FILE = OUTPUT_DIR / "data.json"
RESULT_FILE = OUTPUT_DIR / "result.json"
INDEX_FILE = OUTPUT_DIR / "current_index.txt"
BROWSER_STATE_FILE = OUTPUT_DIR / "browser_state.json"


# ===========================================
# RK10連携クラス
# ===========================================

class RK10Integration:
    """RK10シナリオ連携クラス"""

    def __init__(self):
        self.config = load_config()
        self.logger = get_logger()
        self.uploader: Optional[RakurakuUploader] = None

        # 出力ディレクトリ作成
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        MANUAL_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------
    # 前処理
    # -------------------------------------------

    def preprocess(self) -> int:
        """前処理: PDF検索 → SmartOCR → JSON出力

        Returns:
            終了コード (0=成功, 1=失敗)
        """
        self.logger.info("=== 前処理開始 ===")

        # FAXフォルダ取得
        env = get_env()
        if env == "PROD":
            fax_folder = Path(self.config.get("FAX_FOLDER_PROD", ""))
        else:
            fax_folder = Path(self.config.get("FAX_FOLDER_LOCAL",
                str(BASE_DIR / "data" / "MOCK_FAX")))

        if not fax_folder.exists():
            self.logger.error(f"FAXフォルダが存在しません: {fax_folder}")
            return 1

        # PDF一覧取得
        pdf_files = list(fax_folder.glob("*.pdf"))
        pdf_files = [f for f in pdf_files if not f.name.startswith("_preproc_")]

        self.logger.info(f"FAXフォルダ: {fax_folder}")
        self.logger.info(f"対象PDF数: {len(pdf_files)}")

        if not pdf_files:
            self.logger.info("処理対象PDFがありません")
            self._save_data({"data": [], "manual_queue": []})
            return 0

        # SmartOCR処理
        processor = SmartOCRProcessor()
        data_list = []
        manual_list = []

        for i, pdf_path in enumerate(pdf_files):
            self.logger.info(f"[{i+1}/{len(pdf_files)}] {pdf_path.name}")

            try:
                result = processor.process(str(pdf_path))

                item = {
                    "_index": len(data_list),
                    "_pdf_path": str(pdf_path),
                    "_pdf_name": pdf_path.name,
                    "_preprocessed_path": str(result.preprocess_info.get("output_path", "")),
                    "_confidence": result.confidence,
                    "_requires_manual": result.requires_manual,
                    "vendor_name": result.vendor_name,
                    "issue_date": result.issue_date,
                    "amount": result.amount,
                    "invoice_number": result.invoice_number,
                    "document_type": "請求書",
                    "storage_type": "スキャナ保存"
                }

                if result.requires_manual:
                    manual_list.append(item)
                    self.logger.warning(f"  → 手動キューへ (confidence={result.confidence:.2f})")
                else:
                    data_list.append(item)
                    self.logger.info(f"  → 自動処理可能 (confidence={result.confidence:.2f})")

            except Exception as e:
                self.logger.error(f"  → エラー: {e}")
                manual_list.append({
                    "_index": -1,
                    "_pdf_path": str(pdf_path),
                    "_pdf_name": pdf_path.name,
                    "_error": str(e)
                })

        # JSON保存
        self._save_data({
            "scenario_id": "44",
            "scenario_name": "【44】PDF一般経費楽楽精算申請",
            "created_at": datetime.now().isoformat(),
            "config": {
                "env": env,
                "fax_folder": str(fax_folder)
            },
            "total_count": len(data_list),
            "manual_count": len(manual_list),
            "data": data_list,
            "manual_queue": manual_list
        })

        self.logger.info(f"=== 前処理完了: 自動={len(data_list)}, 手動={len(manual_list)} ===")
        return 0

    # -------------------------------------------
    # 後処理
    # -------------------------------------------

    def postprocess(self) -> int:
        """後処理: 結果記録 → PDF移動

        Returns:
            終了コード (0=成功, 1=失敗)
        """
        self.logger.info("=== 後処理開始 ===")

        # 結果ファイル読み込み
        result_data = self._load_result()
        if not result_data:
            self.logger.warning("結果ファイルが存在しません")
            return 1

        # 成功したPDFを処理済みフォルダへ移動
        success_count = 0
        for item in result_data.get("results", []):
            if item.get("status") == "成功":
                pdf_path = Path(item.get("pdf_path", ""))
                if pdf_path.exists():
                    dest = PROCESSED_DIR / pdf_path.name
                    try:
                        shutil.move(str(pdf_path), str(dest))
                        self.logger.info(f"移動: {pdf_path.name} → processed/")
                        success_count += 1
                    except Exception as e:
                        self.logger.warning(f"移動失敗: {pdf_path.name} - {e}")

        # サマリー更新
        result_data["completed_at"] = datetime.now().isoformat()
        result_data["summary"]["moved"] = success_count
        self._save_result(result_data)

        self.logger.info(f"=== 後処理完了: {success_count}件移動 ===")
        return 0

    # -------------------------------------------
    # データ操作
    # -------------------------------------------

    def reset_index(self) -> str:
        """インデックスリセット"""
        INDEX_FILE.write_text("0", encoding="utf-8")
        return "OK"

    def init_result(self) -> str:
        """結果ファイル初期化"""
        self._save_result({
            "scenario_id": "44",
            "executed_at": datetime.now().isoformat(),
            "summary": {"total": 0, "success": 0, "failed": 0},
            "results": []
        })
        return "OK"

    def get_count(self) -> int:
        """データ件数取得"""
        data = self._load_data()
        return data.get("total_count", 0) if data else 0

    def get_data(self) -> Optional[Dict]:
        """現在のPDFデータ取得"""
        data = self._load_data()
        if not data:
            return None

        index = self._get_current_index()
        items = data.get("data", [])

        if 0 <= index < len(items):
            return items[index]
        return None

    def next_index(self) -> int:
        """次のPDFへ"""
        index = self._get_current_index()
        new_index = index + 1
        INDEX_FILE.write_text(str(new_index), encoding="utf-8")
        return new_index

    def record_result(self, index: int, status: str, message: str) -> str:
        """結果を記録

        Args:
            index: データインデックス
            status: ステータス（成功/失敗）
            message: メッセージ
        """
        data = self._load_data()
        result_data = self._load_result() or {
            "scenario_id": "44",
            "executed_at": datetime.now().isoformat(),
            "summary": {"total": 0, "success": 0, "failed": 0},
            "results": []
        }

        # データ取得
        items = data.get("data", []) if data else []
        item = items[index] if 0 <= index < len(items) else {}

        # 結果追加
        result_data["results"].append({
            "index": index,
            "pdf_name": item.get("_pdf_name", ""),
            "pdf_path": item.get("_pdf_path", ""),
            "status": status,
            "message": message,
            "vendor_name": item.get("vendor_name", ""),
            "amount": item.get("amount", 0),
            "timestamp": datetime.now().isoformat()
        })

        # サマリー更新
        result_data["summary"]["total"] += 1
        if status == "成功":
            result_data["summary"]["success"] += 1
        else:
            result_data["summary"]["failed"] += 1

        self._save_result(result_data)
        return "OK"

    # -------------------------------------------
    # 楽楽精算操作
    # -------------------------------------------

    def login(self) -> str:
        """楽楽精算ログイン（ブラウザ起動含む）"""
        try:
            if self.uploader is None:
                self.uploader = RakurakuUploader(self.config)

            self.uploader.start_browser(headless=False)
            self.uploader.login()

            # ブラウザ状態保存（Playwrightコンテキストは保持）
            self._save_browser_state({"logged_in": True})

            self.logger.info("楽楽精算ログイン成功")
            return "OK"

        except Exception as e:
            self.logger.error(f"ログイン失敗: {e}")
            return f"ERROR: {e}"

    def upload(self) -> str:
        """現在のPDFをアップロード・登録"""
        try:
            # 現在のデータ取得
            data = self.get_data()
            if not data:
                return "ERROR: No data"

            # ブラウザ確認
            if self.uploader is None or self.uploader.page is None:
                return "ERROR: Browser not started. Call --login first"

            # 登録画面へ移動
            self.uploader.navigate_to_receipt_form()

            # PDF取得（前処理済みがあればそれを使用）
            pdf_path = data.get("_preprocessed_path") or data.get("_pdf_path", "")
            if not pdf_path or not Path(pdf_path).exists():
                pdf_path = data.get("_pdf_path", "")

            # アップロード
            if not self.uploader.upload_pdf(pdf_path):
                return "ERROR: Upload failed"

            # フォーム入力
            receipt_data = ReceiptData(
                pdf_path=pdf_path,
                vendor_name=data.get("vendor_name", ""),
                trading_date=data.get("issue_date", ""),
                amount=data.get("amount", 0),
                invoice_number=data.get("invoice_number", ""),
                document_type=data.get("document_type", "請求書"),
                storage_type=data.get("storage_type", "スキャナ保存")
            )
            self.uploader.fill_form(receipt_data)

            # 確定
            if not self.uploader.submit(dry_run=False):
                return "ERROR: Submit failed"

            self.logger.info(f"登録成功: {data.get('_pdf_name', '')}")
            return "OK"

        except Exception as e:
            self.logger.error(f"アップロード失敗: {e}")
            return f"ERROR: {e}"

    def close_browser(self) -> str:
        """ブラウザ終了"""
        try:
            if self.uploader:
                self.uploader.close_browser()
                self.uploader = None

            self._save_browser_state({"logged_in": False})
            self.logger.info("ブラウザ終了")
            return "OK"

        except Exception as e:
            self.logger.error(f"ブラウザ終了失敗: {e}")
            return f"ERROR: {e}"

    # -------------------------------------------
    # 一括処理
    # -------------------------------------------

    def run_all(self, dry_run: bool = False, headless: bool = False, pause: bool = False) -> int:
        """一括処理: ログイン → 全PDF登録 → 終了

        単一プロセス内でブラウザを保持したまま全件処理する。
        RK10から呼び出す場合はこのコマンドを使用する。

        Args:
            dry_run: Trueの場合、確定ボタンを押さない（テスト用）
            headless: Trueの場合、ヘッドレスモードで実行
            pause: Trueの場合、確定前に一時停止

        Returns:
            終了コード (0=成功, 1=失敗)
        """
        self.logger.info("=== 一括処理開始 ===")
        self.logger.info(f"オプション: dry_run={dry_run}, headless={headless}, pause={pause}")

        # データ件数確認
        total_count = self.get_count()
        if total_count == 0:
            self.logger.info("処理対象データがありません")
            return 0

        self.logger.info(f"処理対象: {total_count}件")

        # インデックスリセット
        self.reset_index()

        # 結果ファイル初期化
        self.init_result()

        try:
            # ブラウザ起動・ログイン
            self.logger.info("楽楽精算にログイン中...")
            if self.uploader is None:
                self.uploader = RakurakuUploader(self.config)

            self.uploader.start_browser(headless=headless)
            self.uploader.login()
            self._save_browser_state({"logged_in": True})
            self.logger.info("ログイン成功")

            # 全件ループ処理
            success_count = 0
            fail_count = 0

            for i in range(total_count):
                self.logger.info(f"--- [{i+1}/{total_count}] 処理開始 ---")

                data = self.get_data()
                if not data:
                    self.logger.error(f"データ取得失敗: index={i}")
                    self.record_result(i, "失敗", "データ取得エラー")
                    fail_count += 1
                    self.next_index()
                    continue

                pdf_name = data.get("_pdf_name", "")
                self.logger.info(f"PDF: {pdf_name}")
                self.logger.info(f"  取引先: {data.get('vendor_name', '')}")
                self.logger.info(f"  金額: {data.get('amount', 0):,}円")

                try:
                    # 登録画面へ移動
                    self.uploader.navigate_to_receipt_form()

                    # PDF取得（前処理済みがあればそれを使用）
                    pdf_path = data.get("_preprocessed_path") or data.get("_pdf_path", "")
                    if not pdf_path or not Path(pdf_path).exists():
                        pdf_path = data.get("_pdf_path", "")

                    # アップロード
                    if not self.uploader.upload_pdf(pdf_path):
                        raise Exception("PDFアップロード失敗")

                    # フォーム入力
                    receipt_data = ReceiptData(
                        pdf_path=pdf_path,
                        vendor_name=data.get("vendor_name", ""),
                        trading_date=data.get("issue_date", ""),
                        amount=data.get("amount", 0),
                        invoice_number=data.get("invoice_number", ""),
                        document_type=data.get("document_type", "請求書"),
                        storage_type=data.get("storage_type", "スキャナ保存")
                    )
                    self.uploader.fill_form(receipt_data)

                    # 確定
                    if not self.uploader.submit(dry_run=dry_run, pause_before_submit=pause):
                        raise Exception("確定処理失敗")

                    # 成功記録
                    msg = "登録完了" if not dry_run else "dry-run完了"
                    self.record_result(i, "成功", msg)
                    success_count += 1
                    self.logger.info(f"  → 成功")

                except Exception as e:
                    self.logger.error(f"  → 失敗: {e}")
                    self.record_result(i, "失敗", str(e))
                    fail_count += 1

                # 次へ
                self.next_index()

            self.logger.info(f"=== 一括処理完了: 成功={success_count}, 失敗={fail_count} ===")

        except Exception as e:
            self.logger.error(f"一括処理エラー: {e}")
            return 1

        finally:
            # ブラウザ終了
            self.close_browser()

        return 0 if fail_count == 0 else 1

    # -------------------------------------------
    # ヘルパーメソッド
    # -------------------------------------------

    def _get_current_index(self) -> int:
        """現在のインデックス取得"""
        if INDEX_FILE.exists():
            try:
                return int(INDEX_FILE.read_text(encoding="utf-8").strip())
            except ValueError:
                pass
        return 0

    def _load_data(self) -> Optional[Dict]:
        """data.json読み込み"""
        if DATA_FILE.exists():
            try:
                return json.loads(DATA_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return None

    def _save_data(self, data: Dict):
        """data.json保存"""
        DATA_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _load_result(self) -> Optional[Dict]:
        """result.json読み込み"""
        if RESULT_FILE.exists():
            try:
                return json.loads(RESULT_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return None

    def _save_result(self, data: Dict):
        """result.json保存"""
        RESULT_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _save_browser_state(self, state: Dict):
        """ブラウザ状態保存"""
        BROWSER_STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


# ===========================================
# シングルトンインスタンス
# ===========================================

_integration: Optional[RK10Integration] = None


def get_integration() -> RK10Integration:
    """RK10連携インスタンス取得"""
    global _integration
    if _integration is None:
        _integration = RK10Integration()
    return _integration


# ===========================================
# メイン
# ===========================================

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="RK10シナリオ連携CLI")

    # コマンドグループ
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pre", action="store_true", help="前処理")
    group.add_argument("--post", action="store_true", help="後処理")
    group.add_argument("--reset", action="store_true", help="インデックスリセット")
    group.add_argument("--init-result", action="store_true", help="結果ファイル初期化")
    group.add_argument("--get-count", action="store_true", help="データ件数取得")
    group.add_argument("--get-data", action="store_true", help="現在のPDFデータ取得")
    group.add_argument("--next", action="store_true", help="次のPDFへ")
    group.add_argument("--record", nargs=3, metavar=("INDEX", "STATUS", "MSG"), help="結果記録")
    group.add_argument("--login", action="store_true", help="楽楽精算ログイン")
    group.add_argument("--upload", action="store_true", help="PDFアップロード・登録")
    group.add_argument("--close", action="store_true", help="ブラウザ終了")
    group.add_argument("--run-all", action="store_true", help="一括処理（ログイン→全PDF登録→終了）")

    # オプション
    parser.add_argument("--dry-run", action="store_true", help="確定ボタンを押さない（テスト用）")
    parser.add_argument("--headless", action="store_true", help="ヘッドレスモード")
    parser.add_argument("--pause", action="store_true", help="確定前に一時停止して確認")

    args = parser.parse_args()

    # ロガー設定
    setup_logger("main_44_rk10")

    # 連携インスタンス
    integration = get_integration()

    # コマンド実行
    if args.pre:
        return integration.preprocess()

    elif args.post:
        return integration.postprocess()

    elif args.reset:
        print(integration.reset_index())
        return 0

    elif args.init_result:
        print(integration.init_result())
        return 0

    elif args.get_count:
        print(integration.get_count())
        return 0

    elif args.get_data:
        data = integration.get_data()
        if data:
            print(json.dumps(data, ensure_ascii=False))
        else:
            print("{}")
        return 0

    elif args.next:
        print(integration.next_index())
        return 0

    elif args.record:
        index, status, msg = args.record
        print(integration.record_result(int(index), status, msg))
        return 0

    elif args.login:
        result = integration.login()
        print(result)
        return 0 if result == "OK" else 1

    elif args.upload:
        result = integration.upload()
        print(result)
        return 0 if result == "OK" else 1

    elif args.close:
        result = integration.close_browser()
        print(result)
        return 0 if result == "OK" else 1

    elif args.run_all:
        return integration.run_all(
            dry_run=args.dry_run,
            headless=args.headless,
            pause=args.pause
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
