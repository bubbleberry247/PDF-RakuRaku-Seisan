# FORClaude.md - PDF-RakuRaku-Seisan プロジェクト解説

このファイルは、Claude Codeがこのプロジェクトを理解するための詳細な説明書です。

---

## プロジェクト概要

**名前**: PDF-RakuRaku-Seisan（PDF楽楽精算）

**目的**: KEYENCE RK-10 RPAを使用して、請求書PDF処理から楽楽精算への経費申請を自動化する

**主な対象業務**:
- ソフトバンク携帯電話請求の部門別集計・申請（シナリオ51&52）
- 一般経費PDFのOCR処理・申請（シナリオ44）
- レコル勤怠の公休・有休登録（シナリオ37）
- ドライブレポート抽出（シナリオ42）

---

## アーキテクチャ

```
[RK-10 シナリオ (.rks)]
        │
        ▼
[Python スクリプト]
        │
        ├─→ Playwright（ブラウザ自動操作）
        ├─→ OpenCV/OCR（PDF画像処理）
        └─→ openpyxl（Excel操作）
        │
        ▼
[楽楽精算 Web システム]
```

### 技術スタック
| レイヤー | 技術 |
|---------|------|
| RPA | KEYENCE RK-10（C#ベース） |
| スクリプト | Python 3.11+ |
| ブラウザ自動化 | Playwright（Edge） |
| OCR | EasyOCR, yomitoku |
| Excel | openpyxl |
| PDF | PyMuPDF, pdf2image |

---

## ディレクトリ構造

```
C:\ProgramData\RK10\Robots\
├── 37レコル公休・有休登録\        # シナリオ37
├── 42ドライブレポート抽出作業\    # シナリオ42
├── 44PDF一般経費楽楽精算申請\     # シナリオ44
├── 51&52ソフトバンク部門集計楽楽精算申請\  # シナリオ51&52（メイン）
│   ├── scenario\                  # .rksファイル
│   ├── config\                    # 設定ファイル
│   │   ├── env.txt               # 環境（PROD/LOCAL）
│   │   ├── RK10_config_PROD.xlsx # 本番設定
│   │   ├── RK10_config_LOCAL.xlsx# 開発設定
│   │   ├── department_master.csv # 部門マスタ
│   │   └── phone_master.csv      # 電話番号マスタ
│   ├── tools\                     # Pythonスクリプト
│   │   ├── main_51.py            # Part 1-3 統合
│   │   ├── main_52.py            # Part 4-5 統合
│   │   ├── softbank_scraper.py   # SoftBankサイトスクレイピング
│   │   ├── excel_processor.py    # Excel集計・PDF出力
│   │   ├── rakuraku_receipt.py   # 楽楽精算 領収書登録
│   │   ├── rakuraku_payment.py   # 楽楽精算 支払依頼申請
│   │   └── eisei_pdf_processor.py# 郵送PDF処理
│   └── data\                      # 作業データ
│       ├── csv\                   # ダウンロードCSV
│       ├── excel\                 # 集計Excel
│       └── pdf\                   # 出力PDF
```

---

## シナリオ51&52 詳細（ソフトバンク部門集計）

### 処理フロー

```
Part 1: SoftBank CSV ダウンロード
    │   └─ softbank_scraper.py
    ▼
Part 2: Excel シート作成・集計
    │   └─ excel_processor.py
    ▼
Part 3: PDF 出力
    │   └─ excel_processor.py
    ▼
Part 3.5: 郵送PDF処理（営繕営業部用）
    │   └─ eisei_pdf_processor.py
    ▼
Part 4: 楽楽精算 領収書登録
    │   └─ rakuraku_receipt.py
    ▼
Part 5: 楽楽精算 支払依頼申請
        └─ rakuraku_payment.py
```

### 部門と金額の流れ

| 部門 | 処理 |
|------|------|
| 営業部 | CSV → Excel → PDF → 楽楽精算 |
| 業務部 | CSV → Excel → PDF → 楽楽精算 |
| 技術部 | CSV → Excel → PDF → 楽楽精算 |
| 管理部 | CSV → Excel → PDF → 楽楽精算 |
| 営繕営業部 | CSV + 郵送PDF → Excel → PDF → 楽楽精算 |

---

## 設定ファイル

### env.txt
```
PROD   # 本番環境
LOCAL  # 開発環境
```

### RK10_config_*.xlsx
| セル | 項目 | 例 |
|------|------|-----|
| B2 | ENV | PROD/LOCAL |
| B3 | ROOT_DIR | \\\\server\\share |
| B4 | MAIL_TO | kanri.tic@tokai-ic.co.jp |

---

## .rksファイル編集

.rksファイルはZIP形式。編集対象は`Program.cs`のみ。

```python
import zipfile

# 読み込み
with zipfile.ZipFile('scenario.rks', 'r') as z:
    code = z.read('Program.cs').decode('utf-8-sig')

# 修正
modified_code = code.replace('old', 'new')

# 書き込み
with zipfile.ZipFile('scenario.rks', 'r') as src:
    with zipfile.ZipFile('modified.rks', 'w') as dst:
        for item in src.namelist():
            if item == 'Program.cs':
                dst.writestr(item, modified_code.encode('utf-8-sig'))
            else:
                dst.writestr(item, src.read(item))
```

---

## 重要なルール

1. **ブラウザはEdge**（Chrome禁止）
2. **LOCALモックパス**: `C:\RK10_MOCK`（`C:\Work`禁止）
3. **完了通知メール**: `kanri.tic@tokai-ic.co.jp`
4. **質問への回答 > 状況報告 > ツール実行**（優先順位）

---

## よくあるエラーと解決策

| エラー | 原因 | 解決策 |
|--------|------|--------|
| CS1010 定数の新しい行 | 文字列内に実改行 | MessageBox.Showを1行に |
| ボタンが見つかりません | CSSセレクタ変更 | `a.button-*`形式に |
| OCR信頼度不足 | 画像品質 | DPI調整、yomitoku使用 |

---

## 関連ドキュメント

- `AGENTS.md`: 運用ルール正本
- `plans/decisions.md`: 決定ログ
- `plans/handoff.md`: セッション引継ぎ
- `.claude/skills/`: ドメイン知識スキル

---

*最終更新: 2026-01-25*
