# Notification Email（Andon）

## 1. 件名テンプレート

```
[RPA][{ENV}][{CUSTOMER}][{PROJECT}][{SCENARIO}] {STATUS} step={STEP_ID} run={RUN_ID}
```

### 変数説明

| 変数 | 説明 | 例 |
|------|------|-----|
| {ENV} | 環境 | LOCAL / PROD |
| {CUSTOMER} | 顧客名 | ABC株式会社 |
| {PROJECT} | プロジェクト名 | 経費精算 |
| {SCENARIO} | シナリオ番号 | 44 |
| {STATUS} | ステータス | SUCCESS / FAILED / WARNING |
| {STEP_ID} | 失敗ステップID | S030 |
| {RUN_ID} | 実行ID | 20260119_143025 |

### 件名例

```
[RPA][PROD][ABC株式会社][経費精算][44] FAILED step=S030 run=20260119_143025
```

---

## 2. 本文テンプレート（必須項目）

```
■ 発生日時
{YYYY-MM-DD HH:MM:SS}

■ 環境
{ENV}: LOCAL / PROD

■ 案件情報
- customer: {CUSTOMER}
- project: {PROJECT}
- scenario: {SCENARIO}
- run_id: {RUN_ID}

■ エラー情報
- failure step_id: {STEP_ID}（RK10行番号: {LINE_NO}）
- error_code: {ERROR_CODE}
- error_message: {ERROR_MESSAGE}

■ 次アクション
- 再実行可否: Yes / No
- 再実行する場合の開始STEP_ID: {RESTART_STEP_ID}
- 手動介入が必要な場合の手順: repo:/{PATH_TO_RUNBOOK}

■ ログ/証跡
- LOCAL: {LOCAL_LOG_PATH}
- PROD: {PROD_LOG_PATH}
- スクリーンショット: {SCREENSHOT_PATH}

■ 備考
{NOTES}
```

---

## 3. ステータス別テンプレート

### 3.1 SUCCESS（成功）

```
件名: [RPA][PROD][{CUSTOMER}][{PROJECT}][{SCENARIO}] SUCCESS run={RUN_ID}

本文:
■ 完了日時: {DATETIME}
■ 処理件数: {COUNT}件
■ 処理時間: {DURATION}分
■ 出力ファイル: {OUTPUT_PATH}
```

### 3.2 FAILED（失敗）

```
件名: [RPA][PROD][{CUSTOMER}][{PROJECT}][{SCENARIO}] FAILED step={STEP_ID} run={RUN_ID}

本文:
[本文テンプレート全項目を記載]
```

### 3.3 WARNING（警告）

```
件名: [RPA][PROD][{CUSTOMER}][{PROJECT}][{SCENARIO}] WARNING run={RUN_ID}

本文:
■ 警告内容: {WARNING_MESSAGE}
■ 影響: {IMPACT}
■ 推奨アクション: {RECOMMENDED_ACTION}
```

---

## 4. 通知先設定

| 優先度 | 条件 | 通知先 |
|--------|------|--------|
| HIGH | FAILED | {PRIMARY_EMAIL}, {SECONDARY_EMAIL} |
| MEDIUM | WARNING | {PRIMARY_EMAIL} |
| LOW | SUCCESS | {LOG_EMAIL} |

---

## 5. 実装例（Python）

```python
def send_notification(status, step_id, run_id, error_info=None):
    subject = f"[RPA][{ENV}][{CUSTOMER}][{PROJECT}][{SCENARIO}] {status}"
    if step_id:
        subject += f" step={step_id}"
    subject += f" run={run_id}"

    body = f"""
■ 発生日時
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

■ 環境
{ENV}

■ 案件情報
- customer: {CUSTOMER}
- project: {PROJECT}
- scenario: {SCENARIO}
- run_id: {run_id}
"""
    if error_info:
        body += f"""
■ エラー情報
- failure step_id: {step_id}
- error_code: {error_info.get('code')}
- error_message: {error_info.get('message')}
"""

    send_email(RECIPIENTS, subject, body)
```
