# Config Precedence（設定優先順位詳細）

## 優先順位の原則

```
CLI Arguments  >  Environment Variables  >  config.json  >  Default Values
    (最優先)            (次点)                 (標準)        (最終フォールバック)
```

### 優先順位の理由

| レイヤー | 用途 | 上書き可能性 | 永続性 |
|---------|------|-------------|--------|
| CLI Arguments | テスト・一時実行 | 実行ごと | なし（コマンド引数のみ） |
| Environment Variables | 環境ごとの差異 | セッション or 永続 | setx で永続化可 |
| config.json | プロジェクト標準設定 | 手動編集 | ファイル保存 |
| Default Values | フォールバック | コード変更のみ | コード埋込 |

---

## マージロジック

### 基本アルゴリズム

```typescript
function loadConfig(): Config {
  // 1. Default values（コード内定義）
  const defaultConfig = { ... };

  // 2. config.json読み込み
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

  // 4. CLI arguments
  const cliConfig = parseCLIArgs(process.argv);

  // Deep merge: default < file < env < cli
  const merged = deepMerge(defaultConfig, fileConfig, envConfig, cliConfig);

  // 5. 環境変数展開（${VAR_NAME}）
  return expandEnvVars(merged);
}
```

### deepMerge の挙動

```typescript
// 右側（後の引数）が優先
deepMerge(
  { a: 1, b: { x: 10, y: 20 } },
  { b: { x: 99 }, c: 3 }
)
// → { a: 1, b: { x: 99, y: 20 }, c: 3 }
```

**重要**: ネストしたオブジェクトは再帰的にマージ。配列は右側が完全上書き。

---

## 環境変数展開

### テンプレート構文

```json
{
  "credentials": {
    "rakuraku": {
      "companyCode": "${RAKURAKU_COMPANY_CODE}",
      "userId": "${RAKURAKU_USER_ID}",
      "passwordEnvVar": "RAKURAKU_PASSWORD"
    }
  }
}
```

### 展開タイミング

```
1. config.json読み込み（JSON.parse）
   ↓
2. 4層マージ（default/file/env/cli）
   ↓
3. 環境変数展開（${...}を置換）  ← このタイミング
   ↓
4. 最終Configオブジェクト
```

### 展開の実装

```typescript
function expandEnvVars(config: any): any {
  const json = JSON.stringify(config);
  const expanded = json.replace(/\$\{(\w+)\}/g, (_, varName) =>
    process.env[varName] || ''
  );
  return JSON.parse(expanded);
}
```

**注意**: 環境変数が未定義の場合は空文字列に置換される（エラーにならない）。

---

## CLI引数のパース

### 引数形式

```bash
# Long option (推奨)
--queue-root "\\\\server\\share\\queue"
--dry-run
--timeout 120000

# Short option（サポートする場合）
-q "\\\\server\\share\\queue"
-d
```

### パースロジック例

```typescript
function parseCLIArgs(argv: string[]): Partial<Config> {
  const config: any = {};

  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];

    if (arg === '--queue-root' && argv[i + 1]) {
      config.paths = config.paths || {};
      config.paths.queueRoot = argv[i + 1];
      i++;
    } else if (arg === '--dry-run') {
      config.dryRun = true;
    } else if (arg === '--timeout' && argv[i + 1]) {
      config.timeouts = config.timeouts || {};
      config.timeouts.default = parseInt(argv[i + 1], 10);
      i++;
    }
  }

  return config;
}
```

---

## 環境変数の命名規則

### プレフィックス（オプション）

```bash
# プレフィックスなし（シンプル）
QUEUE_ROOT=\\\\server\\share\\queue
INPUT_DIR=C:\\RPA\\input

# プレフィックスあり（名前空間分離）
RPA_QUEUE_ROOT=\\\\server\\share\\queue
RPA_INPUT_DIR=C:\\RPA\\input
```

### 推奨命名

| 項目 | 環境変数名 | 説明 |
|------|-----------|------|
| キューパス | `QUEUE_ROOT` | 共有フォルダパス |
| 入力フォルダ | `INPUT_DIR` | ローカル入力フォルダ |
| 出力フォルダ | `OUTPUT_DIR` | ローカル出力フォルダ |
| 資格情報 | `RAKURAKU_COMPANY_CODE` | 楽楽精算会社コード |
| 資格情報 | `RAKURAKU_USER_ID` | 楽楽精算ユーザーID |
| 資格情報 | `RAKURAKU_PASSWORD` | 楽楽精算パスワード |

