/**
 * Flow Skeleton Template
 *
 * Playwright RPAフローの標準テンプレート。
 * 証跡収集、エラーハンドリング、ログ出力を統合。
 */

import { Page, Browser, chromium } from '@playwright/test';
import { EvidenceCollector } from '../evidence/collector'; // 仮のパス

// ===== Configuration Interface =====

interface FlowConfig {
  url: string;
  credentials: {
    companyCode: string;
    userId: string;
    password: string;
  };
  timeout?: number; // ms
}

// ===== Main Flow Function =====

/**
 * 楽楽精算 経費申請フロー（テンプレート）
 *
 * @param page Playwrightページオブジェクト
 * @param collector 証跡収集オブジェクト
 * @param config 設定（URL、資格情報等）
 */
export async function rakurakuExpenseFlow(
  page: Page,
  collector: EvidenceCollector,
  config: FlowConfig
): Promise<void> {
  const timeout = config.timeout || 60000; // デフォルト60秒

  // ===== STEP 1: ログイン =====
  collector.logStep('STEP-1', 'Starting login');

  try {
    await page.goto(config.url, { timeout });

    // Locator優先順位: label > placeholder
    await page.getByLabel('会社コード').fill(config.credentials.companyCode);
    await page.getByLabel('ユーザーID').fill(config.credentials.userId);
    await page.getByLabel('パスワード').fill(config.credentials.password);

    // role + name でボタンクリック
    await page.getByRole('button', { name: 'ログイン' }).click();

    // 遷移待機（URL変化を待つ）
    await page.waitForURL(/\/home/, { timeout });

    // エラーチェック（ログイン失敗メッセージ）
    const errorMsg = await page
      .locator('.error-message')
      .textContent()
      .catch(() => null);

    if (errorMsg) {
      throw new Error(`Login failed: ${errorMsg}`);
    }

    collector.logStep('STEP-1', 'Login completed');
  } catch (error) {
    await collector.captureError(error as Error);
    await page.screenshot({ path: `screenshots/step-1-error.png` });
    throw error;
  }

  // ===== STEP 2: 経費申請画面へ遷移 =====
  collector.logStep('STEP-2', 'Navigating to expense application page');

  try {
    await page.getByRole('link', { name: '経費申請' }).click();
    await page.waitForURL(/\/expenses\/new/, { timeout });

    collector.logStep('STEP-2', 'Navigation completed');
  } catch (error) {
    await collector.captureError(error as Error);
    await page.screenshot({ path: `screenshots/step-2-error.png` });
    throw error;
  }

  // ===== STEP 3: フォーム入力 =====
  collector.logStep('STEP-3', 'Filling expense form');

  try {
    // 日付
    await page.getByLabel('日付').fill('2026-02-14');

    // 金額
    await page.getByLabel('金額').fill('10000');

    // 摘要
    await page.getByLabel('摘要').fill('交通費');

    // カテゴリ選択（select要素）
    await page.getByLabel('カテゴリ').selectOption('交通費');

    collector.logStep('STEP-3', 'Form filled');
  } catch (error) {
    await collector.captureError(error as Error);
    await page.screenshot({ path: `screenshots/step-3-error.png` });
    throw error;
  }

  // ===== STEP 4: 申請送信 =====
  collector.logStep('STEP-4', 'Submitting expense application');

  try {
    // API送信完了を待つ
    const responsePromise = page.waitForResponse(
      (res) =>
        res.url().includes('/api/expenses') &&
        (res.status() === 201 || res.status() === 200),
      { timeout }
    );

    await page.getByRole('button', { name: '申請する' }).click();
    const response = await responsePromise;

    // レスポンス確認
    const result = await response.json();
    const expenseId = result.expenseId || result.id;

    collector.logStep('STEP-4', `Expense submitted: ID=${expenseId}`);
  } catch (error) {
    await collector.captureError(error as Error);
    await page.screenshot({ path: `screenshots/step-4-error.png` });
    throw error;
  }

  // ===== STEP 5: 完了確認 =====
  collector.logStep('STEP-5', 'Verifying completion');

  try {
    // 完了メッセージの表示を待つ
    await page
      .getByText('申請が完了しました')
      .waitFor({ state: 'visible', timeout });

    collector.logStep('STEP-5', 'Completion verified');
  } catch (error) {
    await collector.captureError(error as Error);
    await page.screenshot({ path: `screenshots/step-5-error.png` });
    throw error;
  }
}

// ===== Entry Point with Browser Setup =====

/**
 * フロー実行のエントリーポイント
 */
export async function runFlow(config: FlowConfig): Promise<void> {
  const jobId = 'rakuraku-expense-approval';
  const runId = generateRunId();

  const collector = new EvidenceCollector(jobId, runId);
  await collector.initialize();

  let browser: Browser | null = null;
  let page: Page | null = null;

  try {
    // Browser起動
    browser = await chromium.launch({
      headless: process.env.DEBUG ? false : true, // DEBUGモードでブラウザ表示
    });

    // Context作成（証跡設定）
    const context = await browser.newContext({
      // 証跡設定
      recordVideo: process.env.DEBUG ? { dir: `artifacts/${jobId}/${runId}/videos` } : undefined,
      recordHar: { path: `artifacts/${jobId}/${runId}/network/trace.har` },
    });

    // Trace開始（失敗時のみ保存）
    await context.tracing.start({
      screenshots: true,
      snapshots: true,
    });

    page = await context.newPage();

    // フロー実行
    await rakurakuExpenseFlow(page, collector, config);

    // 成功時
    await context.tracing.stop();
    await collector.finalize('success');

    console.log('✓ Flow completed successfully');
  } catch (error) {
    console.error('✗ Flow failed:', error);

    // 失敗時のTrace保存
    if (page) {
      const context = page.context();
      await context.tracing.stop({
        path: `artifacts/${jobId}/${runId}/trace.zip`,
      });
    }

    await collector.finalize('failed');
    throw error;
  } finally {
    // クリーンアップ
    if (page) await page.close();
    if (browser) await browser.close();
  }
}

// ===== Utility Functions =====

function generateRunId(): string {
  const timestamp = new Date()
    .toISOString()
    .replace(/[-:]/g, '')
    .replace(/T/, '-')
    .slice(0, 15); // YYYYMMDD-HHMMSS

  const shortHash = Math.random().toString(36).substring(2, 10); // 8文字
  return `${timestamp}-${shortHash}`;
}

// ===== Mock Evidence Collector (参考実装) =====

class EvidenceCollector {
  constructor(private jobId: string, private runId: string) {}

  async initialize(): Promise<void> {
    console.log(`[Evidence] Initialized for ${this.jobId}/${this.runId}`);
  }

  logStep(stepId: string, message: string): void {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] [INFO] [${stepId}] ${message}`);
  }

  async captureError(error: Error): Promise<void> {
    const timestamp = new Date().toISOString();
    console.error(`[${timestamp}] [ERROR] ${error.message}`);
    console.error(error.stack);
  }

  async finalize(status: 'success' | 'failed'): Promise<void> {
    console.log(`[Evidence] Finalized with status: ${status}`);
  }
}

// ===== CLI Entry Point =====

if (require.main === module) {
  const config: FlowConfig = {
    url: process.env.RAKURAKU_URL || 'https://id.rakurakuseisan.jp/',
    credentials: {
      companyCode: process.env.RAKURAKU_COMPANY_CODE || '',
      userId: process.env.RAKURAKU_USER_ID || '',
      password: process.env.RAKURAKU_PASSWORD || '',
    },
  };

  runFlow(config).catch((error) => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}
