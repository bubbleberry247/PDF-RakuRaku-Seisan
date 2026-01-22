# RK10シナリオ作成 Skill

## 概要
KEYENCE RK-10 RPAシナリオの作成・編集・デバッグに関する知識

## 前提条件
- RK10 3.6.44.51108以上インストール済み
- Python 3.11+環境
- pywinauto, openpyxl, playwright インストール済み

---

## 1. .rksファイル編集（最重要）

### 1.1 ファイル構造
```
.rks (ZIP形式)
├── Program.cs              ← メインロジック（C#コード）★編集対象
├── ExternalActivities.cs   ← 外部アクティビティ定義
├── id                      ← Roslyn構文木の位置情報（自動再生成）
├── meta                    ← GUIレイアウト（自動再生成）
├── rootMeta                ← 実行速度設定など
└── version                 ← ファイルバージョン情報
```

**重要**: Program.csのみ編集すればOK。id/metaはRK10が自動再生成する。

### 1.2 .rks編集テンプレート（Python）

```python
import zipfile

# 1. RKSからProgram.csを読み込み
with zipfile.ZipFile('scenario.rks', 'r') as z:
    code = z.read('Program.cs').decode('utf-8-sig')

# 2. コードを修正
modified_code = code.replace('$@"2025.11"', '$@"{string10}"')

# 3. 新しいRKSを作成（他のファイルもコピー）
with zipfile.ZipFile('original.rks', 'r') as src:
    with zipfile.ZipFile('modified.rks', 'w') as dst:
        for item in src.namelist():
            if item == 'Program.cs':
                dst.writestr(item, modified_code.encode('utf-8-sig'))
            else:
                dst.writestr(item, src.read(item))
```

### 1.3 よくある修正パターン

| 修正前 | 修正後 | 説明 |
|--------|--------|------|
| `$@"2025.11"` | `$@"{string10}"` | 月のシート名を動的変数に |
| `$@"yyyy.MM"` | `$@"yyyyMM"` | 日付フォーマット修正 |
| OpenFileのみ | OpenFile + CloseFile | ファイル閉じ忘れ対応 |

### 1.4 ハードコード検出パターン

検索すべきキーワード:
- `$@"202` - 年月のハードコード
- `$@"C:\\` - 絶対パスのハードコード
- `SelectSheet` + 固定文字列 - シート名ハードコード
- `OpenFile` のみ - CloseFile()の確認

---

## 2. RK10 UI操作（pywinauto）

### 2.1 基本設定
- **バックエンド**: pywinauto UIA
- **起動時エディション選択**: `RPA開発版AI付`を自動選択

### 2.2 UI要素一覧

**シナリオエディター:**
| ボタン | automation_id | 用途 |
|--------|---------------|------|
| 実行 | `ButtonRun` | シナリオ実行 |
| 部分実行 | `PartlyRunButton` | 選択部分のみ実行 |
| 保存 | `Saving` | シナリオ保存 |
| 停止 | `StopButton` | 実行停止 |

**エラーダイアログ:**
| ボタン | automation_id | エラー種別 |
|--------|---------------|-----------|
| コピー | `CopyButton` | ビルドエラー |
| ファイル出力 | `ContactInfoOutputButton` | ランタイムエラー |
| 閉じる | `CloseButton` | 共通 |

### 2.3 実行状態の検出

| 状態 | ButtonRun.is_enabled() | StopButton.is_enabled() | check_error() |
|------|------------------------|-------------------------|---------------|
| アイドル | True | False | False |
| 実行中 | False | True | False |
| エラー表示中 | False | True | True |
| 完了 | True | False | False |

### 2.4 ★最重要★ 操作が効かない場合はダイアログが原因

- pywinautoで指示しても反応がない場合、何かしらのダイアログが表示されている
- 先にそのダイアログを処理（OK/閉じる等）しないと次に進めない
- 常にダイアログの存在を確認してから操作すること

