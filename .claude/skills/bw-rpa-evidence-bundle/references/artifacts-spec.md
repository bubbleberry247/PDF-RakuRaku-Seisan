# Artifacts Specification（証跡仕様詳細）

## Directory Structure（ディレクトリ構成）

### 標準レイアウト

```
artifacts/
├── {jobId}/                    # 業務別（例: rakuraku-expense-approval）
│   ├── {runId}/                # 実行別（例: 20260214-153042-abc123）
│   │   ├── metadata.json       # 実行メタデータ（必須）
│   │   ├── execution.log       # 実行ログ（必須）
│   │   ├── trace.zip           # Playwright trace（失敗時）
│   │   ├── screenshots/        # スクリーンショット（失敗時）
│   │   │   ├── error-001.png
│   │   │   └── error-002.png
│   │   ├── videos/             # 録画（デバッグ時のみ）
│   │   │   └── recording.webm
│   │   ├── input/              # 入力データ（必須）
│   │   │   ├── hash.txt
│   │   │   └── sample.json
│   │   ├── output/             # 出力データ（成功時のみ）
│   │   │   └── result.xlsx
│   │   ├── network/            # ネットワークログ（失敗時）
│   │   │   └── trace.har
│   │   └── dump/               # HTML dump（trace代替）
│   │       └── error-page.html
│   ├── latest -> {runId}       # シンボリックリンク（最新実行）
│   └── last-success -> {runId} # シンボリックリンク（最終成功）
```

## Naming Conventions（命名規約）

### runId生成ルール

```typescript
function generateRunId(): string {
  const timestamp = new Date().toISOString()
    .replace(/[-:]/g, '')
    .replace(/T/, '-')
    .slice(0, 15); // YYYYMMDD-HHMMSS
  const shortHash = randomBytes(4).toString('hex'); // 8文字
  return `${timestamp}-${shortHash}`;
}
// 例: 20260214-153042-abc123de
```

### jobId命名規約

- kebab-case
- 業務内容を表す英語（日本語ローマ字不可）
- 30文字以内
- 例: `rakuraku-expense-approval`, `recoru-holiday-registration`

## File Specifications（ファイル仕様）

### metadata.json（必須）

```typescript
interface Metadata {
  runId: string;              // 実行ID
  jobId: string;              // 業務ID
  startTime: string;          // ISO8601形式
  endTime: string;            // ISO8601形式
  duration: number;           // ミリ秒
  status: 'success' | 'failed' | 'timeout' | 'cancelled';
  exitCode: number;           // 0=成功, 1+=失敗
  error?: {
    type: string;             // エラー型名
    message: string;          // エラーメッセージ
    stack: string;            // スタックトレース
    step?: string;            // 失敗したステップID
  };
  retryCount: number;         // リトライ回数
  environment: {
    os: string;               // OS情報
    nodeVersion: string;      // Node.jsバージョン
    playwrightVersion: string;// Playwrightバージョン
    browserVersion: string;   // ブラウザバージョン
    machineName: string;      // マシン名
    userName: string;         // 実行ユーザー
  };
  input: {
    hash: string;             // SHA-256ハッシュ
    samplePath: string;       // サンプルファイルパス
    size?: number;            // 入力データサイズ（バイト）
  };
  output?: {
    status: 'created' | 'none';
    path: string | null;
    size?: number;            // 出力データサイズ（バイト）
    hash?: string;            // 出力ハッシュ
  };
}
```

### execution.log（必須）

**フォーマット**: 1行1ログ、TSV形式

```
{timestamp}\t{level}\t{stepId}\t{message}
```

**レベル**: INFO, WARN, ERROR, DEBUG

**例**:
```
2026-02-14T15:30:42+09:00	INFO	START	Job started: rakuraku-expense-approval
2026-02-14T15:30:43+09:00	INFO	STEP-1	Starting login
2026-02-14T15:30:45+09:00	INFO	STEP-1	Login completed (2000ms)
2026-02-14T15:30:45+09:00	INFO	STEP-2	Starting expense processing
2026-02-14T15:31:10+09:00	ERROR	STEP-2	Timeout 30000ms exceeded
2026-02-14T15:31:10+09:00	WARN	RETRY	Attempt 1 of 3
```

### trace.zip（失敗時・デバッグ時）

Playwright標準のtrace形式。

**サイズ目安**: 10-50MB
**保持期間**: 30日
**取得条件**: `trace: 'retain-on-failure'` または `trace: 'on'`

### screenshots/（失敗時・デバッグ時）

