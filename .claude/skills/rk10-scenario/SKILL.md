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

## 9. Python連携パターン集（シナリオ55より抽出）

### 9.1 xlwings vs openpyxl の使い分け（★重要）

| 状況 | 推奨ライブラリ | 理由 |
|------|---------------|------|
| 新規Excel作成 | openpyxl | 軽量、COM不要 |
| 単純なExcel読み書き（数シート） | openpyxl | 十分対応可能 |
| **複雑なExcel（多シート・マージセル・数式）** | **xlwings (COM)** | openpyxlはload→saveで破損する |
| 数式を保持したまま値を書き込み | xlwings (COM) | openpyxlは数式を文字列として扱いがち |

**実績**: 78シート×マージセルの振込伝票Excelで、openpyxlは2,734箇所の差分が発生。xlwingsは差分0。

```python
# xlwings COMによるExcel操作の基本
import xlwings as xw

app = xw.App(visible=False)
try:
    wb = app.books.open(excel_path)
    ws = wb.sheets["シート名"]

    # 値の読み書き（数式は保持される）
    val = ws.range("I14").value
    ws.range("I14").value = 10000

    # シートコピー（テンプレートから新シート作成）
    template_ws = wb.sheets["RPAテンプレ"]
    template_ws.api.Copy(After=wb.sheets[-1].api)
    new_ws = wb.sheets[-1]
    new_ws.name = "RPA_R7.10月分"

    wb.save()
finally:
    wb.close()
    app.quit()
```

### 9.2 原本保護パターン（Source Excel Copy Mode）

**原則**: 原本は絶対に直接編集しない。コピーして作業する。

```
docs\原本.xlsx  ──(コピー)──→  work\作業用_YYYYMMDD.xlsx
（read-only）                  （RPAが書き込む対象）
```

```python
import shutil
from datetime import datetime

ORIGINAL = r"docs\原本.xlsx"
WORK_DIR = r"work"
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
work_path = os.path.join(WORK_DIR, f"55_RPA1_{timestamp}.xlsx")
shutil.copy2(ORIGINAL, work_path)
# 以降、work_pathに対してのみ書き込む
```

### 9.3 JIDOKA検証パターン（書込後の読み返し検証）

**TPS自働化**: 書いた値を読み返して一致確認。不一致ならマーク＋停止＋通知。

```python
def verify_writes(ws, written_records: list[dict]) -> list[dict]:
    """書込後に全件読み返して検証"""
    mismatches = []
    for rec in written_records:
        row = rec["row"]
        expected_amount = rec["amount"]
        actual = ws.range((row, 9)).value  # I列

        if actual != expected_amount:
            mismatches.append({
                "row": row,
                "expected": expected_amount,
                "actual": actual,
                "supplier": rec["supplier"]
            })
            # 赤マーク（不完全印）
            ws.range((row, 1)).color = (255, 200, 200)

    if mismatches:
        raise JidokaStopError(f"JIDOKA-STOP: {len(mismatches)}件の不一致")

    return mismatches
```

### 9.4 冪等性ログパターン（二重転記防止）

**再実行安全**: 処理済みレコードをログに記録し、同じデータを二度書かない。

```python
import csv, os

LOG_PATH = "log/v2_processed_LOCAL_matsu.csv"

def load_processed_keys() -> set:
    if not os.path.exists(LOG_PATH):
        return set()
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        return {row["key"] for row in csv.DictReader(f)}

def mark_processed(record: dict):
    exists = os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["key", "supplier", "amount", "timestamp"])
        if not exists:
            writer.writeheader()
        writer.writerow(record)
```

**運用注意**: 再実行時はログをバックアップ＆クリアすること（残存ログ→全件スキップ問題の実績あり）

### 9.5 DOM Smoke Test（スクレイピング前のポカヨケ）

**TPS ポカヨケ**: スクレイピング前にテーブルヘッダーを検証。UI変更を即検知。

```python
EXPECTED_HEADERS = ["No.", "申請者", "件名", "状態", "金額", ...]

def smoke_test_dom(page) -> None:
    headers = page.query_selector_all("table th")
    actual = [h.inner_text().strip() for h in headers]

    for i, (expected, got) in enumerate(zip(EXPECTED_HEADERS, actual)):
        if expected != got:
            raise DOMStructureError(
                f"Column {i}: expected '{expected}', got '{got}'. "
                "楽楽精算のUI変更の可能性あり。"
            )
```

