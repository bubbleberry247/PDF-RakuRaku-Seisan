# Handoff — 2026-04-12

## セッション概要
4つの過去問トレーニングアプリ（積算士・宅建士・建築2次・土木2次）のリポジトリ作成・GASデプロイ・MUJI無印風デザイン適用

---

## 完了タスク

### 1. リポジトリ作成・GitHub push（全4本）

| repo | GitHub | 内容 |
|------|--------|------|
| `sekisan-training` | ✅ push済 | 積算士 650問、MUJI design適用 |
| `takken-training` | ✅ push済 | 宅建士 600問、MUJI design適用 |
| `archi2ji-training` | ✅ push済 | 建築2次 記述式、新規作成 |
| `doboku2ji-training` | ✅ push済 | 土木2次 記述式、新規作成 + parse_doboku2ji.py(55問CSV) |

### 2. GASデプロイ状況（最終 2026-04-12）

| アプリ | Deploy ID | Version | access | 状態 |
|--------|-----------|---------|--------|------|
| sekisan | `AKfycbyA0E4...` | @5 | ANYONE_ANONYMOUS | ✅ 問題650問投入済み |
| takken | `AKfycbyYREY...` | @4 | ANYONE_ANONYMOUS | ✅ 問題600問投入済み |
| archi2ji | `AKfycbxtZzc...` | @10 | ANYONE_ANONYMOUS | ✅ 18問（R5/R6/R7）インポート済み |
| doboku2ji | `AKfycbzJtYZ...` | @7 | ANYONE_ANONYMOUS | ✅ 55行（H28-R7）インポート済み |
| archi-16w | `AKfycbxFrKP...` | @169 | ANYONE_ANONYMOUS | ✅ （意図的修正：ANYONE→ANYONE_ANONYMOUS） |
| doboku-14w | (untouched) | — | ANYONE | ⚠️ 触らない指示（ユーザー指定） |
| construction-permit | (untouched) | — | ANYONE | ⚠️ 触らない指示（ユーザー指定） |

### 3. MUJI（無印良品）デザインシステム
全アプリに適用済み。CSS変数：
```css
--bg:#f5f4f0; --surface:#fff; --accent:#5c4f3d; --btn:#3c3530;
--ok:#4a7c59; --ng:#7c4a4a; border-radius:2px; no gradients/shadows
```

### 4. auto-setup実装
`Code.gs` に `if (!getDbId_()) { setup_(); }` を追加。
初回アクセス時にGoogleドライブにDB Spreadsheetを自動作成。

---

## 完了タスク（2026-04-12 追加）

### 5. Google OAuth 実装（archi2ji・doboku2ji）
auth.gs を移植済み。Script Properties に GOOGLE_CLIENT_ID・GOOGLE_CLIENT_SECRET 設定完了。
ログイン確認済み。

### 6. 問題データインポート ✅
- **appsscript.json バグ修正**: `"access": "ANYONE"` → `"access": "ANYONE_ANONYMOUS"` に変更
  - ANYONE = Googleサインイン必須、ANYONE_ANONYMOUS = 匿名OK（Python scriptからアクセスするため必須）
- **archi2ji**: 18問（R5/R6/R7）インポート完了
  - データソース: `C:/tmp/kakomon/kenchiku2ji/kenchiku2ji_mondai_all.json`
  - GAS: `Questions` シート（statusフィルターなし）
- **doboku2ji**: 55行（H28〜R7）インポート完了
  - データソース: `data/doboku2ji_questions.csv`
  - GAS: `QuestionBank` シート（status='published'で書き込み済み）
- インポートスクリプト: `tools/import_archi2ji.py`, `tools/import_doboku2ji.py`

## 完了タスク（2026-04-12 追加2）

### 7. UI機能追加（archi2ji・doboku2ji）
- **年度一覧に進捗表示**: `answered/count問` を緑色で表示
- **問題一覧にスコアバッジ**: 最終自己採点（◎○△×）を色付きで表示
- **問題詳細に前問/次問ナビ**: ← 前問 / 次問 → ボタン追加
- archi2ji @11、doboku2ji @8 デプロイ済み

### 8. R1-R4 問題データ追加（建築2次）
- **パーサ作成**: `archi2ji-training/tools/parse_archi2ji_r1r4.py`
  - OCR JSON → 問題JSON変換（24問：R1/R2/R3/R4各6問）
  - 清浄化: "亜"→"、" "唖"→"。" 制御文字除去
- **インポート完了**: 24問（R1-R4）archi2jiに投入済み（合計42問：R1-R7）
- import_archi2ji.py に `--data` オプション追加

## 未完了・次回タスク

### ブラウザ確認（ユーザー操作が必要）
- 建築2次 URL → ログイン → 年度一覧（R1-R7）表示確認・スコアバッジ・前後ナビ
- 土木2次 URL → ログイン → 年度一覧（H28-R7）表示確認・スコアバッジ・前後ナビ

---

## 重要ファイルパス

```
C:\ProgramData\Generative AI\Github\
├── sekisan-training\
│   ├── src\sekisanConfig.gs    ← APP_DB_PREFIX_='SekisanTraining_DB_'
│   └── src\index.html          ← MUJI CSS適用済み
├── takken-training\
│   ├── src\sekisanConfig.gs    ← APP_DB_PREFIX_='TakkenTraining_DB_', APP_TITLE_='宅地建物取引士...'
│   └── src\index.html          ← MUJI CSS適用済み
├── archi2ji-training\
│   ├── src\Code.gs             ← doGet + auto-setup + ?action=setup/diag
│   ├── src\api.gs              ← apiGetHome/Questions/Question/SaveNote/ImportQuestions
│   ├── src\db.gs               ← SHEETS={Config,Users,Questions,Notes}
│   └── src\index.html          ← MUJI SPA（年度一覧→問題一覧→問題詳細）
└── doboku2ji-training\
    ├── src\Code.gs             ← 同上
    ├── tools\parse_doboku2ji.py ← page-level JSON → CSV変換
    └── data\doboku2ji_questions.csv ← 55問(H28-R7)解析済み
```

---

## アプリURL（現在のデプロイ）

```
積算士:  https://script.google.com/macros/s/AKfycbyA0E4NEXVo3FmbwvkNej3r4msmdy4W5mHgIbLEqvGIzChYRjn4HWT9TOUvE6E32uQirg/exec
宅建士:  https://script.google.com/macros/s/AKfycbyYREY2qC9lp6-KPlQNbIo5f1fsyKxnGPVceUTs7kQmiS0Zk2CZbSlKEabrkKhXMz6eDw/exec
建築2次: https://script.google.com/macros/s/AKfycbxtZzcKpx0DTlBEMfyBQECD66bjfeMKdw6pSPdRuEF9gJWSurHHmbybGOIEFd5kHgS4/exec
土木2次: https://script.google.com/macros/s/AKfycbzJtYZ7FU986L1TXhqxiIY0ekaNtUBiW6L3XIkP-HDM0241bn9LesUkueiuuAAnr8w9oQ/exec
```

---

## 禁止事項・注意点

- `clasp deploy` は必ず `-i <deploymentId>` を付ける（URLが変わる）
- sekisan/takkenの既存DBは壊さない（既に本番データあり）
- `archi2ji` と `doboku2ji` のauth実装は sekisan/takken の auth.gs をコピーベースにする（独自実装不要）
