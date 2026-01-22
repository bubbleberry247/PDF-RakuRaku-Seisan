# Template: Python CLIスクリプト

## 概要
RK10から呼び出すPythonスクリプトの標準テンプレート

---

## 基本構造

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
[ロボット名] - [処理内容]

Usage:
    python main.py --env PROD --month 202501
    python main.py --env LOCAL --month 202501 --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/main.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def parse_args():
    """コマンドライン引数を解析"""
    parser = argparse.ArgumentParser(description='[ロボット名] - [処理内容]')

    parser.add_argument(
        '--env',
        required=True,
        choices=['PROD', 'LOCAL'],
        help='実行環境（PROD/LOCAL）'
    )
    parser.add_argument(
        '--month',
        required=True,
        help='対象年月（YYYYMM形式）'
    )
    parser.add_argument(
        '--company-code',
        default='300',
        help='会社コード（デフォルト: 300）'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='ドライラン（実際の処理を行わない）'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='詳細ログ出力'
    )

    return parser.parse_args()


def load_config(env: str) -> dict:
    """設定ファイルを読み込み

    Args:
        env: 環境名（PROD/LOCAL）

    Returns:
        設定辞書
    """
    config_path = Path(__file__).parent.parent / 'config' / f'config_{env}.json'

    if not config_path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

    import json
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_month(month_str: str) -> datetime:
    """月パラメータを検証

    Args:
        month_str: YYYYMM形式の文字列

    Returns:
        datetime オブジェクト

    Raises:
        ValueError: 形式が不正な場合
    """
    try:
        return datetime.strptime(month_str + '01', '%Y%m%d')
    except ValueError:
        raise ValueError(f"月の形式が不正です: {month_str}（YYYYMM形式で指定）")


