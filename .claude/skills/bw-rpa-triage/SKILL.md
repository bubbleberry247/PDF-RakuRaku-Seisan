---
name: bw-rpa-triage
description: |
  失敗したrunの証跡から原因を最短で特定し、一次報告(incident report)と恒久対策案まで出す。
  動的コンテキスト注入: 証跡フォルダを解析して主要情報を自動抽出。

  トリガー: 原因究明、トラブルシューティング、失敗、障害、incident report、調査、analyze、診断
disable-model-invocation: true
argument-hint: "[artifact-folder-path or runId]"
allowed-tools: ["Read", "Grep", "Glob", "Bash(node:*)", "Bash(npx:*)"]
---

# bw-rpa-triage

## Purpose（目的）

失敗したRPA実行の証跡を体系的に調査し、原因特定と恒久対策案を出す。

**目標**:
- 原因特定までの時間を最小化（MTTR短縮）
- 属人的な「勘」ではなく、手順化された調査
- 一次報告（incident report）の自動生成
- 恒久対策案の提示

## When to Use（いつ使う）

- RPAジョブが失敗した時（証跡フォルダパスを渡す）
- 障害報告書を作成する時
- 過去の失敗を分析する時
- 類似障害の傾向分析をする時

## Inputs / Outputs

**Inputs**:
- Artifact folder path（例: `artifacts/rakuraku-expense/20260214-160000-abc123`）
- または runId（自動でパス解決）

**Outputs**:
- Incident report（Markdown形式）
- 原因カテゴリと根本原因の特定
- 恒久対策案

## Triage Process（調査手順）

### Phase 1: 証跡収集状況の確認

**動的コンテキスト注入**:
```bash
! node .claude/skills/bw-rpa-triage/scripts/summarize_artifacts.mjs "$ARGUMENTS"
```

出力例:
```
Artifact Summary for: 20260214-160000-abc123
==================================================
Directory: artifacts/rakuraku-expense/20260214-160000-abc123

Files Found:
  ✓ metadata.json (12 KB)
  ✓ execution.log (245 KB)
  ✓ trace.zip (18 MB)
  ✓ screenshots/ (2 files, 450 KB total)
  ✗ videos/ (NOT FOUND)
  ✓ network/trace.har (5 MB)
  ✓ input/hash.txt (65 bytes)
  ✓ input/sample.json (12 KB)

Key Metadata:
  Status: failed
  Error Type: TimeoutError
  Error Message: Timeout 30000ms exceeded.
  Failed Step: STEP-2
  Retry Count: 2
  Duration: 93000 ms
  Start: 2026-02-14T15:30:42+09:00
  End: 2026-02-14T15:32:15+09:00

Log Summary (last 20 lines):
  [INFO] [STEP-1] Login completed (2000ms)
  [INFO] [STEP-2] Starting expense processing
  [ERROR] [STEP-2] Timeout 30000ms exceeded
  [WARN] [RETRY] Attempt 1 of 3
  ...

Recommendation:
  - Trace.zip available → Use Playwright Trace Viewer
  - Screenshots: 2 files → Check for UI changes
  - Network HAR: 5MB → Check for API failures
```

### Phase 2: 原因カテゴリの判定

**典型的な原因カテゴリ**:

| カテゴリ | 特徴的なエラー | 確認すべき証跡 |
|---------|---------------|--------------|
| **UI変更** | TimeoutError, 要素が見つからない | screenshots, trace |
| **認証** | 401, 403, ログインループ | network HAR, screenshots |
| **権限** | 403, EACCES, ファイル書込失敗 | execution.log, metadata.env |
| **ネットワーク** | ECONNREFUSED, ETIMEDOUT, DNS | network HAR, execution.log |
| **Proxy/SSL** | certificate error, CERT_INVALID | network HAR |
| **タイムアウト** | Timeout 30000ms exceeded | execution.log, trace |
| **データ不整合** | 想定外の値、NULL、空配列 | input/, execution.log |
| **リソース不足** | ENOMEM, ディスク容量 | metadata.env, execution.log |

### Phase 3: 見る順番（優先順位）

