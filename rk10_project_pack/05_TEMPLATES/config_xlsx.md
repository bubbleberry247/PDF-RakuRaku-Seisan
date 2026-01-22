# Template: RK10設定ファイル（Excel形式）

## 概要
RK10シナリオで使用する環境別設定ファイルのテンプレート

---

## ファイル構成

```
config/
├── env.txt                    # 環境切替（"PROD" or "LOCAL"）
├── RK10_config_PROD.xlsx      # 本番環境設定
└── RK10_config_LOCAL.xlsx     # ローカル環境設定
```

---

## env.txt

```
PROD
```

または

```
LOCAL
```

**注意:**
- 改行やスペースを含めない
- 大文字で記載（PROD/LOCAL）

---

## RK10_config_*.xlsx 構造

### Sheet1: Settings

| セル | 項目名 | PROD例 | LOCAL例 | 説明 |
|------|--------|--------|---------|------|
| B2 | ENV | PROD | LOCAL | 環境名 |
| B3 | ROOT_PATH | `\\server\share` | `C:\work` | ルートパス |
| B4 | INPUT_PATH | `\\server\share\input` | `C:\work\input` | 入力フォルダ |
| B5 | OUTPUT_PATH | `\\server\share\output` | `C:\work\output` | 出力フォルダ |
| B6 | WORK_PATH | `\\server\share\work` | `C:\work\temp` | 作業フォルダ |
| B7 | LOG_PATH | `\\server\share\logs` | `C:\work\logs` | ログフォルダ |
| B8 | TEMPLATE_PATH | `\\server\share\templates` | `C:\work\templates` | テンプレートフォルダ |
| B9 | CREDENTIAL_NAME | SYS_LOGIN | SYS_LOGIN_LOCAL | 資格情報名 |
| B10 | BASE_URL | `https://prod.example.com` | `https://dev.example.com` | システムURL |
| B11 | COMPANY_CODE | 300 | 300 | 会社コード |
| B12 | RETRY_COUNT | 10 | 3 | リトライ回数 |
| B13 | TIMEOUT_SEC | 600 | 120 | タイムアウト秒 |
| B14 | MAIL_TO | `admin@example.com` | `dev@example.com` | 通知先メール |
| B15 | MAIL_CC | `manager@example.com` | | CC（任意） |

---

### Excel構造例

```
    A                    B
1   項目名               値
2   ENV                  PROD
3   ROOT_PATH            \\server\share
4   INPUT_PATH           \\server\share\input
5   OUTPUT_PATH          \\server\share\output
...
```

---

## RK10での読み込みパターン

### C#（Program.cs）

```csharp
// 1. env.txt読み込み
var Env = Keyence.FileSystemActions.FileAction.ReadAllText(
    $@"..\config\env.txt",
    Keyence.FileSystemActions.AutoEncoding.Auto);
Env = Keyence.TextActions.TextAction.TrimText(Env, Keyence.TextActions.TrimTextPosition.Both);
Env = Keyence.TextActions.TextAction.ChangeTextCase(Env, Keyence.TextActions.CharacterCaseType.UpperCase);

// 2. 設定ファイルパス決定
var ConfigPath = "";
if (Keyence.ComparisonActions.ComparisonAction.CompareString(
    Env, $@"PROD", Keyence.ComparisonActions.CompareStringMethod.Equal, false))
{
    ConfigPath = $@"..\config\RK10_config_PROD.xlsx";
}
else
{
    ConfigPath = $@"..\config\RK10_config_LOCAL.xlsx";
}

// 3. 設定ファイル読み込み
var excel = Keyence.ExcelActions.ExcelAction.OpenFileAndReturnPath(
    ConfigPath, false, "", true, "", true, true);

// 4. 各種設定値を取得
var cfg_ENV = Keyence.ExcelActions.ExcelAction.GetCellValue(
    Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, "B2",
    Keyence.ExcelActions.TableCellValueMode.String);

var ROOT_PATH = Keyence.ExcelActions.ExcelAction.GetCellValue(
    Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, "B3",
    Keyence.ExcelActions.TableCellValueMode.String);

var INPUT_PATH = Keyence.ExcelActions.ExcelAction.GetCellValue(
    Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, "B4",
    Keyence.ExcelActions.TableCellValueMode.String);

var OUTPUT_PATH = Keyence.ExcelActions.ExcelAction.GetCellValue(
    Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, "B5",
    Keyence.ExcelActions.TableCellValueMode.String);

// ... 以降同様

// 5. 設定ファイルを閉じる
Keyence.ExcelActions.ExcelAction.CloseFile();
```

