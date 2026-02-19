---
name: bw-pw-cli-prototype
description: |
  Playwright CLIを使ってフロー作成を高速化し、生成コードを「壊れにくい形」に落とし込む。
  利用は作成フェーズ中心。保守性（locator方針・待機方針）を最優先。

  トリガー: Playwright, CLI, コードジェネレータ, 自動生成, codegen, 探索, プロトタイプ
disable-model-invocation: true
argument-hint: "[flow-name] [target-url]"
---

# bw-pw-cli-prototype

## Purpose（目的）

Playwright CLI (`npx playwright codegen`) を活用して、RPAフローの作成を高速化し、生成コードを保守しやすい形に整形する。

**目標**:
- 初期プロトタイプ作成の時間短縮（手動コーディング不要）
- 生成コードの保守性向上（locator/待機の標準化）
- 探索的開発の効率化（UI構造の把握）

## When to Use（いつ使う）

- 新しいWebアプリのRPAフローを作成開始する時
- UI構造を探索して適切なセレクタを特定したい時
- 手動コーディングの前に概要フローを確認したい時
- 既存フローのリファクタリング時（セレクタ見直し）

## Inputs / Outputs

**Inputs**:
- Flow name（例: `rakuraku-expense-approval`）
- Target URL（例: `https://id.rakurakuseisan.jp/`）

**Outputs**:
- 生成された操作コード（TypeScript）
- 整形されたlocatorと待機ロジック
- プロトタイプから本実装への変換手順

## CLI Workflow（CLI作業フロー）

### Phase 1: 探索（Explore）

```bash
# ブラウザを起動して手動操作
npx playwright codegen https://id.rakurakuseisan.jp/

# 自動で操作が記録される
# - クリック
# - 入力
# - ナビゲーション
```

**やること**:
1. ログイン操作を実行
2. 主要な画面遷移を確認
3. データ入力フォームを探索
4. 画面スナップショット

**やらないこと**:
- 例外処理の実装（CLI生成コードには含まれない）
- ループや条件分岐（後で手動追加）
- 資格情報の入力（ダミーで代用）

### Phase 2: コード生成

CLIが自動的にTypeScriptコードを生成。

**生成コード例**:
```typescript
import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('https://id.rakurakuseisan.jp/');
  await page.getByPlaceholder('会社コード').click();
  await page.getByPlaceholder('会社コード').fill('12345');
  await page.getByPlaceholder('ユーザーID').click();
  await page.getByPlaceholder('ユーザーID').fill('user01');
  await page.getByPlaceholder('パスワード').click();
  await page.getByPlaceholder('パスワード').fill('password');
  await page.getByRole('button', { name: 'ログイン' }).click();
});
```

### Phase 3: コード整形（CLIコード → 本実装）

**整形ルール**:

1. **Locator優先順位の適用**:
   - `data-testid` > `role` > `label` > `placeholder` > `id` > `class`
   - XPath は禁止

2. **待機ロジックの追加**:
   ```typescript
   // Before (CLI生成)
   await page.getByRole('button', { name: 'ログイン' }).click();
   await page.getByText('ホーム').click();

   // After (整形後)
   await page.getByRole('button', { name: 'ログイン' }).click();
   await page.waitForURL(/\/home/); // 画面遷移待機
   await page.getByText('ホーム').click();
   ```

3. **証跡統合**:
   ```typescript
   // Before
   await page.goto('https://...');

   // After
   collector.logStep('STEP-1', 'Starting login');
   await page.goto('https://...');
   await page.screenshot({ path: `screenshots/step-1.png` }); // デバッグ時
   collector.logStep('STEP-1', 'Login page loaded');
   ```

4. **資格情報の外部化**:
   ```typescript
   // Before (ハードコード)
   await page.fill('input[name="password"]', 'password');

   // After (環境変数/config)
   await page.fill('input[name="password"]', process.env.RAKURAKU_PASSWORD);
   ```

5. **エラーハンドリング**:
   ```typescript
   // Before
   await page.click('button[type="submit"]');

   // After
   try {
     await page.click('button[type="submit"]', { timeout: 5000 });
   } catch (error) {
     await collector.captureError(error);
     throw new Error(`Login button not found: ${error.message}`);
   }
   ```

