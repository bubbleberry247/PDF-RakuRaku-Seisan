# Queue Specification（キュー構造仕様）

## Directory Layout（ディレクトリレイアウト）

### 標準構造

```
{queue-root}/
├── inbox/                  # 未処理ジョブ（投入先）
├── inprogress/             # 処理中ジョブ（claimされた）
├── done/                   # 完了ジョブ（日別サブディレクトリ）
├── failed/                 # 失敗ジョブ（日別サブディレクトリ）
│   └── retry/              # リトライ待ち
├── stale/                  # stale検出されたジョブ
├── ledger/                 # 冪等性記録（日別CSV）
└── heartbeat/              # Worker生存確認
```

### inbox/（未処理ジョブ）

**役割**: 新規ジョブの投入先。Workerがここからclaimする。

**ファイル形式**: JSON（1ファイル = 1ジョブ）

**命名規約**: `{jobKey}.json`
- jobKey: 冪等性キー（同じジョブは常に同じキー）
- 例: `app-12345-2026-02-14.json`

**サイズ制限**: 1ファイル最大10MB

### inprogress/（処理中ジョブ）

**役割**: claimされたジョブ。処理完了までここに置かれる。

**ファイル形式**: `{jobKey}.json.{workerId}.lock`

**lockファイル構造**:
- 元のファイル名 + workerId + .lock
- 例: `app-12345-2026-02-14.json.RPA-PC-01.lock`

**lockの意味**:
- このジョブは `RPA-PC-01` が処理中
- 他のworkerはこのジョブをclaimできない

### done/（完了ジョブ）

**役割**: 正常完了したジョブ。

**サブディレクトリ**: 日別（YYYY-MM-DD）
```
done/
├── 2026-02-14/
│   ├── app-001.json
│   └── app-002.json
└── 2026-02-15/
    └── app-003.json
```

**保持期間**: 7日（成功実行は短期保持）

### failed/（失敗ジョブ）

**役割**: 処理失敗したジョブ。

**サブディレクトリ**:
- 日別（YYYY-MM-DD）: 失敗ジョブの記録
- `retry/`: リトライ待ちジョブ

```
failed/
├── 2026-02-14/
│   ├── app-004.json       # 失敗記録
│   └── app-004.error.txt  # エラー内容
└── retry/
    └── app-004.json       # リトライ待ち
```

**保持期間**: 30日

### stale/（stale検出されたジョブ）

**役割**: Heartbeat停止により回収されたジョブ。

**ファイル形式**: `{jobKey}.json.{workerId}.lock`（inprogressと同じ）

**運用**:
- 定期的に確認
- inbox/へ戻す（再投入）
- または手動調査

### ledger/（冪等性記録）

**役割**: 処理済みジョブの台帳。再投入されても二重処理しない。

**ファイル形式**: CSV（日別）

**ファイル名**: `{YYYY-MM-DD}.csv`

**CSV構造**:
```csv
jobKey,workerId,startTime,endTime,status
app-001,RPA-PC-01,2026-02-14T10:00:00Z,2026-02-14T10:02:00Z,success
app-002,RPA-PC-02,2026-02-14T10:00:05Z,2026-02-14T10:03:00Z,success
app-003,RPA-PC-01,2026-02-14T10:05:00Z,2026-02-14T10:08:00Z,failed
```

**保持期間**: 30日

### heartbeat/（Worker生存確認）

**役割**: 各workerの最終生存時刻を記録。

**ファイル形式**: テキスト（1行 = ISO8601タイムスタンプ）

**ファイル名**: `{workerId}.txt`

**内容例**:
```
2026-02-14T15:30:45+09:00
```

**更新頻度**: 30秒ごと

**stale判定**: 5分以上更新されないworkerはstale

## File Permissions（ファイル権限）

### Windows共有フォルダ（SMB/CIFS）

**推奨設定**:
- Everyone: 読み取り + 書き込み + 削除
- NTFS権限: ローカル管理者のみフルコントロール

**注意点**:
- rename/move操作は「削除」権限が必要
- ロックファイル（.lock）は削除権限必須

### アクセス制御

**セキュリティ要件**:
- 共有フォルダはRPAユーザーのみアクセス可能
- 読み取り専用ユーザーは別途作成（監査用）

## Atomic Operations（原子的操作）

### fs.renameSync()の原子性

**POSIX/Linux**:
- rename(2)システムコールは原子的
- 同一ファイルシステム内なら確実

**Windows**:
- MoveFileEx()は原子的
- 同一ドライブ内なら確実
- ネットワークドライブ（SMB）でも原子的

**制限**:
- 異なるファイルシステム間（例: C:\\ → D:\\）は非原子的
- 異なるネットワーク共有間も非原子的

### Claim操作の実装

