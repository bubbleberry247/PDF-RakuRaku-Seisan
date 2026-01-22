# RK10 トラブルシューティング集

## 1. XPath関連エラー

### 1.1 要素が見つからない（ancestor::使用時）

**症状:** `//p[contains(text(), '.zip')]/ancestor::a` で要素が見つからない

**原因:** RK10のXPath実装は以下の構文を**サポートしない**:
- `ancestor::`
- `descendant::`
- `../../..`（複数階層の相対パス）
- `contains(., '...')`（ノード自身のテキスト検索）
- CSSセレクタ

**解決策:**
```
NG: //p[contains(text(), '.zip')]/ancestor::a
NG: //a[descendant::p[contains(text(), '.zip')]]
NG: //p[contains(text(), '.zip')]/../../..

OK: //p[contains(text(), '.zip')]  ← 要素を特定してからクリック
OK: //a[contains(@class, 'target-class')]  ← クラス名で直接指定
OK: //a[@class='sc-gyycJP KKYCe'][1]  ← 完全一致+インデックス
```

**代替案:** Playwright/Selenium + Pythonで処理

---

### 1.2 要素が見つからない（href属性がない場合）

**症状:** `//a[contains(@href, '.zip')]` で要素が見つからない

**原因:** React SPA等でリンクにhref属性がなく、JavaScriptクリックハンドラで処理している

**HTML例:**
```html
<a class="sc-gyycJP KKYCe">
  <div><div><p>file_202512.zip</p></div></div>
</a>
```

**解決策:** テキストを含む子要素から特定
```
//p[contains(text(), '.zip')]
```

---

## 2. Excel操作エラー

### 2.1 シート選択エラー（インデックスが無効）

**症状:** `インデックスが無効です。(DISP_E_BADINDEX)`

**原因:** シート名のハードコード、またはフォーマット不一致

**NG例:**
```csharp
SelectSheet(Name, $@"2025.11", 1);  // ハードコード
```

**OK例:**
```csharp
// 動的にシート名を生成
var sheetName = ConvertFromDatetimeToText(targetDate, true, ShortDate, "yyyy.MM");
SelectSheet(Name, $@"{sheetName}", 1);
```

**よくあるフォーマット不一致:**
| 変数の値 | シート名 | 結果 |
|---------|---------|------|
| 202501 | 2025.01 | NG |
| 2025.01 | 2025.01 | OK |

---

### 2.2 GetMatchValueListの戻り値形式

**症状:** セル位置の取得後、文字列操作で失敗する

**原因:** `GetMatchValueList`は`$列$行`形式で返す

**例:**
```csharp
var list = GetMatchValueList(A1, 1, 1, 1, 1, "j:j", "合計", false);
var cell = GetItem(list, 0);  // "$J$123" 形式

// $を除去して行番号を取得
cell = ReplaceText(cell, "$", false, false, "", false, false);
var rowStr = ReplaceText(cell, "J", false, false, "", false, false);
var row = ConvertFromObjectToInteger(rowStr);  // 123
```

---

### 2.3 Excelファイルが閉じない

**症状:** シナリオ終了後もExcelプロセスが残る

**原因:** `CloseFile()`の呼び忘れ、またはエラー時にCloseFileがスキップされる

**解決策:**
```csharp
try
{
    // Excel操作
    OpenFileAndReturnPath(...);
    // 処理
    SaveFile(...);
}
finally
{
    CloseFile();  // 必ず実行
}
```

---

## 3. ファイル操作エラー

### 3.1 ZIP展開で10回失敗

**症状:** `UncompressFile`が10回リトライしても失敗

**原因:**
1. 前回実行時の解凍フォルダがロック中
2. ファイルパスに日本語/スペースが含まれる
3. ZIPファイル自体が破損

