# Locator Policy（セレクタ方針詳細）

Playwright RPAフローで使用するセレクタの選定方針。保守性を最優先。

---

## 基本原則

1. **保守性 > 簡潔性**: コードが長くなっても、UI変更に強いセレクタを選ぶ
2. **セマンティック優先**: 意味のあるセレクタ（role, label）を優先
3. **XPath禁止**: 可読性・保守性が低いため使用禁止
4. **複数セレクタのフォールバック**: 1つのセレクタに依存しない

---

## 優先順位（1 → 6）

### 1. data-testid（最優先）

**使用例**:
```typescript
await page.getByTestId('login-submit-btn').click();
await page.getByTestId('expense-amount-input').fill('10000');
```

**長所**:
- UI変更（デザイン、class名変更）に強い
- 明示的なテスト用識別子
- 最も安定

**短所**:
- フロントエンドチームが付与する必要あり
- 既存アプリには存在しないことが多い

**推奨**:
- 新規開発時は必ず `data-testid` を付与するよう依頼
- RPA対象アプリに追加してもらう（工数<1日）

---

### 2. role + name（セマンティック）

**使用例**:
```typescript
await page.getByRole('button', { name: 'ログイン' }).click();
await page.getByRole('link', { name: '経費申請' }).click();
await page.getByRole('textbox', { name: '金額' }).fill('10000');
```

**長所**:
- セマンティックで可読性が高い
- WAI-ARIA roleに基づく（アクセシビリティと両立）
- UI変更に比較的強い

**短所**:
- ボタン/リンクのテキストが変わると壊れる
- テキストが動的に変わる場合は使えない

**推奨**:
- ボタン/リンク/フォームコントロールに優先的に使用
- テキストが固定の場合のみ

---

### 3. label（フォーム向き）

**使用例**:
```typescript
await page.getByLabel('会社コード').fill('12345');
await page.getByLabel('ユーザーID').fill('user01');
await page.getByLabel('パスワード').fill('password');
```

**長所**:
- フォームで直感的
- label要素と紐付くため安定

**短所**:
- label要素がない場合は使えない
- labelテキストが変わると壊れる

**推奨**:
- フォーム入力で label 要素がある場合

---

### 4. placeholder（label代替）

**使用例**:
```typescript
await page.getByPlaceholder('会社コードを入力').fill('12345');
```

**長所**:
- label要素がない場合の代替
- 視覚的にわかりやすい

**短所**:
- placeholderテキストが変わると壊れる
- placeholderがない場合は使えない

**推奨**:
- label要素がない場合の次善策

---

### 5. id（動的IDに注意）

**使用例**:
```typescript
await page.locator('#login-btn').click();
await page.locator('#expense-amount').fill('10000');
```

**長所**:
- 一意性が保証される（HTML仕様）
- シンプル

**短所**:
- 動的ID（`id="field-12345-abc"`）は不安定
- UI変更でidが変わる可能性あり

**推奨**:
- 静的id（`id="login-btn"`）のみ使用
- 動的id（UUIDや連番含む）は避ける

**判定方法**:
```typescript
// Good: 静的id
#login-btn
#submit-button
#main-content

// Bad: 動的id（使用禁止）
#field-abc123-def456
#component-1234
#react-select-5
```

---

### 6. class（最終手段）

**使用例**:
```typescript
await page.locator('.btn-primary').click();
```

**長所**:
- 広く使われている

**短所**:
- UI変更（デザイン変更）で class 名が変わりやすい
- 複数要素に同じclassが使われる（一意性なし）

**推奨**:
- 他のセレクタが使えない場合の最終手段
- 必ず `.first()` または `.nth(0)` で一意に特定

**使用禁止パターン**:
```typescript
// ✗ Bad: 複雑なCSSセレクタ（保守困難）
await page.locator('div.container > div:nth-child(2) > button.btn-primary').click();

// ✓ Good: シンプルなclass + first()
await page.locator('.btn-primary').first().click();
```

---

## XPath禁止（使用厳禁）

