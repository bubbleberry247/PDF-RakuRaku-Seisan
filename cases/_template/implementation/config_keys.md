# 設定キー一覧

## 概要

このドキュメントは、プロジェクトで使用する設定キーの一覧と説明を記載する。

---

## 設定ファイル

| ファイル | 用途 | Git管理 |
|----------|------|---------|
| project.yaml | プロジェクト共通設定 | Yes |
| local.yaml | ローカル環境設定（機密含む） | No |

---

## 設定キー一覧

### 認証情報（local.yaml）

| キー | 説明 | 型 | 必須 | 例 |
|------|------|-----|------|-----|
| credentials.site_username | サイトログインID | string | Yes | "user001" |
| credentials.site_password | サイトパスワード | string | Yes | "***" |

### 環境設定（project.yaml）

| キー | 説明 | 型 | 必須 | 例 |
|------|------|-----|------|-----|
| environments.local.robot_path | ローカルロボットパス | string | Yes | "C:\\..." |
| environments.prod.robot_path | 本番ロボットパス | string | Yes | "C:\\..." |

### 通知設定（project.yaml）

| キー | 説明 | 型 | 必須 | 例 |
|------|------|-----|------|-----|
| notification.enabled | 通知有効化 | boolean | Yes | true |
| notification.recipients | 通知先メールアドレス | list | Yes | ["a@b.com"] |

### リトライ設定（project.yaml）

| キー | 説明 | 型 | 必須 | 例 |
|------|------|-----|------|-----|
| retry.default_max_attempts | デフォルトリトライ回数 | integer | Yes | 3 |
| retry.default_wait_seconds | リトライ待機秒数 | integer | Yes | 5 |

### タイムアウト設定（project.yaml）

| キー | 説明 | 型 | 必須 | 例 |
|------|------|-----|------|-----|
| timeout.page_load | ページ読み込み待機（秒） | integer | Yes | 30 |
| timeout.element_wait | 要素待機（秒） | integer | Yes | 10 |

---

## 使用例（コード内）

```python
import yaml

# 設定読み込み
with open('config/project.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 値の取得
robot_path = config['environments']['local']['robot_path']
max_retry = config['retry']['default_max_attempts']
```
