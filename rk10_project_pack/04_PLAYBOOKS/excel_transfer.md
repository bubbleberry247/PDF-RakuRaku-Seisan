# Playbook: Excel転記処理

## 概要
RK10およびPythonでExcelファイル間のデータ転記を行う手順

---

## 前提条件
- RK10 3.6.x（C#シナリオ用）
- Python 3.11+ + openpyxl（Python用）

---

## パターン1: RK10でのExcel転記

### 基本フロー

```csharp
// 1. ソースファイルを開く
var srcExcel = Keyence.ExcelActions.ExcelAction.OpenFileAndReturnPath(
    srcPath, false, "", true, "", true, true);

// 2. データ読み取り
var value = Keyence.ExcelActions.ExcelAction.GetCellValue(
    Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, "B2",
    Keyence.ExcelActions.TableCellValueMode.String);

// 3. ソースを閉じる
Keyence.ExcelActions.ExcelAction.CloseFile();

// 4. 転記先ファイルを開く
var dstExcel = Keyence.ExcelActions.ExcelAction.OpenFileAndReturnPath(
    dstPath, false, "", true, "", true, true);

// 5. シート選択
Keyence.ExcelActions.ExcelAction.SelectSheet(
    Keyence.ExcelActions.SheetSelectionMode.Name, $@"{sheetName}", 1);

// 6. データ書き込み
Keyence.ExcelActions.ExcelAction.WriteCell(
    Keyence.ExcelActions.RangeSpecificationMethod.Number,
    Keyence.ExcelActions.CellSelectionMethod.Specified,
    2, 5, "",  // B5
    Keyence.ExcelActions.InputValueType.String, value,
    default, default, false, false);

// 7. 保存して閉じる
Keyence.ExcelActions.ExcelAction.SaveFile("",
    Keyence.ExcelActions.PreservationMethod.Overwrite,
    Keyence.ExcelActions.SaveFileType.ExtensionCompliant);
Keyence.ExcelActions.ExcelAction.CloseFile();
```

---

### 「合計」行検索パターン

```csharp
// GetMatchValueListは「$列$行」形式で返す
var list = Keyence.ExcelActions.ExcelAction.GetMatchValueList(
    Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, 1, 1,
    "J:J", "合計", false);

var cell = Keyence.BasicActions.ListAction.GetItem(list, 0);  // "$J$123"

// $を除去
cell = Keyence.TextActions.TextAction.ReplaceText(
    cell, "$", false, false, "", false, false);

// 列名を除去して行番号のみ取得
var rowStr = Keyence.TextActions.TextAction.ReplaceText(
    cell, "J", false, false, "", false, false);

var row = Keyence.ConvertActions.ConvertAction.ConvertFromObjectToInteger(rowStr);
// row = 123
```

---

### 部門別金額取得ループ（下から上へ走査）

```csharp
var 金額管理 = -1;
var 金額営業 = -1;
var 金額製造 = -1;
var 金額品質 = -1;
var 金額総務 = -1;
var foundCount = 0;

foreach (var loop in Keyence.LoopActions.LoopAction.RepeatCount(50))
{
    var rowStr = Keyence.ConvertActions.ConvertAction.ConvertFromObjectToText(row);
    var cellJ = Keyence.TextActions.TextAction.Concat("J", rowStr);
    var cellS = Keyence.TextActions.TextAction.Concat("S", rowStr);

    // J列のラベルを確認
    var label = Keyence.ExcelActions.ExcelAction.GetCellValue(
        Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, cellJ,
        Keyence.ExcelActions.TableCellValueMode.String);

    // 「合計」以外の行に到達したら終了
    if (Keyence.ComparisonActions.ComparisonAction.CompareString(
        label, "合計", Keyence.ComparisonActions.CompareString.NotEqual, false))
        break;

    // S列の部門名を取得
    var 部門名 = Keyence.ExcelActions.ExcelAction.GetCellValue(
        Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, cellS,
        Keyence.ExcelActions.TableCellValueMode.String);

    // R列の金額を取得
    var cellR = Keyence.TextActions.TextAction.Concat("R", rowStr);
    var 金額str = Keyence.ExcelActions.ExcelAction.GetCellValue(
        Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, cellR,
        Keyence.ExcelActions.TableCellValueMode.String);
    var 金額 = Keyence.ConvertActions.ConvertAction.ConvertFromObjectToDouble(金額str);

    // 部門別に振り分け
    if (Keyence.ComparisonActions.ComparisonAction.CompareDouble(金額管理, -1d, Keyence.ComparisonActions.CompareDouble.Equal) &&
        Keyence.ComparisonActions.ComparisonAction.CompareString(部門名, "管理", Keyence.ComparisonActions.CompareString.Equal, false))
    {
        金額管理 = 金額;
        foundCount += 1;
    }
    // ... 他の部門も同様

    // 5部門すべて取得したら終了
    if (Keyence.ComparisonActions.ComparisonAction.CompareDouble(foundCount, 5d, Keyence.ComparisonActions.CompareDouble.Equal))
        break;
    else
        row += -1;  // 下から上へ
}
```

