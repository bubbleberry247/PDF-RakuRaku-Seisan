# RK10シナリオ作成 Skill

## 説明
KEYENCE RK-10 RPAシナリオを作成する際の標準手順と蓄積された知見

## 使用方法
```
/rk10-scenario --target "55 振込Excel転記"
```

## 前提条件
- RK10 3.6.44.51108インストール済み
- Python 3.11+環境
- pywinauto, openpyxl, playwright インストール済み

---

## 1. 要件定義フェーズ

### 1.1 ヒアリング項目
- [ ] 処理対象データ特定（支払日、承認ステータス等）
- [ ] 入力元確認（楽楽精算、Excel、CSV、基幹システム等）
- [ ] 出力先確認（Excel、PDF、勘定奉行等）
- [ ] 人間確認ポイント洗い出し（黄色フラグ）
- [ ] 例外処理の洗い出し（エラー時の対応）

### 1.2 PDD（Process Definition Document）作成

業務フローの書き起こし資料は、**RPA開発でいうPDD**に近い粒度で作成。

**必須12列構成:**
| 列 | 項目 | 説明 |
|----|------|------|
| A | No | ステップ番号 |
| B | プロセス/サブプロセス | 処理の大分類 |
| C | 操作種別 | クリック、入力、読込、判定 |
| D | 詳細手順 | 人が読んで理解できる具体的な操作内容 |
| E | 画面名/URL/対象 | 操作対象の画面・URL・ファイルパス |
| F | 入力データ/値 | 入力する値や取得する値の例 |
| G | 判定・分岐条件 | 条件分岐がある場合のロジック |
| H | 例外・エラー対応 | エラー発生時の対処方法 |
| I | 前提条件 | そのステップを実行するために必要な状態 |
| J | 自動化可否 | ○=自動化可能、△=要検討、×=手動のみ |
| K | リスク・制約 | 自動化時のリスクや技術的制約 |
| L | 改善アイデア | 将来の改善案・機能追加案 |

**色分けルール:**
- 緑（C6EFCE）: 自動化可能（○）
- 黄（FFEB9C）: 要検討（△）/ 人間確認ポイント
- 赤（FFC7CE）: 自動化不可（×）

---

## 2. 楽楽精算連携

### 2.1 基本情報
- **ツール**: Playwright + Chromium
- **API連携**: 契約なし、使用不可（ブラウザUI操作が唯一の手段）
- **URL**: `https://rsatonality.rakurakuseisan.jp/rHqny3DOsIa/`

### 2.2 ログイン設定

**Windows資格情報マネージャーに登録:**
| 資格情報名 | 用途 |
|-----------|------|
| `ログインID　楽楽精算` | ログインID |
| `パスワード　楽楽精算` | パスワード |

**ログイン処理（Playwright）:**
```python
from playwright.sync_api import sync_playwright

def login_rakuraku(page, login_id: str, password: str):
    page.goto("https://rsatonality.rakurakuseisan.jp/rHqny3DOsIa/")
    page.wait_for_load_state("networkidle")

    # ログインフォーム
    page.fill('input[name="userId"]', login_id)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')

    # ログイン完了待機
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)  # 追加の安定待機
```

### 2.3 フレーム構造

楽楽精算はフレーム構成が複雑:
```
フレーム0: sapTopPage/mainView（メインフレーム）
フレーム1: sapTopPage/initializeView（コンテンツ - テーブルあり）
フレーム2: sapTopPage/footerView/（フッター）
フレーム3: about:blank
フレーム4: googletagmanager（トラッキング）
```

**フレーム内の要素操作:**
```python
# フレームを取得して操作
frame = page.frame(name="content")  # or page.frames[1]
frame.click('a:has-text("支払依頼")')
```

### 2.4 領収書/請求書登録画面

**画面URL:** `/sapEbookFile/initializeView`（**注意:** sapEbookFile**Import**ではない）

**ファイルアップロード（filechooser方式）:**
```python
with page.expect_file_chooser() as fc_info:
    page.click('//input')  # ファイル選択ボタン
file_chooser = fc_info.value
file_chooser.set_files(pdf_path)
```

**フォーム入力セレクタ（name属性ベース）:**
| 項目 | セレクタ |
|------|---------|
| 取引日（年） | `tradingDateYear(0)` |
| 取引日（月） | `tradingDateMonth(0)` |
| 取引日（日） | `tradingDateDay(0)` |
| 受領日（年） | `receivingDateYear(0)` |
| 受領日（月） | `receivingDateMonth(0)` |
| 受領日（日） | `receivingDateDay(0)` |
| 事業者登録番号 | `invoiceBusinessNumber(0)` |
| 取引先名 | `supplierName(0)` |
| 金額入力1行目 | `saimokuKingaku(0_1)` |
| 金額入力2行目 | `saimokuKingaku(0_2)` |

