---
name: bw-rpa-config-bootstrap
description: |
  各自PC運用でのインストール差分を吸収する設定管理標準。
  入力ファイル/出力先/共有パスを設定で管理。
  初回起動で対話的にconfig作成、再インストール不要な運用に寄せる。

  トリガー: 設定、config, 初回起動, インストール, 環境構築, 各自PC, セットアップ
disable-model-invocation: false
---

# bw-rpa-config-bootstrap

## Purpose（目的）

各自PCでのRPA運用時に、インストール先やファイルパスの差分を設定で吸収し、再インストール不要な運用を実現する。

**目標**:
- インストーラーへの依存を最小化
- 初回起動時の対話的なconfig作成
- 設定の優先順位（default < config < env < cli args）
- パス妥当性の自動検証

## When to Use（いつ使う）

- 新しいRPAプロジェクトをセットアップする時
- 各自PCへのデプロイ時（初回起動）
- 設定項目を追加/変更する時
- 環境間（開発/本番）の設定を切り替える時

## Inputs / Outputs

**Inputs**:
- 初回起動時のユーザー入力（対話的）
- 環境変数（オプション）
- CLIパラメータ（オプション）

**Outputs**:
- `config.json`（設定ファイル）
- 設定スキーマ（JSON Schema）
- 初回起動ウィザードスクリプト

## Configuration Precedence（設定優先順位）

```
CLI Arguments  >  Environment Variables  >  config.json  >  Default Values
    (最優先)            (次点)                 (標準)        (最終フォールバック)
```

### 例

**シナリオ**: 共有フォルダパスを設定

1. **Default**: `\\server\share\rpa-queue`（ハードコード）
2. **config.json**: `\\192.168.1.100\rpa\queue`
3. **環境変数**: `QUEUE_ROOT=\\nas01\work`
4. **CLI引数**: `--queue-root "\\temp\test"`

→ 最終的に使われる値: `\\temp\test`（CLI引数が最優先）

## Config Schema（設定項目）

### 最小限の必須項目

```json
{
  "version": "1.0",
  "jobId": "rakuraku-expense-approval",
  "paths": {
    "queueRoot": "\\\\server\\share\\rpa-queue",
    "artifactsRoot": "C:\\ProgramData\\RPA\\artifacts",
    "inputDir": "C:\\ProgramData\\RPA\\input",
    "outputDir": "C:\\ProgramData\\RPA\\output"
  },
  "credentials": {
    "rakuraku": {
      "companyCode": "${RAKURAKU_COMPANY_CODE}",
      "userId": "${RAKURAKU_USER_ID}",
      "passwordEnvVar": "RAKURAKU_PASSWORD"
    }
  },
  "timeouts": {
    "default": 30000,
    "navigation": 60000,
    "api": 10000
  },
  "retry": {
    "maxAttempts": 3,
    "backoff": "exponential"
  },
  "evidence": {
    "trace": "retain-on-failure",
    "screenshot": "only-on-failure",
    "video": "off"
  }
}
```

### 項目の分類

| カテゴリ | 項目 | 客先が選ぶ？ | 固定してよい？ |
|---------|------|------------|--------------|
| **パス** | queueRoot, artifactsRoot, inputDir, outputDir | ✓ | - |
| **資格情報** | companyCode, userId, passwordEnvVar | ✓ | - |
| **タイムアウト** | default, navigation, api | - | ✓（標準値） |
| **リトライ** | maxAttempts, backoff | - | ✓（標準値） |
| **証跡** | trace, screenshot, video | △ | ✓（デフォルトはoff/失敗時のみ） |

## First-Run Wizard（初回起動ウィザード）

### 動作フロー

```
1. config.jsonが存在するか？
   ├─ Yes → 既存設定をロード
   └─ No  → 初回起動ウィザード開始

2. ウィザードで質問
   - 共有フォルダパス（queueRoot）
   - 入力フォルダパス（inputDir）
   - 出力フォルダパス（outputDir）
   - 楽楽精算の会社コード

3. パス妥当性検証
   - 存在するか？
   - 書込権限があるか？
   - 空き容量は十分か？（最低10GB）

4. config.json作成
   - デフォルト値とユーザー入力をマージ
   - パスワードは環境変数名のみ保存

5. 完了メッセージ
   - config.jsonの場所を表示
   - 環境変数の設定方法を案内
```

### 実装例（TypeScript）

