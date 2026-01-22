# Playbook: サイボウズ（kintone/Garoon）スクレイピング

## 概要
サイボウズ製品（kintone、Garoon）からデータを取得する手順

---

## 前提条件
- Python 3.11+
- requests インストール済み
- kintone/Garoon のAPI認証情報

---

## kintone API

### 基本セットアップ

```python
import requests
import base64

class KintoneClient:
    def __init__(self, subdomain, app_id, api_token=None, username=None, password=None):
        """
        認証方法:
        1. APIトークン認証（推奨）
        2. パスワード認証
        """
        self.base_url = f'https://{subdomain}.cybozu.com/k/v1'
        self.app_id = app_id
        self.session = requests.Session()

        if api_token:
            self.session.headers.update({
                'X-Cybozu-API-Token': api_token
            })
        elif username and password:
            credentials = base64.b64encode(f'{username}:{password}'.encode()).decode()
            self.session.headers.update({
                'X-Cybozu-Authorization': credentials
            })

        self.session.headers.update({
            'Content-Type': 'application/json'
        })

    def get_records(self, query='', fields=None):
        """レコードを取得"""
        url = f'{self.base_url}/records.json'
        params = {
            'app': self.app_id,
            'query': query
        }
        if fields:
            params['fields'] = fields

        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('records', [])

    def add_record(self, record):
        """レコードを追加"""
        url = f'{self.base_url}/record.json'
        data = {
            'app': self.app_id,
            'record': record
        }
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def update_record(self, record_id, record):
        """レコードを更新"""
        url = f'{self.base_url}/record.json'
        data = {
            'app': self.app_id,
            'id': record_id,
            'record': record
        }
        response = self.session.put(url, json=data)
        response.raise_for_status()
        return response.json()

# 使用例
client = KintoneClient(
    subdomain='your-company',
    app_id=123,
    api_token='YOUR_API_TOKEN'
)
```

---

### レコード取得

```python
# 全件取得
records = client.get_records()

# 条件指定
records = client.get_records(
    query='ステータス in ("未処理", "処理中") order by 更新日時 desc limit 100'
)

# フィールド指定
records = client.get_records(
    fields=['$id', '申請者', '金額', 'ステータス']
)

# レコードの値を取得
for record in records:
    record_id = record['$id']['value']
    applicant = record['申請者']['value']
    amount = int(record['金額']['value'])
    print(f"ID:{record_id} {applicant} ¥{amount:,}")
```

---

### レコード追加

```python
# 新規レコード追加
new_record = {
    '申請者': {'value': '山田太郎'},
    '金額': {'value': 10000},
    'ステータス': {'value': '未処理'},
    '申請日': {'value': '2025-01-20'}
}

result = client.add_record(new_record)
print(f"追加されたレコードID: {result['id']}")
```

---

### レコード更新

```python
# ステータス更新
update_data = {
    'ステータス': {'value': '承認済'}
}

client.update_record(record_id=123, record=update_data)
```

---

### 添付ファイルのダウンロード

```python
def download_attachment(client, file_key, output_path):
    """添付ファイルをダウンロード"""
    url = f'{client.base_url}/file.json'
    params = {'fileKey': file_key}

    response = client.session.get(url, params=params)
    response.raise_for_status()

    with open(output_path, 'wb') as f:
        f.write(response.content)

    return output_path

# 使用例
records = client.get_records(fields=['添付ファイル'])
for record in records:
    files = record.get('添付ファイル', {}).get('value', [])
    for file_info in files:
        file_key = file_info['fileKey']
        file_name = file_info['name']
        download_attachment(client, file_key, f'downloads/{file_name}')
```

---

## Garoon API

### 基本セットアップ

```python
class GaroonClient:
    def __init__(self, subdomain, username, password):
        self.base_url = f'https://{subdomain}.cybozu.com/g/api/v1'
        self.session = requests.Session()

        credentials = base64.b64encode(f'{username}:{password}'.encode()).decode()
        self.session.headers.update({
            'X-Cybozu-Authorization': credentials,
            'Content-Type': 'application/json'
        })

    def get_schedule_events(self, start, end, target_type='user', target=None):
        """スケジュールを取得

        Args:
            start: 開始日時（ISO 8601形式）
            end: 終了日時（ISO 8601形式）
            target_type: 'user' または 'facility'
            target: ユーザーID/施設ID
        """
        url = f'{self.base_url}/schedule/events'
        params = {
            'rangeStart': start,
            'rangeEnd': end,
            'targetType': target_type
        }
        if target:
            params['target'] = target

        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('events', [])

# 使用例
garoon = GaroonClient(
    subdomain='your-company',
    username='user@example.com',
    password='password'
)
```

---

### スケジュール取得

```python
from datetime import datetime, timedelta

# 今週のスケジュール
today = datetime.now()
start = today.replace(hour=0, minute=0, second=0).isoformat() + '+09:00'
end = (today + timedelta(days=7)).replace(hour=23, minute=59, second=59).isoformat() + '+09:00'

events = garoon.get_schedule_events(start, end)

for event in events:
    subject = event.get('subject', '(件名なし)')
    start_time = event.get('start', {}).get('dateTime', '')
    print(f"{start_time}: {subject}")
```

