---
name: bw-rpa-evidence-bundle
description: |
  失敗時の証跡（Trace/Screenshot/Video/Logs/Input/Output/Env）を「必ず」揃える標準を定義。
  MTTR（平均復旧時間）最優先。コスト最優先で「重い証跡はfailure時orデバッグ時のみ」を原則とする。

  トリガー: 証跡、エビデンス、失敗、障害、原因究明、trace、screenshot、video、ログ、復旧、MTTR
disable-model-invocation: false
---

# bw-rpa-evidence-bundle

## Purpose（目的）

Playwright(TypeScript)ベースのRPAツールで、失敗時に「問い合わせ1回で復旧できる」証跡セットを標準化する。

**目標**:
- MTTR（平均復旧時間）の最小化
- 「情報が足りない」による往復を0にする
- コスト最優先: 重い証跡（trace/video）は失敗時のみ収集

## When to Use（いつ使う）

- 新しいRPAフローを実装する時（証跡設計の標準適用）
- 失敗したジョブを調査する時（必要証跡の確認）
- 障害報告を作成する時（テンプレート使用）
- コードレビュー時（証跡収集が標準に沿っているか確認）

## Inputs / Outputs

**Inputs**:
- 実装中のRPAフロー（TypeScriptコード）
- 失敗したジョブのartifactディレクトリ

**Outputs**:
- 標準化された証跡ディレクトリ構造
- 障害報告（incident report）
- 証跡zip（共有用）

## Directory Structure Standard（ディレクトリ標準）

### 基本構造
```
artifacts/
├── {jobId}/
│   ├── {runId}/
│   │   ├── metadata.json           # 必須: run情報
│   │   ├── execution.log           # 必須: 実行ログ
│   │   ├── trace.zip               # 失敗時のみ: Playwright trace
│   │   ├── screenshots/            # 失敗時のみ: エラー時スクリーンショット
│   │   ├── videos/                 # デバッグ時のみ: 画面録画
│   │   ├── input/                  # 必須: 入力データ（ハッシュ/サンプル）
│   │   ├── output/                 # 成功時のみ: 出力データ
│   │   └── network/                # 失敗時のみ: HAR（ネットワークログ）
```

### 命名規約
- **jobId**: 業務識別子（例: `rakuraku-expense-approval`）
- **runId**: 実行ID（例: `20260214-153042-abc123`）
  - フォーマット: `{YYYYMMDD}-{HHMMSS}-{shortHash}`
- **timestamp**: ISO8601形式（`2026-02-14T15:30:42+09:00`）

## Metadata Standard（metadata.json必須項目）

```json
{
  "runId": "20260214-153042-abc123",
  "jobId": "rakuraku-expense-approval",
  "startTime": "2026-02-14T15:30:42+09:00",
  "endTime": "2026-02-14T15:32:15+09:00",
  "duration": 93000,
  "status": "failed",
  "exitCode": 1,
  "error": {
    "type": "TimeoutError",
    "message": "Timeout 30000ms exceeded.",
    "stack": "..."
  },
  "retryCount": 2,
  "environment": {
    "os": "Windows 11",
    "nodeVersion": "20.11.0",
    "playwrightVersion": "1.41.0",
    "browserVersion": "chromium 121.0.6167.57",
    "machineName": "RPA-PC-01",
    "userName": "rpa_user"
  },
  "input": {
    "hash": "sha256:abc123...",
    "samplePath": "input/sample.json"
  },
  "output": {
    "status": "none",
    "path": null
  }
}
```

## Execution Log Standard（execution.log必須項目）

各ログ行は以下のフォーマット:
```
[{ISO8601 timestamp}] [{LEVEL}] [{stepId}] {message}
```

