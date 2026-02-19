---
name: bw-rpa-shared-work-queue
description: |
  共有フォルダベースのワークキュー。複数PC/複数人が処理しても重複しない。
  落ちたPCのジョブを回収可能。交代制でも状態引継ぎ可能。
  コスト最優先でDB等は使わず、ファイルベースを前提。

  トリガー: 共有フォルダ、ワークキュー、重複、並列、複数PC、交代制、claim、回収、冪等性、queue
disable-model-invocation: true
argument-hint: "[queue-root-path] [job-definition-path]"
---

# bw-rpa-shared-work-queue

## Purpose（目的）

複数のRPA実行環境（各自PC）が共有フォルダ上で協調動作するためのワークキュー設計。

**目標**:
- 重複処理の完全防止（原子的claim）
- 障害時のジョブ回収（stale detection）
- 冪等性保証（再投入しても二重処理にならない）
- コスト最小化（DB不要、ファイルベースのみ）

## When to Use（いつ使う）

- 各自PCでRPAを運用開始する時（共有ワーク設計）
- 複数人が同時に処理する業務を自動化する時
- 障害で止まったPCのジョブを別PCで再開したい時
- 交代制（日勤/夜勤等）でジョブを引き継ぎたい時

## Inputs / Outputs

**Inputs**:
- Queue root path（例: `\\server\share\rpa-queue`）
- Job definition（例: JSON/CSVファイル）

**Outputs**:
- 標準化されたキューディレクトリ構造
- Ledger（冪等性記録）
- Worker実装パターン（TypeScript擬似コード）

## Queue Directory Structure（キュー構造）

### 基本レイアウト

```
{queue-root}/
├── inbox/                  # 未処理ジョブ（投入先）
│   ├── job-001.json
│   ├── job-002.json
│   └── job-003.json
├── inprogress/             # 処理中ジョブ（claimされた）
│   ├── job-001.json.{workerId}.lock
│   └── job-002.json.{workerId}.lock
├── done/                   # 完了ジョブ
│   ├── 2026-02-14/
│   │   ├── job-001.json
│   │   └── job-002.json
│   └── 2026-02-15/
│       └── job-003.json
├── failed/                 # 失敗ジョブ
│   ├── 2026-02-14/
│   │   └── job-004.json
│   └── retry/              # リトライ待ち
│       └── job-004.json
├── stale/                  # stale検出されたジョブ
│   └── job-005.json.RPA-PC-01.lock
├── ledger/                 # 冪等性記録
│   ├── 2026-02-14.csv
│   └── 2026-02-15.csv
└── heartbeat/              # Worker生存確認
    ├── RPA-PC-01.txt       # 最終更新: 2026-02-14 15:30:45
    └── RPA-PC-02.txt
```

## Atomic Claim（原子的claim）

### 原理

ファイルシステムの **move/rename は原子的** であることを利用。

```typescript
// 擬似コード
function claim(jobFile: string, workerId: string): boolean {
  const lockFile = `${jobFile}.${workerId}.lock`;
  try {
    // inbox/ → inprogress/ へ原子的に移動（rename/move）
    fs.renameSync(
      path.join('inbox', jobFile),
      path.join('inprogress', lockFile)
    );
    return true; // claim成功
  } catch (err) {
    // 他のworkerが先にclaimした
    return false;
  }
}
```

**重要**:
- `fs.renameSync()` は POSIX/Windows 共に原子的
- 同じファイルに対して複数workerが同時にrenameしても、1つだけ成功
- 失敗したworkerは次のジョブへ進む

### Windows互換性

Windows共有フォルダ（SMB/CIFS）でも動作するが、注意点:

