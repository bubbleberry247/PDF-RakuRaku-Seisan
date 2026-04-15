---
name: rpa-patterns
description: Use when creating new RPA scenarios — retry loops, JIDOKA verification, 冪等性 log, DOM smoke test, iframe operations, HTMLメール通知, Excel automation patterns
---

# RPA 共通パターン集（実戦検証済み）

## 概要
複数のRPAシナリオから抽出した再利用可能な実装パターン。
新規シナリオ作成時に「同じ失敗を繰り返さない」ための定石集。

**ルール**: このスキルのパターンを使う場合は**参照**する。シナリオ固有スキルへの**複製禁止**。

## キーワード
シナリオ作成, ロボット作成, 新規シナリオ, 新しいシナリオ, パターン, 前例, テンプレ, 書き方, 使えるスキル探して, スキル探して, 使えるスキル

---

## パターン一覧

| # | パターン名 | 用途 | 出典 |
|---|-----------|------|------|
| 1 | リトライループ | ファイル操作の一時失敗対策 | S43 |
| 2 | Excel「合計」行検索 | 可変位置の集計行を特定 | S43 |
| 3 | 部門別金額取得（下→上走査） | 集計行から部門別に逆走査 | S43 |
| 4 | PDF座標テキスト抽出 | PDF固定位置からデータ取得 | S43 |
| 5 | xlwings vs openpyxl判定 | Excel操作ライブラリ選択 | S55 |
| 6 | 原本保護（docs→workコピー） | 原本ファイル破損防止 | S55 |
| 7 | JIDOKA検証（書込後読み返し） | 書込データの自動検証 | S55 |
| 8 | 冪等性ログ（二重処理防止） | 再実行安全の確保 | S55 |
| 9 | DOM Smoke Test | スクレイピング前のUI検証 | S55 |
| 10 | iframe/frame操作 | SaaS iframe構造の対処 | S55 |
| 11 | HTMLメール通知 | 処理結果の即時通知 | S43/S55 |
| 12 | 銀行休業日対応 | 支払日の営業日調整 | S55 |

---

## 1. リトライループ（C# / RK10）

ファイル操作・ZIP展開など一時的に失敗する処理のリトライ。

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

---

## 2. Excel「合計」行検索（C# / RK10）

可変位置の「合計」行を動的に探す。

```csharp
// J列で「合計」を検索
var list2 = Keyence.ExcelActions.ExcelAction.GetMatchValueList(A1, 1, 1, 1, 1, "j:j", "合計", false);
cellJ = Keyence.ListActions.ListAction.GetItem(list2, 0);  // "$J$123" 形式

// "$J$123" → "123" に変換
cellJ = Keyence.TextActions.TextAction.ReplaceText(cellJ, "$", false, false, "", false, false);
var rowStr = Keyence.TextActions.TextAction.ReplaceText(cellJ, "J", false, false, "", false, false);
foundRow = Keyence.NumericActions.NumericAction.ConvertFromObjectToInteger(rowStr);
```

**使い所**: 行数が毎月変わるExcelで集計行を見つけたいとき。列名を変えればどのExcelにも使える。

---

## 3. 部門別金額取得 — 下→上走査（C# / RK10）

「合計」行から上に向かって部門名と金額を取得する。

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

    // 部門名取得（列は案件に合わせて変更）
    cellS = Concat("S", rowStr);
    部門名 = GetCellValue(A1, 1, 1, cellS, String);

    // 金額取得（列は案件に合わせて変更）
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

**カスタマイズ**: 列名（J/S/Q）と部門名を案件に合わせて変更するだけ。

---

## 4. PDF座標テキスト抽出（C# / RK10）

PDF内の固定位置からテキストを取得する。

```csharp
// ExtractText(pdfPath, pageNum, x, y, width, height)
var 発行日 = Keyence.PdfActions.PdfActions.ExtractText(pdfPath, 1, 143, 308, 141, 13);
var 請求金額 = Keyence.PdfActions.PdfActions.ExtractText(pdfPath, 1, 115, 275, 189, 18);
```

**注意:** 座標はピクセル単位。PDFレイアウト変更時は要修正。

---

## 5. xlwings vs openpyxl 判定表（Python）

| 状況 | 推奨 | 理由 |
|------|------|------|
| 新規Excel作成 | openpyxl | 軽量、COM不要 |
| 単純な読み書き（数シート） | openpyxl | 十分対応可能 |
| **複雑なExcel（多シート・マージセル・数式）** | **xlwings** | openpyxlはload→saveで破損する |
| 数式を保持したまま値を書き込み | xlwings | openpyxlは数式を文字列として扱いがち |

**実績**: 78シート×マージセルのExcelで、openpyxlは2,734箇所の差分。xlwingsは差分0。

```python
import xlwings as xw

app = xw.App(visible=False)
try:
    wb = app.books.open(excel_path)
    ws = wb.sheets["シート名"]

    val = ws.range("I14").value
    ws.range("I14").value = 10000

    # シートコピー
    template_ws = wb.sheets["テンプレ"]
    template_ws.api.Copy(After=wb.sheets[-1].api)
    new_ws = wb.sheets[-1]
    new_ws.name = "新シート名"

    wb.save()
finally:
    wb.close()
    app.quit()
```