**必須ログポイント**:
1. 実行開始: `[INFO] [START] Job started: {jobId}, runId: {runId}`
2. 各ステップ開始: `[INFO] [STEP-{n}] Starting: {stepName}`
3. 各ステップ終了: `[INFO] [STEP-{n}] Completed: {stepName} (duration: {ms}ms)`
4. エラー発生: `[ERROR] [STEP-{n}] Failed: {error.message}`
5. リトライ: `[WARN] [RETRY] Attempt {n} of {max}`
6. 実行終了: `[INFO] [END] Job completed: status={status}, duration={ms}ms`

## Evidence Collection Policy（証跡収集方針）

### コスト優先原則
| 証跡 | 常時 | 失敗時 | デバッグ時 | 理由 |
|------|------|--------|-----------|------|
| metadata.json | ✓ | ✓ | ✓ | 軽量・必須 |
| execution.log | ✓ | ✓ | ✓ | 軽量・必須 |
| input hash/sample | ✓ | ✓ | ✓ | 再現性に必須 |
| output | ✓ | - | ✓ | 成功時のみ |
| trace.zip | - | ✓ | ✓ | 重い（10-50MB） |
| screenshots | - | ✓ | ✓ | 失敗箇所特定 |
| videos | - | - | ✓ | 最重（100-500MB） |
| network HAR | - | ✓ | ✓ | API問題調査 |

### Playwright設定例（TypeScript）

```typescript
// playwright.config.ts
export default defineConfig({
  use: {
    // 常時
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',

    // デバッグ時のみ（環境変数で制御）
    video: process.env.DEBUG ? 'on' : 'off',
  },
});
```

## Failure Bundle（失敗時のzip化）

失敗時は以下を1つのzipにまとめて共有:

```bash
# 自動化例
zip -r "failure-{runId}.zip" \
  metadata.json \
  execution.log \
  trace.zip \
  screenshots/ \
  input/ \
  network/
```

**zipに含めないもの**:
- videos/（大きすぎる。必要なら別途要求）
- node_modules/（無関係）
- .env（秘密情報）

## Minimum Alternative（trace.zipが無い時の代替）

Playwrightのtraceが取れない環境の場合、最低限以下を収集:

1. **HTML Dump**: エラー時のDOM全体
   ```typescript
   await page.content(); // HTML全体を保存
   ```

2. **Console Logs**: ブラウザコンソールログ
   ```typescript
   page.on('console', msg => log.write(`[CONSOLE] ${msg.text()}\n`));
   ```

3. **Network Failures**: 失敗したリクエストのみ
   ```typescript
   page.on('requestfailed', req =>
     log.write(`[NET-FAIL] ${req.url()} - ${req.failure()?.errorText}\n`)
   );
   ```

## Instructions（実装手順）

### 1. プロジェクトセットアップ

```typescript
// src/evidence/collector.ts
export interface EvidenceCollector {
  initialize(jobId: string, runId: string): Promise<void>;
  logStep(stepId: string, message: string): void;
  captureError(error: Error): Promise<void>;
  finalize(status: 'success' | 'failed'): Promise<string>; // Returns zip path
}
```

### 2. 実行開始時

```typescript
const collector = new EvidenceCollector();
await collector.initialize(jobId, generateRunId());
```

### 3. 各ステップでログ

```typescript
collector.logStep('STEP-1', 'Starting login');
try {
  await login(page);
  collector.logStep('STEP-1', 'Login completed');
} catch (error) {
  await collector.captureError(error);
  throw error;
}
```

### 4. 実行終了時

```typescript
try {
  // ... RPA処理
  const zipPath = await collector.finalize('success');
} catch (error) {
  const zipPath = await collector.finalize('failed');
  throw error;
}
```

### 5. 例外処理

- ディスク容量不足: 古いartifactを自動削除（保持期間: 30日）
- ネットワーク障害: ローカルに保存、後で共有フォルダへコピー
- 権限エラー: エラーログのみ記録、証跡収集はスキップ

## Examples（使用例）

### Example 1: 標準的な実装