1. **ネットワーク遅延**: ローカルFSより遅い（100-500ms）
2. **競合時のリトライ**: EBUSY/EACCES エラーを短時間リトライ（100ms × 3回）
3. **UNCパス**: `\\server\share\` 形式を使用

```typescript
function claimWithRetry(jobFile: string, workerId: string): boolean {
  for (let i = 0; i < 3; i++) {
    try {
      return claim(jobFile, workerId);
    } catch (err) {
      if (err.code === 'EBUSY' || err.code === 'EACCES') {
        sleep(100); // 100ms待機
        continue;
      }
      throw err;
    }
  }
  return false;
}
```

## Heartbeat and Stale Detection（生存確認とstale回収）

### Heartbeat（生存確認）

各workerは定期的に heartbeat ファイルを更新。

```typescript
setInterval(() => {
  fs.writeFileSync(
    path.join('heartbeat', `${workerId}.txt`),
    new Date().toISOString()
  );
}, 30000); // 30秒ごと
```

### Stale Detection（stale回収）

Heartbeatが更新されない worker のジョブを回収。

```typescript
const STALE_THRESHOLD = 5 * 60 * 1000; // 5分

function detectStaleJobs() {
  const locks = fs.readdirSync('inprogress');

  for (const lock of locks) {
    // lock ファイル名: job-001.json.RPA-PC-01.lock
    const workerId = lock.split('.').slice(-2, -1)[0];
    const heartbeatFile = path.join('heartbeat', `${workerId}.txt`);

    if (!fs.existsSync(heartbeatFile)) {
      // heartbeat ファイルが無い → stale
      moveToStale(lock);
      continue;
    }

    const lastHeartbeat = new Date(fs.readFileSync(heartbeatFile, 'utf-8'));
    const now = new Date();

    if (now - lastHeartbeat > STALE_THRESHOLD) {
      // 5分以上更新されていない → stale
      moveToStale(lock);
    }
  }
}

function moveToStale(lockFile: string) {
  fs.renameSync(
    path.join('inprogress', lockFile),
    path.join('stale', lockFile)
  );
}
```

### Stale Recovery（stale回収）

Staleジョブを inbox へ戻す（再投入）。

```typescript
function recoverStaleJobs() {
  const staleLocks = fs.readdirSync('stale');

  for (const lock of staleLocks) {
    // lock ファイル名: job-001.json.RPA-PC-01.lock
    const originalName = lock.split('.').slice(0, -2).join('.');

    // stale/ → inbox/ へ戻す（.lock は除去）
    fs.renameSync(
      path.join('stale', lock),
      path.join('inbox', originalName)
    );
  }
}
```

## Idempotency（冪等性）

### Ledger（台帳）

処理済みジョブを記録し、再投入されても二重処理しない。

**ledger/{date}.csv**:
```csv
jobKey,workerId,startTime,endTime,status
job-001,RPA-PC-01,2026-02-14T15:30:00Z,2026-02-14T15:32:00Z,success
job-002,RPA-PC-02,2026-02-14T15:30:05Z,2026-02-14T15:33:00Z,success
job-003,RPA-PC-01,2026-02-14T15:35:00Z,2026-02-14T15:38:00Z,failed
```

### Job Key Design（ジョブキー設計）

冪等性の要。同じジョブは常に同じkeyを持つ。

**推奨設計**:
```typescript
function getJobKey(job: any): string {
  // 例: 楽楽精算の経費申請
  // キー: 申請ID + 申請日 + 申請者
  return `${job.applicationId}-${job.date}-${job.applicant}`;
}
```

**NGパターン**:
- タイムスタンプを含める → 再投入時にキーが変わる
- ファイル名のみ → ファイル名変更で重複処理

### Ledger Check（台帳確認）

```typescript
function isProcessed(jobKey: string): boolean {
  const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
  const ledgerFile = path.join('ledger', `${today}.csv`);

  if (!fs.existsSync(ledgerFile)) {
    return false;
  }

  const lines = fs.readFileSync(ledgerFile, 'utf-8').split('\n');
  return lines.some(line => line.startsWith(jobKey + ','));
}

