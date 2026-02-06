# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

For every project, write a detailed FOR[yourname].md file that explains the whole project in plain language.

---

## 憲法（Constitution）— 全ての判断に優先する原則

### 業界標準リサーチ原則
**問題に対する業界標準のアプローチを調査し、それを参考に独自のアプローチを導き出す。**

- 設計判断・技術選定・実装パターンの決定前に、まず業界がどう解いているかを調べる
- 調査結果をそのままコピーするのではなく、自分たちの文脈（規模・頻度・制約）に合わせて適用する
- 「なぜこのアプローチか」を業界標準との比較で説明できる状態にする

---

## Canonical rules (Source of Truth)

@AGENTS.md

---

## Claude Code runtime notes（Claude Code固有）

- plansDirectory は `./plans`（設定済み）
- SessionStart hook で、セッション開始時に以下を自動注入：
  - `plans/decisions.md`（必読）
  - `plans/handoff.md`（あれば）
- context_window が 70% 以上になったら：
  1) `plans/handoff.md` を短く更新（Done/Next/Risks/検証）
  2) 新しい"決定"があれば `plans/decisions.md` に追記
  3) 必要なら `/compact`
- hook timeout は最大 120 秒（重い処理はhookに入れない）

---

## 「MDに書いて」の追記先（重要）

- 原則：恒常ルールは `AGENTS.md` 末尾 `## Project Memory` に追記する（CLAUDE.mdは入口のため肥大化させない）
- 例外：Claude Code固有の設定・運用（hooks/statusLine/plansDirectory など）を明示的に書きたい場合のみ、本ファイルの runtime セクションへ追記

---

## Skills（ドメイン知識スキル）

### RK10シナリオスキル（最重要）

**場所**: `.claude/skills/rk10-scenario/`
**自動参照**: @.claude/skills/rk10-scenario/SKILL.md

**キーワード**: RK10、Keyence、シナリオ、.rks、Program.cs、pywinauto

**知識範囲**:
- .rksファイル編集（ZIP形式、Program.csのみ編集）
- RK10 UI操作（pywinauto UIA）
- Keyence C# API（Excel、日付、ファイル操作）
- エラーパターンと解決策

---

### PDF OCRスキル

**場所**: `.claude/skills/pdf-ocr/`
**自動参照**: @.claude/skills/pdf-ocr/SKILL.md

**キーワード**: PDF、OCR、テキスト抽出、請求書、領収書、回転補正、傾き補正

---

### レコル（RecoRu）スキル

**場所**: `.claude/skills/recoru/`

**自動起動キーワード**: レコル、RecoRu、勤怠管理、勤務区分、有休、振休、代休、公休、打刻、締め、申請

**使用方法**:
- 上記キーワードを含む質問をするとスキルが自動起動
- スキルはドメイン知識ドキュメント（`docs/domain/recoru/`）を参照して回答

**参照ドキュメント**:
| ドキュメント | 用途 |
|-------------|------|
| `docs/domain/recoru/10_kbn_dictionary.md` | 勤務区分辞書（最重要） |
| `docs/domain/recoru/30_application_howto.md` | 申請手順 |
| `docs/domain/recoru/40_edge_cases.md` | 例外ケース |

**質問例**:
```
振休と代休の違いは？
有休申請の手順を教えて
締め後に修正したい
```

---

### GAS Webapp（SPA）スキル

**場所**: `.claude/skills/gas-webapp/`
**自動参照**: @.claude/skills/gas-webapp/SKILL.md

**キーワード**: GAS、Google Apps Script、Webアプリ、SPA、clasp、doGet、google.script.run、HtmlService、スプレッドシートDB

**知識範囲**:
- GAS + HTML SPA構成（単一index.html、インラインCSS/JS）
- Spreadsheet as DB（SHEETS/HEADERS定義、CRUD helpers）
- api.gs パターン（clientUserKey、toSerializable_、エラー返却）
- ハイブリッド認証（Google + localStorage + 復元コード）
- clasp デプロイ（`-i`必須）
- 実績: archi-16w トレーニングアプリ（@37バージョン、本番運用中）

---

## 再発防止チェックリスト（2026-02-02 振り返り）

### 1. UI変更は影響範囲を全画面で検証する

**事例**: archi-16w @32 ナビボタンポカヨケ（回答前は非表示）→ Home/中断するボタンまで消えるリグレッション発生 → @34で修正

**ルール**:
- UI要素の表示/非表示を変更する場合、**その要素が表示される全画面・全状態**を列挙してからコードを書く
- 特に「条件付き非表示」は、意図しない要素まで巻き込むリスクが高い
- デプロイ前チェック: 変更した画面だけでなく、隣接画面（前後の遷移先）も必ず確認

### 2. clasp deploy は必ず `-i <deploymentId>` を付ける

**事例**: `-i`なしで`clasp deploy`を実行すると新しいデプロイメントが作成され、URLが変わる（既存ユーザーがアクセスできなくなる）

**ルール**:
```bash
# 正しい（既存URLを更新）
clasp deploy -i AKfycbxVu6IgDAj5lbx9KCVEwsTC-GdG1-H5oYAOotW0x7DdBesM2UrpNkF0KRhliPi0Q-zUcg

# 危険（新URL生成）
clasp deploy
```

### 3. OCR修正は必ずフル回帰テストを実行してから適用する

**事例**:
- Fix 5（OCR confidence閾値でスキップ）→ 他ファイルで金額欠損リグレッション → ロールバック
- Fix 1（円サフィックス除去）→ Super Safety帳票でリグレッション → 条件追加で修正
- bbox座標アプローチ → -5件の金額リグレッション → アプローチ自体を断念

**ルール**:
- OCRパターン追加/変更後、**全テストケース（ALL-N）のスコア**を変更前後で比較する
- スコアが1件でも悪化したら、原因特定してから適用する（「他は改善したから」で押し通さない）
- 新パターンは既存パターンを壊さない**追加型**にする（既存ロジックの書き換えは最終手段）

### 4. エラーハンドリングは類似関数と揃える

**事例**: `doStartMock`のsuccessハンドラに`res._error`/`!res.attemptId`のバリデーションがない（`doStartTest`にはある）→ 模試中断→再開でHomeに戻されるバグ（未解決）

**ルール**:
- 新しいAPI呼び出し関数を書くとき、**同じパターンの既存関数**（doStartTest等）のエラーハンドリングをコピーしてから開始する
- successハンドラでも「サーバーが論理エラーを返す可能性」を常に想定する

### 5. 「小さく変えて、測って、学んで、また変える」を徹底する

**事例**: 複数の改善を1デプロイにまとめた結果、リグレッション発生時にどの変更が原因か特定しにくい

**ルール**:
- 1デプロイ = 1変更（可能な限り）
- 複数変更をまとめる場合、各変更の影響範囲が独立していることを確認する
- リグレッション発生時は「どの変更が原因か」を最初に切り分ける

---

## Debug

- `/memory` でメモリロード状況（imports含む）を確認する