**解決策:**
```csharp
// 作業フォルダをクリーンアップしてから解凍
if (Exists(解凍フォルダ))
{
    DeleteDirectory(解凍フォルダ, true);
    Wait(1d);  // 削除完了を待機
}
UncompressFile(zipPath, 解凍フォルダ, true, "", ShiftJis);
```

---

### 3.2 ファイルコピーが失敗する

**症状:** `CopyFileDirectory`でエラー

**原因:**
- コピー先にファイルが存在しロック中
- ネットワークドライブへの書き込み権限なし

**解決策:**
```csharp
foreach (var カウンター in RepeatCount(30))
{
    try
    {
        CopyFileDirectory(srcPath, dstPath, true);
        break;
    }
    catch (System.Exception エラー) when (エラー is not ForceExitException)
    {
        // 待機なしでリトライ
    }
}
```

---

### 3.3 番号付きファイル名の問題

**症状:** ダウンロードフォルダで`GetNewestFilePath`が番号付きファイルを取得

**例:** `file_202512 (8).zip`

**原因:** 同名ファイルが既に存在し、ブラウザが自動で番号を付与

**解決策:**
```csharp
// スペースで分割して番号部分を除去
var list1 = SplitText(filename, Space, ...);
var baseName = GetItem(list1, 0);  // "file_202512"
```

---

## 4. DataTable/ExternalResources エラー

### 4.1 ConvertExcelToDataTableでエラー

**症状:** `ExternalResourceReader.GetResourceText`でエラー

**原因:** 第2引数`serializedConfig`にGUIで設定した値が期待されている

**解決策:** 空のJSON `{}` を指定
```csharp
var dataTable = ConvertExcelToDataTable(excelPath, "{}", 1, true, true, true);
```

**注意:** 空JSONでは1行目がヘッダーとして扱われ、全データが読み込まれる

---

## 5. 日付・時刻エラー

### 5.1 日付フォーマット不一致

**症状:** シート名やファイル名の検索で一致しない

| フォーマット | 結果例 | 用途 |
|-------------|--------|------|
| `yyyyMM` | 202501 | ファイル名、CSVシート名 |
| `yyyy.MM` | 2025.01 | Excelシート名 |
| `yyyy/MM/dd` | 2025/01/08 | 表示用 |
| `yyyyMMdd` | 20250108 | ファイル名用 |

**変換例:**
```csharp
// 202501 → 2025.01
var yyyyMM = "202501";
var dt = ConvertFromTextToDatetime($"{yyyyMM}01", true, "yyyyMMdd");
var formatted = ConvertFromDatetimeToText(dt, true, ShortDate, "yyyy.MM");
// → "2025.01"
```

---

### 5.2 翌月計算の落とし穴

**症状:** 月末日から翌月を計算すると意図しない結果

**原因:** 1月31日 + 1ヶ月 = 2月28日（3月1日にならない）

**解決策:** 月初日から計算する
```csharp
// 月初に正規化してから翌月計算
var baseDate = ConvertFromTextToDatetime($"{yyyyMM}01", true, "yyyyMMdd");
var nextMonth = AddDatetime(baseDate, 1, Month);
```

---

## 6. ブラウザ操作エラー

### 6.1 Bot検出でアクセス拒否

**症状:** Webサイトへのアクセスが403/429エラー

**原因:** RK10標準のブラウザ操作はBot検出されやすい

**解決策:** Playwrightを使用
```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...'
    )
    page = await context.new_page()
    await page.goto(url)
```

---

### 6.2 ダウンロード待機が効かない

**症状:** `WaitForFileDownload`でタイムアウト

**原因:** JavaScriptでダウンロードが開始される場合、RK10の待機が効かない

**解決策（Playwright）:**
```python
async with page.expect_download() as download_info:
    await page.click('a.download-link')
download = await download_info.value
await download.save_as(f'C:/Downloads/{download.suggested_filename}')
```

---

## 7. pywinauto/UI自動化エラー

### 7.1 ボタンクリックが反応しない