function markProcessed(jobKey: string, workerId: string, status: string) {
  const today = new Date().toISOString().split('T')[0];
  const ledgerFile = path.join('ledger', `${today}.csv`);

  const entry = [
    jobKey,
    workerId,
    new Date().toISOString(),
    new Date().toISOString(),
    status
  ].join(',') + '\n';

  fs.appendFileSync(ledgerFile, entry);
}
```

## Integration with Evidence Bundle（証跡バンドルとの統合）

キューの各ジョブには **jobId** と **runId** を紐付ける。

```typescript
interface QueueJob {
  jobKey: string;        // 冪等性キー
  jobId: string;         // 証跡用ジョブID（例: "rakuraku-expense"）
  runId: string;         // 実行ID（自動生成）
  payload: any;          // 実際のデータ
}

async function processJob(job: QueueJob, workerId: string) {
  // 1. 冪等性チェック
  if (isProcessed(job.jobKey)) {
    console.log(`Job ${job.jobKey} already processed, skipping`);
    return;
  }

  // 2. runId生成（証跡用）
  job.runId = generateRunId();

  // 3. 証跡収集開始
  const collector = new EvidenceCollector(job.jobId, job.runId);
  await collector.initialize();

  try {
    // 4. 実際の処理
    collector.logStep('START', `Processing ${job.jobKey}`);
    await doActualWork(job.payload);
    collector.logStep('END', 'Job completed');

    // 5. 台帳記録
    markProcessed(job.jobKey, workerId, 'success');

    // 6. done/ へ移動
    await collector.finalize('success');
    moveJobToDone(job);

  } catch (error) {
    await collector.captureError(error);
    markProcessed(job.jobKey, workerId, 'failed');
    await collector.finalize('failed');
    moveJobToFailed(job);
  }
}
```

## Instructions（実装手順）

### 1. キュー初期化

```bash
# 共有フォルダに標準ディレクトリ作成
mkdir -p "\\server\share\rpa-queue"/{inbox,inprogress,done,failed,stale,ledger,heartbeat}
```

### 2. Worker実装

```typescript
// worker.ts
class WorkerLoop {
  constructor(
    private queueRoot: string,
    private workerId: string
  ) {}

  async start() {
    // Heartbeat開始
    this.startHeartbeat();

    // メインループ
    while (true) {
      // 1. Stale検出（1分に1回）
      if (this.shouldDetectStale()) {
        detectStaleJobs();
        recoverStaleJobs();
      }

      // 2. ジョブclaim
      const job = this.claimNextJob();
      if (!job) {
        await sleep(5000); // 5秒待機
        continue;
      }

      // 3. 処理
      await processJob(job, this.workerId);
    }
  }

  private claimNextJob(): QueueJob | null {
    const jobs = fs.readdirSync(path.join(this.queueRoot, 'inbox'));

    for (const jobFile of jobs) {
      if (claimWithRetry(jobFile, this.workerId)) {
        const lockFile = `${jobFile}.${this.workerId}.lock`;
        const content = fs.readFileSync(
          path.join(this.queueRoot, 'inprogress', lockFile),
          'utf-8'
        );
        return JSON.parse(content);
      }
    }

    return null; // 全てのジョブが他workerにclaimされた
  }

  private startHeartbeat() {
    setInterval(() => {
      fs.writeFileSync(
        path.join(this.queueRoot, 'heartbeat', `${this.workerId}.txt`),
        new Date().toISOString()
      );
    }, 30000); // 30秒ごと
  }
}
```

### 3. ジョブ投入

```typescript
// enqueue.ts
function enqueueJob(job: QueueJob, queueRoot: string) {
  const jobFile = `${job.jobKey}.json`;
  const jobPath = path.join(queueRoot, 'inbox', jobFile);

  fs.writeFileSync(jobPath, JSON.stringify(job, null, 2));
}
```

### 4. 運用開始

```bash
# Worker起動（PC1）
node worker.js --queue-root "\\server\share\rpa-queue" --worker-id "RPA-PC-01"

