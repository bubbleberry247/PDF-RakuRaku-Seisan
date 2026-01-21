# RK10_config_{ENV}.xlsx Schema（項目定義）v0.1

**最終更新**: 2026-01-17
**ステータス**: ドラフト

---

## 1. 目的

- LOCAL/PROD差分を設定で吸収し、ハードコードを減らす
- 検証ルールを固定し、設定ミスによる事故を防ぐ
- 機微情報の管理ポリシーを明確化

---

## 2. ファイル構成

| 環境 | ファイルパス | Git管理 |
|------|-------------|---------|
| LOCAL | `config/RK10_config_LOCAL.xlsx` | **×（.gitignore）** |
| PROD | `config/RK10_config_PROD.xlsx` | **×（.gitignore）** |
| テンプレート | `config/RK10_config_TEMPLATE.xlsx` | ○ |

---

## 3. 項目一覧

### 3.1 シート構成（想定）

| シート名 | 内容 |
|---------|------|
| General | 基本設定（ENV、パスなど） |
| Auth | 認証情報（楽楽精算、API） |
| Paths | ファイルパス設定 |
| OCR | OCR関連パラメータ |
| Thresholds | 閾値設定 |

### 3.2 General（基本設定）

| key | 説明 | 必須 | ENV差分 | 形式/制約 | 検証 | 機微 |
|-----|------|------|---------|----------|------|------|
| env | 環境識別子 | ○ | ○ | LOCAL/PROD | enum確認 | × |
| log_level | ログレベル | × | △ | DEBUG/INFO/WARNING/ERROR | enum確認 | × |
| dry_run | ドライランモード | × | △ | true/false | bool確認 | × |

### 3.3 Auth（認証情報）

| key | 説明 | 必須 | ENV差分 | 形式/制約 | 検証 | 機微 |
|-----|------|------|---------|----------|------|------|
| rakuraku_url | 楽楽精算URL | ○ | ○ | URL形式 | URL妥当性 | × |
| rakuraku_user | ログインユーザー | ○ | ○ | 文字列 | 非空確認 | **○** |
| rakuraku_pass | ログインパスワード | ○ | ○ | 文字列 | 非空確認 | **○** |
| adobe_api_key | Adobe PDF Services APIキー | △ | × | 文字列 | 非空確認 | **○** |

### 3.4 Paths（パス設定）

| key | 説明 | 必須 | ENV差分 | 形式/制約 | 検証 | 機微 |
|-----|------|------|---------|----------|------|------|
| input_dir | 入力PDFフォルダ | ○ | ○ | ディレクトリパス | 存在確認 | × |
| output_dir | 出力フォルダ | ○ | △ | ディレクトリパス | 存在確認 | × |
| processed_dir | 処理済みフォルダ | ○ | △ | ディレクトリパス | 存在確認 | × |
| manual_queue_dir | 手動キューフォルダ | ○ | △ | ディレクトリパス | 存在確認 | × |
| log_dir | ログフォルダ | ○ | △ | ディレクトリパス | 存在確認 | × |

### 3.5 OCR（OCR設定）

| key | 説明 | 必須 | ENV差分 | 形式/制約 | 検証 | 機微 |
|-----|------|------|---------|----------|------|------|
| ocr_engine | 優先OCRエンジン | × | × | yomitoku/adobe | enum確認 | × |
| fallback_enabled | フォールバック有効 | × | × | true/false | bool確認 | × |

### 3.6 Thresholds（閾値設定）

| key | 説明 | 必須 | ENV差分 | 形式/制約 | 検証 | 機微 |
|-----|------|------|---------|----------|------|------|
| confidence_threshold | OCR信頼度閾値 | × | × | 0.0-1.0 | 範囲確認 | × |
| rotation_confidence | 回転検出信頼度閾値 | × | × | 0.0-100.0 | 範囲確認 | × |
| max_skew_angle | 最大傾き角度（度） | × | × | 0-90 | 範囲確認 | × |
| timeout_sec | 処理タイムアウト（秒） | × | × | 正整数 | 正整数確認 | × |

---

## 4. 検証ルール

### 4.1 起動時検証

以下を起動時にチェックし、不正があればエラー終了。

```python
def validate_config(config: dict) -> list[str]:
    errors = []

    # 必須項目チェック
    required = ['env', 'rakuraku_url', 'input_dir']
    for key in required:
        if not config.get(key):
            errors.append(f"Required key missing: {key}")

    # パス存在チェック
    path_keys = ['input_dir', 'output_dir', 'processed_dir']
    for key in path_keys:
        path = config.get(key)
        if path and not os.path.exists(path):
            errors.append(f"Path not found: {key}={path}")

    # 閾値範囲チェック
    if not (0.0 <= config.get('confidence_threshold', 0.4) <= 1.0):
        errors.append("confidence_threshold must be 0.0-1.0")

    return errors
```

### 4.2 機微項目の扱い

- **ログに出さない**: `logging_policy.md` 準拠
- **Gitに入れない**: `.gitignore` で除外
- **テンプレートには空で入れる**: 値は各環境でのみ設定

---

## 5. LOCAL/PROD差分管理

### 5.1 差分が発生する項目

| 項目 | LOCAL | PROD |
|------|-------|------|
| env | LOCAL | PROD |
| input_dir | `data\MOCK_FAX\` | `\\192.168.1.251\...` |
| rakuraku_url | テスト環境URL | 本番URL |
| rakuraku_user | テストユーザー | 本番ユーザー |
| rakuraku_pass | テストパスワード | 本番パスワード |

### 5.2 差分が発生しない項目

| 項目 | 共通値 |
|------|--------|
| confidence_threshold | 0.40 |
| rotation_confidence | 5.0 |
| ocr_engine | yomitoku |

---

## 6. テンプレート

`config/RK10_config_TEMPLATE.xlsx` として以下を提供（機微項目は空）。

```
シート: General
| key | value | description |
|-----|-------|-------------|
| env | | LOCAL or PROD |
| log_level | INFO | DEBUG/INFO/WARNING/ERROR |
| dry_run | false | true/false |

シート: Auth
| key | value | description |
|-----|-------|-------------|
| rakuraku_url | | 楽楽精算URL |
| rakuraku_user | | ログインユーザー（機密） |
| rakuraku_pass | | パスワード（機密） |

...
```

---

## 7. TBD（要確認事項）

- [ ] 実際のconfig/*.xlsxの構造を確認して項目を埋める
- [ ] 検証関数の実装
- [ ] テンプレートファイルの作成
- [ ] LOCAL/PROD差分の正確な洗い出し

---

## 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|----------|
| 2026-01-17 | v0.1 | 初版作成（項目は想定） |
