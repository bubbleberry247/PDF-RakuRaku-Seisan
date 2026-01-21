# Windows セットアップ手順

## 1. リポジトリをクローン

PowerShellを開いて実行:

```powershell
cd C:\Users\okamac\Documents
git clone https://github.com/bubbleberry247/my-claude-skills.git
```

## 2. Git設定（初回のみ）

```powershell
git config --global user.name "bubbleberry247"
git config --global user.email "kalimistk@gmail.com"
```

## 3. VSCode設定

### 方法1: VSCode UIから設定（推奨）

1. VSCodeを開く
2. `Ctrl + Shift + P` を押してコマンドパレットを開く
3. `Preferences: Open User Settings (JSON)` を検索して選択
4. 開いた `settings.json` に以下を追加:

```json
{
  "claudeCode.binaryPath": "C:\\Users\\okamac\\.local\\bin\\claude.exe",
  "claude.skills.paths": [
    "C:\\Users\\okamac\\Documents\\my-claude-skills"
  ]
}
```

**既に他の設定がある場合は、カンマで区切って追加:**

```json
{
  "editor.fontSize": 22,
  "claudeCode.binaryPath": "C:\\Users\\okamac\\.local\\bin\\claude.exe",
  "claude.skills.paths": [
    "C:\\Users\\okamac\\Documents\\my-claude-skills"
  ]
}
```

5. ファイルを保存（`Ctrl + S`）
6. VSCodeを再起動

### 方法2: 直接ファイルを編集

**場所:** `C:\Users\okamac\AppData\Roaming\Code\User\settings.json`

エクスプローラーのアドレスバーに以下を貼り付けて開く:

```
%APPDATA%\Code\User
```

`settings.json` を開いて上記の設定を追加。

## 4. 動作確認

設定が正しく反映されているか確認:

```powershell
# パスが存在するか確認
Test-Path "C:\Users\okamac\Documents\my-claude-skills"
# → True と表示されればOK

# スキルファイルが存在するか確認
Test-Path "C:\Users\okamac\Documents\my-claude-skills\rk10-scenario\skill.md"
# → True と表示されればOK
```

## 5. 使用方法

### Claude Codeで使う

VSCodeでClaude Codeを開き、以下を入力:

```
/rk10-scenario
```

または単に:

```
次のRK10シナリオを作成してください
```

### スキルが認識されているか確認

Claude Codeで以下を入力:

```
利用可能なスキルを教えて
```

`rk10-scenario` が表示されればOK。

## 6. 更新方法

Macで更新した内容をWindowsに反映する:

```powershell
cd C:\Users\okamac\Documents\my-claude-skills
git pull
```

## 7. 初回セットアップ完全版（コピペ用）

PowerShellで以下を順番に実行:

```powershell
# 1. ホームディレクトリに移動
cd C:\Users\okamac\Documents

# 2. リポジトリをクローン
git clone https://github.com/bubbleberry247/my-claude-skills.git

# 3. Git設定
git config --global user.name "bubbleberry247"
git config --global user.email "kalimistk@gmail.com"

# 4. パスを確認
Test-Path "C:\Users\okamac\Documents\my-claude-skills"
Test-Path "C:\Users\okamac\Documents\my-claude-skills\rk10-scenario\skill.md"

# 5. VSCode設定ファイルの場所を開く
explorer "%APPDATA%\Code\User"
```

最後のコマンドでエクスプローラーが開くので、`settings.json` を編集して以下を追加:

```json
{
  "claude.skills.paths": [
    "C:\\Users\\okamac\\Documents\\my-claude-skills"
  ]
}
```

VSCodeを再起動して完了！

## トラブルシューティング

### 認証エラーが出る場合

1. Personal Access Tokenを作成: https://github.com/settings/tokens
2. 権限: `repo` にチェック
3. クローン時にトークンを使用:

```powershell
git clone https://bubbleberry247:<YOUR_TOKEN>@github.com/bubbleberry247/my-claude-skills.git
```

### スキルが認識されない場合

1. VSCodeを再起動
2. `claude.skills.paths` が正しく設定されているか確認
3. パスが実際に存在するか確認:

```powershell
Test-Path "C:\Users\okamac\Documents\my-claude-skills"
```
