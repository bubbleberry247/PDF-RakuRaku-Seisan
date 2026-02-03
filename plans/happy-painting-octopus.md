# Plan: AI コスト管理ダッシュボード（GAS Webapp）

## 概要

AIサービスの **固定サブスク + API従量課金** を一元管理し、月別合計・予算対比を可視化するGAS Webアプリ。

## データ設計（Spreadsheet）

### Subscriptions シート（固定費）
| 列 | 説明 | 例 |
|----|------|-----|
| id | 自動生成ID | sub_001 |
| name | サービス名 | ChatGPT Pro |
| category | カテゴリ | AI Chat |
| type | fixed / api | fixed |
| monthlyCost | 月額（USD）※fixedのみ | 200 |
| currency | 通貨 | USD |
| billingDay | 請求日 | 15 |
| startDate | 開始日 | 2025-01-15 |
| endDate | 終了日（空=継続中） | |
| status | active / cancelled / paused | active |
| monthlyBudget | API予算上限（USD）※apiのみ | 100 |
| notes | メモ | 年払いなら$2400/yr |
| updatedAt | 更新日時 | 2026-02-02T10:00:00 |

### ApiUsage シート（API従量課金の月次記録）
| 列 | 説明 | 例 |
|----|------|-----|
| id | 自動生成ID | usage_202602_anthropic |
| subscriptionId | Subscriptionsのid | sub_005 |
| yearMonth | 年月 | 2026-02 |
| actualCostUSD | 実績コスト（USD） | 87.50 |
| inputTokens | 入力トークン数 | 12000000 |
| outputTokens | 出力トークン数 | 3500000 |
| notes | メモ | Opus多用 |
| recordedAt | 記録日時 | 2026-02-02T10:00:00 |

### Config シート
| key | value |
|-----|-------|
| MONTHLY_BUDGET_USD | 800 |
| USD_JPY_RATE | 150 |
| ALERT_THRESHOLD_PCT | 80 |

## GASファイル構成

```
ai-subscription-dashboard/
├── .clasp.json
└── src/
    ├── Code.gs       # doGet + admin endpoints (?action=setupDb&dbId=xxx)
    ├── api.gs        # apiGetDashboard, apiUpsertSubscription, apiDeleteSubscription
    ├── logic.gs      # 集計ロジック（月別合計、予算対比、為替換算）
    ├── db.gs         # SHEETS/HEADERS定義、CRUD helpers
    └── index.html    # SPA（一覧テーブル + 追加/編集フォーム + サマリーカード）
```

## 画面設計

### ホーム画面（1画面SPA）

```
┌──────────────────────────────────────────────┐
│  AI Cost Dashboard                 2026年2月  │
├──────────────────────────────────────────────┤
│                                              │
│  [月額合計]     [予算]      [残り]            │
│   $650/月       $800/月     $150 (19%)       │
│   ¥97,500       ¥120,000   ¥22,500          │
│                                              │
│  ── 固定サブスクリプション ($350) ──          │
│                                              │
│  │ ChatGPT Pro     $200/月  毎月15日    │    │
│  │ Claude Max      $100/月  毎月1日     │    │
│  │ Cursor Pro       $20/月  毎月10日    │    │
│  │ Gemini Advanced  $20/月  毎月5日     │    │
│  │ GitHub Copilot   $10/月  毎月1日     │    │
│                                              │
│  ── API従量課金 (今月 $300 / 予算 $450) ──   │
│                                              │
│  │ Anthropic API   $200  [████████░░] 80%│   │
│  │ OpenAI API       $87  [████░░░░░░] 44%│   │
│  │ Google AI        $13  [█░░░░░░░░░] 13%│   │
│                                              │
│  [+ 追加]  [API実績を記録]                    │
│                                              │
│  ── 停止済み ──                               │
│  │ Midjourney       $10/月  2025-12停止  │   │
│                                              │
└──────────────────────────────────────────────┘
```

### 追加/編集モーダル

**固定サブスク (type=fixed):**
- サービス名、カテゴリ、月額、通貨、請求日、ステータス、メモ

**API従量課金 (type=api):**
- サービス名、カテゴリ、月予算上限、通貨、ステータス、メモ

### API実績記録モーダル

- サービス選択（apiタイプのみ）
- 年月（YYYY-MM）
- 実績コスト（USD）
- トークン数（入力/出力、任意）
- メモ

## API設計

| 関数名 | 引数 | 戻り値 |
|--------|------|--------|
| `apiGetDashboard(yearMonth)` | "2026-02" | { subscriptions, apiUsage, summary, config } |
| `apiUpsertSubscription(data)` | { id?, name, type, monthlyCost, ... } | { ok, subscription } |
| `apiDeleteSubscription(id)` | id | { ok } |
| `apiRecordApiUsage(data)` | { subscriptionId, yearMonth, actualCostUSD, ... } | { ok } |
| `apiUpdateConfig(key, value)` | key, value | { ok } |

## サマリー計算ロジック（logic.gs）

