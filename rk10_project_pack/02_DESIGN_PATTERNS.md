# RK10 設計パターン集

## 1. 環境切替パターン

### 1.1 env.txt + RK10_config_{ENV}.xlsx

**構造:**
```
config/
├── env.txt                    # "PROD" or "LOCAL"
├── RK10_config_PROD.xlsx      # 本番環境設定
└── RK10_config_LOCAL.xlsx     # ローカル環境設定
```

**C#実装:**
```csharp
// env.txt読み込み→Trim→UpperCase
var Env = ReadAllText("..\\config\\env.txt", Auto);
Env = TrimText(Env, Both);
Env = ChangeTextCase(Env, UpperCase);

// 環境に応じた設定ファイル選択
if (CompareString(Env, "PROD", Equal, false))
    ConfigPath = "..\\config\\RK10_config_PROD.xlsx";
else if (CompareString(Env, "PROD", NotEqual, false))
    ConfigPath = "..\\config\\RK10_config_LOCAL.xlsx";
```

**設定ファイル構造（RK10_config_*.xlsx）:**
| セル | 項目 | 例 |
|------|------|-----|
| B2 | ENV | PROD/LOCAL |
| B3 | ROOT_PATH | \\\\server\\share |
| B4-B24 | 各種パス・設定 | 入出力パス等 |

---

## 2. リトライパターン

### 2.1 RepeatCount + try-catch + break

**標準形:**
```csharp
var 処理成功 = false;
foreach (var カウンター1 in RepeatCount(10))
{
    try
    {
        // 処理本体
        UncompressFile(string11, 解凍フォルダ, true, "", ShiftJis);
        処理成功 = true;
        break;  // 成功したらループ脱出
    }
    catch (System.Exception エラー1) when (エラー1 is not ForceExitException)
    {
        Wait(2d);  // 待機してリトライ
    }
}
if (InvertBool(処理成功))
{
    OutputUserLog("処理に10回失敗。処理を終了します。");
    return;  // シナリオ終了
}
```

**重要ポイント:**
- `ForceExitException`は再throwする（シナリオ強制終了用）
- 成功時は`break`でループ脱出
- 失敗時は`return`でシナリオ終了
- Waitの値は`d`サフィックス（double型）

### 2.2 ファイルコピーのリトライ（待機なし）

```csharp
foreach (var カウンター2 in RepeatCount(30))
{
    try
    {
        CopyFileDirectory(srcPath, dstPath, true);
        MoveDirectory(srcDir, dstDir, true);
        break;
    }
    catch (System.Exception エラー2) when (エラー2 is not ForceExitException)
    {
        // 待機なしでリトライ（ファイルロック解除待ち）
    }
}
```

---

## 3. Excel操作パターン

### 3.1 設定ファイルからの変数展開

```csharp
var excel = OpenFileAndReturnPath(ConfigPath, false, "", true, "", true, true);
var cfg_ENV = GetCellValue(A1, 1, 1, "B2", String);
var ROOT_TIC_MAIN = GetCellValue(A1, 1, 1, "B3", String);
// ... B4〜B24まで各種パス・設定を取得
CloseFile();
```

### 3.2 「合計」行検索パターン

```csharp
// GetMatchValueListは「$列$行」形式で返す
var list2 = GetMatchValueList(A1, 1, 1, 1, 1, "j:j", "合計", false);
cellJ = GetItem(list2, 0);  // "$J$123" 形式
cellJ = ReplaceText(cellJ, "$", false, false, "", false, false);
var string19 = ReplaceText(cellJ, "J", false, false, "", false, false);
foundRow = ConvertFromObjectToInteger(string19);
```

### 3.3 部門別金額取得ループ（下から上への走査）

```csharp
var 金額管理 = -1;  // -1は未取得の意味
var foundCount = 0;
foreach (var loop1 in RepeatCount(50))
{
    var rowStr = ConvertFromObjectToText(row);
    cellJ = Concat("J", rowStr);
    合計ラベル = GetCellValue(A1, 1, 1, cellJ, String);

    if (CompareString(合計ラベル, "合計", NotEqual, false))
        break;  // 「合計」以外の行に到達したら終了

    cellR = Concat("S", rowStr);
    部門名 = GetCellValue(A1, 1, 1, cellR, String);

    if (CompareDouble(金額管理, -1d, Equal) && CompareString(部門名, "管理", Equal, false))
    {
        金額管理 = 取得金額;
        foundCount += 1;
    }
    // ... 他の部門も同様

    if (CompareDouble(foundCount, 5d, Equal))
        break;  // 5部門すべて取得したら終了
    else
        row += -1;  // 下から上へ
}
```

---

## 4. 日付操作パターン

### 4.1 ファイル名から使用年月を抽出