```typescript
function claim(jobFile: string, workerId: string): boolean {
  const srcPath = path.join(QUEUE_ROOT, 'inbox', jobFile);
  const dstPath = path.join(QUEUE_ROOT, 'inprogress', `${jobFile}.${workerId}.lock`);

  try {
    // 原子的rename
    fs.renameSync(srcPath, dstPath);
    return true; // claim成功
  } catch (err) {
    if (err.code === 'ENOENT') {
      // 他のworkerが先にclaimした
      return false;
    }
    throw err; // その他のエラーは再throw
  }
}
```

## Job File Format（ジョブファイル形式）

### 標準スキーマ

```typescript
interface QueueJob {
  jobKey: string;        // 冪等性キー（必須）
  jobId: string;         // 証跡用ジョブID（必須）
  runId: string;         // 実行ID（処理時に生成）
  priority: number;      // 優先度（1-10、デフォルト5）
  createdAt: string;     // ジョブ作成日時（ISO8601）
  payload: any;          // 実際のデータ（業務による）
}
```

### payload例（楽楽精算）

```json
{
  "jobKey": "app-12345-2026-02-14",
  "jobId": "rakuraku-expense-approval",
  "runId": "",
  "priority": 5,
  "createdAt": "2026-02-14T10:00:00+09:00",
  "payload": {
    "applicationId": "12345",
    "applicant": "田中太郎",
    "amount": 10000,
    "date": "2026-02-14",
    "description": "交通費"
  }
}
```

## Error Handling（エラー処理）

### ジョブ処理失敗時

1. **lockファイルを維持**（inprogress/に残す）
2. **エラー内容を記録**（failed/に.error.txtを作成）
3. **ledgerに記録**（status=failed）
4. **リトライ判定**:
   - 一時的エラー（ネットワーク等） → `failed/retry/`へ
   - 恒久的エラー（データ不整合等） → `failed/{date}/`へ

### リトライロジック

```typescript
const RETRYABLE_ERRORS = [
  'ETIMEDOUT',
  'ECONNREFUSED',
  'ECONNRESET',
  'TimeoutError',
];

function shouldRetry(error: Error, retryCount: number): boolean {
  if (retryCount >= MAX_RETRIES) {
    return false;
  }

  return RETRYABLE_ERRORS.some(pattern =>
    error.message.includes(pattern) || error.name === pattern
  );
}
```

## Cleanup Policy（クリーンアップ方針）

### 自動削除

| ディレクトリ | 保持期間 | 削除条件 |
|------------|---------|---------|
| done/ | 7日 | 成功実行は短期保持 |
| failed/ | 30日 | 失敗実行は長期保持（調査用） |
| ledger/ | 30日 | 冪等性記録も30日 |
| stale/ | 即時 | inbox/へ戻した後削除 |
| heartbeat/ | 即時 | worker停止後削除（オプション） |

### クリーンアップスクリプト例

```bash
#!/bin/bash
# cleanup-queue.sh

QUEUE_ROOT="\\\\server\\share\\rpa-queue"

# done/ の7日以上前を削除
find "$QUEUE_ROOT/done" -type d -mtime +7 -exec rm -rf {} \;

# failed/ の30日以上前を削除
find "$QUEUE_ROOT/failed" -type d -mtime +30 -exec rm -rf {} \;

# ledger/ の30日以上前を削除
find "$QUEUE_ROOT/ledger" -name "*.csv" -mtime +30 -delete

# stale/ を全削除（inbox/へ戻した後）
rm -rf "$QUEUE_ROOT/stale"/*
```

## Monitoring（モニタリング）

### 監視すべきメトリクス

| メトリクス | 正常範囲 | 異常時の対応 |
|-----------|---------|------------|
| inbox/ジョブ数 | < 100 | Worker追加、または処理速度改善 |
| inprogress/ジョブ数 | < 10 | stale検出が機能しているか確認 |
| stale/ジョブ数 | 0 | worker異常停止の調査 |
| done/処理件数（日別） | 業務による | 急減時は異常 |
| failed/失敗率 | < 5% | 失敗原因の調査 |

### アラート基準

```typescript
interface QueueMetrics {
  inboxCount: number;
  inprogressCount: number;
  staleCount: number;
  failureRate: number; // 0.0 - 1.0
}

function checkAlerts(metrics: QueueMetrics): string[] {
  const alerts: string[] = [];

  if (metrics.inboxCount > 100) {
    alerts.push('WARN: inbox has > 100 jobs. Consider adding more workers.');
  }

  if (metrics.staleCount > 0) {
    alerts.push(`WARN: ${metrics.staleCount} stale jobs detected. Check worker health.`);
  }

  if (metrics.failureRate > 0.05) {
    alerts.push(`ERROR: Failure rate ${(metrics.failureRate * 100).toFixed(1)}% exceeds 5%.`);
  }

  return alerts;
}
```

## References

- [Worker実装例](../examples/worker-loop.ts)
- [SKILL.md](../SKILL.md)
