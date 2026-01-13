# -*- coding: utf-8 -*-
"""
ログ出力モジュール

Usage:
    from common.logger import setup_logger, get_logger

    # セットアップ（スクリプト開始時に1回）
    setup_logger("scenario_44")

    # ロガー取得
    logger = get_logger()
    logger.info("処理開始")
    logger.error("エラー発生", exc_info=True)
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ベースディレクトリ
BASE_DIR = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請")
LOG_DIR = BASE_DIR / "log"

# グローバルロガー
_logger: Optional[logging.Logger] = None


def setup_logger(
    name: str,
    log_level: int = logging.INFO,
    console_output: bool = True
) -> logging.Logger:
    """ロガーをセットアップ

    Args:
        name: ロガー名（ログファイル名のプレフィックスにも使用）
        log_level: ログレベル
        console_output: コンソールにも出力するか

    Returns:
        設定済みのロガー
    """
    global _logger

    # ログディレクトリ作成
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ログファイル名（日付入り）
    today = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"{name}_{today}.log"

    # ロガー作成
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # 既存のハンドラをクリア
    logger.handlers.clear()

    # フォーマッタ
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # ファイルハンドラ
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # コンソールハンドラ
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    _logger = logger
    logger.info(f"ログ開始: {log_file}")

    return logger


def get_logger() -> logging.Logger:
    """現在のロガーを取得

    Returns:
        ロガー（未設定の場合はデフォルトロガーを返す）
    """
    global _logger

    if _logger is None:
        # デフォルトロガーを作成
        _logger = setup_logger("default")

    return _logger


class LogContext:
    """ログコンテキストマネージャー

    処理ブロックの開始・終了をログに記録

    Usage:
        with LogContext("CSVダウンロード"):
            # 処理
    """

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.logger = get_logger()

    def __enter__(self):
        self.logger.info(f"=== {self.operation_name} 開始 ===")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.logger.info(f"=== {self.operation_name} 完了 ===")
        else:
            self.logger.error(f"=== {self.operation_name} 失敗 ===", exc_info=True)
        return False  # 例外を再送出


if __name__ == "__main__":
    # テスト実行
    sys.stdout.reconfigure(encoding='utf-8')

    logger = setup_logger("test_logger")
    logger.info("テストメッセージ: INFO")
    logger.warning("テストメッセージ: WARNING")
    logger.error("テストメッセージ: ERROR")

    with LogContext("テスト処理"):
        logger.info("処理中...")

    print(f"\nログファイル: {LOG_DIR}")