**金額行の追加:**
```python
# 初期状態は1行のみ。2行目以降は追加ボタンをクリック
page.click('#addKingaku(0)')
```

**確定ボタン:**
```python
# クラス名で特定（XPathだと複数要素にマッチする場合あり）
page.click('button.kakuteiEbook, button.accesskeyOk.red')
```

### 2.5 承認ステータスの判定

列12（cells[12]）に承認ステータスが格納。日本語の微妙な表記揺れに注意:

| 値 | 意味 | 処理対象 |
|----|------|---------|
| `確認済(YYYY/MM/DD 支払)` | 承認済み＋支払済み | 対象 |
| `確認` | 承認済み（完全一致） | 対象 |
| `確定待` | 経理確認待ち | **対象（見逃しやすい）** |
| `承認依頼中 X/Y` | 承認フロー途中 | 除外 |

```python
def _is_approved(self, approval_status: str) -> bool:
    """承認状況が「承認済み」かどうか判定"""
    if not approval_status:
        return False
    return (
        approval_status.startswith("確認済") or
        approval_status == "確認" or
        approval_status == "確定待"
    )
```

### 2.3 会社コードフィルタ

楽楽精算の検索条件「会社名」に会社コードを入力:
- フィルタなし: 12,596件
- 会社コード300（東海インプル建設）: 2,070件
- 会社コード300 + 末日: 28件

### 2.4 列インデックスの調査方法

```python
# check_columns.py でヘッダー行を確認
for i, cell in enumerate(cells):
    print(f"列{i}: {cell.text_content()}")
```

### 2.5 支払日フィルタ
- 15日/25日/末日の動的な日付計算が必要
- 末日は土日の場合、前営業日に調整

---

## 3. RK10 UI操作パターン

### 3.1 基本設定
- **バックエンド**: pywinauto UIA
- **起動時エディション選択**: `RPA開発版AI付`を自動選択
- **編集確認ダイアログ**: pyautogui座標クリック（詳細は3.5参照）

### 3.2 UI要素一覧

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

### 3.3 実行状態の検出

| 状態 | ButtonRun.is_enabled() | StopButton.is_enabled() | check_error() |
|------|------------------------|-------------------------|---------------|
| アイドル | True | False | False |
| 実行中 | False | True | False |
| エラー表示中 | False | True | True |
| 完了 | True | False | False |

### 3.4 ★最重要★ 操作が効かない場合はダイアログが原因

- pywinautoで指示しても反応がない場合、何かしらのダイアログが表示されている
- 先にそのダイアログを処理（OK/閉じる等）しないと次に進めない
- 常にダイアログの存在を確認してから操作すること

### 3.5 「編集しますか」ダイアログの処理

RK-10で.rksファイルを開くと「編集しますか？」確認ダイアログが表示される。
このダイアログはpywinautoで要素を特定できないため、**pyautogui座標クリック**で処理。

**問題:**
- ダイアログはモーダルで、処理しないと次の操作ができない
- pywinautoのautomation_idでは要素を特定できない
- ウィンドウ内の相対位置でボタンをクリックする必要がある

**解決策（pyautogui座標クリック）:**
```python
import pyautogui
import time

def handle_edit_dialog():
    """RK-10の「編集しますか」ダイアログで「はい(Y)」をクリック"""
    # ダイアログ表示を待機
    time.sleep(0.5)

    # 「はい(Y)」ボタンの位置（RK10ウィンドウ左上からの相対位置）
    # 標準的な画面位置での座標
    pyautogui.click(515, 340)
```

**座標の補足:**
- 座標 (515, 340) はRK-10ウィンドウが標準位置にある場合の「はい(Y)」ボタン位置
- ウィンドウ位置が変わると座標も変わるため、実行環境で調整が必要な場合あり
- 確実性を高めるには、ウィンドウ位置を取得して相対座標で計算する方法もある

**より堅牢な実装:**
```python
import pyautogui
from pywinauto import Desktop

def handle_edit_dialog_robust():
    """ウィンドウ位置を考慮した「編集しますか」ダイアログ処理"""
    desktop = Desktop(backend="uia")

    # RK-10エディターウィンドウを探す
    for win in desktop.windows():
        if "シナリオエディター" in win.window_text():
            rect = win.rectangle()
            # ダイアログの「はい」ボタンはウィンドウ中央付近
            # ウィンドウ左上からの相対オフセット
            button_x = rect.left + 200  # 調整が必要
            button_y = rect.top + 150   # 調整が必要
            pyautogui.click(button_x, button_y)
            return True
    return False
```

**注意事項:**
- pyautoguiは画面解像度やDPIスケーリングの影響を受ける
- マルチモニター環境では座標に注意
- クリック前に適切な待機時間を入れる（0.3〜0.5秒）

