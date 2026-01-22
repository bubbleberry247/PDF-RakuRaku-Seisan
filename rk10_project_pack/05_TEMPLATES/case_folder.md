# Template: ケースフォルダ構造

## 概要
RK10ロボットの標準フォルダ構造テンプレート

---

## 標準ディレクトリ構造

```
C:\ProgramData\RK10\Robots\{NN} {ロボット名}\
├── scenario/                    # RK10シナリオ
│   ├── main.rks                 # メインシナリオ
│   └── main_v2_fix.rks          # 修正版（バージョン管理）
├── tools/                       # Pythonスクリプト
│   ├── main.py                  # エントリーポイント
│   ├── scraper.py               # スクレイピング処理
│   ├── converter.py             # データ変換処理
│   └── excel_writer.py          # Excel出力処理
├── config/                      # 設定ファイル
│   ├── env.txt                  # 環境切替（PROD/LOCAL）
│   ├── RK10_config_PROD.xlsx    # 本番環境設定
│   ├── RK10_config_LOCAL.xlsx   # ローカル環境設定
│   └── master.csv               # マスタデータ
├── work/                        # 作業フォルダ（一時ファイル）
│   └── .gitkeep
├── logs/                        # ログフォルダ
│   └── .gitkeep
├── docs/                        # ドキュメント
│   ├── {ロボット名}_要件定義書.xlsx
│   ├── 運用手順書.md
│   └── エラー対応.md
└── tests/                       # テストデータ
    ├── input/                   # テスト入力
    └── expected/                # 期待出力
```

---

## フォルダ詳細

### scenario/

**用途:** RK10シナリオファイル（.rks）

**命名規則:**
- メインシナリオ: `{機能名}.rks`
- 修正版: `{機能名}_v{N}_{修正内容}.rks`

**例:**
```
scenario/
├── 43ETC_fixed.rks
├── 43ETC_fixed_v2_mailfix.rks
└── 43ETC_fixed_v3_xpath.rks
```

---

### tools/

**用途:** Pythonスクリプト

**標準ファイル:**
| ファイル | 用途 |
|----------|------|
| main.py | エントリーポイント、CLI引数処理 |
| scraper.py | Webスクレイピング処理 |
| converter.py | データ変換・整形処理 |
| excel_writer.py | Excel出力処理 |
| notification.py | 通知処理（メール等） |

---

### config/

**用途:** 設定ファイル、マスタデータ

**必須ファイル:**
| ファイル | 用途 |
|----------|------|
| env.txt | 環境切替（PROD/LOCAL） |
| RK10_config_PROD.xlsx | 本番環境設定 |
| RK10_config_LOCAL.xlsx | ローカル環境設定 |

**オプション:**
| ファイル | 用途 |
|----------|------|
| employee_master.csv | 従業員マスタ |
| account_master.csv | 科目マスタ |
| supplier_master.csv | 取引先マスタ |

---

### work/

**用途:** 作業フォルダ（一時ファイル）

**注意:**
- 処理開始時にクリーンアップ推奨
- Git管理対象外（.gitignoreに追加）
- ネットワークドライブへのコピー前の一時保存場所

---

### logs/

**用途:** ログファイル

**ログファイル命名:**
```
{ロボット名}_{YYYYMMDD}.log
{ロボット名}_{YYYYMMDD}_error.log
```

---

### docs/

**用途:** ドキュメント

**必須ドキュメント:**
| ファイル | 用途 |
|----------|------|
| {ロボット名}_要件定義書.xlsx | 要件定義書 |
| 運用手順書.md | 日常運用手順 |
| エラー対応.md | エラー発生時の対応手順 |

---

## フォルダ作成スクリプト

```python
from pathlib import Path


def create_robot_folder(robot_number: int, robot_name: str, base_path: str = None):
    """ロボットフォルダを作成

    Args:
        robot_number: ロボット番号（例: 55）
        robot_name: ロボット名（例: "15日25日末日振込Excel作成"）
        base_path: ベースパス（省略時はデフォルト）
    """
    if base_path is None:
        base_path = r"C:\ProgramData\RK10\Robots"

    folder_name = f"{robot_number} {robot_name}"
    root = Path(base_path) / folder_name

    # フォルダ構造
    folders = [
        'scenario',
        'tools',
        'config',
        'work',
        'logs',
        'docs',
        'tests/input',
        'tests/expected',
    ]

    for folder in folders:
        (root / folder).mkdir(parents=True, exist_ok=True)
        print(f"作成: {root / folder}")

    # .gitkeepを作成
    for folder in ['work', 'logs']:
        gitkeep = root / folder / '.gitkeep'
        gitkeep.touch()

    # env.txtを作成
    env_file = root / 'config' / 'env.txt'
    env_file.write_text('LOCAL', encoding='utf-8')

    print(f"\nフォルダ作成完了: {root}")
    return root


# 使用例
create_robot_folder(55, "15日25日末日振込Excel作成")
```

---

## README.md テンプレート

```markdown
# {NN} {ロボット名}

## 概要
[このロボットの目的・機能を1-2行で説明]

## 実行タイミング
- 15日/25日/末日（振込日の3営業日前）

## 前提条件
- VPN接続
- Windows資格情報マネージャーに認証情報登録済み

## 実行方法

### 本番環境
1. `config/env.txt` が `PROD` になっていることを確認
2. RK10で `scenario/main.rks` を開いて実行

### ローカル環境
1. `config/env.txt` を `LOCAL` に変更
2. RK10で `scenario/main.rks` を開いて実行

## 出力ファイル
- `\\server\share\output\{ファイル名}.xlsx`

## エラー時の対応
- `docs/エラー対応.md` を参照

## 変更履歴
| 日付 | バージョン | 変更内容 |
|------|-----------|----------|
| 2026/01/20 | 1.0 | 初版作成 |
```

---

## 運用手順書テンプレート

```markdown
# {ロボット名} 運用手順書

## 日常運用

### 実行前確認
- [ ] VPN接続確認
- [ ] 入力データの準備完了

### 実行手順
1. RK10を起動
2. `scenario/main.rks` を開く
3. 「編集しますか？」→「はい」
4. 実行ボタンをクリック
5. 完了メッセージを確認

### 実行後確認
- [ ] 出力ファイルの存在確認
- [ ] 件数・金額の照合

## 月次作業
[月次で必要な作業があれば記載]

## トラブルシューティング
[よくある問題と対処法]
```

---

## エラー対応テンプレート

```markdown
# {ロボット名} エラー対応

## エラー一覧

### E001: ログインエラー
**症状:** ログイン画面で停止
**原因:** 資格情報の期限切れ
**対処:**
1. 資格情報マネージャーを開く
2. `{資格情報名}` を更新

### E002: ファイルが見つからない
**症状:** 「ファイルが見つかりません」エラー
**原因:** 入力ファイルが準備されていない
**対処:**
1. 入力フォルダを確認
2. 必要なファイルを配置

### E003: ネットワークエラー
**症状:** タイムアウトエラー
**原因:** VPN切断、サーバーダウン
**対処:**
1. VPN接続を確認
2. 対象システムにブラウザでアクセスできるか確認
3. 問題なければリトライ
```
