# シナリオ44 担当者PC直接実行：実装計画

## 決定事項（確定）

1. **RK10不要**: 担当者PCでbat直接実行（Playwright単独）
2. **3段階bat**: OCR+リネーム → 登録 → 申請
3. **共有フォルダ（A案）**: `\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\FAX作業フォルダ`
   - ※瀬戸さん確認待ち

---

## フォルダ構成

```
\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\FAX作業フォルダ\
├─ input/       ← 処理対象PDF（担当者が移動）
├─ output/      ← リネーム済みPDF（登録batが参照）
├─ error/       ← 要修正ファイル
└─ archive/     ← 処理済み（月次アーカイブ）
```

---

## 業務フロー

```
[FAX受信] → メインSV FAXフォルダ
    ↓
[担当者] PDFを選別 → input/ に移動
    ↓
[担当者] 「1_OCRリネーム.bat」実行
    ↓ 成功→output/  エラー→error/
[担当者] error/のファイルを手動修正 → output/へ
    ↓
[担当者] 「2_楽楽登録.bat」実行
    ↓ 楽楽精算に登録完了
[担当者] 楽楽精算で内容確認・修正
    ↓ OKなら
[担当者] 「3_楽楽申請.bat」実行
    ↓ 申請完了
[自動] 処理済みPDF → archive/へ移動
```

---

## 作成ファイル一覧

### batファイル（3つ）

| ファイル | 用途 | 呼び出すPython |
|---------|------|---------------|
| `1_OCRリネーム.bat` | PDF前処理（OCR+リネーム） | `pdf_ocr_smart.py` |
| `2_楽楽登録.bat` | 楽楽精算へ登録 | `rakuraku_upload.py` |
| `3_楽楽申請.bat` | 未申請明細を申請 | `rakuraku_submit.py`（既存） |

### 設置場所

```
C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\
├─ scenario/
│   ├─ 1_OCRリネーム.bat      ← 新規作成
│   ├─ 2_楽楽登録.bat         ← 新規作成
│   └─ 申請実行.bat           ← 既存（3_楽楽申請.batにリネーム）
└─ tools/
    ├─ pdf_ocr_smart.py       ← 既存
    ├─ rakuraku_upload.py     ← 既存
    └─ rakuraku_submit.py     ← 既存
```

---

## 実装詳細

### 1. `1_OCRリネーム.bat`

```batch
@echo off
chcp 65001 >nul
cd /d "%~dp0..\tools"

echo ============================================================
echo Step 1: OCR + リネーム処理
echo ============================================================

set INPUT_DIR=\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\FAX作業フォルダ\input
set OUTPUT_DIR=\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\FAX作業フォルダ\output
set ERROR_DIR=\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\FAX作業フォルダ\error

python pdf_ocr_smart.py --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --error "%ERROR_DIR%"

if %errorlevel% neq 0 (
    echo エラーが発生しました。error/フォルダを確認してください。
)
pause
```

### 2. `2_楽楽登録.bat`

```batch
@echo off
chcp 65001 >nul
cd /d "%~dp0..\tools"

echo ============================================================
echo Step 2: 楽楽精算 登録処理
echo ============================================================

set OUTPUT_DIR=\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\FAX作業フォルダ\output

python rakuraku_upload.py --input "%OUTPUT_DIR%"

if %errorlevel% neq 0 (
    echo エラーが発生しました。
)
pause
```

### 3. `3_楽楽申請.bat`（既存の申請実行.batをリネーム）

既存の `申請実行.bat` をそのまま使用（変更不要）

---

## 担当者PC環境要件

### 必須ソフトウェア
- Python 3.11+
- Playwright（Chromium）
- 必要なPythonパッケージ

### Windows資格情報
- `楽楽精算` という名前でID/PWを登録済み

### ネットワーク
- メインSV（192.168.1.251）にアクセス可能

---

## 環境セットアップスクリプト

`setup_env.bat` を作成して、担当者PCで1回実行:

```batch
@echo off
echo 環境セットアップ開始...

REM Pythonパッケージインストール
pip install playwright openpyxl pillow opencv-python numpy

REM Playwrightブラウザインストール
playwright install chromium

echo セットアップ完了
pause
```

---

## 設定ファイル更新

### `RK10_config_PROD.xlsx` 更新項目

| 項目 | 現在値 | 新しい値 |
|-----|-------|---------|
| INPUT_DIR | （瀬戸個人フォルダ） | `\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\FAX作業フォルダ\input` |
| OUTPUT_DIR | - | `\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\FAX作業フォルダ\output` |
| ERROR_DIR | - | `\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\FAX作業フォルダ\error` |
| ARCHIVE_DIR | - | `\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\FAX作業フォルダ\archive` |

---

## 検証手順

### Step 1: フォルダ作成確認
```
dir "\\192.168.1.251\TIC-mainSV\管理部\40.一般経費用データ\FAX作業フォルダ"
```
→ input/, output/, error/, archive/ が存在すること

### Step 2: OCR+リネームテスト
1. テストPDFを input/ に配置
2. `1_OCRリネーム.bat` 実行
3. output/ にリネーム済みPDFが出力されること

### Step 3: 登録テスト（dry-run）
1. `2_楽楽登録.bat --dry-run` 実行
2. ログイン成功・フォーム入力確認（実際の登録はスキップ）

### Step 4: 申請テスト（dry-run）
1. `3_楽楽申請.bat --dry-run` 実行
2. ログイン成功・一覧画面アクセス確認

### Step 5: 本番テスト（実データ）
1. 実際のFAX PDFで全フロー実行
2. 楽楽精算画面で登録・申請が完了していることを確認

---

## リスク・注意点

1. **瀬戸さん確認待ち**: A案フォルダパスの最終確認
2. **申請ボタンセレクタ**: 実データでの検証が必要
3. **ネットワーク速度**: メインSVアクセスが遅い場合のタイムアウト調整

---

## 次のアクション

1. [ ] batファイル3つを作成
2. [ ] setup_env.bat を作成
3. [ ] RK10_config_PROD.xlsx を更新（パス確定後）
4. [ ] 担当者PCで環境セットアップ実行
5. [ ] dry-runテスト実行
6. [ ] 本番テスト実行