---

### ワークフロー取得

```python
def get_workflow_requests(client, status='progress'):
    """ワークフロー申請を取得

    Args:
        status: 'progress'(処理中), 'finish'(完了), 'cancel'(取消)
    """
    url = f'{client.base_url}/workflow/admin/requests'
    params = {'status': status}

    response = client.session.get(url, params=params)
    response.raise_for_status()
    return response.json().get('requests', [])
```

---

## 大量データの取得（ページネーション）

```python
def get_all_records(client, query='', batch_size=500):
    """全レコードを取得（ページネーション対応）"""
    all_records = []
    offset = 0

    while True:
        paged_query = f'{query} limit {batch_size} offset {offset}'
        records = client.get_records(query=paged_query)

        if not records:
            break

        all_records.extend(records)
        offset += batch_size

        print(f"取得中: {len(all_records)}件")

        if len(records) < batch_size:
            break

    return all_records

# 使用例
all_records = get_all_records(client, query='ステータス = "承認済"')
print(f"総件数: {len(all_records)}")
```

---

## データ変換・出力

### kintoneレコードをDataFrameに変換

```python
import pandas as pd

def records_to_dataframe(records, fields=None):
    """kintoneレコードをDataFrameに変換"""
    data = []
    for record in records:
        row = {}
        for field_code, field_data in record.items():
            if fields and field_code not in fields:
                continue

            value = field_data.get('value')

            # 配列型の処理
            if isinstance(value, list):
                if value and isinstance(value[0], dict):
                    # サブテーブル等
                    value = str(value)
                else:
                    value = ', '.join(str(v) for v in value)

            row[field_code] = value
        data.append(row)

    return pd.DataFrame(data)

# 使用例
df = records_to_dataframe(records, fields=['$id', '申請者', '金額'])
df.to_excel('output.xlsx', index=False)
```

---

### Excel出力

```python
from openpyxl import Workbook

def export_kintone_to_excel(records, output_path, field_mapping=None):
    """kintoneレコードをExcelに出力

    Args:
        records: kintoneレコードのリスト
        output_path: 出力ファイルパス
        field_mapping: {フィールドコード: 表示名} のマッピング
    """
    wb = Workbook()
    ws = wb.active

    if not records:
        wb.save(output_path)
        return

    # フィールドコード一覧
    field_codes = list(records[0].keys())

    # ヘッダー
    for col, code in enumerate(field_codes, 1):
        header = field_mapping.get(code, code) if field_mapping else code
        ws.cell(row=1, column=col, value=header)

    # データ
    for row, record in enumerate(records, 2):
        for col, code in enumerate(field_codes, 1):
            value = record.get(code, {}).get('value', '')
            if isinstance(value, list):
                value = str(value)
            ws.cell(row=row, column=col, value=value)

    wb.save(output_path)
    print(f"出力完了: {output_path}")

# 使用例
field_mapping = {
    '$id': 'レコードID',
    '申請者': '申請者名',
    '金額': '申請金額'
}
export_kintone_to_excel(records, 'kintone_data.xlsx', field_mapping)
```

---

## エラーハンドリング

```python
import time

def safe_request(func, max_retries=3, retry_delay=5):
    """リトライ付きリクエスト"""
    for attempt in range(max_retries):
        try:
            return func()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limit
                print(f"レート制限。{retry_delay}秒待機...")
                time.sleep(retry_delay)
            elif e.response.status_code >= 500:  # Server error
                print(f"サーバーエラー。リトライ {attempt + 1}/{max_retries}")
                time.sleep(retry_delay)
            else:
                raise
        except requests.exceptions.ConnectionError:
            print(f"接続エラー。リトライ {attempt + 1}/{max_retries}")
            time.sleep(retry_delay)

    raise Exception(f"リトライ上限に達しました")

# 使用例
records = safe_request(lambda: client.get_records(query='...'))
```

---

## 完全なサンプルスクリプト

```python
"""kintoneデータ取得・Excel出力"""
from datetime import datetime

def main():
    # クライアント初期化
    client = KintoneClient(
        subdomain='your-company',
        app_id=123,
        api_token='YOUR_API_TOKEN'
    )

    # 今月のデータを取得
    year_month = datetime.now().strftime('%Y-%m')
    query = f'申請日 like "{year_month}" order by 申請日 asc'

    print(f"データ取得中: {query}")
    records = get_all_records(client, query)
    print(f"取得件数: {len(records)}")

    # Excel出力
    output_path = f'kintone_data_{year_month}.xlsx'
    export_kintone_to_excel(records, output_path)

    print(f"\n処理完了: {output_path}")

if __name__ == '__main__':
    main()
```

---

## 注意事項

1. **APIトークン認証推奨**: パスワード認証より安全
2. **レート制限**: 大量リクエスト時は適切な間隔を空ける
3. **フィールドコード**: 日本語フィールド名ではなくフィールドコードを使用
4. **タイムゾーン**: Garoon APIは+09:00（JST）形式を要求
5. **添付ファイル**: ファイルキーは一時的なもの、再取得時は新しいキーが発行される