```javascript
function calculateSummary_(subscriptions, apiUsage, config) {
  var rate = Number(config.USD_JPY_RATE || 150);
  var budget = Number(config.MONTHLY_BUDGET_USD || 800);

  var fixedUSD = 0;
  var apiActualUSD = 0;
  var apiBudgetUSD = 0;

  subscriptions.forEach(function(s) {
    if (s.status !== 'active') return;
    var cost = Number(s.monthlyCost || 0);
    if (s.currency === 'JPY') cost = cost / rate;

    if (s.type === 'api') {
      apiBudgetUSD += Number(s.monthlyBudget || 0);
    } else {
      fixedUSD += cost;
    }
  });

  // Current month API actual
  apiUsage.forEach(function(u) {
    apiActualUSD += Number(u.actualCostUSD || 0);
  });

  var totalUSD = fixedUSD + apiActualUSD;

  return {
    fixedUSD: fixedUSD,
    apiActualUSD: apiActualUSD,
    apiBudgetUSD: apiBudgetUSD,
    totalUSD: totalUSD,
    totalJPY: Math.round(totalUSD * rate),
    budgetUSD: budget,
    remainUSD: budget - totalUSD,
    remainPct: Math.round((budget - totalUSD) / budget * 100),
    overBudget: totalUSD > budget
  };
}
```

## 認証

- archi-16wのハイブリッド認証は不要（個人利用ダッシュボード）
- GASデプロイ設定で「自分のみ」にすればGoogle認証で十分
- 複数人で共有する場合は「組織内」に設定

## 実装ステップ

1. **GASプロジェクト作成** — `clasp create --type webapp --title "AI Sub Dashboard"`
2. **db.gs** — SHEETS/HEADERS定義、getDb_/getSheet_/readRecords_/upsertByKey_ helpers
3. **logic.gs** — calculateSummary_、ID生成
4. **api.gs** — apiGetDashboard / apiUpsertSubscription / apiDeleteSubscription
5. **Code.gs** — doGet + setupDb endpoint
6. **index.html** — サマリーカード + テーブル + 追加/編集モーダル
7. **初期データ投入** — 現在のサブスク一覧をSpreadsheetに手入力 or UIから追加
8. **デプロイ** — `clasp push && clasp deploy`

## 対象ファイル（新規作成）

| ファイル | 内容 |
|---------|------|
| `ai-subscription-dashboard/src/Code.gs` | エントリポイント |
| `ai-subscription-dashboard/src/api.gs` | Public API |
| `ai-subscription-dashboard/src/logic.gs` | 集計ロジック |
| `ai-subscription-dashboard/src/db.gs` | データ層 |
| `ai-subscription-dashboard/src/index.html` | SPA UI |
| `ai-subscription-dashboard/.clasp.json` | clasp設定 |

## 配置先

`C:\ProgramData\Generative AI\Github\ai-subscription-dashboard\`
（独立リポジトリ。PDF-RakuRaku-Seisanとは別）

## Phase 2: 自動金額計算（@6）

### 概要
派生計算（年間予測・JPY換算・予算進捗）+ API実績自動取得の基盤を追加。

### 2A: 派生計算（クライアント側 — index.html）

| 計算 | 場所 | 内容 |
|------|------|------|
| 年間コスト予測 | サマリーカード追加 | totalUSD × 12, totalJPY × 12 |
| フォーム内JPY換算 | 追加/編集モーダル | 月額USD入力時にリアルタイムで「≈ ¥XX,XXX」表示 |
| 予算消化率バー | サマリーカード | 全体予算の消化%を視覚的プログレスバーで表示 |
| 固定費小計 | 固定サブスクセクション見出し | 既存（$350）に加えて ¥52,500 も表示 |
| API小計 | APIセクション見出し | 実績$300 + 予算$450 に加えて ¥換算も表示 |

### 2B: API実績自動取得（サーバー側 — api.gs + logic.gs）

**対象API:**
| サービス | 課金API | Configキー |
|----------|---------|------------|
| Anthropic | `https://api.anthropic.com/v1/organizations/{org_id}/usage` | ANTHROPIC_API_KEY |
| OpenAI | `https://api.openai.com/v1/organization/costs` | OPENAI_API_KEY |
| Google AI | `https://generativelanguage.googleapis.com/` (なし→手動) | — |

**フロー:**
```
ユーザー「自動取得」ボタン押下
  ↓
apiAutoFetchUsage(yearMonth)
  ↓
各サービスのConfigにAPIキーがあるか確認
  ↓ あれば
UrlFetchApp で課金APIを呼び出し
  ↓
結果をApiUsageシートに自動記録（upsert）
  ↓
ダッシュボード自動リロード
```

**APIキー未設定時:** 「APIキーをConfigに登録してください」メッセージ表示。手動入力は引き続き可能。

### 新規API関数
```javascript
// api.gs
function apiAutoFetchUsage(yearMonth) {
  // Config からAPIキーを取得
  // 各プロバイダーの課金APIを呼び出し
  // ApiUsageシートにupsert
  // 結果サマリーを返す
}
```

### 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `index.html` | 年間予測カード、JPYリアルタイム換算、予算消化バー、「自動取得」ボタン |
| `api.gs` | `apiAutoFetchUsage(yearMonth)` 追加 |
| `logic.gs` | `fetchAnthropicUsage_()`, `fetchOpenAIUsage_()` 追加 |
| `db.gs` | 変更なし |

### Verification
1. サマリーに年間予測（$7,800/yr, ¥1,170,000/yr）が表示される
2. 月額入力フォームでUSD入力→JPY換算がリアルタイム表示
3. 予算消化プログレスバーが正しく表示
4. APIキー未設定で「自動取得」→適切なエラーメッセージ
5. （将来）APIキー設定後、「自動取得」→ApiUsageに自動記録

---

## Verification（Phase 1）

1. `clasp push && clasp deploy` 成功
2. デプロイURL → ダッシュボード表示
3. サブスク追加 → テーブルに反映 → サマリー更新
4. サブスク編集 → 変更がSpreadsheetに保存
5. サブスク停止 → 「停止済み」セクションに移動 → 合計から除外
6. 予算超過 → サマリーに警告表示
