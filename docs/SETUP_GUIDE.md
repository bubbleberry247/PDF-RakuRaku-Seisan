# セットアップガイド（新規PC向け）

## 前提条件

- Windows 10/11
- 管理者権限
- インターネット接続

---

## 1. Python インストール

### 推奨バージョン: Python 3.10 または 3.11
**注意: Python 3.13 は PaddleOCR との互換性問題があるため非推奨**

```powershell
# winget でインストール（推奨）
winget install Python.Python.3.11

# または公式サイトからダウンロード
# https://www.python.org/downloads/
```

インストール時に「Add Python to PATH」にチェックを入れること。

### 確認
```powershell
python --version
# Python 3.11.x と表示されればOK
```

---

## 2. 必須パッケージのインストール

```powershell
# 基本パッケージ
pip install openpyxl requests pandas beautifulsoup4 Pillow

# PDF処理
pip install PyMuPDF

# OCR関連（44PDF用）
pip install yomitoku easyocr

# ブラウザ自動化（オプション）
pip install playwright
playwright install chromium
```

### 一括インストール用コマンド
```powershell
pip install openpyxl PyMuPDF yomitoku easyocr requests pandas beautifulsoup4 Pillow
```

---

## 3. ディレクトリ構成の作成

```powershell
# ベースディレクトリ
mkdir C:\ProgramData\RK10
mkdir C:\ProgramData\RK10\Robots
mkdir C:\ProgramData\RK10\Tools

# 44PDF一般経費楽楽精算申請
mkdir "C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請"
mkdir "C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\config"
mkdir "C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools"
mkdir "C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\work"
mkdir "C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\log"
mkdir "C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data"

# 37レコル公休・有休登録
mkdir "C:\ProgramData\RK10\Robots\37レコル公休・有休登録"
mkdir "C:\ProgramData\RK10\Robots\37レコル公休・有休登録\config"
mkdir "C:\ProgramData\RK10\Robots\37レコル公休・有休登録\tools"
mkdir "C:\ProgramData\RK10\Robots\37レコル公休・有休登録\work"
mkdir "C:\ProgramData\RK10\Robots\37レコル公休・有休登録\senario"

# サンプルPDFフォルダ
mkdir "C:\ProgramData\RK10\Tools\sample PDF"
mkdir "C:\ProgramData\RK10\Tools\sample PDF\精度低い"
```

---

## 4. ソースコードの配置

### GitHubからクローン
```powershell
cd "C:\ProgramData\Generative AI"
mkdir Github
cd Github
git clone https://github.com/bubbleberry247/PDF-RakuRaku-Seisan.git
```

### ファイルのコピー（手動の場合）
以下のファイルを元PCからコピー：

| 元 | 先 |
|----|---|
| `tools/*.py` | `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\` |
| `config/*.xlsx` | `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\config\` |
| `config/env.txt` | 同上 |

---

## 5. 環境設定

### 44PDF一般経費楽楽精算申請
```powershell
# config/env.txt を作成
echo "LOCAL" > "C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\config\env.txt"
```

### 37レコル公休・有休登録
```powershell
# config/env.txt を作成
echo "ENV=LOCAL" > "C:\ProgramData\RK10\Robots\37レコル公休・有休登録\config\env.txt"
```

---

## 6. 認証情報の登録（37レコル用）

```powershell
cd "C:\ProgramData\RK10\Robots\37レコル公休・有休登録\tools"

# レコル認証情報
python register_credentials.py --recoru

# サイボウズ認証情報
python register_credentials.py --cybozu
```

プロンプトに従ってユーザー名・パスワードを入力。
認証情報はWindows資格情報マネージャーに安全に保存される。

---

## 7. 動作確認

### 44PDF OCRテスト
```powershell
cd "C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools"

# サンプルPDFでテスト（カスケードモード）
python test_sample_ocr.py --cascade --sample-dir "C:\ProgramData\RK10\Tools\sample PDF\精度低い"
# 期待結果: OK 11/13 (84.6%)
```

### 37レコル テスト
```powershell
cd "C:\ProgramData\RK10\Robots\37レコル公休・有休登録"
run_37_test.bat
```

---

## 8. 設定ファイル一覧

### 44PDF一般経費楽楽精算申請
| ファイル | 説明 |
|---------|------|
| `config/env.txt` | 環境切替（LOCAL/PROD） |
| `config/RK10_config_LOCAL.xlsx` | ローカル環境設定 |
| `config/RK10_config_PROD.xlsx` | 本番環境設定 |

### 37レコル公休・有休登録
| ファイル | 説明 |
|---------|------|
| `config/env.txt` | 環境切替（ENV=LOCAL/PROD） |
| `config/RK10_config_LOCAL.xlsx` | ローカル環境設定 |
| `config/RK10_config_PROD.xlsx` | 本番環境設定 |
| `config/dept_master.json` | 部署マスタ |
| `config/employee_master.json` | 従業員マスタ |
| `config/leave_type_mapping.json` | 休暇タイプマッピング |

---

## 9. トラブルシューティング

### YomiToku インストールエラー
```powershell
# PyTorchを先にインストール
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install yomitoku
```

### EasyOCR インストールエラー
```powershell
# 依存関係を個別インストール
pip install numpy opencv-python-headless
pip install easyocr
```

### `ModuleNotFoundError: No module named 'xxx'`
```powershell
pip install xxx
```

### OCR精度が低い場合
1. `docs/KNOWLEDGE_OCR_PREPROCESSING.md` を参照
2. 診断ログを確認: `work/ocr_debug/`
3. カスケードモード（`--cascade`）を使用

---

## 10. 参考ドキュメント

| ドキュメント | 場所 |
|-------------|------|
| 運用ガイド | `AGENTS.md` |
| OCR知見 | `docs/KNOWLEDGE_OCR_PREPROCESSING.md` |
| 引継ぎ情報 | `plans/handoff.md` |
| 決定ログ | `plans/decisions.md` |

---

## 更新履歴

- 2026-01-19: 初版作成