---

## 4. .rksファイル編集

### 4.1 ファイル構造

```
.rks (ZIP形式)
├── Program.cs              ← メインロジック（C#コード）★編集可能
├── ExternalActivities.cs   ← 外部アクティビティ定義
├── id                      ← Roslyn構文木の位置情報（自動再生成）
├── meta                    ← GUIレイアウト（自動再生成）
├── rootMeta                ← 実行速度設定など
├── externalActivitiesMeta  ← 外部アクティビティメタ
└── version                 ← ファイルバージョン情報
```

**重要**: Program.csのみ編集すればOK。id/metaは自動再生成される。

### 4.2 ハードコード検出パターン

検索すべきキーワード:
- `$@"202` - 年月のハードコード
- `$@"C:\\` - 絶対パスのハードコード
- `SelectSheet` + 固定文字列 - シート名ハードコード
- `OpenFile` のみ - CloseFile()の確認

### 4.3 よくある修正パターン

| 修正前 | 修正後 | 説明 |
|--------|--------|------|
| `$@"2025.11"` | `$@"{string10}"` | 月のシート名を動的変数に |
| `$@"yyyy.MM"` | `$@"yyyyMM"` | 日付フォーマット修正 |
| OpenFileのみ | OpenFile + CloseFile | ファイル閉じ忘れ対応 |

### 4.4 RKSファイル編集テンプレート

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

---

## 5. Excel転記の重要ポイント

### 5.1 2行1セット構造（55番シナリオ）

**本体行（奇数行: 17, 19, 21...）**
| 列 | 内容 | 転記対象 |
|----|------|----------|
| A | 業者番号 | - |
| B | 支払先名 | - |
| C | 摘要 | **★転記する** |
| I | 支払額（税込金額） | **★転記する** |
| J | 支払先計 | 触らない（SUM数式） |

**税行（偶数行: 18, 20, 22...）**
- **絶対に触らない**（数式で全自動計算）
- E列: 「仮払消費税」または「-」
- H列: =ROUNDDOWN(I本体行*10/110,0)

### 5.2 支払先マッチングの正規化

```python
def normalize_payee(name: str) -> str:
    # 全角→半角変換
    # 株式会社→㈱、有限会社→㈲
    # スペース正規化
    # 括弧内の補足情報（ボディマン等）を分離
    pass
```

### 5.3 6799行（未登録支払先）への転記

- 業者番号「6799」は未登録/都度取引先用の汎用番号
- 末日支払セクション（行87-588）の本体行のみ検索
- 業者番号=6799 かつ 支払額（I列）が空欄の行を使用
- **A列（業者番号）は空欄にする**（担当者が後で記入）

### 5.4 科目推定の暗黙知

**同一支払先で複数科目が使われるケース:**
| 支払先 | 科目パターン |
|--------|-------------|
| 安城印刷㈱ | 消耗品費(17)/広告宣伝費(4) |
| ㈱八木商会 | 支払手数料(7)/消耗品費(3) |

→ 科目推定は「支払先のみ」では不十分。**摘要内容も見る必要あり**

**暗黙知:**
- 申請者は「近い科目（消耗品/広告宣伝/手数料）」で起票
- 経理担当がExcel転記時に**過去踏襲（社内ルール）に合わせて科目補正**
- RPA実装: 「仕入先×摘要キーワード」から科目を引く補正テーブルが必要

---

## 6. 設定ファイルパターン

### 6.1 env.txt
```
PROD
```
または
```
LOCAL
```

### 6.2 RK10_config_*.xlsx 構造
| セル | 項目 | 例 |
|------|------|-----|
| B2 | ENV | PROD/LOCAL |
| B3 | ROOT_PATH | \\\\server\\share |
| B4 | INPUT_FILE | 入力ファイルパス |
| B5 | OUTPUT_FILE | 出力ファイルパス |

### 6.3 コード内での環境判定パターン

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

## 7. RK10とPython連携

### 7.1 シナリオ構成（推奨）

```
1. env.txt読み込み（PROD/LOCAL判定）
2. 設定ファイル読み込み（RK10_config_*.xlsx）
3. Python呼び出し（main.py）
   - 引数: --env PROD --payment-date 末日 --company-code 300
4. 処理結果確認（エラー時は通知）
5. 完了通知
```

### 7.2 Python呼び出し例（C#）

```csharp
// Pythonスクリプトを実行
var pythonPath = @"C:\Python311\python.exe";
var scriptPath = ROBOT_DIR + @"\tools\main.py";
var args = $"--env {Env} --payment-date 末日 --company-code 300";

Keyence.SystemActions.SystemAction.ExecuteApplication(
    pythonPath, $"\"{scriptPath}\" {args}", "", true, 600);
```

