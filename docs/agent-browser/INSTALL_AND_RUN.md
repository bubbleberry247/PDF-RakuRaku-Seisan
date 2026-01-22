# Agent Browser インストール・実行ガイド

## 概要

Agent Browser は Playwright ベースのブラウザ自動操作CLIツールです（v0.6.0）。
サーバー起動不要で、コマンドラインから直接ブラウザを操作できます。

---

## インストール済み環境

| 項目 | 値 |
|------|-----|
| インストール先 | `C:\ProgramData\RK10\tools\agent-browser\` |
| 実行ファイル | `agent-browser-win32-x64.exe` |
| バージョン | 0.6.0 |
| Playwrightブラウザ | `pw-browsers\` |

---

## 環境変数

| 変数名 | 説明 | 設定値 |
|--------|------|--------|
| `AGENT_BROWSER_HOME` | デーモン(JS版)用distパス | `C:\ProgramData\RK10\tools\agent-browser\app\agent-browser\agent-browser` |
| `PLAYWRIGHT_BROWSERS_PATH` | Playwrightブラウザパス | `C:\ProgramData\RK10\tools\agent-browser\pw-browsers` |
| `AGENT_BROWSER_SESSION` | セッション名（オプション） | 任意の文字列 |

---

## 基本コマンド

### バージョン確認
```cmd
agent-browser-win32-x64.exe --version
```

### ヘルプ表示
```cmd
agent-browser-win32-x64.exe --help
```

---

## 主要コマンド一覧

| コマンド | 説明 | 例 |
|----------|------|-----|
| `open <url>` | URLを開く | `open https://example.com` |
| `click <selector>` | 要素をクリック | `click "button#submit"` |
| `fill <selector> <text>` | 入力欄に値を入力 | `fill "#email" "test@example.com"` |
| `type <selector> <text>` | キーボード入力 | `type "#search" "keyword"` |
| `snapshot` | DOM構造のスナップショット | `snapshot -c` (コンパクト) |
| `screenshot` | スクリーンショット保存 | `screenshot output.png` |
| `pdf` | PDFとして保存 | `pdf output.pdf` |
| `wait <ms>` | 待機 | `wait 1000` |
| `close` | ブラウザを閉じる | `close` |

### スナップショットオプション

| オプション | 説明 |
|------------|------|
| `-i` | インタラクティブモード |
| `-c` | コンパクト出力 |
| `-d <n>` | 深さ指定 |

---

## セッション管理

複数のコマンドを同じブラウザセッションで実行する場合:

```cmd
rem セッション名を指定して実行
agent-browser-win32-x64.exe --session my-session open https://example.com
agent-browser-win32-x64.exe --session my-session click "#login"
agent-browser-win32-x64.exe --session my-session fill "#email" "test@example.com"
```

または環境変数で設定:
```cmd
set AGENT_BROWSER_SESSION=my-session
agent-browser-win32-x64.exe open https://example.com
```

---

## Chrome DevTools Protocol (CDP) 接続

既存のChromeに接続する場合:

```cmd
rem Chromeをリモートデバッグモードで起動
chrome.exe --remote-debugging-port=9222

rem Agent Browserから接続
agent-browser-win32-x64.exe --cdp 9222 snapshot
rem または
agent-browser-win32-x64.exe connect 9222
```

---

## ヘルパースクリプト

本リポジトリに用意されたスクリプト:

| スクリプト | 場所 | 用途 |
|-----------|------|------|
| `check_version.cmd` | `tools/agent-browser/` | バージョン確認 |
| `print_help.cmd` | `tools/agent-browser/` | ヘルプ表示 |
| `run_demo.cmd` | `tools/agent-browser/` | デモ実行（URL開く→スナップショット→スクリーンショット） |

---

## 実行例

### 例1: Webページを開いてスクリーンショット取得

```cmd
set ROOT=C:\ProgramData\RK10\tools\agent-browser
set EXE=%ROOT%\agent-browser-win32-x64.exe

%EXE% --session test open https://www.google.com
%EXE% --session test screenshot google.png
%EXE% --session test close
```

### 例2: ログインフォームの自動入力

```cmd
%EXE% --session login open https://example.com/login
%EXE% --session login fill "#username" "myuser"
%EXE% --session login fill "#password" "mypass"
%EXE% --session login click "#submit"
%EXE% --session login wait 2000
%EXE% --session login screenshot after_login.png
```

---

## トラブルシューティング

### 問題: コマンドが応答しない
**解決**: `PLAYWRIGHT_BROWSERS_PATH` が正しく設定されているか確認

### 問題: ブラウザが起動しない
**解決**: `pw-browsers` フォルダにChromiumがインストールされているか確認

### 問題: セッションが見つからない
**解決**: 同じ `--session` 名を使用しているか確認

---

## 参照

- 元のラッパースクリプト: `C:\ProgramData\RK10\tools\agent-browser\run_agent_browser.cmd`
- Playwright公式: https://playwright.dev/