# Worker起動（PC2）
node worker.js --queue-root "\\server\share\rpa-queue" --worker-id "RPA-PC-02"
```

### 5. 例外処理

**ディスク容量不足**:
- done/failed の古いジョブを自動削除（30日以上前）

**ネットワーク切断**:
- Heartbeat更新失敗 → ログ記録、継続試行
- ジョブclaim失敗 → スキップして次へ

**Worker異常終了**:
- Heartbeat停止 → 他workerがstale検出 → 自動回収

## Examples（使用例）

### Example 1: 楽楽精算 経費申請の並列処理

```typescript
// Job定義
interface ExpenseJob extends QueueJob {
  jobKey: string;        // 例: "app-12345-2026-02-14"
  jobId: string;         // "rakuraku-expense-approval"
  runId: string;         // 自動生成
  payload: {
    applicationId: string;
    applicant: string;
    amount: number;
    date: string;
  };
}

// 100件のジョブを投入
for (const app of applications) {
  const job: ExpenseJob = {
    jobKey: `app-${app.id}-${app.date}`,
    jobId: 'rakuraku-expense-approval',
    runId: '',
    payload: app
  };
  enqueueJob(job, queueRoot);
}

// PC1とPC2が自動的に分担処理
// - PC1: 50件処理
// - PC2: 50件処理
// - 重複なし（原子的claim）
```

### Example 2: 障害回収

```typescript
// PC1がクラッシュ（15:30）
// → inprogress/job-010.json.RPA-PC-01.lock が残る

// PC2のstale検出（15:35）
// → Heartbeat更新なし（5分経過）
// → inprogress/ → stale/ へ移動

// PC2のstale回収（15:36）
// → stale/ → inbox/ へ戻す
// → PC2が再claim → 処理再開
```

## Troubleshooting（トラブルシューティング）

### 問題1: ジョブが重複処理される

**原因**: Job keyの設計が不適切（タイムスタンプ等を含む）

**解決**:
- Job keyに揮発性の値を含めない
- 業務上の一意識別子のみを使用（申請ID等）

### 問題2: Stale検出が遅い

**原因**: Heartbeat間隔が長すぎる

**解決**:
```typescript
// Heartbeat間隔を短縮（30秒 → 10秒）
setInterval(updateHeartbeat, 10000);

// Stale閾値を短縮（5分 → 2分）
const STALE_THRESHOLD = 2 * 60 * 1000;
```

### 問題3: inbox/に大量のジョブが溜まる

**原因**: Worker数が不足、または処理速度が遅い

**解決**:
- Worker数を増やす（PC3, PC4を追加）
- 処理の並列化（複数ブラウザコンテキスト）
- ジョブのバッチ処理（10件ずつまとめる）

### 問題4: Ledgerファイルが肥大化

**原因**: 日別で分割していない、または古いファイルを削除していない

**解決**:
```typescript
// 30日以上前のledgerを削除
const ledgers = fs.readdirSync('ledger');
const cutoffDate = new Date();
cutoffDate.setDate(cutoffDate.getDate() - 30);

for (const ledger of ledgers) {
  const date = new Date(ledger.replace('.csv', ''));
  if (date < cutoffDate) {
    fs.unlinkSync(path.join('ledger', ledger));
  }
}
```

### 問題5: Windows共有フォルダでclaimが失敗

**原因**: ネットワーク遅延、SMBロック競合

**解決**:
- リトライロジックを追加（claimWithRetry）
- タイムアウトを延長（100ms → 500ms）
- UNCパス直接指定（ドライブマッピング避ける）

## References

- [Queue構造仕様](references/queue-spec.md)
- [Worker実装例](examples/worker-loop.ts)
- [フォルダレイアウト例](examples/queue-layout.md)