---

## 8. エラーパターン集

### エラー1: Excelシート名ハードコード
**症状:** 特定行で待機したまま停止
**エラーメッセージ:** `インデックスが無効です。(DISP_E_BADINDEX)`

**原因:** シート名がハードコードされていた
```csharp
// NG
Keyence.ExcelActions.ExcelAction.SelectSheet(
    Keyence.ExcelActions.SheetSelectionMode.Name, $@"2025.11", 1);
```

**解決策:** 動的変数を使用
```csharp
// OK
Keyence.ExcelActions.ExcelAction.SelectSheet(
    Keyence.ExcelActions.SheetSelectionMode.Name, $@"{string10}", 1);
```

### エラー2: 日付フォーマット不一致
**症状:** シート選択で失敗
**原因:** 変数のフォーマットとExcelシート名の形式が不一致
```csharp
// NG: yyyy.MM形式 → "2025.01" を生成
// しかし実際のシート名は "202501" 形式
```
**解決策:** 正しいフォーマットに修正（yyyyMM等）

### エラー3: Excelファイル閉じ忘れ
**症状:** シナリオ終了後もExcelファイルが開いたまま残る
**発見方法:** Program.cs内で `OpenFile` を検索し、対応する `CloseFile()` があるか確認
**解決策:** 処理終了時にCloseFile()を追加

### エラー4: ZIP展開リトライループで停止
**症状:** ZIP展開で10回失敗して停止
**原因:** 前回実行時のCSV/PDFファイルが開いたまま（ファイルロック）
**解決策:** ダウンロードフォルダ内の展開済みファイルを全て閉じる
**予防策:** シナリオ開始時に作業フォルダをクリーンアップする処理を追加

### エラー5: 承認ステータス「確定待」の見逃し
**症状:** 承認済みデータが抽出されない
**原因:** `_is_approved()`が「確認済」「確認」のみチェックしていた
**調査方法:**
```python
# 文字コードを調査
print([hex(ord(c)) for c in status])
# 結果: ['0x78ba', '0x5b9a', '0x5f85'] = 確定待
```
**解決策:** `_is_approved()`に「確定待」を追加

### エラー6: pywinauto操作が効かない
**症状:** ボタンクリック等の操作が反応しない
**原因:** ダイアログ（確認ダイアログ、エラーダイアログ等）が表示されている
**解決策:** 先にダイアログを処理（OK/閉じる等）してから操作

---

## 9. Keyence C# API リファレンス

### 9.1 Excel操作

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

### 9.2 日付変換

```csharp
// 日付→テキスト変換（フォーマット指定）
var dateStr = Keyence.TextActions.TextAction.ConvertFromDatetimeToText(
    dateVar, true, Keyence.TextActions.DateTimeFormat.ShortDate, $@"yyyyMM");

// よく使うフォーマット
// "yyyyMM"     → "202501"
// "yyyy.MM"    → "2025.01"
// "yyyy/MM/dd" → "2025/01/08"
// "yyyyMMdd"   → "20250108"
```

### 9.3 Windows資格情報

```csharp
// パスワード取得（資格情報マネージャーから）
var password = Keyence.SystemActions.SystemAction.ReadPasswordFromCredential("資格情報名");
```

### 9.4 ファイル操作

```csharp
// 最新ファイル取得
var newestFile = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath(
    directory, $@"*.pdf", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

// ファイル存在チェック
var exists = Keyence.FileSystemActions.FileAction.Exists(filePath);
```

### 9.5 待機・ログ

```csharp
// 待機
Keyence.ThreadingActions.ThreadingAction.Wait(5d);

// ログ出力
Keyence.CommentActions.LogAction.OutputUserLog(message);
```

---

## 10. テンプレート

### 10.1 楽楽精算スクレイピング（Playwright）

```python
from playwright.sync_api import sync_playwright

class RakurakuScraper:
    def __init__(self, config: dict):
        self.config = config

    def scrape_payment_requests(self, payment_date: str, company_code: str = None):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            # ログイン
            page.goto(self.config["RAKURAKUSEISAN_WEB"])
            # ... ログイン処理

            # 会社コードでフィルタ
            if company_code:
                page.fill('input[name="company"]', company_code)

            # 支払日でフィルタ
            # ... フィルタ処理

            # データ抽出
            rows = page.query_selector_all('table tbody tr')
            data = []
            for row in rows:
                cells = row.query_selector_all('td')
                if self._is_approved(cells[12].text_content()):
                    data.append(self._extract_row(cells))

            browser.close()
            return data

    def _is_approved(self, status: str) -> bool:
        return (
            status.startswith("確認済") or
            status == "確認" or
            status == "確定待"
        )
```

### 10.2 Excel転記（openpyxl）