def main():
    """メイン処理"""
    args = parse_args()

    # 詳細ログ設定
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info(f"処理開始: env={args.env}, month={args.month}")
    logger.info("=" * 60)

    try:
        # 設定読み込み
        config = load_config(args.env)
        logger.debug(f"設定: {config}")

        # パラメータ検証
        target_month = validate_month(args.month)
        logger.info(f"対象月: {target_month.strftime('%Y年%m月')}")

        # ドライラン確認
        if args.dry_run:
            logger.info("[DRY-RUN] 実際の処理は行いません")

        # ===== メイン処理 =====
        # TODO: ここに実際の処理を実装

        # 例: データ取得
        # data = scrape_data(config, target_month)

        # 例: データ変換
        # converted = convert_data(data)

        # 例: Excel出力
        # if not args.dry_run:
        #     export_to_excel(converted, config['output_path'])

        # ===== 処理完了 =====
        logger.info("=" * 60)
        logger.info("処理正常終了")
        logger.info("=" * 60)
        return 0

    except FileNotFoundError as e:
        logger.error(f"ファイルエラー: {e}")
        return 1
    except ValueError as e:
        logger.error(f"パラメータエラー: {e}")
        return 1
    except Exception as e:
        logger.exception(f"予期しないエラー: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
```

---

## 設定ファイル（config_PROD.json / config_LOCAL.json）

```json
{
    "env": "PROD",
    "base_url": "https://xxx.example.com",
    "input_path": "\\\\server\\share\\input",
    "output_path": "\\\\server\\share\\output",
    "credential_name": "RK10_SystemLogin",
    "retry_count": 10,
    "timeout_seconds": 300,
    "mail": {
        "smtp_server": "smtp.example.com",
        "from_address": "robot@example.com",
        "to_address": "admin@example.com"
    }
}
```

---

## ディレクトリ構造

```
{ロボットフォルダ}/
├── scenario/
│   └── main.rks              # RK10シナリオ
├── tools/
│   ├── main.py               # エントリーポイント
│   ├── scraper.py            # スクレイピング処理
│   ├── converter.py          # データ変換処理
│   └── excel_writer.py       # Excel出力処理
├── config/
│   ├── env.txt               # 環境切替（PROD/LOCAL）
│   ├── config_PROD.json      # 本番環境設定
│   └── config_LOCAL.json     # ローカル環境設定
├── work/                     # 作業フォルダ
├── logs/                     # ログフォルダ
└── docs/
    └── 要件定義書.xlsx
```

---

## RK10からの呼び出し例

```csharp
// Python実行
var pythonPath = @"C:\Python311\python.exe";
var scriptPath = ROBOT_DIR + @"\tools\main.py";
var args = $"--env {Env} --month {yyyyMM} --company-code 300";

Keyence.SystemActions.SystemAction.ExecuteApplication(
    pythonPath,
    $"\"{scriptPath}\" {args}",
    "",      // 作業ディレクトリ
    true,    // 完了待機
    600      // タイムアウト秒
);
```

---

## モジュール分割例

### scraper.py

```python
"""スクレイピング処理モジュール"""
import logging
from playwright.async_api import async_playwright
import asyncio

logger = logging.getLogger(__name__)


class Scraper:
    def __init__(self, config: dict):
        self.config = config
        self.base_url = config['base_url']

    async def login(self, page, username: str, password: str):
        """ログイン処理"""
        await page.goto(self.base_url)
        await page.fill('#username', username)
        await page.fill('#password', password)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state('networkidle')
        logger.info("ログイン完了")

    async def download_csv(self, page, target_month: str, output_dir: str) -> str:
        """CSVダウンロード"""
        # 実装
        pass

    def run(self, target_month: str, output_dir: str) -> str:
        """同期的に実行"""
        return asyncio.run(self._run_async(target_month, output_dir))

    async def _run_async(self, target_month: str, output_dir: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            # ログイン
            await self.login(page, 'user', 'pass')

            # ダウンロード
            result = await self.download_csv(page, target_month, output_dir)

            await browser.close()
            return result
```

### converter.py

```python
"""データ変換モジュール"""
import csv
import logging
from dataclasses import dataclass
from typing import List
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Record:
    """データレコード"""
    id: str
    date: str
    amount: int
    description: str


def parse_csv(csv_path: str, encoding: str = 'cp932') -> List[Record]:
    """CSVを解析"""
    records = []

    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = Record(
                id=row.get('ID', ''),
                date=row.get('日付', ''),
                amount=int(row.get('金額', '0').replace(',', '')),
                description=row.get('摘要', '')
            )
            records.append(record)

    logger.info(f"CSV解析完了: {len(records)}件")
    return records


def convert_records(records: List[Record]) -> List[dict]:
    """レコードを変換"""
    converted = []
    for record in records:
        converted.append({
            'record_id': record.id,
            'expense_date': record.date,
            'amount': record.amount,
            'description': record.description,
            # 追加の変換処理
        })
    return converted
```

### excel_writer.py

```python
"""Excel出力モジュール"""
import logging
from typing import List
from openpyxl import load_workbook
from openpyxl.styles import Font

logger = logging.getLogger(__name__)


def write_to_excel(
    records: List[dict],
    template_path: str,
    output_path: str,
    sheet_name: str
):
    """Excelに出力

    Args:
        records: 出力するレコードのリスト
        template_path: テンプレートファイルパス
        output_path: 出力ファイルパス
        sheet_name: シート名
    """
    wb = load_workbook(template_path)

    # シート選択
    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    else:
        ws = wb.create_sheet(sheet_name)

    # データ書き込み（17行目から開始）
    start_row = 17
    for i, record in enumerate(records):
        row = start_row + (i * 2)  # 2行1セット

        ws[f'C{row}'] = record['description']
        ws[f'I{row}'] = record['amount']

    wb.save(output_path)
    logger.info(f"Excel出力完了: {output_path}")
```

---

## エラーハンドリングパターン

```python
class RobotError(Exception):
    """ロボット処理エラーの基底クラス"""
    pass


class LoginError(RobotError):
    """ログインエラー"""
    pass


class DataNotFoundError(RobotError):
    """データが見つからないエラー"""
    pass


class ValidationError(RobotError):
    """データ検証エラー"""
    pass


# 使用例
def process_data(data):
    if not data:
        raise DataNotFoundError("対象データが0件です")

    if not validate(data):
        raise ValidationError("データ検証に失敗しました")

    return transformed_data
```

---

## 終了コード規約

| コード | 意味 | RK10側の処理 |
|--------|------|-------------|
| 0 | 正常終了 | 次のステップへ |
| 1 | エラー（リトライ可能） | リトライ |
| 2 | エラー（致命的） | 停止・通知 |
| 3 | データなし（正常） | ログ出力して終了 |