## Locator Policy（セレクタ方針）

### 優先順位（高 → 低）

| 順位 | セレクタ | 例 | 安定性 | 備考 |
|------|---------|-----|--------|------|
| 1 | `data-testid` | `page.getByTestId('login-btn')` | ★★★★★ | 最優先（UI変更に強い） |
| 2 | `role` | `page.getByRole('button', { name: 'ログイン' })` | ★★★★ | セマンティック |
| 3 | `label` | `page.getByLabel('会社コード')` | ★★★★ | フォーム向き |
| 4 | `placeholder` | `page.getByPlaceholder('会社コード')` | ★★★ | label無い場合 |
| 5 | `id` | `page.locator('#login-btn')` | ★★ | 動的IDに注意 |
| 6 | `class` | `page.locator('.btn-primary')` | ★ | UI変更で壊れやすい |
| ✗ | XPath | `page.locator('//button[@type="submit"]')` | - | **禁止** |

### Locator選定の判断基準

**良い例**:
```typescript
// 1. data-testid優先（アプリ側で付与されている場合）
await page.getByTestId('expense-submit-btn').click();

// 2. role + name（セマンティック）
await page.getByRole('button', { name: '申請する' }).click();

// 3. label（フォーム）
await page.getByLabel('金額').fill('10000');
```

**悪い例**:
```typescript
// ✗ class名依存（UI変更で壊れる）
await page.locator('.btn-primary.btn-lg').click();

// ✗ 複雑なCSSセレクタ（保守困難）
await page.locator('div.container > div:nth-child(2) > button').click();

// ✗ XPath（可読性・保守性が低い）
await page.locator('//div[@class="form"]//button[@type="submit"]').click();
```

## Wait Strategy（待機方針）

### 基本方針

**自動待機を信頼しつつ、明示的待機を追加**:

```typescript
// 1. Navigation後は必ず waitForURL
await page.click('a[href="/expenses"]');
await page.waitForURL(/\/expenses/);

// 2. API呼び出し後は waitForResponse
const responsePromise = page.waitForResponse(res =>
  res.url().includes('/api/expenses') && res.status() === 200
);
await page.click('button[type="submit"]');
await responsePromise;

// 3. 動的コンテンツは waitForSelector
await page.waitForSelector('table.expense-list');

// 4. ネットワークアイドル待機（最終手段）
await page.waitForLoadState('networkidle');
```

### タイムアウト設定

```typescript
// Default: 30秒
// 楽楽精算など遅いSaaSは延長
const context = await browser.newContext({
  timeout: 60000, // 60秒
});

// 個別操作のタイムアウト
await page.click('button', { timeout: 10000 }); // 10秒
```

## Instructions（実装手順）

### 1. CLIでプロトタイプ作成

```bash
# コマンド
npx playwright codegen --target typescript \
  --output prototypes/rakuraku-expense.spec.ts \
  https://id.rakurakuseisan.jp/

# 操作を記録
# - ログイン
# - 経費申請画面へ遷移
# - データ入力
# - 申請ボタンクリック

# Ctrl+C で記録終了
```

### 2. 生成コードのレビュー

```typescript
// prototypes/rakuraku-expense.spec.ts を開く
// - Locatorの種類を確認
// - 待機ロジックの不足を確認
// - ハードコードされた値を確認
```

### 3. 本実装への変換

```bash
# 新しいファイル作成
cp prototypes/rakuraku-expense.spec.ts src/flows/rakuraku-expense.ts
```

```typescript
// src/flows/rakuraku-expense.ts

import { Page } from '@playwright/test';
import { EvidenceCollector } from '../evidence/collector';

export async function rakurakuExpenseApproval(
  page: Page,
  collector: EvidenceCollector,
  data: { companyCode: string; userId: string; password: string }
) {
  // STEP 1: ログイン
  collector.logStep('STEP-1', 'Starting login');
  await page.goto('https://id.rakurakuseisan.jp/');

  await page.getByLabel('会社コード').fill(data.companyCode);
  await page.getByLabel('ユーザーID').fill(data.userId);
  await page.getByLabel('パスワード').fill(data.password);

  await page.getByRole('button', { name: 'ログイン' }).click();
  await page.waitForURL(/\/home/);

  collector.logStep('STEP-1', 'Login completed');

  // STEP 2: 経費申請
  collector.logStep('STEP-2', 'Creating expense');
  await page.getByRole('link', { name: '経費申請' }).click();
  await page.waitForURL(/\/expenses\/new/);

  // ... 以下続く
}
```

