# Snippets: Keyence C# API

## 概要
RK10シナリオ（Program.cs）で使用するKeyence C# APIのスニペット集

---

## 1. ファイル操作

### ファイル読み込み

```csharp
// テキストファイル読み込み
var content = Keyence.FileSystemActions.FileAction.ReadAllText(
    $@"C:\path\to\file.txt",
    Keyence.FileSystemActions.AutoEncoding.Auto);
```

### ファイル存在確認

```csharp
var exists = Keyence.FileSystemActions.FileAction.Exists($@"C:\path\to\file.txt");
if (exists)
{
    // ファイルが存在する場合の処理
}
```

### 最新ファイル取得

```csharp
var newestFile = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath(
    $@"C:\Downloads",           // ディレクトリ
    $@"*.zip",                  // パターン
    Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(),
    true);                       // サブフォルダ含む
```

### ファイルコピー

```csharp
Keyence.FileSystemActions.FileAction.CopyFileDirectory(
    $@"C:\source\file.xlsx",    // コピー元
    $@"C:\dest\file.xlsx",      // コピー先
    true);                       // 上書き
```

### ディレクトリ作成

```csharp
Keyence.FileSystemActions.DirectoryAction.CreateDirectory($@"C:\new\folder");
```

### ディレクトリ削除

```csharp
Keyence.FileSystemActions.DirectoryAction.DeleteDirectory(
    $@"C:\folder\to\delete",
    true);  // 再帰的に削除
```

### ZIP解凍

```csharp
Keyence.FileSystemActions.FileAction.UncompressFile(
    $@"C:\file.zip",            // ZIPファイル
    $@"C:\output\folder",       // 出力先
    true,                        // 既存ファイル上書き
    "",                          // パスワード
    Keyence.FileSystemActions.CompressionEncoding.ShiftJis);
```

---

## 2. Excel操作

### ファイルを開く

```csharp
var excelPath = Keyence.ExcelActions.ExcelAction.OpenFileAndReturnPath(
    $@"C:\file.xlsx",
    false,      // 読み取り専用
    "",         // パスワード
    true,       // 表示
    "",         // 書き込みパスワード
    true,       // マクロ有効
    true);      // アラート抑制
```

### ファイルを閉じる

```csharp
Keyence.ExcelActions.ExcelAction.CloseFile();
```

### シート選択（名前指定）

```csharp
Keyence.ExcelActions.ExcelAction.SelectSheet(
    Keyence.ExcelActions.SheetSelectionMode.Name,
    $@"2025.01",    // シート名
    1);              // インデックス（Name指定時は無視）
```

### シート選択（インデックス指定）

```csharp
Keyence.ExcelActions.ExcelAction.SelectSheet(
    Keyence.ExcelActions.SheetSelectionMode.Index,
    "",              // シート名（Index指定時は無視）
    3);              // 3番目のシート
```

### セル値取得（A1形式）

```csharp
var value = Keyence.ExcelActions.ExcelAction.GetCellValue(
    Keyence.ExcelActions.RangeSpecificationMethod.A1,
    1, 1,           // 行・列（Number指定時に使用）
    "B5",           // セル番地（A1形式）
    Keyence.ExcelActions.TableCellValueMode.String);
```

### セル値取得（行列番号指定）

```csharp
var value = Keyence.ExcelActions.ExcelAction.GetCellValue(
    Keyence.ExcelActions.RangeSpecificationMethod.Number,
    5, 2,           // 5行目2列目
    "",             // セル番地（Number指定時は無視）
    Keyence.ExcelActions.TableCellValueMode.String);
```

### セル書き込み

```csharp
Keyence.ExcelActions.ExcelAction.WriteCell(
    Keyence.ExcelActions.RangeSpecificationMethod.Number,
    Keyence.ExcelActions.CellSelectionMethod.Specified,
    2, 5,           // B5（2列目、5行目）
    "",             // セル名（Specified時は無視）
    Keyence.ExcelActions.InputValueType.String,
    $@"書き込む値",
    default,        // 数式タイプ
    default,        // 参照スタイル
    false,          // 行・列固定
    false);         // 絶対参照
```