```python
from openpyxl import load_workbook
from openpyxl.comments import Comment

def write_to_excel(excel_path: str, data: list, sheet_name: str):
    wb = load_workbook(excel_path)
    ws = wb[sheet_name]

    for item in data:
        # 本体行のみ処理（奇数行）
        for row in range(17, 590, 2):
            if ws.cell(row=row, column=9).value is None:  # I列が空
                ws.cell(row=row, column=3).value = item['summary']  # C列: 摘要
                ws.cell(row=row, column=9).value = item['amount']   # I列: 支払額
                break

    wb.save(excel_path)
```

### 10.3 RK10 UI操作（pywinauto）

```python
from pywinauto import Desktop
import time

class RK10Controller:
    def __init__(self):
        self.desktop = Desktop(backend="uia")

    def find_scenario_editor(self):
        for win in self.desktop.windows():
            if "シナリオエディター" in win.window_text():
                return win
        return None

    def run_scenario(self) -> bool:
        editor = self.find_scenario_editor()
        if not editor:
            return False

        for btn in editor.descendants(control_type="Button"):
            if btn.automation_id() == "ButtonRun":
                btn.invoke()
                return True
        return False

    def check_error(self) -> tuple:
        """Returns: (has_error, error_type: 'build'|'runtime'|None)"""
        editor = self.find_scenario_editor()
        if not editor:
            return False, None

        for btn in editor.descendants(control_type="Button"):
            aid = btn.automation_id()
            if aid == "CopyButton":
                return True, "build"
            if aid == "ContactInfoOutputButton":
                return True, "runtime"
        return False, None
```

---

## 11. 参考資料

- **CLAUDE.md**: RK10自動化プロジェクト全体の知見
  - C:\RK10-MCP\CLAUDE.md (Windows)
  - /Users/okamac/CLAUDE.md (Mac)
- **各ロボットフォルダ**:
  - C:\ProgramData\RK10\Robots\43 一般経費_...(ETC)明細の作成\
  - C:\ProgramData\RK10\Robots\47 出退勤確認\
  - C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\
  - C:\ProgramData\RK10\Robots\56 資金繰り表エクセル入力\

---

## 12. 設計思想

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

## 13. サイボウズ連携（37シナリオ知見）

### 13.1 基本情報
- **ツール**: Playwright + Chromium
- **URL**: `https://uc8w7.cybozu.com/o/`
- **認証**: Windows資格情報マネージャー（`RK10_Cybozu`）

### 13.2 ログイン処理

サイボウズはcybozu.comの統合ログインを使用。サービス選択画面が表示される場合がある。

```python
def login(self) -> bool:
    """サイボウズにログイン"""
    page = self.page
    page.goto(self.LOGIN_URL)
    page.wait_for_load_state("networkidle")

    # ログインフォーム
    username, password = get_cybozu_credential()
    page.fill('input[name="_account"]', username)
    page.fill('input[name="_password"]', password)
    page.click('input[type="submit"]')

    # サービス選択画面の検出
    if page.locator('a:has-text("サイボウズ Office")').count() > 0:
        page.click('a:has-text("サイボウズ Office")')
        page.wait_for_load_state("networkidle")

    return True
```

### 13.3 ワークフロー一覧取得

```python
WORKFLOW_URL = "https://uc8w7.cybozu.com/o/ag.cgi?page=WorkFlowIndex"

# 対象フォーム名パターン
TARGET_FORMS = [
    "01.休暇取得申請書",
    "02.届度有休・その他休暇申請",
    "【TIC】01.休暇取得申請",
]

# 一覧ページから申請を取得
def get_pending_workflows(self):
    page.goto(self.WORKFLOW_URL)
    rows = page.query_selector_all('table.list tr')

    workflows = []
    for row in rows:
        cells = row.query_selector_all('td')
        if len(cells) >= 5:
            form_type = cells[1].text_content().strip()
            if any(target in form_type for target in self.TARGET_FORMS):
                workflows.append({
                    'wf_id': self._extract_wf_id(cells),
                    'form_type': form_type,
                    'applicant_name': cells[2].text_content().strip(),
                    'href': cells[0].query_selector('a').get_attribute('href'),
                })
    return workflows
```

### 13.4 申請詳細から休暇日を取得

```python
def parse_leave_dates(self, page) -> List[Dict]:
    """申請詳細ページから休暇日を解析"""
    leave_dates = []

    # テーブル行を走査
    rows = page.query_selector_all('table tr')
    for row in rows:
        cells = row.query_selector_all('td')
        text = row.text_content()

        # 日付パターン: YYYY/MM/DD
        date_match = re.search(r'(\d{4}/\d{2}/\d{2})', text)
        if date_match:
            date = date_match.group(1)

            # 休暇種別判定
            if '公休' in text:
                leave_type = '公休'
            elif '有休' in text or '有給' in text:
                leave_type = '有休'
            else:
                leave_type = '不明'

            # 期間判定
            if '午前' in text:
                period = '午前'
            elif '午後' in text:
                period = '午後'
            else:
                period = '終日'

            leave_dates.append({
                'date': date,
                'type': leave_type,
                'period': period
            })

    return leave_dates
```