### 2.5 「編集しますか」ダイアログの処理

RK-10で.rksファイルを開くと「編集しますか？」確認ダイアログが表示される。
このダイアログはpywinautoで要素を特定できないため、**pyautogui座標クリック**で処理。

```python
import pyautogui
import time

def handle_edit_dialog():
    """RK-10の「編集しますか」ダイアログで「はい(Y)」をクリック"""
    time.sleep(0.5)
    pyautogui.click(515, 340)  # 標準位置での座標（環境で調整）
```

---

## 3. Keyence C# API リファレンス

### 3.1 Excel操作

```csharp
// ファイルを開く
var excel = Keyence.ExcelActions.ExcelAction.OpenFileAndReturnPath(
    filePath, false, "", true, "", true, true);

// シート選択（名前）
Keyence.ExcelActions.ExcelAction.SelectSheet(
    Keyence.ExcelActions.SheetSelectionMode.Name, $@"{sheetName}", 1);

// セル値を取得
var value = Keyence.ExcelActions.ExcelAction.GetCellValue(
    Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, "B2",
    Keyence.ExcelActions.TableCellValueMode.String);

// セル書き込み
Keyence.ExcelActions.ExcelAction.WriteCell(
    Keyence.ExcelActions.RangeSpecificationMethod.Number,
    Keyence.ExcelActions.CellSelectionMethod.Specified,
    col, row, "",
    Keyence.ExcelActions.InputValueType.String, value,
    default, default, false, false);

// 保存して閉じる
Keyence.ExcelActions.ExcelAction.SaveFile("",
    Keyence.ExcelActions.PreservationMethod.Overwrite,
    Keyence.ExcelActions.SaveFileType.ExtensionCompliant);
Keyence.ExcelActions.ExcelAction.CloseFile();
```

### 3.2 日付変換

```csharp
// 日付→テキスト変換（フォーマット指定）
var dateStr = Keyence.TextActions.TextAction.ConvertFromDatetimeToText(
    dateVar, true, Keyence.TextActions.DateTimeFormat.ShortDate, $@"yyyyMM");

// よく使うフォーマット
// "yyyyMM"     → "202501"
// "yyyy.MM"    → "2025.01"
// "yyyy/MM/dd" → "2025/01/08"
```

### 3.3 Windows資格情報

```csharp
// パスワード取得（資格情報マネージャーから）
var password = Keyence.SystemActions.SystemAction.ReadPasswordFromCredential("資格情報名");
```

### 3.4 ファイル操作

```csharp
// 最新ファイル取得
var newestFile = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath(
    directory, $@"*.pdf", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

// ファイル存在チェック
var exists = Keyence.FileSystemActions.FileAction.Exists(filePath);
```

### 3.5 待機・ログ

```csharp
// 待機
Keyence.ThreadingActions.ThreadingAction.Wait(5d);

// ログ出力
Keyence.CommentActions.LogAction.OutputUserLog(message);
```

---

## 4. エラーパターン集

### エラー1: Excelシート名ハードコード
**症状:** 特定行で待機したまま停止
**エラー:** `インデックスが無効です。(DISP_E_BADINDEX)`
**原因:** シート名がハードコード
**解決:** 動的変数を使用 `$@"{string10}"`

### エラー2: 日付フォーマット不一致
**症状:** シート選択で失敗
**原因:** 変数フォーマットとシート名形式の不一致
**解決:** 正しいフォーマットに修正（yyyyMM等）

### エラー3: Excelファイル閉じ忘れ
**症状:** シナリオ終了後もExcelが開いたまま
**解決:** CloseFile()を追加

### エラー4: ZIP展開リトライループで停止
**症状:** ZIP展開で10回失敗して停止
**原因:** 前回実行時のファイルがロック中
**解決:** 作業フォルダクリーンアップ処理を追加

