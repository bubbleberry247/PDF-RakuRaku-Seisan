# Playbook: 楽楽精算スクレイピング

## 概要
楽楽精算（経費精算SaaS）からCSVデータをダウンロードし、Excelに転記するまでの手順

---

## 前提条件
- Python 3.11+
- Playwright インストール済み（`pip install playwright && playwright install`）
- Windows資格情報マネージャーに認証情報登録済み

---

## 処理フロー

```
1. ログイン（資格情報マネージャーから取得）
     ↓
2. 明細プレビュー画面へ遷移
     ↓
3. データ抽出ボタンクリック
     ↓
4. CSVダウンロード
     ↓
5. ZIP解凍（パスワード付きの場合あり）
     ↓
6. CSV解析・データ整形
     ↓
7. Excel転記
```

---

## Step 1: Playwrightセットアップ

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

        # 以降の処理
        await browser.close()

asyncio.run(main())
```

---

## Step 2: ログイン処理

```python
async def login(page, company_id, user_id, password):
    """楽楽精算にログイン"""
    await page.goto('https://www.rakurakuseisan.jp/')

    # 会社ID入力
    await page.fill('input[name="company_id"]', company_id)

    # ユーザーID入力
    await page.fill('input[name="user_id"]', user_id)

    # パスワード入力
    await page.fill('input[name="password"]', password)

    # ログインボタンクリック
    await page.click('button[type="submit"]')

    # ログイン完了待機
    await page.wait_for_url('**/top**', timeout=30000)
    print("ログイン完了")
```

---

## Step 3: 明細プレビュー画面へ遷移

```python
async def navigate_to_preview(page, target_month):
    """明細プレビュー画面へ遷移

    Args:
        page: Playwrightページオブジェクト
        target_month: 対象月（例: "2025.01"）
    """
    # メニューから経費精算を選択
    await page.click('text=経費精算')
    await page.wait_for_timeout(1000)

    # 明細プレビューを選択
    await page.click('text=明細プレビュー')
    await page.wait_for_selector('.preview-table', timeout=10000)

    # 対象月を選択
    await page.select_option('select[name="target_month"]', target_month)
    await page.click('button:has-text("検索")')
    await page.wait_for_load_state('networkidle')
```

---

## Step 4: CSVダウンロード

```python
async def download_csv(page, download_dir):
    """CSVをダウンロード"""
    async with page.expect_download() as download_info:
        await page.click('button:has-text("データ抽出")')

    download = await download_info.value
    file_path = f"{download_dir}/{download.suggested_filename}"
    await download.save_as(file_path)

    print(f"ダウンロード完了: {file_path}")
    return file_path
```

---

## Step 5: ZIP解凍

```python
import zipfile
from pathlib import Path

def extract_zip(zip_path, output_dir, password=None):
    """ZIPファイルを解凍

    Args:
        zip_path: ZIPファイルパス
        output_dir: 出力ディレクトリ
        password: パスワード（オプション）

    Returns:
        解凍されたファイルのリスト
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as z:
        if password:
            z.setpassword(password.encode())
        z.extractall(output_dir)
        return [output_dir / name for name in z.namelist()]
```

---

## Step 6: CSV解析

```python
import csv
from dataclasses import dataclass
from typing import List
from datetime import datetime

@dataclass
class ExpenseRecord:
    """経費レコード"""
    application_no: str      # 申請番号
    applicant: str           # 申請者
    department: str          # 部門
    expense_date: str        # 利用日
    vendor: str              # 支払先
    description: str         # 摘要
    amount: int              # 金額（税込）
    account: str             # 勘定科目
    status: str              # ステータス

def parse_csv(csv_path, encoding='cp932'):
    """楽楽精算CSVを解析

    Args:
        csv_path: CSVファイルパス
        encoding: 文字エンコーディング（デフォルト: cp932/Shift_JIS）

    Returns:
        ExpenseRecordのリスト
    """
    records = []

    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = ExpenseRecord(
                application_no=row.get('申請番号', ''),
                applicant=row.get('申請者', ''),
                department=row.get('部門', ''),
                expense_date=row.get('利用日', ''),
                vendor=row.get('支払先', ''),
                description=row.get('摘要', ''),
                amount=int(row.get('金額', '0').replace(',', '')),
                account=row.get('勘定科目', ''),
                status=row.get('ステータス', ''),
            )
            records.append(record)

    return records
```

---

## Step 7: Excel転記

```python
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

# 確度による色分け
COLORS = {
    'exact': Font(color='000000'),        # 完全一致: 黒
    'estimated': Font(color='FFCC00'),    # 推定: 黄色
    'unknown': Font(color='FF0000'),      # 不明: 赤
}

def write_to_excel(records, excel_path, sheet_name):
    """Excelに転記

    Args:
        records: ExpenseRecordのリスト
        excel_path: 出力Excelファイルパス
        sheet_name: シート名（例: "2025.01"）
    """
    wb = load_workbook(excel_path)

    # シートを選択（なければ作成）
    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    else:
        ws = wb.create_sheet(sheet_name)

    # ヘッダー行（17行目から開始の場合）
    start_row = 17

    for i, record in enumerate(records):
        row = start_row + (i * 2)  # 2行1セット（本体行+税行）

        # 本体行に書き込み
        ws[f'C{row}'] = record.description  # 摘要
        ws[f'I{row}'] = record.amount       # 金額

        # 確度に応じた色設定
        confidence = get_confidence(record)
        ws[f'C{row}'].font = COLORS.get(confidence, COLORS['unknown'])

    wb.save(excel_path)
    print(f"Excel保存完了: {excel_path}")

def get_confidence(record):
    """確度を判定"""
    # マスタ照合ロジック（簡略化）
    if record.account:
        return 'exact'
    elif record.vendor:
        return 'estimated'
    return 'unknown'
```

---

## 完全なサンプルスクリプト

```python
"""楽楽精算スクレイピング 完全版"""
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

async def main():
    # 設定
    company_id = 'YOUR_COMPANY_ID'
    user_id = 'YOUR_USER_ID'
    password = 'YOUR_PASSWORD'  # 実際は資格情報マネージャーから取得
    target_month = '2025.01'
    download_dir = Path('C:/work/downloads')
    excel_path = Path('C:/work/output.xlsx')

    download_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # ログイン
        await login(page, company_id, user_id, password)

        # 明細プレビューへ遷移
        await navigate_to_preview(page, target_month)

        # CSVダウンロード
        csv_zip = await download_csv(page, download_dir)

        await browser.close()

    # ZIP解凍
    csv_files = extract_zip(csv_zip, download_dir)

    # CSV解析
    records = []
    for csv_file in csv_files:
        if csv_file.suffix == '.csv':
            records.extend(parse_csv(csv_file))

    # Excel転記
    write_to_excel(records, excel_path, target_month)

    print(f"処理完了: {len(records)}件")

if __name__ == '__main__':
    asyncio.run(main())
```

---

## 注意事項

1. **Bot検出対策**: `--disable-blink-features=AutomationControlled`を必ず設定
2. **認証情報管理**: パスワードはコードに埋め込まず、資格情報マネージャーから取得
3. **待機処理**: ページ遷移後は`wait_for_load_state('networkidle')`で安定化
4. **文字コード**: 楽楽精算のCSVは`cp932`（Shift_JIS系）が多い
5. **2行1セット**: 本体行と税行のペアを意識して転記
