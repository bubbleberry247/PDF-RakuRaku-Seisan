# keyence-project

KEYENCE scenario project

## Setup

### 初回セットアップ

```bash
git clone https://github.com/bubbleberry247/keyence-project.git
cd keyence-project
```

### Git設定の確認

```bash
# ユーザー名とメールアドレスを設定（初回のみ）
git config --global user.name "your-username"
git config --global user.email "your-email@example.com"

# 設定を確認
git config --global user.name
git config --global user.email
```

## CODEX設定

このプロジェクトはVS CodeのCODEX拡張機能で使用できるように設定されています。

### 必要な環境変数

`.env`ファイルにOpenAI APIキーを設定してください：

```bash
cp .env.example .env
# .envファイルを編集してAPIキーを入力
```

### VS Code設定

`.vscode/settings.json`に以下の設定が含まれています：

- `codex.enabled`: CODEXを有効化
- `codex.model`: 使用するモデル (gpt-5.2-codex)
- `codex.autoContext`: 自動コンテキスト取得
- `codex.apiKey`: 環境変数からAPIキーを読み込み

## ファイル名文字化け修正ツール

Windowsで日本語ファイル名が文字化けした場合に使用するツールです。

### 使い方

#### 1. Mac/Linuxでファイル情報を収集

ファイル名が正常に表示される環境（Mac/Linux）で実行：

```bash
python3 collect_file_info.py
```

このスクリプトは以下の情報を含む `file_info_mapping.json` を生成します：
- 正しいファイル名（UTF-8エンコード）
- ファイルサイズ、作成日時、更新日時
- MD5ハッシュ（ファイル特定用）
- ファイルの相対パス・絶対パス

#### 2. Windowsでファイル名を修正

`file_info_mapping.json` をWindowsマシンにコピーして実行：

```bash
python fix_filenames.py
```

このスクリプトは：
- 現在のディレクトリ内のファイルを検索
- MD5ハッシュで正しいファイル名を照合
- 対話形式でファイル名をリネーム
- 自動的にバックアップを作成（`renamed_backup/` ディレクトリ）

### 主な機能

- **自動ファイル照合**: MD5ハッシュでファイルを特定
- **安全なリネーム**: リネーム前に自動バックアップ
- **対話形式**: 各ファイルを確認しながら修正
- **日本語対応**: UTF-8で正しく日本語ファイル名を扱う

### 注意事項

- `.git`, `.vscode`, `venv`, `node_modules` などのディレクトリは自動的に除外されます
- リネーム前に必ずバックアップが作成されます
- `file_info_mapping.json` は定期的に更新することを推奨します

## Git同期方法

このプロジェクトは以下のスクリプトでGitHubと簡単に同期できます。

### Mac/Linux

#### 変更をプッシュ（アップロード）

```bash
./git_push.sh "変更内容の説明"
```

例:
```bash
./git_push.sh "PDFツールを追加"
```

#### 変更をプル（ダウンロード）

```bash
./git_pull.sh
```

#### プル→プッシュを一度に実行

```bash
./git_sync.sh "変更内容の説明"
```

### 手動でGit操作する場合

```bash
# 変更をプッシュ
git add .
git commit -m "変更内容の説明"
git push origin main

# 変更をプル
git pull origin main

# 現在の状態を確認
git status
```

### Windows向けGit同期

Windows環境では以下のコマンドを使用:

```cmd
# 変更をプッシュ
cd "プロジェクトのパス"
git add .
git commit -m "変更内容の説明"
git push

# 変更をプル
cd "プロジェクトのパス"
git pull
```

### GitHub CLI（オプション）

より高度な操作にはGitHub CLIが便利です：

```bash
# インストール（Mac）
brew install gh

# 認証
gh auth login

# プルリクエストの作成
gh pr create

# イシューの確認
gh issue list
```