**NG例**:
```typescript
// ✗ 使用禁止
await page.locator('//div[@class="form"]//button[@type="submit"]').click();
```

**理由**:
- 可読性が低い
- 保守性が低い
- PlaywrightはCSSセレクタとセマンティックセレクタを推奨

**代替案**:
```typescript
// ✓ Good
await page.getByRole('button', { name: '送信' }).click();
```

---

## 複数セレクタのフォールバック

1つのセレクタに依存せず、複数を順に試行。

**実装例**:
```typescript
async function clickLoginButton(page: Page) {
  // 優先順位: testid > role > id > class
  const selectors = [
    () => page.getByTestId('login-btn'),
    () => page.getByRole('button', { name: 'ログイン' }),
    () => page.locator('#login-btn'),
    () => page.locator('.btn-primary').first(),
  ];

  for (const getSelector of selectors) {
    try {
      const locator = getSelector();
      if (await locator.isVisible({ timeout: 1000 })) {
        await locator.click();
        return;
      }
    } catch (err) {
      // 次のセレクタへ
    }
  }

  throw new Error('Login button not found with any selector');
}
```

---

## セレクタ選定フローチャート

```
開始
  ↓
data-testid がある？ ──Yes→ getByTestId()
  ↓ No
role + name が使える？ ──Yes→ getByRole()
  ↓ No
label がある？（フォーム） ──Yes→ getByLabel()
  ↓ No
placeholder がある？ ──Yes→ getByPlaceholder()
  ↓ No
静的 id がある？ ──Yes→ locator('#id')
  ↓ No
class名（最終手段） ──→ locator('.class').first()
```

---

## セレクタレビューチェックリスト

コードレビュー時に以下を確認:

- [ ] XPathを使用していないか？
- [ ] 動的IDを使用していないか？（UUID、連番等）
- [ ] 複雑なCSSセレクタ（`>`、`:nth-child()`等）を使用していないか？
- [ ] より優先度の高いセレクタ（role, testid）に変更できないか？
- [ ] 複数要素がマッチする場合、`.first()` で明示しているか？

---

## 実例: 楽楽精算ログインフォーム

**Before（Playwright CLI生成）**:
```typescript
await page.getByPlaceholder('会社コード').fill('12345');
await page.getByPlaceholder('ユーザーID').fill('user01');
await page.getByPlaceholder('パスワード').fill('password');
await page.locator('button.btn-primary').click();
```

**After（ポリシー適用）**:
```typescript
// label 優先（placeholder よりセマンティック）
await page.getByLabel('会社コード').fill('12345');
await page.getByLabel('ユーザーID').fill('user01');
await page.getByLabel('パスワード').fill('password');

// role + name 優先（class より安定）
await page.getByRole('button', { name: 'ログイン' }).click();
```

---

## トラブルシューティング

### 問題1: 複数要素がマッチする

**症状**:
```
Error: locator.click: Error: strict mode violation: locator(".btn") resolved to 3 elements
```

**解決**:
```typescript
// Bad
await page.locator('.btn').click();

// Good: .first() で最初の要素を明示
await page.locator('.btn').first().click();

// Better: より具体的なセレクタ
await page.getByRole('button', { name: 'ログイン' }).click();
```

### 問題2: セレクタが見つからない

**症状**:
```
TimeoutError: locator.click: Timeout 30000ms exceeded.
```

**解決**:
1. DOM構造を確認（DevTools）
2. より上位のセレクタを試す（role, label）
3. 待機条件を確認（`waitForSelector`）

### 問題3: 動的要素のセレクタ

**症状**: ページ読込ごとにidが変わる

**解決**:
```typescript
// Bad: 動的id
await page.locator('#react-select-3--value').click();

// Good: role または aria-label
await page.getByRole('combobox', { name: '都道府県' }).click();
```

---

## References

- [Playwright Locators公式ドキュメント](https://playwright.dev/docs/locators)
- [WAI-ARIA Roles](https://www.w3.org/TR/wai-aria-1.2/#role_definitions)
