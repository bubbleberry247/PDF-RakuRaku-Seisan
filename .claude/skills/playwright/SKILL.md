# Playwright MCP + Skill ハイブリッド運用

## 概要
ブラウザ自動化シナリオ開発で Playwright MCP と Skill を併用

---

## 使い分け

| フェーズ | ツール | 目的 |
|---------|--------|------|
| 調査 | **MCP** | 画面構造把握、セレクタ特定、DOM探索 |
| 開発 | **MCP** | リアルタイム動作確認、デバッグ |
| テンプレ化 | **Skill** | 成功パターンをこのファイルに記録 |
| 量産 | **Skill** | 類似処理を高速生成 |

---

## MCP使用方法

### インストール済み
```bash
npm install -g @playwright/mcp@latest
```

### MCP設定（claude_desktop_config.json）
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

### 主要MCPツール
| ツール | 用途 |
|--------|------|
| `browser_navigate` | URLへ遷移 |
| `browser_click` | 要素クリック |
| `browser_type` | テキスト入力 |
| `browser_snapshot` | DOM構造取得 |
| `browser_take_screenshot` | スクリーンショット |

---

## よく使うパターン（Skill）

### 1. 楽楽精算ログイン
```python
# Python (playwright) テンプレート
async def login_rakuraku(page, company_code, user_id, password):
    await page.goto("https://id.rakurakuseisan.jp/")
    await page.fill('input[name="company_code"]', company_code)
    await page.fill('input[name="user_id"]', user_id)
    await page.fill('input[name="password"]', password)
    await page.click('button[type="submit"]')
    await page.wait_for_load_state("networkidle")
```

### 2. テーブルデータ取得
```python
async def get_table_data(page, table_selector):
    rows = await page.query_selector_all(f"{table_selector} tr")
    data = []
    for row in rows:
        cells = await row.query_selector_all("td")
        row_data = [await cell.inner_text() for cell in cells]
        data.append(row_data)
    return data
```

### 3. ファイルダウンロード待機
```python
async def download_file(page, click_selector, download_dir):
    async with page.expect_download() as download_info:
        await page.click(click_selector)
    download = await download_info.value
    path = os.path.join(download_dir, download.suggested_filename)
    await download.save_as(path)
    return path
```

### 4. セレクタ探索（MCP調査結果から）
```python
# よく使うセレクタパターン
SELECTORS = {
    "rakuraku_login_btn": 'button[type="submit"]',
    "rakuraku_menu": '.main-menu',
    "rakuraku_expense_list": 'table.expense-list',
    # 追加していく
}
```

---

## RK10シナリオへの変換

### Playwright → Keyence C# 変換表
| Playwright | Keyence C# |
|------------|------------|
| `page.goto(url)` | `Keyence.BrowserActions.BrowserAction.Navigate(url)` |
| `page.click(selector)` | `Keyence.BrowserActions.BrowserAction.Click(selector)` |
| `page.fill(selector, text)` | `Keyence.BrowserActions.BrowserAction.Type(selector, text)` |
| `page.wait_for_selector()` | `Keyence.BrowserActions.BrowserAction.WaitForElement()` |

---

## トラブルシューティング

### 問題1: MCP接続エラー
```
Error: Could not connect to browser
```
**解決**: Chromiumが起動していることを確認

### 問題2: セレクタが見つからない
**解決**: `browser_snapshot` でDOM構造を確認し、正しいセレクタを特定

### 問題3: タイムアウト
**解決**: `wait_for_load_state("networkidle")` を追加

---

## 客先への影響

**重要**: 客先はClaude有料課金不要
- 開発時のみClaude + MCP使用
- 本番環境は生成済みPythonスクリプト実行のみ
- AIなしで動作可能

---

## 対象シナリオ

| シナリオ | ブラウザ操作 | 適用度 |
|---------|-------------|--------|
| 51&52 ソフトバンク楽楽精算 | 楽楽精算申請 | ★★★ |
| 37 レコル公休・有休登録 | レコル打刻・申請 | ★★★ |
| 42 ドライブレポート抽出 | Google Drive操作 | ★★ |

---

## 更新履歴

- 2026-01-24: 初版作成（MCP + Skill ハイブリッド運用開始）