### 13.5 社員マスタ連携

申請者名から社員番号を取得するマッピングが必要:

```python
# 社員マスタ (employees.json)
{
    "employees": [
        {"name": "山田成章", "employee_id": "5027", "department": "産建営業部"},
        {"name": "鈴木一郎", "employee_id": "1234", "department": "管理部"}
    ]
}

# 名前→社員番号マッピング
def _load_employee_master(self):
    mapping = {}
    for emp in data.get("employees", []):
        name = emp.get("name", "")
        emp_id = emp.get("employee_id", "")
        if name and emp_id:
            mapping[name] = emp_id
            # 姓のみでもマッチできるように
            if len(name) >= 2:
                mapping[name[:2]] = emp_id
    return mapping
```

---

## 14. レコル（勤怠システム）連携（37シナリオ知見）

### 14.1 基本情報
- **ツール**: Playwright + Chromium
- **URL**: 設定ファイルから取得
- **認証**: Windows資格情報マネージャー（`RK10_Recoru`）

### 14.2 休暇登録処理

```python
def register_leaves(employee_id: str, leave_dates: List[Dict], headless: bool = True) -> Dict:
    """
    レコルに休暇を登録

    Args:
        employee_id: 社員番号
        leave_dates: [{'date': 'YYYY/MM/DD', 'type': '公休/有休', 'period': '終日/午前/午後'}]

    Returns:
        {'status': '成功/失敗', 'message': '...'}
    """
    # 社員検索
    # カレンダー操作
    # 休暇種別選択
    # 登録確定
```

---

## 15. Python CLI パターン（37シナリオ知見）

### 15.1 標準CLIインターフェース

```python
"""
【37】レコル公休・有休登録 - メインスクリプト

コマンド一覧:
  --pre                   前処理（サイボウズからデータ取得）
  --post                  後処理（レポート出力）
  --reset                 インデックスリセット
  --init-result           結果ファイル初期化
  --get-count             未処理申請件数取得
  --get-data              現在の申請データ取得（JSON出力）
  --next                  次の申請へ
  --record STATUS MSG     結果記録
  --register-leave        レコル登録実行
  --complete-wf WF_ID     WF処理完了
  --send-mail             処理結果メールを送信

オプション:
  --test-mode             テストモード（テストアドレスに送信）
  --dry-run               ドライランモード（サンプルデータ使用）
  --visible               ブラウザを表示
"""
```

### 15.2 Program.cs からの呼び出しパターン

```csharp
// Pythonスクリプト実行ヘルパー
private static PythonResult RunPython(string script, string args)
{
    var info = new System.Diagnostics.ProcessStartInfo();
    info.FileName = "python";
    info.Arguments = "\"" + script + "\" " + args;
    info.WorkingDirectory = System.IO.Path.GetDirectoryName(script);
    info.UseShellExecute = false;
    info.RedirectStandardOutput = true;
    info.RedirectStandardError = true;
    info.CreateNoWindow = true;
    info.StandardOutputEncoding = System.Text.Encoding.UTF8;
    info.StandardErrorEncoding = System.Text.Encoding.UTF8;

    var process = System.Diagnostics.Process.Start(info);
    process.WaitForExit(120000);  // 2分タイムアウト（ブラウザ操作があるため長め）

    return new PythonResult
    {
        ExitCode = process.ExitCode,
        Output = process.StandardOutput.ReadToEnd(),
        Error = process.StandardError.ReadToEnd()
    };
}

// 使用例
var preResult = RunPython(PythonScript, "--pre --dry-run");
if (preResult.ExitCode != 0) {
    Keyence.CommentActions.LogAction.OutputUserLog("エラー: " + preResult.Error);
    return;
}
```

### 15.3 データ受け渡しパターン

PythonからC#へはJSON文字列で受け渡し:

```csharp
// データ件数取得
var countResult = RunPython(PythonScript, "--get-count");
var dataCount = 0;
int.TryParse(countResult.Output.Trim(), out dataCount);

// 現在のデータ取得（JSON）
var dataResult = RunPython(PythonScript, "--get-data");
var jsonData = dataResult.Output.Trim();
var data = ParseJson(jsonData);  // 簡易JSONパーサー

// フィールド取得
var wfId = GetValue(data, "wf_id");
var applicantName = GetValue(data, "applicant_name");
```

---

## 16. メール送信パターン（37シナリオ知見）

### 16.1 テストモード対応