---

## パターン2: PythonでのExcel転記

### openpyxlを使った基本操作

```python
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

def transfer_data(src_path, dst_path, sheet_name):
    """Excelファイル間でデータ転記"""

    # ソースファイルを開く
    src_wb = load_workbook(src_path, data_only=True)
    src_ws = src_wb.active

    # データ読み取り
    data = []
    for row in src_ws.iter_rows(min_row=2, values_only=True):
        if row[0] is None:  # A列が空なら終了
            break
        data.append(row)

    src_wb.close()

    # 転記先ファイルを開く
    dst_wb = load_workbook(dst_path)

    # シート選択（なければ作成）
    if sheet_name in dst_wb.sheetnames:
        dst_ws = dst_wb[sheet_name]
    else:
        dst_ws = dst_wb.create_sheet(sheet_name)

    # データ書き込み
    start_row = 17  # 開始行
    for i, row_data in enumerate(data):
        current_row = start_row + i
        for j, value in enumerate(row_data):
            dst_ws.cell(row=current_row, column=j+1, value=value)

    # 保存
    dst_wb.save(dst_path)
    print(f"転記完了: {len(data)}行")
```

---

### 2行1セット構造への転記

```python
from openpyxl import load_workbook

def transfer_2row_set(records, excel_path, sheet_name):
    """2行1セット（本体行+税行）構造に転記

    本体行（奇数行: 17, 19, 21...）
    - C列: 摘要
    - I列: 支払額（税込金額）
    - J列: 支払先計（SUM数式、触らない）

    税行（偶数行: 18, 20, 22...）
    - 絶対に触らない（数式で自動計算）
    """
    wb = load_workbook(excel_path)
    ws = wb[sheet_name]

    start_row = 17  # 最初の本体行

    for i, record in enumerate(records):
        body_row = start_row + (i * 2)  # 本体行
        # tax_row = body_row + 1  # 税行（触らない）

        # 本体行のみ書き込み
        ws[f'C{body_row}'] = record.description
        ws[f'I{body_row}'] = record.amount

        # J列（支払先計）は数式が入っているので触らない

    wb.save(excel_path)
```

---

### 「合計」行の検索

```python
from openpyxl import load_workbook

def find_total_row(excel_path, sheet_name, search_column='J'):
    """「合計」行を検索"""
    wb = load_workbook(excel_path, data_only=True)
    ws = wb[sheet_name]

    for row in range(1, ws.max_row + 1):
        cell_value = ws[f'{search_column}{row}'].value
        if cell_value == '合計':
            return row

    return None

# 使用例
total_row = find_total_row('data.xlsx', '2025.01')
print(f"合計行: {total_row}")
```

---

### 部門別金額の取得

```python
def get_department_amounts(excel_path, sheet_name, total_row):
    """部門別金額を取得（下から上へ走査）"""
    wb = load_workbook(excel_path, data_only=True)
    ws = wb[sheet_name]

    departments = {}
    required = {'管理', '営業', '製造', '品質', '総務'}

    row = total_row
    while len(departments) < len(required) and row > 1:
        label = ws[f'J{row}'].value
        if label != '合計':
            break

        dept_name = ws[f'S{row}'].value
        amount = ws[f'R{row}'].value or 0

        if dept_name in required and dept_name not in departments:
            departments[dept_name] = amount

        row -= 1  # 下から上へ

    return departments

# 使用例
amounts = get_department_amounts('data.xlsx', '2025.01', 150)
# {'管理': 123456, '営業': 234567, ...}
```

---

## 確度による色分け

```python
from openpyxl.styles import Font

CONFIDENCE_COLORS = {
    'exact': Font(color='000000'),      # 完全一致: 黒
    'estimated': Font(color='FFB900'),  # 推定: 黄色
    'unknown': Font(color='FF0000'),    # 不明: 赤
}

def apply_confidence_color(ws, row, column, confidence):
    """確度に応じた色を適用"""
    cell = ws.cell(row=row, column=column)
    cell.font = CONFIDENCE_COLORS.get(confidence, CONFIDENCE_COLORS['unknown'])
```

---

## 注意事項

1. **ファイルロック**: Excelファイルが開いているとエラーになる。リトライパターンを使用
2. **数式の保持**: `data_only=True`で開くと数式が値に変換される。数式を保持したい場合は省略
3. **シート名のフォーマット**: `yyyy.MM`形式が多い（`2025.01`など）
4. **2行1セット**: 税行は絶対に触らない（数式で自動計算）
5. **日付型の扱い**: openpyxlは日付をdatetime型で返す場合がある
