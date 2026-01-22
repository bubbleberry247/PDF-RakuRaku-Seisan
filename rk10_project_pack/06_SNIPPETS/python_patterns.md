# Snippets: Python パターン集

## 概要
RK10ロボットのPythonスクリプトで使用する頻出パターン

---

## 1. ファイル操作

### パス操作（pathlib）

```python
from pathlib import Path

# パス結合
path = Path('C:/work') / 'input' / 'file.xlsx'

# 親ディレクトリ
parent = path.parent

# ファイル名（拡張子含む）
name = path.name  # "file.xlsx"

# ファイル名（拡張子なし）
stem = path.stem  # "file"

# 拡張子
suffix = path.suffix  # ".xlsx"

# 存在確認
if path.exists():
    print("存在します")

# ディレクトリ作成
Path('C:/work/output').mkdir(parents=True, exist_ok=True)
```

### ファイル一覧取得

```python
from pathlib import Path

# 特定パターンのファイル
files = list(Path('C:/work').glob('*.xlsx'))

# 再帰的に検索
files = list(Path('C:/work').rglob('*.csv'))

# 最新ファイル
newest = max(Path('C:/work').glob('*.zip'), key=lambda p: p.stat().st_mtime)
```

### ZIP操作

```python
import zipfile
from pathlib import Path

# 解凍
with zipfile.ZipFile('file.zip', 'r') as z:
    z.extractall('output/')

# パスワード付き解凍
with zipfile.ZipFile('file.zip', 'r') as z:
    z.setpassword(b'password')
    z.extractall('output/')

# 圧縮
with zipfile.ZipFile('output.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for file in Path('folder').rglob('*'):
        if file.is_file():
            z.write(file, file.relative_to('folder'))
```

---

## 2. CSV操作

### CSV読み込み

```python
import csv

# 辞書形式で読み込み
with open('file.csv', 'r', encoding='cp932') as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(row['列名'])

# リスト形式で読み込み
with open('file.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)  # ヘッダー行
    for row in reader:
        print(row[0], row[1])
```

### CSV書き込み

```python
import csv

# 辞書形式で書き込み
data = [
    {'名前': '山田', '金額': 1000},
    {'名前': '田中', '金額': 2000},
]
with open('output.csv', 'w', encoding='cp932', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['名前', '金額'])
    writer.writeheader()
    writer.writerows(data)
```

---

## 3. Excel操作（openpyxl）

### 読み込み

```python
from openpyxl import load_workbook

# 読み込み
wb = load_workbook('file.xlsx')
ws = wb.active

# シート選択
ws = wb['シート名']

# セル値取得
value = ws['B5'].value
value = ws.cell(row=5, column=2).value

# 行イテレーション
for row in ws.iter_rows(min_row=2, values_only=True):
    print(row[0], row[1])

wb.close()
```

### 書き込み

```python
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

wb = load_workbook('template.xlsx')
ws = wb['Sheet1']

# セル書き込み
ws['B5'] = '値'
ws.cell(row=5, column=2, value='値')

# スタイル適用
ws['B5'].font = Font(color='FF0000', bold=True)
ws['B5'].fill = PatternFill(start_color='FFFF00', fill_type='solid')

# 保存
wb.save('output.xlsx')
```

---

## 4. 日付操作

### 基本操作

```python
from datetime import datetime, timedelta

# 現在日時
now = datetime.now()

# フォーマット
date_str = now.strftime('%Y%m%d')  # "20250120"
date_str = now.strftime('%Y.%m')   # "2025.01"

# パース
dt = datetime.strptime('20250120', '%Y%m%d')
dt = datetime.strptime('2025.01', '%Y.%m')

# 加算
next_month = now + timedelta(days=30)

# 月初・月末
from calendar import monthrange
first_day = now.replace(day=1)
_, last_day = monthrange(now.year, now.month)
last_date = now.replace(day=last_day)
```

### 翌月計算

```python
from datetime import datetime
from dateutil.relativedelta import relativedelta

now = datetime.now()
next_month = now + relativedelta(months=1)

# または標準ライブラリのみ
def add_months(dt, months):
    month = dt.month + months
    year = dt.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return dt.replace(year=year, month=month, day=1)
```

---

## 5. 文字列操作

### 正規表現

```python
import re

# 検索
match = re.search(r'\d{4}年\d{1,2}月\d{1,2}日', text)
if match:
    date_str = match.group()

# すべてマッチ
amounts = re.findall(r'[\d,]+円', text)

# 置換
result = re.sub(r'\s+', ' ', text)  # 連続空白を1つに

# 分割
parts = re.split(r'[,、]', text)
```

### 金額パース