### 4. 例外処理の追加

```typescript
try {
  await rakurakuExpenseApproval(page, collector, credentials);
} catch (error) {
  await collector.captureError(error);
  await page.screenshot({ path: `screenshots/error.png` });
  throw error;
}
```

### 5. テスト実行

```bash
# Dry-run（本番データ使わない）
npm run test:dry-run

# 本実行
npm run flow:rakuraku-expense
```

## Examples（使用例）

### Example 1: 楽楽精算ログインフロー

**CLI生成コード**:
```typescript
await page.goto('https://id.rakurakuseisan.jp/');
await page.getByPlaceholder('会社コード').fill('12345');
await page.getByPlaceholder('ユーザーID').fill('user01');
await page.getByPlaceholder('パスワード').fill('password');
await page.getByRole('button', { name: 'ログイン' }).click();
```

**整形後**:
```typescript
async function login(page: Page, config: Config) {
  await page.goto('https://id.rakurakuseisan.jp/');

  // Locator: placeholder → label に変更（より安定）
  await page.getByLabel('会社コード').fill(config.companyCode);
  await page.getByLabel('ユーザーID').fill(config.userId);
  await page.getByLabel('パスワード').fill(config.password);

  // 待機: クリック後のURL遷移を待つ
  await page.getByRole('button', { name: 'ログイン' }).click();
  await page.waitForURL(/\/home/);

  // エラーチェック: ログイン失敗時のメッセージ
  const errorMsg = await page.locator('.error-message').textContent().catch(() => null);
  if (errorMsg) {
    throw new Error(`Login failed: ${errorMsg}`);
  }
}
```

### Example 2: フォーム入力フロー

**CLI生成コード**:
```typescript
await page.locator('#expense-date').fill('2026-02-14');
await page.locator('#expense-amount').fill('10000');
await page.locator('#expense-description').fill('交通費');
await page.locator('button.submit').click();
```

**整形後**:
```typescript
async function submitExpense(page: Page, expense: Expense) {
  // Locator: id → label （より保守しやすい）
  await page.getByLabel('日付').fill(expense.date);
  await page.getByLabel('金額').fill(String(expense.amount));
  await page.getByLabel('摘要').fill(expense.description);

  // 待機: API送信完了を待つ
  const responsePromise = page.waitForResponse(res =>
    res.url().includes('/api/expenses') && res.status() === 201
  );

  await page.getByRole('button', { name: '申請する' }).click();
  const response = await responsePromise;

  // レスポンス確認
  const result = await response.json();
  return result.expenseId;
}
```

## Troubleshooting（トラブルシューティング）

### 問題1: CLIが起動しない

**原因**: Playwrightがインストールされていない

**解決**:
```bash
npm install -D @playwright/test
npx playwright install chromium
```

### 問題2: 生成コードが動かない

**原因**: 動的なセレクタ（IDが毎回変わる等）

**解決**:
- `data-testid` の追加をフロントエンドチームに依頼
- または `role` / `label` で代替

### 問題3: 資格情報が記録に残る

**対応**:
- 生成ファイルから削除
- `.gitignore` に `prototypes/` を追加
- 環境変数/config に移行

### 問題4: 待機時間が不足

**原因**: SaaSが遅い、ネットワーク遅延

**解決**:
```typescript
// タイムアウト延長
await page.click('button', { timeout: 60000 }); // 60秒

// または networkidle
await page.waitForLoadState('networkidle');
```

### 問題5: 生成コードが長すぎる

**対応**:
- 複数のフローに分割
- 共通操作を関数化（login, logout等）

## References

- [Playwright CLI公式ドキュメント](https://playwright.dev/docs/codegen)
- [Locator方針](references/locator-policy.md)
- [フロー雛形](examples/flow-skeleton.ts)