```python
# mail_sender.py
MAIL_TO = "kanri@example.co.jp"  # 本番宛先
MAIL_CC = ""
TEST_MAIL_TO = "test@example.com"  # テスト宛先

def send_result_mail(test_mode: bool = False, dry_run: bool = False):
    """
    処理結果メールを送信

    Args:
        test_mode: Trueの場合、TEST_MAIL_TOに送信
        dry_run: Trueの場合、送信せずにログ出力のみ
    """
    to_addr = TEST_MAIL_TO if test_mode else MAIL_TO

    if dry_run:
        logger.info(f"[DRY-RUN] メール送信スキップ: {to_addr}")
        return 0

    # SMTP送信処理...
```

### 16.2 Program.csからの呼び出し

```csharp
// Phase 4: メール送信（テストモード）
var mailResult = RunPython(PythonScript, "--send-mail --test-mode");
if (mailResult.ExitCode == 0)
{
    Keyence.CommentActions.LogAction.OutputUserLog("メール送信完了");
}
else
{
    Keyence.CommentActions.LogAction.OutputUserLog("メール送信エラー: " + mailResult.Error);
}
```

---

## 17. ドライランモードパターン（37シナリオ知見）

### 17.1 サンプルデータの埋め込み

```python
def preprocess(headless: bool = True, dry_run: bool = False) -> int:
    """前処理: データを取得してJSONに保存"""

    if dry_run:
        # ドライラン: サンプルデータを使用
        logger.info("ドライランモード: サンプルデータを使用")
        data_list = [
            {
                "_index": 0,
                "wf_id": "28483",
                "form_type": "01.休暇取得申請書",
                "applicant_name": "山田成章",
                "employee_id": "5027",
                "department": "産建営業部",
                "application_date": "2025/12/16",
                "leave_dates": [
                    {"date": "2026/01/12", "type": "公休", "period": "終日"},
                    {"date": "2026/01/24", "type": "公休", "period": "終日"}
                ],
                "status": "pending"
            }
        ]
    else:
        # 実際にサイボウズからデータ取得
        from cybozu_scraper import scrape_workflows
        data_list = scrape_workflows(headless=headless)

    save_data(data_list)
    return 0
```

---

## 18. チェックリスト

### シナリオ作成前
- [ ] 要件定義書（PDD）作成済み
- [ ] 入出力ファイルのサンプル入手済み
- [ ] 人間確認ポイント洗い出し済み
- [ ] LOCAL/PROD環境の設定ファイル準備済み

### シナリオ作成後
- [ ] ハードコード検出（年月、パス、シート名）
- [ ] 全てのOpenFileに対応するCloseFile()があるか
- [ ] エラー時のダイアログ処理が入っているか
- [ ] LOCAL環境でのテスト完了
- [ ] 完了レポート出力機能あり
- [ ] ドライランモード対応（--dry-run）
- [ ] テストモード対応（--test-mode）

---

## 19. RKSファイル操作（37シナリオ知見）

### 19.1 RKSファイルの構造

RKSファイルはZIP形式のアーカイブ。拡張子を.zipに変えて展開可能。

```
*.rks (ZIP形式)
├── Program.cs          # メインC#コード
├── meta                # メタデータ
├── id                  # 一意識別子
├── rootMeta            # ルートメタデータ
├── version             # バージョン情報
└── ExternalActivities.cs  # 外部アクティビティ
```

### 19.2 RKSファイルの編集方法（PowerShell）

```powershell
# 1. RKSをZIPとしてコピー・展開
$rksPath = "C:\path\to\scenario.rks"
$tempZip = "C:\temp\scenario.zip"
$extractDir = "C:\temp\rks_extract"

Copy-Item $rksPath $tempZip
Expand-Archive -Path $tempZip -DestinationPath $extractDir -Force

# 2. Program.csを編集
# (別途作成したProgram.csで上書き)
Copy-Item "C:\path\to\new\Program.cs" "$extractDir\Program.cs"

# 3. 再圧縮してRKSとして保存
$newRks = "C:\path\to\new_scenario.rks"
Compress-Archive -Path "$extractDir\*" -DestinationPath $tempZip -Force
Move-Item $tempZip $newRks -Force
```

### 19.3 本番/テスト版RKSの違い

| 項目 | テスト版 | 本番版 |
|------|----------|--------|
| ファイル名 | `*_dryrun.rks` | `*_PROD.rks` |
| 前処理フラグ | `--pre --dry-run` | `--pre` |
| メール送信 | `--send-mail --test-mode` | `--send-mail` |
| データソース | サンプルデータ | 実際のシステム |
| 送信先 | テストアドレス | 本番アドレス |

---

## 20. 要件定義書テンプレート（37シナリオ知見）

### 20.1 標準シート構成（10シート）