**命名**: `error-{連番3桁}.png` または `step-{stepId}-{timestamp}.png`
**フォーマット**: PNG
**サイズ目安**: 100-500KB/枚
**最大枚数**: 10枚（それ以上は最初と最後のみ保持）

### videos/（デバッグ時のみ）

**命名**: `recording-{timestamp}.webm`
**フォーマット**: WebM
**サイズ目安**: 100-500MB
**取得条件**: `DEBUG=1` 環境変数または明示的指定

### network/trace.har（失敗時・デバッグ時）

**フォーマット**: HAR (HTTP Archive)
**サイズ目安**: 1-10MB
**取得方法**:
```typescript
await page.context().harExport({ path: 'trace.har' });
```

### input/（必須）

**hash.txt**: SHA-256ハッシュ（再現性確認用）
**sample.json**: 入力データの一部（個人情報マスク済み）

**サイズ制限**: sample.jsonは最大1MB（それ以上は先頭1000行のみ）

### output/（成功時のみ）

実行結果のファイル。形式は業務による（Excel, CSV, JSON等）。

## Size Limits and Retention（サイズ制限と保持期間）

### サイズ制限

| ファイル/ディレクトリ | 最大サイズ | 超過時の対応 |
|---------------------|-----------|-------------|
| metadata.json | 100KB | なし（制限内に収める） |
| execution.log | 10MB | ローテーション（1MB/ファイル） |
| trace.zip | 50MB | なし（制限内に収まる） |
| screenshots/ | 5MB | 最初と最後のみ保持 |
| videos/ | 500MB | なし（デバッグ時のみ） |
| network/trace.har | 10MB | なし（制限内に収める） |
| 1つのrunId全体 | 100MB | 警告ログ出力 |

### 保持期間

| 状態 | 保持期間 |
|------|---------|
| 成功実行 | 7日 |
| 失敗実行 | 30日 |
| デバッグ実行 | 90日 |
| 最新実行（latest） | 無期限 |
| 最終成功（last-success） | 無期限 |

### クリーンアップスクリプト

```bash
# scripts/cleanup-artifacts.sh
#!/bin/bash
find artifacts/ -type d -name "202*" -mtime +30 -exec rm -rf {} \;
```

## Success vs Failure Differences（成功時と失敗時の差分）

### 成功時の最小セット

```
artifacts/{jobId}/{runId}/
├── metadata.json          # status: "success"
├── execution.log
├── input/
│   ├── hash.txt
│   └── sample.json
└── output/
    └── result.xlsx
```

### 失敗時の完全セット

```
artifacts/{jobId}/{runId}/
├── metadata.json          # status: "failed", error: {...}
├── execution.log
├── trace.zip              # ★ 失敗時のみ
├── screenshots/           # ★ 失敗時のみ
│   ├── error-001.png
│   └── error-002.png
├── network/               # ★ 失敗時のみ
│   └── trace.har
├── input/
│   ├── hash.txt
│   └── sample.json
└── dump/                  # ★ trace代替
    └── error-page.html
```

## Integration with Playwright（Playwright統合）

### playwright.config.ts設定例

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  use: {
    // 証跡設定
    trace: process.env.CI ? 'retain-on-failure' : 'on',
    screenshot: 'only-on-failure',
    video: process.env.DEBUG ? 'on' : 'off',

    // ネットワークログ
    recordHar: {
      mode: 'minimal',
      path: `artifacts/${process.env.JOB_ID}/${process.env.RUN_ID}/network/trace.har`,
    },
  },

  // 証跡ディレクトリ
  outputDir: `artifacts/${process.env.JOB_ID}/${process.env.RUN_ID}`,
});
```

## Security Considerations（セキュリティ考慮事項）

### 秘密情報の除外

**除外すべき情報**:
- パスワード、トークン、APIキー
- 個人情報（氏名、メールアドレス、電話番号）
- クレジットカード番号
- 社外秘情報

**サニタイズ例**:
```typescript
function sanitize(text: string): string {
  return text
    .replace(/password[=:]\s*\S+/gi, 'password=***REDACTED***')
    .replace(/token[=:]\s*\S+/gi, 'token=***REDACTED***')
    .replace(/\d{4}-\d{4}-\d{4}-\d{4}/g, '****-****-****-****'); // カード番号
}
```

### アクセス制御

- artifacts/ディレクトリは管理者のみアクセス可能
- 共有時はzip化してパスワード保護
- 個人情報が含まれる場合は社内のみ共有

## References

- [Playwright Trace Viewer](https://playwright.dev/docs/trace-viewer)
- [HAR Format Spec](http://www.softwareishard.com/blog/har-12-spec/)