**症状:** `button.click()`しても何も起きない

**原因:** ダイアログ（確認ダイアログ、エラーダイアログ等）が表示されている

**解決策:** 先にダイアログを処理
```python
import pyautogui

def handle_dialog():
    """ダイアログを検出して処理"""
    # ダイアログ検出
    try:
        dialog = app.window(title_re='.*確認.*')
        if dialog.exists():
            pyautogui.click(515, 340)  # 「はい」ボタン座標
            return True
    except:
        pass
    return False
```

---

### 7.2 RK10「編集しますか」ダイアログ

**症状:** .rksファイルを開いた後、操作が効かない

**原因:** 「編集しますか？」確認ダイアログが表示されている

**解決策:** pyautoguiで座標クリック
```python
import pyautogui
import time

def handle_edit_dialog():
    time.sleep(0.5)
    pyautogui.click(515, 340)  # 「はい(Y)」ボタン
```

---

## 8. 認証・資格情報エラー

### 8.1 資格情報が取得できない

**症状:** `ReadPasswordFromCredential`でエラー

**原因:**
1. 資格情報マネージャーに登録されていない
2. 資格情報名が異なる
3. 実行ユーザーと登録ユーザーが異なる

**確認方法:**
1. コントロールパネル → 資格情報マネージャー
2. Windows資格情報 → 対象の資格情報を確認
3. RK10で使用している名前と完全一致しているか確認

---

## 9. メール送信エラー

### 9.1 SendHtmlMailで失敗

**症状:** メール送信でタイムアウトまたはエラー

**チェックポイント:**
1. SMTPサーバー設定（RK10設定画面）
2. 送信元アドレスの認証
3. ファイアウォール/プロキシ設定

**デバッグ用ログ:**
```csharp
OutputUserLog($"送信先: {mailAddress}");
OutputUserLog($"添付ファイル: {attachmentPath}");
OutputUserLog($"ファイル存在: {Exists(attachmentPath)}");
```

---

## 10. 環境固有の問題

### 10.1 PROD/LOCAL環境切替が効かない

**症状:** 環境変数を変えても設定が変わらない

**チェックポイント:**
1. `env.txt`の内容（改行やスペースが入っていないか）
2. 大文字/小文字の統一（`PROD` vs `Prod`）
3. キャッシュされた変数が残っていないか

**デバッグ:**
```csharp
var Env = ReadAllText($@"..\config\env.txt", Auto);
OutputUserLog($"env.txt内容: [{Env}]");  // 前後の空白を確認

Env = TrimText(Env, Both);
Env = ChangeTextCase(Env, UpperCase);
OutputUserLog($"正規化後: [{Env}]");
```

---

### 10.2 ネットワークドライブ接続エラー

**症状:** `\\server\share`へのアクセスが失敗

**原因:**
1. VPN未接続
2. 資格情報の期限切れ
3. サーバーIPアドレスの変更（UTM入替等）

**解決策:**
```csharp
// 接続確認を先に実行
if (InvertBool(Exists($@"\\server\share\test.txt")))
{
    OutputUserLog("ネットワークドライブに接続できません。VPN接続を確認してください。");
    return;
}
```

---

## クイックリファレンス：エラー別対処表

| エラーメッセージ | 原因 | 対処 |
|-----------------|------|------|
| インデックスが無効です (DISP_E_BADINDEX) | シート名不一致 | フォーマット確認、ハードコード除去 |
| 要素が見つかりません | XPath非対応構文 | 構文変更、Playwright使用 |
| 処理に10回失敗 | ファイルロック | 作業フォルダクリーンアップ |
| ExternalResourceReader | DataTable設定不備 | 空JSON `{}` を指定 |
| タイムアウト | ダイアログ表示中 | ダイアログ処理を先に実行 |
| 認証エラー | 資格情報不備 | 資格情報マネージャー確認 |