```typescript
// main.ts
import { EvidenceCollector } from './evidence/collector';
import { PlaywrightRunner } from './runner';

async function main() {
  const jobId = 'rakuraku-expense-approval';
  const runId = generateRunId();
  const collector = new EvidenceCollector(jobId, runId);

  await collector.initialize();

  const runner = new PlaywrightRunner({
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: process.env.DEBUG ? 'on' : 'off',
  });

  try {
    collector.logStep('START', `Starting job: ${jobId}`);

    const page = await runner.newPage();

    collector.logStep('STEP-1', 'Logging in');
    await login(page);

    collector.logStep('STEP-2', 'Processing expenses');
    await processExpenses(page);

    collector.logStep('END', 'Job completed successfully');
    await collector.finalize('success');

  } catch (error) {
    await collector.captureError(error);
    const zipPath = await collector.finalize('failed');
    console.error(`Failure bundle created: ${zipPath}`);
    throw error;
  }
}
```

### Example 2: 証跡確認スクリプト

```typescript
// scripts/verify-evidence.ts
import * as fs from 'fs';
import * as path from 'path';

async function verifyEvidence(runId: string) {
  const artifactDir = path.join('artifacts', jobId, runId);

  const required = [
    'metadata.json',
    'execution.log',
    'input',
  ];

  const missing = required.filter(file =>
    !fs.existsSync(path.join(artifactDir, file))
  );

  if (missing.length > 0) {
    throw new Error(`Missing required evidence: ${missing.join(', ')}`);
  }

  const metadata = JSON.parse(
    fs.readFileSync(path.join(artifactDir, 'metadata.json'), 'utf-8')
  );

  if (metadata.status === 'failed') {
    const failureRequired = ['trace.zip', 'screenshots'];
    const failureMissing = failureRequired.filter(file =>
      !fs.existsSync(path.join(artifactDir, file))
    );

    if (failureMissing.length > 0) {
      console.warn(`Failure evidence incomplete: ${failureMissing.join(', ')}`);
    }
  }

  console.log('Evidence verification passed');
}
```

## Troubleshooting（トラブルシューティング）

### 問題1: trace.zipが生成されない

**原因**: Playwright設定で `trace: 'off'` になっている

**解決**:
```typescript
// playwright.config.ts
use: {
  trace: 'retain-on-failure', // または 'on'
}
```

### 問題2: ディスク容量不足でartifact保存失敗

**原因**: 古いartifactが溜まっている

**解決**:
```typescript
// scripts/cleanup-old-artifacts.ts
const RETENTION_DAYS = 30;
const cutoffDate = new Date();
cutoffDate.setDate(cutoffDate.getDate() - RETENTION_DAYS);

// artifacts/配下の古いrunIdフォルダを削除
```

### 問題3: zipファイルが大きすぎてメール送信できない

**原因**: video/が含まれている

**解決**:
- videoは別途共有フォルダに保存
- zipにはtrace.zip + screenshots のみ含める
- 必要に応じてvideoへのリンクを報告に記載

### 問題4: 秘密情報（パスワード等）がログに混入

**原因**: ログ出力にフィルタがない

**解決**:
```typescript
// logger.ts
const SENSITIVE_PATTERNS = [/password/i, /token/i, /secret/i];

function sanitizeLog(message: string): string {
  let sanitized = message;
  SENSITIVE_PATTERNS.forEach(pattern => {
    sanitized = sanitized.replace(pattern, '***REDACTED***');
  });
  return sanitized;
}
```

### 問題5: metadata.jsonのenvironment情報が不足

**原因**: 環境情報の収集ロジックが不完全

**解決**:
```typescript
async function collectEnvironment() {
  return {
    os: process.platform + ' ' + os.release(),
    nodeVersion: process.version,
    playwrightVersion: require('playwright/package.json').version,
    browserVersion: await browser.version(),
    machineName: os.hostname(),
    userName: process.env.USERNAME || process.env.USER,
  };
}
```

## References

- [Artifact仕様詳細](references/artifacts-spec.md)
- [障害報告テンプレート](assets/incident-report-template.md)
- [期待される成果物ツリー](examples/artifact-tree.txt)