### 検索（GetMatchValueList）

```csharp
// 戻り値は「$列$行」形式（例: "$J$123"）
var list = Keyence.ExcelActions.ExcelAction.GetMatchValueList(
    Keyence.ExcelActions.RangeSpecificationMethod.A1,
    1, 1, 1, 1,     // 範囲（Number指定時に使用）
    "J:J",          // 検索範囲（A1形式）
    "合計",         // 検索文字列
    false);         // 完全一致

var cell = Keyence.BasicActions.ListAction.GetItem(list, 0);
// cell = "$J$123"
```

### 保存

```csharp
Keyence.ExcelActions.ExcelAction.SaveFile(
    "",             // 別名保存パス（空なら上書き）
    Keyence.ExcelActions.PreservationMethod.Overwrite,
    Keyence.ExcelActions.SaveFileType.ExtensionCompliant);
```

### 別名保存

```csharp
Keyence.ExcelActions.ExcelAction.SaveFile(
    $@"C:\new\path\file.xlsx",
    Keyence.ExcelActions.PreservationMethod.OtherName,
    Keyence.ExcelActions.SaveFileType.ExtensionCompliant);
```

---

## 3. テキスト操作

### 文字列結合

```csharp
var result = Keyence.TextActions.TextAction.Concat("Hello", " ", "World");
// result = "Hello World"
```

### 文字列置換

```csharp
var result = Keyence.TextActions.TextAction.ReplaceText(
    "Hello World",  // 元の文字列
    "World",        // 検索文字列
    false,          // 正規表現
    false,          // 大文字小文字区別
    "RK10",         // 置換文字列
    false,          // 最初の一致のみ
    false);         // 空白を無視
// result = "Hello RK10"
```

### 部分文字列取得

```csharp
var result = Keyence.TextActions.TextAction.GetSubText(
    "20250120",
    Keyence.TextActions.TextPositionMode.CharacterPosition,
    0,              // 開始位置
    Keyence.TextActions.TextLengthType.NumberOfChars,
    6);             // 文字数
// result = "202501"
```

### 文字列分割

```csharp
var list = Keyence.TextActions.TextAction.SplitText(
    "a_b_c_d",
    true,           // 空要素を削除
    Keyence.TextActions.DelimiterType.Space,  // ★注意: Specifiedは使えない
    1,              // 空白数（Space指定時）
    "_",            // 区切り文字（参考用、実際はSpaceで分割）
    false);         // 正規表現

// ★カスタム区切り文字を使うには、先にスペースに置換
var replaced = Keyence.TextActions.TextAction.ReplaceText(
    "a_b_c_d", "_", false, false, " ", false, false);
var list = Keyence.TextActions.TextAction.SplitText(
    replaced, true, Keyence.TextActions.DelimiterType.Space, 1, " ", false);
```

### トリム

```csharp
var result = Keyence.TextActions.TextAction.TrimText(
    "  Hello  ",
    Keyence.TextActions.TrimTextPosition.Both);
// result = "Hello"
```

### 大文字/小文字変換

```csharp
var upper = Keyence.TextActions.TextAction.ChangeTextCase(
    "hello",
    Keyence.TextActions.CharacterCaseType.UpperCase);
// upper = "HELLO"
```

---

## 4. 日付操作

### 日付→テキスト変換

```csharp
var dateStr = Keyence.TextActions.TextAction.ConvertFromDatetimeToText(
    dateVar,
    true,           // カスタムフォーマット
    Keyence.TextActions.DateTimeFormat.ShortDate,
    $@"yyyyMM");    // フォーマット
// dateStr = "202501"
```

### テキスト→日付変換

```csharp
var dateObj = Keyence.ConvertActions.ConvertAction.ConvertFromTextToDatetime(
    "20250120",
    true,           // カスタムフォーマット
    $@"yyyyMMdd");
```

### 日付加算

```csharp
var nextMonth = Keyence.DateTimeActions.DateTimeAction.AddDatetime(
    dateObj,
    1,              // 加算値
    Keyence.DateTimeActions.DateTimeUnit.Month);
```

