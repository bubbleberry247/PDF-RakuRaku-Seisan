/**
 * Worker Loop Example
 *
 * 共有フォルダベースのワークキューを処理するWorkerの実装例。
 * 原子的claim、Heartbeat、Stale検出、冪等性を実装。
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

// ===== Configuration =====

interface WorkerConfig {
  queueRoot: string;          // 例: "\\\\server\\share\\rpa-queue"
  workerId: string;           // 例: "RPA-PC-01"
  heartbeatInterval: number;  // ms（デフォルト30秒）
  staleThreshold: number;     // ms（デフォルト5分）
  pollInterval: number;       // ms（デフォルト5秒）
}

interface QueueJob {
  jobKey: string;
  jobId: string;
  runId: string;
  priority: number;
  createdAt: string;
  payload: any;
}

// ===== Worker Loop Class =====

class WorkerLoop {
  private config: WorkerConfig;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private running = false;

  constructor(config: WorkerConfig) {
    this.config = {
      heartbeatInterval: 30000,
      staleThreshold: 5 * 60 * 1000,
      pollInterval: 5000,
      ...config,
    };
  }

  // ===== Main Loop =====

  async start(): Promise<void> {
    console.log(`Worker ${this.config.workerId} starting...`);
    this.running = true;

    // Heartbeat開始
    this.startHeartbeat();

    // メインループ
    let lastStaleCheck = Date.now();

    while (this.running) {
      try {
        // 1. Stale検出（1分に1回）
        const now = Date.now();
        if (now - lastStaleCheck > 60000) {
          this.detectStaleJobs();
          this.recoverStaleJobs();
          lastStaleCheck = now;
        }

        // 2. ジョブclaim
        const job = this.claimNextJob();
        if (!job) {
          // ジョブなし → 待機
          await this.sleep(this.config.pollInterval);
          continue;
        }

        // 3. ジョブ処理
        await this.processJob(job);

      } catch (error) {
        console.error('Worker loop error:', error);
        await this.sleep(5000); // エラー時は少し待つ
      }
    }

    this.stopHeartbeat();
    console.log(`Worker ${this.config.workerId} stopped.`);
  }

  stop(): void {
    this.running = false;
  }

  // ===== Atomic Claim =====

  private claimNextJob(): QueueJob | null {
    const inboxDir = path.join(this.config.queueRoot, 'inbox');
    if (!fs.existsSync(inboxDir)) {
      return null;
    }

    const jobs = fs.readdirSync(inboxDir).filter(f => f.endsWith('.json'));

    // 優先度順にソート（ファイル名から読み取り、またはファイル内容から）
    // ここでは簡単のため、先着順

    for (const jobFile of jobs) {
      if (this.claimWithRetry(jobFile)) {
        // claim成功 → ジョブ内容を読み込み
        const lockFile = `${jobFile}.${this.config.workerId}.lock`;
        const lockPath = path.join(this.config.queueRoot, 'inprogress', lockFile);
        const content = fs.readFileSync(lockPath, 'utf-8');
        return JSON.parse(content) as QueueJob;
      }
    }

    return null; // 全てのジョブが他workerにclaimされた
  }

  private claimWithRetry(jobFile: string, maxRetries = 3): boolean {
    for (let i = 0; i < maxRetries; i++) {
      try {
        const srcPath = path.join(this.config.queueRoot, 'inbox', jobFile);
        const dstPath = path.join(
          this.config.queueRoot,
          'inprogress',
          `${jobFile}.${this.config.workerId}.lock`
        );

        // 原子的rename
        fs.renameSync(srcPath, dstPath);
        console.log(`Claimed job: ${jobFile}`);
        return true; // claim成功

      } catch (err: any) {
        if (err.code === 'ENOENT') {
          // 他のworkerが先にclaimした
          return false;
        }

        if (err.code === 'EBUSY' || err.code === 'EACCES') {
          // Windows共有フォルダでの一時的な競合 → リトライ
          this.sleepSync(100);
          continue;
        }

        throw err; // その他のエラーは再throw
      }
    }

    return false; // リトライ上限
  }

  // ===== Job Processing =====

  private async processJob(job: QueueJob): Promise<void> {
    console.log(`Processing job: ${job.jobKey}`);

    // 1. 冪等性チェック
    if (this.isProcessed(job.jobKey)) {
      console.log(`Job ${job.jobKey} already processed, skipping`);
      this.moveJobToDone(job);
      return;
    }

    try {
      // 2. 実際の処理（例: RPA実行）
      await this.doActualWork(job);

      // 3. 台帳記録
      this.markProcessed(job.jobKey, 'success');

      // 4. done/ へ移動
      this.moveJobToDone(job);

      console.log(`Job ${job.jobKey} completed successfully`);

    } catch (error: any) {
      console.error(`Job ${job.jobKey} failed:`, error);

      // 5. 失敗記録
      this.markProcessed(job.jobKey, 'failed');

      // 6. failed/ へ移動
      this.moveJobToFailed(job, error);
    }
  }

  private async doActualWork(job: QueueJob): Promise<void> {
    // TODO: 実際のRPAフロー実行
    // 例: await rakurakuExpenseApproval(job.payload)

    // ここでは仮の処理
    await this.sleep(1000);
    console.log(`  Processed payload:`, job.payload);
  }

  // ===== Idempotency (Ledger) =====

  private isProcessed(jobKey: string): boolean {
    const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
    const ledgerFile = path.join(this.config.queueRoot, 'ledger', `${today}.csv`);

    if (!fs.existsSync(ledgerFile)) {
      return false;
    }

    const lines = fs.readFileSync(ledgerFile, 'utf-8').split('\n');
    return lines.some(line => line.startsWith(jobKey + ','));
  }

  private markProcessed(jobKey: string, status: 'success' | 'failed'): void {
    const today = new Date().toISOString().split('T')[0];
    const ledgerDir = path.join(this.config.queueRoot, 'ledger');
    const ledgerFile = path.join(ledgerDir, `${today}.csv`);

    if (!fs.existsSync(ledgerDir)) {
      fs.mkdirSync(ledgerDir, { recursive: true });
    }

    const entry = [
      jobKey,
      this.config.workerId,
      new Date().toISOString(),
      new Date().toISOString(),
      status
    ].join(',') + '\n';

    fs.appendFileSync(ledgerFile, entry);
  }

  // ===== Job Movement =====

  private moveJobToDone(job: QueueJob): void {
    const lockFile = `${job.jobKey}.json.${this.config.workerId}.lock`;
    const srcPath = path.join(this.config.queueRoot, 'inprogress', lockFile);

    const today = new Date().toISOString().split('T')[0];
    const doneDir = path.join(this.config.queueRoot, 'done', today);
    if (!fs.existsSync(doneDir)) {
      fs.mkdirSync(doneDir, { recursive: true });
    }

    const dstPath = path.join(doneDir, `${job.jobKey}.json`);

    fs.renameSync(srcPath, dstPath);
  }

  private moveJobToFailed(job: QueueJob, error: Error): void {
    const lockFile = `${job.jobKey}.json.${this.config.workerId}.lock`;
    const srcPath = path.join(this.config.queueRoot, 'inprogress', lockFile);

    const today = new Date().toISOString().split('T')[0];
    const failedDir = path.join(this.config.queueRoot, 'failed', today);
    if (!fs.existsSync(failedDir)) {
      fs.mkdirSync(failedDir, { recursive: true });
    }

    const dstPath = path.join(failedDir, `${job.jobKey}.json`);
    const errorPath = path.join(failedDir, `${job.jobKey}.error.txt`);

    fs.renameSync(srcPath, dstPath);
    fs.writeFileSync(errorPath, error.stack || error.message);

    // リトライ可能なエラーの場合、retry/へもコピー
    if (this.shouldRetry(error)) {
      const retryDir = path.join(this.config.queueRoot, 'failed', 'retry');
      if (!fs.existsSync(retryDir)) {
        fs.mkdirSync(retryDir, { recursive: true });
      }
      fs.copyFileSync(dstPath, path.join(retryDir, `${job.jobKey}.json`));
    }
  }

  private shouldRetry(error: Error): boolean {
    const RETRYABLE_ERRORS = [
      'ETIMEDOUT',
      'ECONNREFUSED',
      'ECONNRESET',
      'TimeoutError',
    ];

    return RETRYABLE_ERRORS.some(pattern =>
      error.message.includes(pattern) || error.name === pattern
    );
  }

  // ===== Heartbeat =====

  private startHeartbeat(): void {
    this.updateHeartbeat(); // 初回即座に更新

    this.heartbeatTimer = setInterval(() => {
      this.updateHeartbeat();
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private updateHeartbeat(): void {
    const heartbeatDir = path.join(this.config.queueRoot, 'heartbeat');
    if (!fs.existsSync(heartbeatDir)) {
      fs.mkdirSync(heartbeatDir, { recursive: true });
    }

    const heartbeatFile = path.join(heartbeatDir, `${this.config.workerId}.txt`);
    fs.writeFileSync(heartbeatFile, new Date().toISOString());
  }

  // ===== Stale Detection =====

  private detectStaleJobs(): void {
    const inprogressDir = path.join(this.config.queueRoot, 'inprogress');
    if (!fs.existsSync(inprogressDir)) {
      return;
    }

    const locks = fs.readdirSync(inprogressDir).filter(f => f.endsWith('.lock'));

    for (const lock of locks) {
      // lock ファイル名: job-001.json.RPA-PC-01.lock
      const parts = lock.split('.');
      if (parts.length < 3) continue;

      const workerId = parts[parts.length - 2];
      const heartbeatFile = path.join(this.config.queueRoot, 'heartbeat', `${workerId}.txt`);

      if (!fs.existsSync(heartbeatFile)) {
        // heartbeat ファイルが無い → stale
        this.moveToStale(lock);
        continue;
      }

      const lastHeartbeat = new Date(fs.readFileSync(heartbeatFile, 'utf-8'));
      const now = new Date();

      if (now.getTime() - lastHeartbeat.getTime() > this.config.staleThreshold) {
        // 閾値以上更新されていない → stale
        console.log(`Detected stale job: ${lock} (worker: ${workerId})`);
        this.moveToStale(lock);
      }
    }
  }

  private moveToStale(lockFile: string): void {
    const srcPath = path.join(this.config.queueRoot, 'inprogress', lockFile);
    const staleDir = path.join(this.config.queueRoot, 'stale');
    if (!fs.existsSync(staleDir)) {
      fs.mkdirSync(staleDir, { recursive: true });
    }

    const dstPath = path.join(staleDir, lockFile);
    fs.renameSync(srcPath, dstPath);
  }

  private recoverStaleJobs(): void {
    const staleDir = path.join(this.config.queueRoot, 'stale');
    if (!fs.existsSync(staleDir)) {
      return;
    }

    const staleLocks = fs.readdirSync(staleDir).filter(f => f.endsWith('.lock'));

    for (const lock of staleLocks) {
      // lock ファイル名: job-001.json.RPA-PC-01.lock
      const parts = lock.split('.');
      const originalName = parts.slice(0, -2).join('.'); // "job-001.json"

      const srcPath = path.join(staleDir, lock);
      const dstPath = path.join(this.config.queueRoot, 'inbox', originalName);

      // stale/ → inbox/ へ戻す（.lock は除去）
      fs.renameSync(srcPath, dstPath);
      console.log(`Recovered stale job: ${originalName}`);
    }
  }

  // ===== Utilities =====

  private async sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private sleepSync(ms: number): void {
    const start = Date.now();
    while (Date.now() - start < ms) {
      // Busy wait
    }
  }
}

// ===== Entry Point =====

async function main() {
  const config: WorkerConfig = {
    queueRoot: process.env.QUEUE_ROOT || '\\\\server\\share\\rpa-queue',
    workerId: process.env.WORKER_ID || `RPA-${os.hostname()}`,
  };

  const worker = new WorkerLoop(config);

  // Graceful shutdown
  process.on('SIGINT', () => {
    console.log('Shutting down...');
    worker.stop();
  });

  await worker.start();
}

if (require.main === module) {
  main().catch(console.error);
}

export { WorkerLoop, WorkerConfig, QueueJob };
