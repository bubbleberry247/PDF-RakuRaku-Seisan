# Playbook: レコル（RecoRu）勤怠API

## 概要
レコル勤怠管理システムからデータを取得し、勤務区分判定やExcel出力を行う手順

---

## 前提条件
- Python 3.11+
- requests, openpyxl インストール済み
- レコルAPIの認証情報

---

## 勤務区分辞書（最重要）

### 主要な勤務区分

| 区分コード | 名称 | 説明 |
|-----------|------|------|
| 出勤 | 通常出勤 | 標準の勤務 |
| 有休 | 年次有給休暇 | 事前申請必須 |
| 振休 | 振替休日 | 休日出勤の代休（1:1交換、取得期限あり） |
| 代休 | 代替休日 | 休日出勤の代休（取得期限なし） |
| 公休 | 公休日 | 会社カレンダーの休日 |
| 特休 | 特別休暇 | 慶弔等 |
| 欠勤 | 欠勤 | 無届の休み |
| 遅刻 | 遅刻 | 始業時刻後の出勤 |
| 早退 | 早退 | 終業時刻前の退勤 |

### 区分判定ロジック

```python
def determine_work_type(record):
    """勤務区分を判定

    Args:
        record: 勤怠レコード（dict）

    Returns:
        str: 勤務区分
    """
    # 打刻がない場合
    if not record.get('clock_in') and not record.get('clock_out'):
        if record.get('is_holiday'):
            return '公休'
        elif record.get('leave_type'):
            return record['leave_type']  # 有休、振休など
        return '欠勤'

    # 打刻がある場合
    scheduled_start = record.get('scheduled_start')
    actual_start = record.get('clock_in')

    if scheduled_start and actual_start:
        if actual_start > scheduled_start:
            # 遅刻判定（猶予時間考慮）
            grace_minutes = 5
            diff = (actual_start - scheduled_start).total_seconds() / 60
            if diff > grace_minutes:
                return '遅刻'

    return '出勤'
```

---

## API基本操作

### 認証

```python
import requests

class RecoruClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

    def get(self, endpoint, params=None):
        url = f'{self.base_url}/{endpoint}'
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint, data=None):
        url = f'{self.base_url}/{endpoint}'
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

# 使用例
client = RecoruClient(
    base_url='https://api.recoru.jp/v1',
    api_key='YOUR_API_KEY'
)
```

---

### 従業員一覧取得

```python
def get_employees(client):
    """従業員一覧を取得"""
    result = client.get('employees')
    return result.get('employees', [])

# 使用例
employees = get_employees(client)
for emp in employees:
    print(f"{emp['id']}: {emp['name']} ({emp['department']})")
```

---

### 勤怠データ取得

```python
from datetime import datetime, timedelta

def get_attendance(client, employee_id, start_date, end_date):
    """勤怠データを取得

    Args:
        client: RecoruClient
        employee_id: 従業員ID
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）

    Returns:
        list: 勤怠レコードのリスト
    """
    result = client.get('attendance', params={
        'employee_id': employee_id,
        'start_date': start_date,
        'end_date': end_date
    })
    return result.get('records', [])

# 使用例：今月の勤怠を取得
today = datetime.now()
start = today.replace(day=1).strftime('%Y-%m-%d')
end = today.strftime('%Y-%m-%d')

records = get_attendance(client, 'EMP001', start, end)
```

---

### 有休残日数取得

```python
def get_leave_balance(client, employee_id):
    """有休残日数を取得"""
    result = client.get(f'employees/{employee_id}/leave-balance')
    return {
        'paid_leave': result.get('paid_leave', 0),       # 有休
        'substitute': result.get('substitute', 0),        # 振休
        'compensatory': result.get('compensatory', 0),    # 代休
    }

# 使用例
balance = get_leave_balance(client, 'EMP001')
print(f"有休残: {balance['paid_leave']}日")
```

---

## データ整形・出力

### 月次勤怠サマリー作成

```python
from dataclasses import dataclass
from typing import List, Dict
from collections import defaultdict

@dataclass
class MonthlySummary:
    employee_id: str
    employee_name: str
    year_month: str
    work_days: int           # 出勤日数
    paid_leave_days: float   # 有休取得日数
    late_count: int          # 遅刻回数
    early_leave_count: int   # 早退回数
    overtime_hours: float    # 残業時間

def create_monthly_summary(records: List[dict], employee_name: str) -> MonthlySummary:
    """月次サマリーを作成"""
    work_types = defaultdict(int)
    overtime_minutes = 0

    for record in records:
        work_type = determine_work_type(record)
        work_types[work_type] += 1
        overtime_minutes += record.get('overtime_minutes', 0)

    return MonthlySummary(
        employee_id=records[0]['employee_id'] if records else '',
        employee_name=employee_name,
        year_month=records[0]['date'][:7] if records else '',
        work_days=work_types['出勤'],
        paid_leave_days=work_types['有休'],
        late_count=work_types['遅刻'],
        early_leave_count=work_types['早退'],
        overtime_hours=overtime_minutes / 60
    )
```