### 現在日時取得

```csharp
var now = Keyence.DateTimeActions.DateTimeAction.GetCurrentDatetime();
```

---

## 5. 比較・条件

### 文字列比較

```csharp
var isEqual = Keyence.ComparisonActions.ComparisonAction.CompareString(
    value1,
    value2,
    Keyence.ComparisonActions.CompareStringMethod.Equal,
    false);         // 大文字小文字区別

if (isEqual)
{
    // 一致する場合
}
```

### 数値比較

```csharp
var isGreater = Keyence.ComparisonActions.ComparisonAction.CompareDouble(
    value1,
    value2,
    Keyence.ComparisonActions.CompareDoubleMethod.Greater);
```

### 論理反転

```csharp
var notValue = Keyence.ComparisonActions.ComparisonAction.InvertBool(boolValue);
```

---

## 6. ループ・リスト

### RepeatCount（回数指定ループ）

```csharp
foreach (var i in Keyence.LoopActions.LoopAction.RepeatCount(10))
{
    // 10回繰り返し
}
```

### リスト要素取得

```csharp
var item = Keyence.BasicActions.ListAction.GetItem(list, 0);  // 最初の要素
```

### リスト要素数

```csharp
var count = Keyence.BasicActions.ListAction.GetCount(list);
```

---

## 7. 型変換

### オブジェクト→文字列

```csharp
var str = Keyence.ConvertActions.ConvertAction.ConvertFromObjectToText(obj);
```

### オブジェクト→整数

```csharp
var num = Keyence.ConvertActions.ConvertAction.ConvertFromObjectToInteger(obj);
```

### オブジェクト→小数

```csharp
var dbl = Keyence.ConvertActions.ConvertAction.ConvertFromObjectToDouble(obj);
```

---

## 8. 待機

### 秒数待機

```csharp
Keyence.ThreadingActions.ThreadingAction.Wait(5d);  // 5秒待機
// 注意: 値には「d」サフィックス（double型）が必要
```

---

## 9. ログ・コメント

### ユーザーログ出力

```csharp
Keyence.CommentActions.LogAction.OutputUserLog($@"処理開始: {dateStr}");
```

---

## 10. 認証

### Windows資格情報からパスワード取得

```csharp
var password = Keyence.SystemActions.SystemAction.ReadPasswordFromCredential(
    $@"RK10_SystemLogin");
```

---

## 11. メール送信

### HTMLメール送信

```csharp
Keyence.MailActions.MailAction.SendHtmlMail(
    "",                         // 差出人
    mailAddress,                // 宛先
    "",                         // CC
    "",                         // BCC
    $@"件名",
    attachmentPath,             // 添付ファイル
    false,                      // 開封確認
    new List<HtmlMailBodyContent> {
        Keyence.MailActions.HtmlBodyContentCreator.CreateString("本文テキスト"),
        Keyence.MailActions.HtmlBodyContentCreator.CreateHyperlink("リンク表示名", "https://...")
    },
    "");                        // 返信先
```

---

## 12. 外部アプリケーション実行

### Python実行

```csharp
Keyence.SystemActions.SystemAction.ExecuteApplication(
    $@"C:\Python311\python.exe",
    $@"""C:\path\to\script.py"" --arg1 value1",
    "",             // 作業ディレクトリ
    true,           // 完了待機
    600);           // タイムアウト秒
```

---

## 13. 変数宣言の注意

### 日本語変数名（推奨）

```csharp
var 処理成功 = false;
var 金額合計 = 0d;
var エラーメッセージ = "";
```

### Keyence固有型のサフィックス

| 型 | サフィックス | 例 |
|----|-------------|-----|
| double | d | `5d`, `-1d` |
| float | f | `1.5f` |
| long | L | `1000L` |

---

## 14. try-catch パターン

### ForceExitExceptionを除外するパターン

```csharp
try
{
    // 処理
}
catch (System.Exception エラー) when (エラー is not ForceExitException)
{
    // ForceExitException以外のエラーを処理
    // ForceExitExceptionは再throwされる（シナリオ強制終了用）
}
```