### 9.6 Playwright iframe/frame操作（SaaS対応）

楽楽精算などのSaaSはiframe/frame構造を使用。`page.query_selector()`では要素が見つからない。

```python
# Bad: ページ直接アクセス（要素が見つからない）
element = page.query_selector("table.data")  # → None

# Good: frame経由でアクセス
for frame in page.frames:
    element = frame.query_selector("table.data")
    if element:
        break

# Good: 直接URLナビゲーション（frame内リンクをクリックする代わり）
page.goto("https://app.rakurakuseisan.jp/specific/page/url")
```

### 9.7 HTMLメール通知（Python + Outlook COM）

**TPS アンドン**: 処理結果を担当者に即時通知。ハイパーリンク付き。

```python
import win32com.client

def send_notification(subject: str, body_html: str, to: str, file_path: str = None):
    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)
    mail.To = to
    mail.Subject = subject
    mail.HTMLBody = f"""
    <html><body>
    <p>{body_html}</p>
    <p>出力ファイル: <a href="file:///{file_path}">{file_path}</a></p>
    </body></html>
    """
    mail.Send()
```

**エラー時は必ず通知**（`--no-mail`オプションでもエラーは送信）:
- 件名に「★エラー発生★」を明示
- traceback全文を含める
- 開発者CC: `karimistk@gmail.com`

### 9.8 テンプレートスロット検索（既存行の再利用）

Excel原本に既存の空行（業者名だけ登録、金額=0）がある場合、新規行挿入より既存スロットを優先活用。

```python
def find_supplier_row(supplier_name: str, cache: dict) -> int | None:
    """3段階マッチング: 完全一致 → 変異体 → 部分一致"""
    normalized = normalize_name(supplier_name)

    # Pass 1: 完全一致（正規化後）
    if normalized in cache:
        return get_unused_row(cache[normalized])

    # Pass 2: 変異体マッチ（㈱↔株式会社、全角↔半角）
    for variant in generate_variants(normalized):
        if variant in cache:
            return get_unused_row(cache[variant])

    # Pass 3: 部分一致（3文字以上）
    if len(normalized) >= 3:
        for key in cache:
            if normalized in key or key in normalized:
                return get_unused_row(cache[key])

    return None  # 未登録 → 新規行挿入 or A=6799（赤字）
```

### 9.9 銀行休業日対応（支払日の自動判定）

末日支払の場合、年末年始（12/31）は銀行休業日のため前営業日（12/30等）に繰り上げ。

```python
from datetime import date

BANK_HOLIDAYS = {12: {31}}  # 月: {休業日set}

def get_actual_payment_date(year: int, month: int, day_type: str) -> date:
    """支払グループ(15日/25日/末日)から実際の支払日を算出"""
    if day_type == "末日":
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        d = date(year, month, last_day)
        # 銀行休業日チェック（土日 + 年末年始）
        while d.weekday() >= 5 or d.day in BANK_HOLIDAYS.get(d.month, set()):
            d -= timedelta(days=1)
        return d
```

---

## 10. フォルダ構成規約（全シナリオ共通）

```
C:\ProgramData\RK10\Robots\{番号} {シナリオ名}\
├── config\          設定ファイル（env.txt, RK10_config_*.xlsx, マスタCSV/JSON）
├── docs\            原本・テンプレート（★read-only、作業禁止）
├── work\            作業出力（生成ファイル、中間ファイル）
├── log\             実行ログ、冪等性ログ
├── tools\           Pythonスクリプト（正本のみ）
├── data\            入力データ（スクレイピング結果CSV等）
└── scenario\        .rksファイル
```

**重要**: `docs\` = 原本保管場所（書き換え禁止）、`work\` = 作業出力場所

---

## 11. 参照

- **詳細スキル**: `repo:/external-repos/my-claude-skills/rk10-scenario/skill.md`
- **各ロボットフォルダ**: `C:\ProgramData\RK10\Robots\`
- **シナリオ43完成版**: `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\４３一般経費_日本情報サービス協同組合(ETC)明細の作成_完成版.rks`