```csharp
// ファイル名: "11278_11278_東海インプル建設㈱_202512.zip"
var list1 = SplitText(string12, true, DelimiterType.Space, 1, "_", false);
var 使用年月 = GetItem(list1, 3);  // "202512"
var 使用年 = GetSubText(使用年月, CharacterPosition, 0, NumberOfChars, 6);
```

### 4.2 翌月の日付を計算

```csharp
var 使用翌月 = AddDatetime(
    ConvertFromTextToDatetime($"{使用年}01", true, "yyyyMMdd"),
    1, Month);

// yyyy.MM形式に変換
var string10 = ConvertFromDatetimeToText(使用翌月, true, ShortDate, "yyyy.MM");
```

### 4.3 よく使う日付フォーマット

| フォーマット | 結果例 | 用途 |
|-------------|--------|------|
| `yyyyMM` | 202501 | CSVシート名 |
| `yyyy.MM` | 2025.01 | Excelシート名 |
| `yyyy/MM/dd` | 2025/01/08 | 表示用日付 |
| `yyyyMMdd` | 20250108 | ファイル名用 |

---

## 5. 科目推定パターン

### 5.1 支払先×摘要キーワード方式

**問題:** 同一支払先で複数科目が使われるケース

| 支払先 | 科目パターン |
|--------|-------------|
| 安城印刷㈱ | 消耗品費(17件)/広告宣伝費(4件) |
| ㈱八木商会 | 支払手数料(7件)/消耗品費(3件) |

**解決策:** 支払先のみではなく、**摘要内容も見る**

```python
# 科目推定マスタ（支払先×摘要キーワード）
ACCOUNT_MAPPING = {
    ("安城印刷", "名刺"): "消耗品費",
    ("安城印刷", "チラシ"): "広告宣伝費",
    ("八木商会", "手数料"): "支払手数料",
    ("八木商会", "文具"): "消耗品費",
}
```

### 5.2 確度による色分け

| 確度 | 色 | 条件 |
|------|-----|------|
| 完全一致 | 黒字 | マスタに完全一致あり |
| 推定 | 黄字 | 支払先のみ一致 |
| 不明/新規 | 赤字 | マッチなし→人間確認必要 |

---

## 6. PDF座標抽出パターン

### 6.1 座標指定でのテキスト抽出

```csharp
// ExtractText(pdfPath, pageNum, x, y, width, height)
var 発行日情報 = ExtractText(pdfPath, 1, 143, 308, 141, 13);
var 請求金額情報 = ExtractText(pdfPath, 1, 115, 275, 189, 18);
```

**注意:** 座標はピクセル単位。PDFレイアウト変更時は座標の再調査が必要。

---

## 7. メール送信パターン

### 7.1 HTML形式メール

```csharp
SendHtmlMail("", mailAddress, "", "", subject, attachmentPath, false,
    new List<HtmlMailBodyContent> {
        HtmlBodyContentCreator.CreateString("本文テキスト"),
        HtmlBodyContentCreator.CreateHyperlink("リンク表示名", "https://...")
    }, "");
```

---

## 8. カスタム区切り文字による分割

### 8.1 ReplaceText + DelimiterType.Space

**問題:** `DelimiterType.Specified`は存在しない

**解決策:**
```csharp
// アンダースコアをスペースに置換してから分割
var list1_replaced = ReplaceText(list1_first, "_", " ", ReplaceMode.All, ...);
var list2 = SplitText(list1_replaced, ..., DelimiterType.Space, ..., " ", ...);
```

---

## 9. 番号付きファイル名への対応

### 9.1 問題

ダウンロードフォルダに番号付きファイル（例: `file_202512 (8).zip`）が存在すると、`GetNewestFilePath`が番号付きを取得し、分割ロジックが失敗する。

### 9.2 解決策

```csharp
// スペースで分割後、最初の要素のみ使用
var list1 = SplitText(filename, Space, ...);
var list1_first = GetItem(list1, 0);  // 番号部分を除去

// さらにアンダースコアで分割
var list1_replaced = ReplaceText(list1_first, "_", " ", ReplaceMode.All, ...);
var list2 = SplitText(list1_replaced, Space, ...);
var 使用月元 = GetItem(list2, 3);  // "202512"
```

---

## 10. Excel転記の2行1セット構造

### 10.1 本体行と税行

**本体行（奇数行: 17, 19, 21...）**
| 列 | 内容 | 転記対象 |
|----|------|----------|
| A | 業者番号 | - |
| B | 支払先名 | - |
| C | 摘要 | ★転記する |
| I | 支払額（税込金額） | ★転記する |
| J | 支払先計 | 触らない（SUM数式） |

**税行（偶数行: 18, 20, 22...）**
- **絶対に触らない**（数式で全自動計算）
- E列: 「仮払消費税」または「-」
- H列: =ROUNDDOWN(I本体行*10/110,0)