---

### Excel出力

```python
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side

def export_to_excel(summaries: List[MonthlySummary], output_path: str):
    """月次サマリーをExcelに出力"""
    wb = Workbook()
    ws = wb.active
    ws.title = '勤怠サマリー'

    # ヘッダー
    headers = ['社員ID', '氏名', '年月', '出勤日数', '有休', '遅刻', '早退', '残業時間']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')

    # データ
    for row, summary in enumerate(summaries, 2):
        ws.cell(row=row, column=1, value=summary.employee_id)
        ws.cell(row=row, column=2, value=summary.employee_name)
        ws.cell(row=row, column=3, value=summary.year_month)
        ws.cell(row=row, column=4, value=summary.work_days)
        ws.cell(row=row, column=5, value=summary.paid_leave_days)
        ws.cell(row=row, column=6, value=summary.late_count)
        ws.cell(row=row, column=7, value=summary.early_leave_count)
        ws.cell(row=row, column=8, value=f'{summary.overtime_hours:.1f}h')

    # 列幅調整
    for col in ws.columns:
        max_length = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_length + 2

    wb.save(output_path)
    print(f"出力完了: {output_path}")
```

---

## 申請処理

### 有休申請

```python
def submit_leave_request(client, employee_id, leave_type, start_date, end_date, reason=''):
    """休暇申請を提出

    Args:
        client: RecoruClient
        employee_id: 従業員ID
        leave_type: 休暇種別（paid_leave/substitute/compensatory）
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        reason: 理由（オプション）

    Returns:
        dict: 申請結果
    """
    result = client.post('leave-requests', data={
        'employee_id': employee_id,
        'leave_type': leave_type,
        'start_date': start_date,
        'end_date': end_date,
        'reason': reason
    })
    return result

# 使用例
result = submit_leave_request(
    client,
    employee_id='EMP001',
    leave_type='paid_leave',
    start_date='2025-02-01',
    end_date='2025-02-01',
    reason='私用のため'
)
```

---

### 勤怠修正申請

```python
def submit_correction_request(client, employee_id, date, clock_in=None, clock_out=None, reason=''):
    """勤怠修正申請を提出"""
    data = {
        'employee_id': employee_id,
        'date': date,
        'reason': reason
    }
    if clock_in:
        data['clock_in'] = clock_in
    if clock_out:
        data['clock_out'] = clock_out

    result = client.post('correction-requests', data=data)
    return result
```

---

## 例外ケース対応

### 締め後の修正

```python
def check_closing_status(client, year_month):
    """締め状態を確認

    Returns:
        str: 'open', 'closed', 'locked' のいずれか
    """
    result = client.get('closing-status', params={'year_month': year_month})
    return result.get('status', 'unknown')

def request_unlock(client, year_month, reason):
    """締め解除を申請"""
    result = client.post('unlock-requests', data={
        'year_month': year_month,
        'reason': reason
    })
    return result
```

### 半日有休

```python
def submit_half_day_leave(client, employee_id, date, half='am'):
    """半日有休を申請

    Args:
        half: 'am'（午前）または 'pm'（午後）
    """
    result = client.post('leave-requests', data={
        'employee_id': employee_id,
        'leave_type': 'paid_leave',
        'start_date': date,
        'end_date': date,
        'half_day': half,
        'days': 0.5
    })
    return result
```

---

## 完全なサンプルスクリプト

```python
"""レコル勤怠データ取得・出力"""
from datetime import datetime

def main():
    # クライアント初期化
    client = RecoruClient(
        base_url='https://api.recoru.jp/v1',
        api_key='YOUR_API_KEY'
    )

    # 対象期間
    year_month = '2025-01'
    start_date = f'{year_month}-01'
    end_date = f'{year_month}-31'

    # 従業員一覧取得
    employees = get_employees(client)
    print(f"従業員数: {len(employees)}")

    # 各従業員の勤怠を取得
    summaries = []
    for emp in employees:
        records = get_attendance(client, emp['id'], start_date, end_date)
        summary = create_monthly_summary(records, emp['name'])
        summaries.append(summary)
        print(f"  {emp['name']}: {summary.work_days}日勤務")

    # Excel出力
    output_path = f'勤怠サマリー_{year_month}.xlsx'
    export_to_excel(summaries, output_path)

    print(f"\n処理完了: {output_path}")

if __name__ == '__main__':
    main()
```

---

## 注意事項

1. **APIレート制限**: 大量リクエスト時は適切な間隔を空ける
2. **認証情報管理**: APIキーはコードに埋め込まず環境変数等から取得
3. **締め状態確認**: 締め後のデータは変更不可の場合がある
4. **半日単位**: 有休は0.5日単位で管理されることがある
5. **タイムゾーン**: 日時データはJST前提で処理