### エラー5: pywinauto操作が効かない
**症状:** ボタンクリック等が反応しない
**原因:** ダイアログが表示されている
**解決:** 先にダイアログを処理

### エラー6: ExternalResourceReader.GetResourceText が空
**症状:** `ConvertExcelToDataTable`で「表の抽出に失敗しました」
**原因:** `ExternalResourceReader.GetResourceText`の引数をコードで書き換えた
**解決:** **RK10 GUIで「表の抽出」ノードを再設定する必要あり**（手動修正不可）

---

## 5. 設定ファイルパターン

### 5.1 env.txt
```
PROD
```
または
```
LOCAL
```

### 5.2 RK10_config_*.xlsx 構造
| セル | 項目 | 例 |
|------|------|-----|
| B2 | ENV | PROD/LOCAL |
| B3 | ROOT_PATH | \\\\server\\share |
| B4 | INPUT_FILE | 入力ファイルパス |
| B5 | OUTPUT_FILE | 出力ファイルパス |

### 5.3 環境判定パターン（C#）

```csharp
// env.txt読み込み
var Env = Keyence.FileSystemActions.FileAction.ReadAllText($@"..\config\env.txt", ...);
Env = Keyence.TextActions.TextAction.TrimText(Env, ...);
Env = Keyence.TextActions.TextAction.ChangeTextCase(Env, ...UpperCase);

// 環境に応じた設定ファイル選択
var ConfigPath = "";
if (Keyence.ComparisonActions.ComparisonAction.CompareString(Env, $@"PROD", ...Equal, false))
{
    ConfigPath = "..\\config\\RK10_config_PROD.xlsx";
}
else
{
    ConfigPath = "..\\config\\RK10_config_LOCAL.xlsx";
}
```

---

## 6. RK10とPython連携

### 6.1 シナリオ構成（推奨）

```
1. env.txt読み込み（PROD/LOCAL判定）
2. 設定ファイル読み込み（RK10_config_*.xlsx）
3. Python呼び出し（main.py）
   - 引数: --env PROD --payment-date 末日 --company-code 300
4. 処理結果確認（エラー時は通知）
5. 完了通知
```

### 6.2 Python呼び出し例（C#）

```csharp
var pythonPath = @"C:\Python311\python.exe";
var scriptPath = ROBOT_DIR + @"\tools\main.py";
var args = $"--env {Env} --payment-date 末日 --company-code 300";

Keyence.SystemActions.SystemAction.ExecuteApplication(
    pythonPath, $"\"{scriptPath}\" {args}", "", true, 600);
```

---

## 7. 設計思想

### 「人間の判断を代替する」のではなく「人間が判断しやすい状態を作る」

**ロボットの役割:**
1. データを集める（スクレイピング）
2. パターンに基づいて分類・提案する
3. 人間が確認しやすいレポートを出力する
4. 確認済みデータを転記する

**人間の役割:**
1. 科目の最終確認・修正
2. 按分が必要な明細の判断と分割
3. 例外ケースの処理

---

## 8. 実践パターン集（シナリオ43完成版より抽出）

### 8.1 リトライパターン（ZIP展開/ファイルコピー）

```csharp
var UnzipOK = false;
foreach (var カウンター1 in Keyence.Activities.Samples.RepeatExtensions.RepeatCount(10))
{
    try
    {
        Keyence.FileSystemActions.CompressionAction.UncompressFile(zipPath, destDir, true, "", ShiftJis);
        UnzipOK = true;
        break;
    }
    catch (System.Exception エラー1) when (エラー1 is not Keyence.Activities.Exceptions.ForceExitException)
    {
        Keyence.ThreadingActions.ThreadingAction.Wait(2d);
    }
}
if (Keyence.Activities.Samples.VariableAction.InvertBool(UnzipOK))
{
    Keyence.CommentActions.LogAction.OutputUserLog("ZIP展開に10回失敗");
    return;  // シナリオ終了
}
```

