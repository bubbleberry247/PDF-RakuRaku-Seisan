# Playbook: .rksファイル編集

## 概要
KEYENCE RK-10のシナリオファイル（.rks）をプログラムで編集する手順

---

## 前提条件
- Python 3.11+
- zipfileモジュール（標準ライブラリ）

---

## .rksファイル構造

```
scenario.rks (ZIP形式)
├── Program.cs              ← メインロジック（C#コード）★編集対象
├── ExternalActivities.cs   ← 外部アクティビティ定義
├── id                      ← Roslyn構文木の位置情報（自動再生成）
├── meta                    ← GUIレイアウト（自動再生成）
├── rootMeta                ← 実行速度設定など
└── version                 ← ファイルバージョン情報
```

**重要:** Program.csのみ編集すればOK。`id`と`meta`はRK10が自動再生成する。

---

## 手順

### Step 1: Program.csを読み込み

```python
import zipfile

rks_path = 'scenario.rks'

with zipfile.ZipFile(rks_path, 'r') as z:
    code = z.read('Program.cs').decode('utf-8-sig')

print(code[:500])  # 確認用
```

### Step 2: コードを修正

```python
# 例1: ハードコードされた日付を動的変数に変更
modified_code = code.replace('$@"2025.11"', '$@"{string10}"')

# 例2: 日付フォーマットを修正
modified_code = modified_code.replace('$@"yyyy.MM"', '$@"yyyyMM"')

# 例3: ファイルクローズを追加（正規表現使用）
import re
if 'CloseFile()' not in modified_code:
    modified_code = re.sub(
        r'(SaveFile\([^)]+\);)',
        r'\1\n        Keyence.ExcelActions.ExcelAction.CloseFile();',
        modified_code
    )
```

### Step 3: 新しい.rksを作成

```python
output_path = 'scenario_modified.rks'

with zipfile.ZipFile(rks_path, 'r') as src:
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as dst:
        for item in src.namelist():
            if item == 'Program.cs':
                dst.writestr(item, modified_code.encode('utf-8-sig'))
            else:
                dst.writestr(item, src.read(item))

print(f"出力: {output_path}")
```

---

## よくある修正パターン

### パターン1: シート名ハードコードの修正

**Before:**
```csharp
Keyence.ExcelActions.ExcelAction.SelectSheet(
    Keyence.ExcelActions.SheetSelectionMode.Name, $@"2025.01", 1);
```

**After:**
```csharp
Keyence.ExcelActions.ExcelAction.SelectSheet(
    Keyence.ExcelActions.SheetSelectionMode.Name, $@"{string10}", 1);
```

### パターン2: ファイルパスの環境変数化

**Before:**
```csharp
var filePath = $@"C:\Data\input.xlsx";
```

**After:**
```csharp
var filePath = ROOT_PATH + $@"\input.xlsx";
```

### パターン3: CloseFile追加

```python
# SaveFileの後にCloseFileがない場合に追加
pattern = r'(Keyence\.ExcelActions\.ExcelAction\.SaveFile\([^)]+\);)(?!\s*Keyence\.ExcelActions\.ExcelAction\.CloseFile)'
replacement = r'\1\n        Keyence.ExcelActions.ExcelAction.CloseFile();'
modified_code = re.sub(pattern, replacement, code)
```

---

## ハードコード検出スクリプト

```python
import zipfile
import re

def detect_hardcodes(rks_path):
    """ハードコードされた値を検出"""
    with zipfile.ZipFile(rks_path, 'r') as z:
        code = z.read('Program.cs').decode('utf-8-sig')

    issues = []

    # 年月のハードコード
    for match in re.finditer(r'\$@"(202[0-9]\.[01][0-9])"', code):
        issues.append(f"日付ハードコード: {match.group(1)}")

    # 絶対パスのハードコード
    for match in re.finditer(r'\$@"([A-Z]:\\[^"]+)"', code):
        issues.append(f"絶対パス: {match.group(1)}")

    # CloseFile確認
    open_count = len(re.findall(r'OpenFileAndReturnPath', code))
    close_count = len(re.findall(r'CloseFile\(\)', code))
    if open_count > close_count:
        issues.append(f"CloseFile不足: Open={open_count}, Close={close_count}")

    return issues

# 使用例
issues = detect_hardcodes('scenario.rks')
for issue in issues:
    print(f"[警告] {issue}")
```

---

## 一括修正スクリプト

```python
import zipfile
import re
from pathlib import Path

def fix_rks(input_path, output_path, replacements):
    """
    .rksファイルを一括修正

    Args:
        input_path: 入力.rksファイルパス
        output_path: 出力.rksファイルパス
        replacements: [(検索パターン, 置換文字列), ...] のリスト
    """
    with zipfile.ZipFile(input_path, 'r') as z:
        code = z.read('Program.cs').decode('utf-8-sig')

    for pattern, replacement in replacements:
        code = re.sub(pattern, replacement, code)

    with zipfile.ZipFile(input_path, 'r') as src:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as dst:
            for item in src.namelist():
                if item == 'Program.cs':
                    dst.writestr(item, code.encode('utf-8-sig'))
                else:
                    dst.writestr(item, src.read(item))

    return output_path

# 使用例
replacements = [
    (r'\$@"2025\.01"', r'$@"{string10}"'),
    (r'C:\\\\固定パス', r'{ROOT_PATH}'),
]
fix_rks('input.rks', 'output.rks', replacements)
```

---

## 注意事項

1. **バックアップ必須**: 編集前に必ず元ファイルをバックアップ
2. **エンコーディング**: `utf-8-sig`（BOM付きUTF-8）を使用
3. **検証**: 編集後はRK10 GUIで開いてビルドエラーがないか確認
4. **id/metaの再生成**: Program.cs以外のファイルはそのままコピーすればOK