---

## Pythonでの読み込みパターン

### openpyxlを使用

```python
from openpyxl import load_workbook
from pathlib import Path


def load_rk10_config(config_dir: str, env: str = None) -> dict:
    """RK10設定ファイルを読み込み

    Args:
        config_dir: configフォルダのパス
        env: 環境名（省略時はenv.txtから読み込み）

    Returns:
        設定辞書
    """
    config_dir = Path(config_dir)

    # env.txt読み込み
    if env is None:
        env_file = config_dir / 'env.txt'
        env = env_file.read_text(encoding='utf-8').strip().upper()

    # 設定ファイル読み込み
    config_file = config_dir / f'RK10_config_{env}.xlsx'
    wb = load_workbook(config_file, data_only=True)
    ws = wb.active

    # 設定値を辞書に格納
    config = {}
    for row in range(2, ws.max_row + 1):
        key = ws.cell(row=row, column=1).value
        value = ws.cell(row=row, column=2).value

        if key:
            config[key] = value

    wb.close()
    return config


# 使用例
config = load_rk10_config('C:/ProgramData/RK10/Robots/XX/config')
print(config['ROOT_PATH'])
print(config['INPUT_PATH'])
```

---

## 設定項目カテゴリ

### 必須項目

| 項目 | 説明 |
|------|------|
| ENV | 環境名（PROD/LOCAL） |
| ROOT_PATH | ルートパス |
| INPUT_PATH | 入力フォルダ |
| OUTPUT_PATH | 出力フォルダ |

### 推奨項目

| 項目 | 説明 |
|------|------|
| WORK_PATH | 作業フォルダ |
| LOG_PATH | ログフォルダ |
| CREDENTIAL_NAME | 資格情報名 |
| RETRY_COUNT | リトライ回数 |
| TIMEOUT_SEC | タイムアウト秒 |

### 通知関連

| 項目 | 説明 |
|------|------|
| MAIL_TO | 通知先メールアドレス |
| MAIL_CC | CC（任意） |
| MAIL_SUBJECT_PREFIX | 件名プレフィックス |

### システム固有

| 項目 | 説明 |
|------|------|
| BASE_URL | システムURL |
| COMPANY_CODE | 会社コード |
| API_KEY | APIキー（セキュリティ注意） |

---

## セキュリティ注意事項

1. **パスワードは設定ファイルに書かない**
   - Windows資格情報マネージャーを使用
   - `CREDENTIAL_NAME`で参照名のみ記載

2. **APIキーの取り扱い**
   - 可能であれば環境変数を使用
   - 設定ファイルに記載する場合は暗号化を検討

3. **ファイルアクセス権限**
   - 設定ファイルは必要最小限のユーザーのみアクセス可能に

---

## 設定ファイル作成スクリプト

```python
from openpyxl import Workbook
from openpyxl.styles import Font


def create_config_template(output_path: str, env: str, settings: dict):
    """設定ファイルテンプレートを作成"""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Settings'

    # ヘッダー
    ws['A1'] = '項目名'
    ws['B1'] = '値'
    ws['A1'].font = Font(bold=True)
    ws['B1'].font = Font(bold=True)

    # 設定値
    row = 2
    for key, value in settings.items():
        ws.cell(row=row, column=1, value=key)
        ws.cell(row=row, column=2, value=value)
        row += 1

    # 列幅調整
    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 50

    wb.save(output_path)


# 使用例
prod_settings = {
    'ENV': 'PROD',
    'ROOT_PATH': r'\\server\share',
    'INPUT_PATH': r'\\server\share\input',
    'OUTPUT_PATH': r'\\server\share\output',
    'WORK_PATH': r'\\server\share\work',
    'LOG_PATH': r'\\server\share\logs',
    'CREDENTIAL_NAME': 'SYS_LOGIN',
    'BASE_URL': 'https://prod.example.com',
    'RETRY_COUNT': 10,
    'TIMEOUT_SEC': 600,
    'MAIL_TO': 'admin@example.com',
}

create_config_template('RK10_config_PROD.xlsx', 'PROD', prod_settings)
```