```typescript
import * as fs from 'fs';
import * as path from 'path';
import * as readline from 'readline';

async function firstRunWizard(): Promise<void> {
  console.log('=== RPA Config Wizard ===\n');

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  const question = (prompt: string): Promise<string> =>
    new Promise(resolve => rl.question(prompt, resolve));

  // 質問
  const queueRoot = await question('共有フォルダパス（queueRoot）: ');
  const inputDir = await question('入力フォルダパス（inputDir）: ');
  const outputDir = await question('出力フォルダパス（outputDir）: ');
  const companyCode = await question('楽楽精算の会社コード: ');

  rl.close();

  // 検証
  console.log('\nValidating paths...');
  validatePath(queueRoot, 'queueRoot');
  validatePath(inputDir, 'inputDir');
  validatePath(outputDir, 'outputDir');

  // config.json作成
  const config = {
    version: '1.0',
    jobId: 'rakuraku-expense-approval',
    paths: {
      queueRoot,
      artifactsRoot: path.join(outputDir, 'artifacts'),
      inputDir,
      outputDir
    },
    credentials: {
      rakuraku: {
        companyCode,
        userId: '${RAKURAKU_USER_ID}',
        passwordEnvVar: 'RAKURAKU_PASSWORD'
      }
    },
    // ... デフォルト値
  };

  fs.writeFileSync('config.json', JSON.stringify(config, null, 2));

  console.log('\n✓ config.json created successfully!');
  console.log('  Location:', path.resolve('config.json'));
  console.log('\nNext steps:');
  console.log('  1. Set environment variables:');
  console.log('     setx RAKURAKU_USER_ID "your-user-id"');
  console.log('     setx RAKURAKU_PASSWORD "your-password"');
  console.log('  2. Run the RPA: npm start');
}

function validatePath(p: string, name: string): void {
  if (!fs.existsSync(p)) {
    throw new Error(`${name} does not exist: ${p}`);
  }

  // 書込権限チェック（Windows）
  try {
    const testFile = path.join(p, '.write-test');
    fs.writeFileSync(testFile, 'test');
    fs.unlinkSync(testFile);
  } catch (err) {
    throw new Error(`${name} is not writable: ${p}`);
  }

  console.log(`  ✓ ${name}: ${p}`);
}
```

## Config Loading（設定読み込み）

### 優先順位を適用したロード

```typescript
import * as fs from 'fs';
import * as path from 'path';

interface Config {
  paths: {
    queueRoot: string;
    artifactsRoot: string;
    inputDir: string;
    outputDir: string;
  };
  // ... その他
}

function loadConfig(): Config {
  // 1. Default values
  const defaultConfig: Config = {
    paths: {
      queueRoot: '\\\\server\\share\\rpa-queue',
      artifactsRoot: 'C:\\ProgramData\\RPA\\artifacts',
      inputDir: 'C:\\ProgramData\\RPA\\input',
      outputDir: 'C:\\ProgramData\\RPA\\output'
    },
    // ...
  };

  // 2. Load config.json
  let fileConfig = {};
  if (fs.existsSync('config.json')) {
    fileConfig = JSON.parse(fs.readFileSync('config.json', 'utf-8'));
  }

  // 3. Environment variables
  const envConfig = {
    paths: {
      queueRoot: process.env.QUEUE_ROOT,
      inputDir: process.env.INPUT_DIR,
      outputDir: process.env.OUTPUT_DIR,
    }
  };

  // 4. CLI arguments (例: --queue-root="...")
  const cliConfig = {
    paths: {
      queueRoot: process.argv.includes('--queue-root')
        ? process.argv[process.argv.indexOf('--queue-root') + 1]
        : undefined,
    }
  };

  // マージ（優先順位: default < file < env < cli）
  const merged = deepMerge(defaultConfig, fileConfig, envConfig, cliConfig);

  // 環境変数展開（${VAR_NAME}）
  return expandEnvVars(merged);
}

function expandEnvVars(config: any): any {
  const json = JSON.stringify(config);
  const expanded = json.replace(/\$\{(\w+)\}/g, (_, varName) =>
    process.env[varName] || ''
  );
  return JSON.parse(expanded);
}
```

## Path Validation（パス妥当性検証）

### チェック項目

```typescript
function validateConfig(config: Config): void {
  // 1. 存在チェック
  for (const [key, p] of Object.entries(config.paths)) {
    if (!fs.existsSync(p)) {
      throw new Error(`Path does not exist: ${key}=${p}`);
    }
  }

  // 2. 書込権限チェック
  for (const [key, p] of Object.entries(config.paths)) {
    if (key.endsWith('Dir') || key.endsWith('Root')) {
      try {
        const testFile = path.join(p, '.write-test');
        fs.writeFileSync(testFile, 'test');
        fs.unlinkSync(testFile);
      } catch (err) {
        throw new Error(`Path is not writable: ${key}=${p}`);
      }
    }
  }

  // 3. 空き容量チェック（Windows）
  // 注: Node.jsには標準機能なし、外部ライブラリ使用またはスキップ
  console.warn('Disk space check not implemented (requires external library)');

  console.log('✓ All paths validated successfully');
}
```