**ポイント:**
- `RepeatCount(N)` でN回ループ
- 成功時は `break` で抜ける
- `ForceExitException` は再throw（シナリオ強制終了用）
- 失敗時は `return` でシナリオ終了

### 8.2 Excel「合計」行検索パターン

```csharp
// J列で「合計」を検索
var list2 = Keyence.ExcelActions.ExcelAction.GetMatchValueList(A1, 1, 1, 1, 1, "j:j", "合計", false);
cellJ = Keyence.ListActions.ListAction.GetItem(list2, 0);  // "$J$123" 形式

// "$J$123" → "123" に変換
cellJ = Keyence.TextActions.TextAction.ReplaceText(cellJ, "$", false, false, "", false, false);
var rowStr = Keyence.TextActions.TextAction.ReplaceText(cellJ, "J", false, false, "", false, false);
foundRow = Keyence.NumericActions.NumericAction.ConvertFromObjectToInteger(rowStr);
```

### 8.3 部門別金額取得（下から上に走査）

```csharp
var 金額管理 = -1;  // -1は未取得
var foundCount = 0;
var row = foundRow;
row += -1;

foreach (var loop1 in RepeatCount(50))
{
    var rowStr = ConvertFromObjectToText(row);
    cellJ = Concat("J", rowStr);
    合計ラベル = GetCellValue(A1, 1, 1, cellJ, String);

    if (CompareString(合計ラベル, "合計", NotEqual, false))
        break;  // 「合計」以外に到達したら終了

    // 部門名取得
    cellS = Concat("S", rowStr);
    部門名 = GetCellValue(A1, 1, 1, cellS, String);

    // 金額取得
    cellQ = Concat("Q", rowStr);
    金額str = GetCellValue(A1, 1, 1, cellQ, String);
    金額str = ReplaceText(金額str, ",", false, false, "", false, false);
    金額 = ConvertFromObjectToInteger(金額str);

    // 部門別に振り分け
    if (CompareDouble(金額管理, -1d, Equal) && CompareString(部門名, "管理", Equal, false))
    {
        金額管理 = 金額;
        foundCount += 1;
    }
    // ... 他の部門も同様

    if (CompareDouble(foundCount, 5d, Equal))
        break;  // すべて取得したら終了
    else
        row += -1;  // 1行上へ
}
```

### 8.4 PDF座標指定テキスト抽出

```csharp
// ExtractText(pdfPath, pageNum, x, y, width, height)
var 発行日 = Keyence.PdfActions.PdfActions.ExtractText(pdfPath, 1, 143, 308, 141, 13);
var 請求金額 = Keyence.PdfActions.PdfActions.ExtractText(pdfPath, 1, 115, 275, 189, 18);
```

**注意:** 座標はピクセル単位。PDFレイアウト変更時は要修正

### 8.5 HTMLメール送信（ハイパーリンク付き）

```csharp
Keyence.OutlookActions.OutlookAction.SendHtmlMail(
    "",                    // 送信者（空=デフォルト）
    mailAddress,           // 宛先
    "",                    // CC
    "",                    // BCC
    subject,               // 件名
    attachmentPath,        // 添付ファイル
    false,                 // 下書き保存
    new List<HtmlMailBodyContent> {
        HtmlBodyContentCreator.CreateString("プロセスが完了しました。\n以下リンクからご確認ください"),
        HtmlBodyContentCreator.CreateHyperlink("楽楽精算　ログイン", "https://...")
    },
    ""                     // 署名
);
Keyence.OutlookActions.OutlookAction.CloseOutlook();
```

---

## 9. 参照

- **詳細スキル**: `repo:/external-repos/my-claude-skills/rk10-scenario/skill.md`
- **各ロボットフォルダ**: `C:\ProgramData\RK10\Robots\`
- **シナリオ43完成版**: `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版.rks`