```python
def parse_amount(text: str) -> int:
    """金額文字列を整数に変換"""
    # カンマ、円記号、スペースを除去
    cleaned = re.sub(r'[,，\s¥\\￥円]', '', str(text))
    try:
        return int(cleaned)
    except ValueError:
        return 0

# 使用例
amount = parse_amount('¥1,234,567円')  # 1234567
```

---

## 6. データクラス

### dataclass使用

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ExpenseRecord:
    """経費レコード"""
    id: str
    date: str
    vendor: str
    amount: int
    description: str = ''
    category: str = ''
    confidence: str = 'unknown'

    @property
    def formatted_amount(self) -> str:
        return f'¥{self.amount:,}'

# 使用例
record = ExpenseRecord(
    id='001',
    date='20250120',
    vendor='株式会社テスト',
    amount=10000
)
print(record.formatted_amount)  # ¥10,000
```

---

## 7. ログ設定

### 基本設定

```python
import logging
import sys
from pathlib import Path

def setup_logging(log_dir: str = 'logs', level=logging.INFO):
    """ログ設定"""
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                Path(log_dir) / 'main.log',
                encoding='utf-8'
            )
        ]
    )
    return logging.getLogger(__name__)

# 使用例
logger = setup_logging()
logger.info('処理開始')
logger.error('エラー発生')
```

---

## 8. リトライパターン

### デコレータ方式

```python
import time
from functools import wraps

def retry(max_attempts=3, delay=1, exceptions=(Exception,)):
    """リトライデコレータ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    print(f"リトライ {attempt + 1}/{max_attempts}: {e}")
                    time.sleep(delay)
        return wrapper
    return decorator

# 使用例
@retry(max_attempts=5, delay=2)
def download_file(url):
    # ダウンロード処理
    pass
```

### ループ方式

```python
def with_retry(func, max_attempts=3, delay=1):
    """リトライ付き関数実行"""
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            print(f"リトライ {attempt + 1}/{max_attempts}: {e}")
            time.sleep(delay)

# 使用例
result = with_retry(lambda: requests.get(url), max_attempts=5)
```

---

## 9. 設定ファイル読み込み

### JSON

```python
import json
from pathlib import Path

def load_config(config_path: str) -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config('config/config.json')
```

### YAML

```python
import yaml

def load_yaml(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
```

---

## 10. Windows資格情報

### keyring使用

```python
import keyring

# 取得
password = keyring.get_password('service_name', 'username')

# 設定
keyring.set_password('service_name', 'username', 'password')
```

### win32cred使用

```python
import win32cred

def get_credential(target_name: str) -> tuple:
    """Windows資格情報を取得"""
    try:
        cred = win32cred.CredRead(target_name, win32cred.CRED_TYPE_GENERIC)
        username = cred['UserName']
        password = cred['CredentialBlob'].decode('utf-16-le')
        return username, password
    except Exception as e:
        raise ValueError(f"資格情報が見つかりません: {target_name}")

# 使用例
username, password = get_credential('RK10_SystemLogin')
```

---

## 11. Playwright パターン

### 基本構造

```python
from playwright.async_api import async_playwright
import asyncio

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        await page.goto('https://example.com')

        # 処理

        await browser.close()

asyncio.run(main())
```

### ダウンロード待機

```python
async def download_file(page, selector, save_path):
    async with page.expect_download() as download_info:
        await page.click(selector)
    download = await download_info.value
    await download.save_as(save_path)
    return save_path
```

---

## 12. エラーハンドリング

### カスタム例外

```python
class RobotError(Exception):
    """ロボットエラー基底クラス"""
    pass

class LoginError(RobotError):
    """ログインエラー"""
    pass

class DataNotFoundError(RobotError):
    """データが見つからないエラー"""
    pass

# 使用例
def login(username, password):
    if not authenticate(username, password):
        raise LoginError(f"ログイン失敗: {username}")
```

---

## 13. CLIパターン

### argparse

```python
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='処理スクリプト')
    parser.add_argument('--env', required=True, choices=['PROD', 'LOCAL'])
    parser.add_argument('--month', required=True, help='対象年月（YYYYMM）')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    print(f"env={args.env}, month={args.month}")
```

---

## 14. メール送信

### smtplib

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(to_addr, subject, body, smtp_server='smtp.example.com'):
    msg = MIMEMultipart()
    msg['From'] = 'robot@example.com'
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    with smtplib.SMTP(smtp_server) as server:
        server.send_message(msg)

# 使用例
send_email('admin@example.com', '処理完了', '処理が正常に完了しました。')
```

---

## 15. 進捗表示

### tqdm

```python
from tqdm import tqdm

for item in tqdm(items, desc='処理中'):
    process(item)
```

### 手動進捗

```python
total = len(items)
for i, item in enumerate(items, 1):
    print(f'\r処理中: {i}/{total} ({i*100//total}%)', end='')
    process(item)
print()  # 改行
```