## Integration with Shared Work Queue（共有ワークとの統合）

### config.jsonにキューパスを含める

```json
{
  "paths": {
    "queueRoot": "\\\\server\\share\\rpa-queue",
    "artifactsRoot": "C:\\ProgramData\\RPA\\artifacts",
    "inputDir": "C:\\ProgramData\\RPA\\input",
    "outputDir": "C:\\ProgramData\\RPA\\output"
  }
}
```

### Worker起動時にconfigから読み込み

```typescript
const config = loadConfig();

const worker = new WorkerLoop(
  config.paths.queueRoot,
  `RPA-${os.hostname()}`
);

await worker.start();
```

## Instructions（実装手順）

### 1. スキーマ定義

```bash
# references/config-schema.json を作成（JSON Schema形式）
```

### 2. 初回起動ウィザード実装

```typescript
// src/config/wizard.ts
```

### 3. Config読み込みロジック実装

```typescript
// src/config/loader.ts
```

### 4. main.tsで統合

```typescript
// main.ts
import { loadConfig, validateConfig } from './config/loader';
import { firstRunWizard } from './config/wizard';
import * as fs from 'fs';

async function main() {
  if (!fs.existsSync('config.json')) {
    await firstRunWizard();
  }

  const config = loadConfig();
  validateConfig(config);

  // ... RPAフロー実行
}
```

### 5. 環境変数の案内

**README.md**:
```markdown
## Setup

### First-time setup

1. Run the RPA once:
   ```
   npm start
   ```

2. Follow the wizard prompts

3. Set environment variables:
   ```
   setx RAKURAKU_USER_ID "your-user-id"
   setx RAKURAKU_PASSWORD "your-password"
   ```

4. Run again:
   ```
   npm start
   ```
```

## Examples（使用例）

### Example 1: 初回起動

```bash
$ npm start

=== RPA Config Wizard ===

共有フォルダパス（queueRoot）: \\192.168.1.100\rpa\queue
入力フォルダパス（inputDir）: C:\RPA\input
出力フォルダパス（outputDir）: C:\RPA\output
楽楽精算の会社コード: 12345

Validating paths...
  ✓ queueRoot: \\192.168.1.100\rpa\queue
  ✓ inputDir: C:\RPA\input
  ✓ outputDir: C:\RPA\output

✓ config.json created successfully!
  Location: C:\ProgramData\RPA\config.json

Next steps:
  1. Set environment variables:
     setx RAKURAKU_USER_ID "your-user-id"
     setx RAKURAKU_PASSWORD "your-password"
  2. Run the RPA: npm start
```

### Example 2: 環境変数で上書き

```bash
# config.jsonではqueueRoot=\\server\share
# 環境変数で一時的に変更
set QUEUE_ROOT=\\test\queue
npm start

# → \\test\queue が使われる
```

### Example 3: CLI引数で上書き

```bash
# 本番実行（config.jsonの値を使用）
npm start

# テスト実行（CLI引数で上書き）
npm start -- --queue-root "C:\temp\test-queue" --dry-run
```

## Troubleshooting（トラブルシューティング）

### 問題1: ウィザードがループする

**原因**: パス検証に失敗している

**解決**:
- 指定したパスが存在するか確認
- 書込権限があるか確認
- UNCパスの場合、ネットワーク接続を確認

### 問題2: 環境変数が反映されない

**原因**: `set`（一時）と `setx`（永続）を間違えている

**解決**:
```bash
# 永続設定（新しいターミナルで有効）
setx RAKURAKU_PASSWORD "password"

# 一時設定（現在のターミナルのみ）
set RAKURAKU_PASSWORD=password
```

### 問題3: config.jsonが見つからない

**原因**: カレントディレクトリが異なる

**解決**:
```typescript
// 絶対パスで指定
const configPath = path.join(__dirname, 'config.json');
```

### 問題4: 共有フォルダにアクセスできない

**原因**: ネットワークドライブがマッピングされていない、または認証が必要

**解決**:
- UNCパス直接指定（`\\server\share`）を推奨
- ドライブマッピング（`Z:\`）は避ける
- 認証が必要な場合、Windowsの資格情報マネージャーに保存

### 問題5: パスワードが平文でconfig.jsonに保存された

**対応**:
- 即座に削除
- 環境変数名（`${RAKURAKU_PASSWORD}`）に置き換え
- config.jsonを`.gitignore`に追加

## References

- [設定優先順位仕様](references/config-precedence.md)
- [設定スキーマ](references/config-schema.json)
- [サンプルconfig](examples/config.sample.json)
- [初回起動ウィザード](assets/first-run-wizard-script.md)
