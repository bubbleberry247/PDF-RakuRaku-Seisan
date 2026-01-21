# 共通ツール（common/tools）

## 概要

プロジェクト横断で使用する汎用ツール集。

## ツール一覧

### ファイル名修正ツール（external-repos/keyence-project/tools/）

日本語ファイル名の文字化け修正用。

| ファイル | 用途 |
|----------|------|
| `collect_file_info.py` | Mac/Linuxで正しいファイル名を収集 |
| `fix_filenames.py` | WindowsでMD5ハッシュ照合してリネーム |

**使い方**:
1. Mac/Linuxで `collect_file_info.py` 実行 → `file_info_mapping.json` 生成
2. Windowsに `file_info_mapping.json` をコピー
3. `fix_filenames.py` でリネーム

## 追加予定

必要に応じて以下のカテゴリでツールを追加:

```
common/tools/
├─ README.md
├─ file_utils/      # ファイル操作関連
├─ date_utils/      # 日付操作関連
├─ excel_utils/     # Excel操作関連
└─ notification/    # 通知関連
```