42シナリオと同じテンプレートを使用:

1. **1.概要** - 目的、背景、スコープ
2. **2.機能一覧** - 機能ID、機能名、説明、優先度
3. **3.非機能一覧** - 性能、信頼性、運用・保守要件
4. **4.既知事項** - 処理パターン、認証情報、対象データ
5. **5.データ仕様** - 入力/出力ファイル、外部データ
6. **6.外部IF・連携** - 外部システム、認証情報、ブラウザ要件
7. **7.設計方針** - コアコンセプト、処理フロー、セキュリティ
8. **8.業務フロー** - 全体フロー（事前準備→処理→完了）
9. **9.PDD詳細手順** - ファイルパス、詳細手順書
10. **Q&A確認事項** - 質問回答、納品物一覧（フルパス）

### 20.2 要件定義書作成のポイント

- **納品物フルパス**: 必ず記載（RKS、要件定義書、Python、設定ファイル）
- **入出力明確化**: どこから取得→どこに出力するか
- **処理フロー**: いつ・どこで・何が編集されるか
- **認証情報**: Windows資格情報名を明記
- **テスト/本番切替**: モード切替方法を明記

### 20.3 openpyxlでの要件定義書生成

```python
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

# スタイル定義
header_font = Font(bold=True, size=11)
thin_border = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)
header_fill = PatternFill(start_color="DAEEF3", end_color="DAEEF3", fill_type="solid")
section_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")

# テーブルスタイル適用関数
def apply_table_style(ws, start_row, headers, data):
    row = start_row
    for j, val in enumerate(headers):
        cell = ws.cell(row=row, column=j+1, value=val)
        cell.font = Font(bold=True, size=10)
        cell.border = thin_border
        cell.fill = header_fill
    row += 1
    for item in data:
        for j, val in enumerate(item):
            cell = ws.cell(row=row, column=j+1, value=val)
            cell.border = thin_border
        row += 1
    return row
```

---

## 21. ログファイル管理（37シナリオ知見）

### 21.1 ログ出力先

```
C:\ProgramData\RK10\Robots\{シナリオ名}\work\log\
├── YYYYMMDD_HHMMSS_37.log   # Python実行ログ
└── ...
```

### 21.2 RK10ログ出力

```csharp
// RK10のログ出力API
Keyence.CommentActions.LogAction.OutputUserLog("メッセージ");

// フェーズ区切りパターン
Keyence.CommentActions.LogAction.OutputUserLog("========================================");
Keyence.CommentActions.LogAction.OutputUserLog("[Phase 0] 初期化 - サイボウズデータ取得");
Keyence.CommentActions.LogAction.OutputUserLog("========================================");
```

---

## 22. 納品物チェックリスト

### 必須納品物
- [ ] 本番用RKS: `{シナリオ名}_PROD.rks`
- [ ] テスト用RKS: `{シナリオ名}_*_dryrun.rks`
- [ ] 要件定義書: `{シナリオ名}_要件定義書.xlsx`（10シート構成）
- [ ] Pythonスクリプト: `tools/main_{番号}.py`
- [ ] 設定ファイル: `config/*.json` or `config/*.xlsx`

### 要件定義書必須項目
- [ ] 概要（目的、背景、スコープ）
- [ ] 機能一覧（ID、名前、説明、優先度）
- [ ] 非機能一覧（性能、信頼性、運用）
- [ ] データ仕様（入力、出力、外部データ）
- [ ] 外部IF・連携（URL、認証、ブラウザ）
- [ ] 業務フロー（全体フロー図）
- [ ] PDD詳細手順（ファイルパス、手順）
- [ ] 納品物一覧（フルパス記載）

---

## 23. シナリオ別スケジュール・処理日

### 23.1 月次処理スケジュール

| シナリオ | 処理日 | 備考 |
|----------|--------|------|
| 42 ドライブレポート | 毎月10日 | 月次処理 |
| 43 ETC明細作成 | 利用月翌月 | ZIPダウンロード→Excel集計→PDF生成 |

### 23.2 43 ETC明細作成 知見

#### 出力先フォルダ

| 操作 | 出力先 | 設定セル |
|------|--------|----------|
| フォルダ移動 | `\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\日本情報サービス協同組合\データ` | B5 (KUMIAI_DATA_DIR) |
| PDFコピー（申請用） | `\\192.168.1.251\TIC-mainSV\経理\請求書【keiei】\{YYYY.MM月締分処理}\申請用` | B8 (KEIRI_KEIEI_DIR) |
| PDFコピー（ローカル） | `{PDF_OUT_DIR}` | B10 |

※ `{YYYY.MM月締分処理}`は処理月によって変動（例：2025.11月締分処理、2025.12月締分処理）
※ 締分処理フォルダ名は請求書PDFのファイル名から自動取得