1. **metadata.json**: エラー型、失敗ステップ、環境情報
2. **execution.log**: エラー前後のステップ、リトライ状況
3. **screenshots**: UI変更の有無、エラー画面
4. **trace.zip**: 詳細な操作履歴（Playwright Trace Viewer）
5. **network/trace.har**: API呼び出し、レスポンス、エラーコード
6. **input/**: 入力データの妥当性

### Phase 4: 根本原因の特定

**5 Whys法**:
```
現象: 楽楽精算へのログインが失敗

Why1: ログインボタンが見つからない
  → セレクタが無効

Why2: セレクタが無効になった理由は？
  → UIが変更された

Why3: UIが変更されたのはいつ？
  → 2026-02-14（前日の実行は成功していた）

Why4: なぜ事前に検知できなかった？
  → UI変更検知の仕組みがない

Why5: なぜ仕組みがない？
  → 設計時に考慮されていなかった

根本原因: UI変更検知の仕組み不足
```

### Phase 5: 再実行判定

**再実行して良い条件**:
- 一時的なネットワーク障害
- タイムアウト（業務ピーク時間帯のみ）
- リソース不足（メモリ/ディスク一時的）

**再実行してはいけない条件**:
- UI変更（修正なしでは必ず失敗する）
- 認証エラー（アカウント無効化等）
- データ不整合（入力データの修正が必要）
- 副作用あり（すでに一部処理済み）

### Phase 6: Incident Report生成

テンプレートを埋めて出力:
- [assets/incident-report-template.md](../bw-rpa-evidence-bundle/assets/incident-report-template.md) を使用

## Instructions（実装手順）

### 1. スキル呼び出し

```bash
/bw-rpa-triage artifacts/rakuraku-expense/20260214-160000-abc123
```

または

```bash
/bw-rpa-triage 20260214-160000-abc123
```

### 2. 動的コンテキスト注入の実行

スキルが自動的に `summarize_artifacts.mjs` を実行し、証跡の概要を取得。

### 3. 段階的調査

Claude Codeが以下を実施:

1. **metadata.json読み取り**: エラー型、失敗ステップ特定
2. **execution.log検索**: エラー前後の文脈確認
3. **screenshots確認**: UI変更の有無を目視
4. **原因カテゴリ判定**: 典型パターンとマッチング
5. **根本原因特定**: 5 Whys法で掘り下げ
6. **恒久対策案**: 再発防止策を提示

### 4. Incident Report出力

```markdown
# Incident Report

## 基本情報
- 発生日時: 2026-02-14 15:30:42 (JST)
- ジョブID: rakuraku-expense-approval
- 実行ID: 20260214-160000-abc123
- 報告者: Claude Code
- 影響範囲: 10件中5件が未完了
- 緊急度: 中

## 症状
楽楽精算への経費申請登録処理が30秒でタイムアウトし、失敗。

## 原因
- **カテゴリ**: UI変更
- **根本原因**: ログインボタンのセレクタが `button[type="submit"]` から `#login-btn` に変更

## 証跡
- trace.zip: 18MB
- screenshots: 2枚（エラー画面含む）

## 暫定対応
セレクタを手動修正し、再実行成功。

## 恒久対策案
1. セレクタを `data-testid` に変更（UI変更に強い）
2. 定期的なUI構造スナップショット比較
3. タイムアウト時間を60秒に延長

...
```

### 5. 例外処理

- **証跡不足**: 最低限（metadata + log）があれば調査可能。traceなしでも推測
- **複数原因**: 最も影響が大きいものを主原因とし、他は副次的要因として記載
- **原因不明**: 「現時点で特定できず、追加調査が必要」と明記

## Examples（使用例）

### Example 1: UI変更による失敗

```bash
/bw-rpa-triage 20260214-160000-abc123
```

**出力**:
```markdown
# Triage Result

## 原因カテゴリ: UI変更

## 根本原因
ログインボタンのセレクタ `button[type="submit"]` が無効。
スクリーンショットから、ボタンが `#login-btn` に変更されていることを確認。

## 証拠
- screenshots/error-001.png: ログイン画面（ボタン要素確認）
- trace.zip: クリック試行の詳細（Timeout発生箇所）

## 恒久対策案
1. セレクタ優先順位: `data-testid` > `role` > `id` > `class`
2. UI変更検知: 毎朝のヘルスチェックでDOM構造を比較
3. リトライロジック: 複数セレクタを順に試行

## 再実行判定
✗ 再実行不可（コード修正必要）
```

### Example 2: ネットワーク一時障害

```bash
/bw-rpa-triage 20260214-120000-xyz789
```

**出力**:
```markdown
# Triage Result

## 原因カテゴリ: ネットワーク

## 根本原因
社内Proxy経由のAPI呼び出しが ETIMEDOUT。
network/trace.har から、12:00-12:05の間のみ障害発生を確認（業務ピーク時）。

## 証拠
- network/trace.har: API呼び出し失敗ログ
- execution.log: "ETIMEDOUT" エラー

## 恒久対策案
1. リトライロジック: 3回まで自動リトライ（exponential backoff）
2. タイムアウト延長: 30秒 → 60秒
3. 実行時間帯の調整: ピーク時（12:00-13:00）を避ける

## 再実行判定
✓ 再実行可（一時的障害、現在は復旧）
```

## Troubleshooting（トラブルシューティング）

### 問題1: summarize_artifacts.mjs が実行できない

**原因**: Node.jsがインストールされていない、またはパスが通っていない

**解決**:
```bash
# Node.jsバージョン確認
node --version

# インストールされていない場合
# https://nodejs.org/ からダウンロード
```

### 問題2: 証跡フォルダが見つからない

**原因**: runIdが間違っている、またはartifacts/パスが異なる

**解決**:
```bash
# runIdで検索
find artifacts/ -type d -name "*20260214*"

# フルパスで指定
/bw-rpa-triage "C:\path\to\artifacts\rakuraku-expense\20260214-160000-abc123"
```

### 問題3: trace.zipが開けない

**原因**: Playwright Trace Viewerがインストールされていない

**解決**:
```bash
# Trace Viewerを起動
npx playwright show-trace artifacts/.../trace.zip

# またはオンライン版
# https://trace.playwright.dev/
# → zipファイルをアップロード
```

### 問題4: 原因が複数ある

**対応**:
- 最も影響が大きいものを主原因として記載
- 他は「副次的要因」セクションに列挙
- 各原因に対して個別の対策案を提示

### 問題5: 同じ原因の障害が繰り返し発生

**対応**:
- 恒久対策が実施されていない → チケット化
- 対策が不十分 → 対策のレビューと改善
- 新たな原因 → トラブルシューティングガイドに追加

## References

- [原因カテゴリ別チェックリスト](references/triage-checklist.md)
- [障害報告テンプレート](../bw-rpa-evidence-bundle/assets/incident-report-template.md)
- [証跡解析スクリプト](scripts/summarize_artifacts.mjs)