---

## 6. 原本保護パターン（Python）

**原則**: 原本は絶対に直接編集しない。コピーして作業する。

```
docs\原本.xlsx  ──(コピー)──→  work\作業用_YYYYMMDD.xlsx
（read-only）                  （RPAが書き込む対象）
```

```python
import shutil, os
from datetime import datetime

ORIGINAL = r"docs\原本.xlsx"
WORK_DIR = r"work"
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
work_path = os.path.join(WORK_DIR, f"RPA_{timestamp}.xlsx")
shutil.copy2(ORIGINAL, work_path)
# 以降、work_pathに対してのみ書き込む
```

---

## 7. JIDOKA検証 — 書込後読み返し（Python）

**TPS自働化**: 書いた値を読み返して一致確認。不一致なら停止＋通知。

```python
def verify_writes(ws, written_records: list[dict]) -> list[dict]:
    """書込後に全件読み返して検証"""
    mismatches = []
    for rec in written_records:
        row = rec["row"]
        expected = rec["amount"]
        actual = ws.range((row, 9)).value  # 書込列

        if actual != expected:
            mismatches.append({
                "row": row, "expected": expected,
                "actual": actual, "supplier": rec["supplier"]
            })
            ws.range((row, 1)).color = (255, 200, 200)  # 赤マーク

    if mismatches:
        raise JidokaStopError(f"JIDOKA-STOP: {len(mismatches)}件の不一致")
    return mismatches
```

**使い所**: Excel書込後に毎回実行。列番号はシナリオに合わせて変更。

---

## 8. 冪等性ログ — 二重処理防止（Python）

**再実行安全**: 処理済みレコードをログに記録し、同じデータを二度書かない。

```python
import csv, os

LOG_PATH = "log/processed.csv"

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

**運用注意**: 再実行時はログをバックアップ＆クリアすること（残存ログ→全件スキップ問題の実績あり）。

---

## 9. DOM Smoke Test — スクレイピング前検証（Python）

**TPSポカヨケ**: スクレイピング前にテーブルヘッダーを検証。SaaS UI変更を即検知。

```python
EXPECTED_HEADERS = ["No.", "申請者", "件名", "状態", "金額"]  # 案件に合わせて変更

def smoke_test_dom(page) -> None:
    headers = page.query_selector_all("table th")
    actual = [h.inner_text().strip() for h in headers]

    for i, (expected, got) in enumerate(zip(EXPECTED_HEADERS, actual)):
        if expected != got:
            raise DOMStructureError(
                f"Column {i}: expected '{expected}', got '{got}'. "
                "SaaSのUI変更の可能性あり。"
            )
```

---

## 10. iframe/frame操作（Python / Playwright）

SaaS（楽楽精算等）はiframe構造。`page.query_selector()` では要素が見つからない。

```python
# Bad: ページ直接アクセス（要素が見つからない）
element = page.query_selector("table.data")  # → None

# Good: frame経由でアクセス
for frame in page.frames:
    element = frame.query_selector("table.data")
    if element:
        break

# Good: 直接URLナビゲーション（frame内クリックを避ける）
page.goto("https://app.example.com/specific/page/url")
```

---

## 11. HTMLメール通知（C# / RK10 & Python）

**TPSアンドン**: 処理結果を担当者に即時通知。ハイパーリンク付き。

### C# / RK10版
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
        HtmlBodyContentCreator.CreateString("プロセスが完了しました。"),
        HtmlBodyContentCreator.CreateHyperlink("確認リンク", "https://...")
    },
    ""                     // 署名
);
Keyence.OutlookActions.OutlookAction.CloseOutlook();
```

### Python版
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

**エラー時の必須ルール**:
- `--no-mail` オプションでもエラー通知は必ず送信する
- 件名に「★エラー発生★」を明示
- traceback全文を含める

---

## 12. 銀行休業日対応（Python）

末日支払で12/31（年末年始）は銀行休業日。前営業日に繰り上げ。

```python
from datetime import date, timedelta
import calendar

BANK_HOLIDAYS = {12: {31}}  # 月: {休業日set}

def get_actual_payment_date(year: int, month: int, day_type: str) -> date:
    """支払グループ(15日/25日/末日)から実際の支払日を算出"""
    if day_type == "末日":
        last_day = calendar.monthrange(year, month)[1]
        d = date(year, month, last_day)
    elif day_type == "25日":
        d = date(year, month, 25)
    elif day_type == "15日":
        d = date(year, month, 15)
    else:
        raise ValueError(f"Unknown day_type: {day_type}")

    # 銀行休業日チェック（土日 + 年末年始）
    while d.weekday() >= 5 or d.day in BANK_HOLIDAYS.get(d.month, set()):
        d -= timedelta(days=1)
    return d
```

---

## このスキルの使い方

1. 新規シナリオ作成前に一覧を確認
2. 必要なパターンを**参照**してシナリオに適用（コピペ→パラメータ変更）
3. 新しいパターンを発見したら、まずシナリオ固有スキルに追加
4. 別シナリオでも使われたら、このスキルに**昇格**