---

## 優先順位の実例

### 例1: queueRoot の決定

```typescript
// デフォルト
const defaultConfig = {
  paths: { queueRoot: "\\\\default-server\\queue" }
};

// config.json
{
  "paths": { "queueRoot": "\\\\config-server\\queue" }
}

// 環境変数
QUEUE_ROOT=\\\\env-server\\queue

// CLI引数
--queue-root "\\\\cli-server\\queue"
```

**結果**: `\\\\cli-server\\queue`（CLI引数が最優先）

---

### 例2: 部分的な上書き

```typescript
// デフォルト
{
  timeouts: { default: 30000, navigation: 60000, api: 10000 }
}

// config.json
{
  timeouts: { navigation: 90000 }
}

// マージ結果
{
  timeouts: { default: 30000, navigation: 90000, api: 10000 }
}
```

**ポイント**: `timeouts.navigation` のみ上書き、他は残る。

---

## 環境変数の永続化（Windows）

### 一時設定（現在のセッションのみ）

```cmd
set QUEUE_ROOT=\\\\server\\queue
```

**有効範囲**: 現在のコマンドプロンプト/PowerShellセッションのみ

---

### 永続設定（全セッション）

```cmd
setx QUEUE_ROOT "\\\\server\\queue"
```

**有効範囲**: 新しいターミナルセッション以降（現在のセッションには反映されない）

**注意**: `setx` 実行後、**新しいターミナルを開く**必要がある。

---

## トラブルシューティング

### 問題1: 環境変数が反映されない

**原因**: `set` を使用している（一時設定）

**解決**:
```cmd
# 永続設定に変更
setx QUEUE_ROOT "\\\\server\\queue"

# 新しいターミナルを開く
```

---

### 問題2: config.json の値が環境変数で上書きできない

**原因**: 環境変数名が間違っている

**確認方法**:
```cmd
# 環境変数の確認
echo %QUEUE_ROOT%

# または
set | findstr QUEUE
```

---

### 問題3: CLI引数が無視される

**原因**: パースロジックのバグ、または引数の形式が間違っている

**確認方法**:
```typescript
// デバッグ出力
console.log('CLI args:', process.argv);
console.log('Parsed config:', cliConfig);
```

---

### 問題4: ${VAR_NAME} が展開されない

**原因**: 環境変数が設定されていない

**確認方法**:
```cmd
# 環境変数の確認
echo %RAKURAKU_PASSWORD%

# 未設定の場合は設定
setx RAKURAKU_PASSWORD "your_password_here"
```

---

## セキュリティ考慮事項

### パスワード等の秘密情報

**NG例**:
```json
{
  "credentials": {
    "password": "plaintextPassword123"  // 平文で保存（危険）
  }
}
```

**推奨例**:
```json
{
  "credentials": {
    "passwordEnvVar": "RAKURAKU_PASSWORD"  // 環境変数名のみ保存
  }
}
```

実行時に環境変数から取得:
```typescript
const password = process.env[config.credentials.passwordEnvVar];
```

---

## ベストプラクティス

1. **デフォルト値は「動く最小構成」にする**
   - 開発環境ですぐ動く値を設定
   - 本番環境は環境変数/CLI引数で上書き

2. **config.json はリポジトリに含める（秘密情報なし）**
   - テンプレート値を記載
   - パスワードは `${VAR_NAME}` で参照

3. **環境変数は `.env.example` で文書化**
   ```bash
   # .env.example
   QUEUE_ROOT=\\\\server\\share\\queue
   RAKURAKU_COMPANY_CODE=12345
   RAKURAKU_USER_ID=user01
   RAKURAKU_PASSWORD=your_password_here
   ```

4. **CLI引数はテスト用途に限定**
   - 本番運用では config.json + 環境変数を推奨
   - CLI引数は一時的なテスト・検証のみ

5. **検証を忘れない**
   - 必須項目の存在チェック
   - パスの存在・権限チェック
   - 型の検証（number, boolean等）

---

## まとめ

- **優先順位**: CLI > ENV > file > defaults
- **マージ**: ネストオブジェクトは再帰的にマージ
- **環境変数展開**: マージ後に `${VAR_NAME}` を置換
- **永続化**: `setx`（Windows）または `export`（Linux/Mac）の .bashrc/.zshrc 追記
- **セキュリティ**: 秘密情報は環境変数経由のみ
