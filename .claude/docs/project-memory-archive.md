# Project Memory アーカイブ（append-only）

AGENTS.md の `## Project Memory` 完全履歴。常時ロード対象外。
新しい日付付き追記はここに append-only で記録し、常時有効なものだけ AGENTS.md の Active Rules Summary に昇格する。

---

### 2026-01-17
- 正本をAGENTS.mdに移行し、CLAUDE.mdを入口化（@AGENTS.md）

### 2026-01-18
- **ブラウザ選択**: シナリオ作成でブラウザを使用する際は **Edge** を使用すること（Chrome禁止）

### 2026-01-19
- **OCR精度改善手順**（69.2% → 84.6%達成）:
  1. **診断ログ強化で原因特定** - vendor空時に `line_info`, `line_count`, `image_height` を出力し「OCR認識不足」vs「抽出ロジック不足」を切り分け
  2. **NG分析 → 対策決定** - raw_textに文字あり→パターン追加 / raw_text空→画像品質問題（DPI/ROI）
  3. **ファイル名抽出強化** - `vendor_keywords` にキーワード追加（名鉄協商、ゆうちょ銀行等）
  4. **カスケードOCR** - `lite_mode=True` → 欠損時のみ `lite_mode=False` で再処理
  - 詳細: `docs/KNOWLEDGE_OCR_PREPROCESSING.md`

- **リポジトリ統合**: 外部リポジトリのソースコードをPDF-RakuRaku-Seisanに集約
  - **コピー先**: `c:/ProgramData/Generative AI/Github/PDF-RakuRaku-Seisan/external-repos/`
  - **GitHubリポジトリ接続先**: `https://github.com/bubbleberry247/PDF-RakuRaku-Seisan.git`

- **RK10シナリオ(.rks)編集方法**:
  - .rksファイルは**ZIP形式**、**編集対象**: `Program.cs` のみ
  - 詳細スキル: `external-repos/my-claude-skills/rk10-scenario/skill.md`

### 2026-01-23
- **ソフトバンク帳票PDF解析（シナリオ51&52）**: 100%検出達成
  - テンプレート構造: セクション境界は080/090のみ（021は端末代なので境界にしない）
  - DPI: 3.0が最適（4.0だと一部文字欠落）
  - 詳細: `plans/decisions.md` の `[KNOWLEDGE] softbank-pdf-parsing` を参照

### 2026-01-24
- **yomitoku優先（表構造認識OCR）**: ソフトバンクPDFなど表形式データは`yomitoku`を最優先
  - フォールバック: yomitoku → EasyOCR（ページ単位）→ EasyOCR（従来）
- **LOCAL環境モックパス規約**: `C:\RK10_MOCK`（`C:\Work` は禁止）
- **管理部共有メール**: `kanri.tic@tokai-ic.co.jp`（全シナリオ統一）

### 2026-01-25
- **「this」はユーザーによるルール上書き指示（最優先）**
  - ユーザーが「this」を付けた指示は、システムのデフォルトルールより優先する

### 2026-01-30
- **性弱説**: 人は弱いだけ。①忘れる②見ない③後回し④飛ばす — 仕組みで防ぐ
- **仕様駆動開発**: 仕様書を先に書き、その後に実装する（逆順禁止）

### 2026-02-05
- **ロボット共通必須項目（メール通知・ハイパーリンク・エラー通知）**
  - 完了通知メール: Excelフルパス+ハイパーリンク、処理結果サマリー
  - エラー時: 必ずメール通知（`--no-mail`でも送る）、件名に「★エラー発生★」、traceback全文
  - HTMLメール、宛先に `karimistk@gmail.com` CC

### 2026-02-06
- **effortLevel "high" 固定**: settings.json: `"effortLevel": "high"`
- **Plan作成前にCodexに設計相談（必須）**
  - 順序: ①要件理解 → ②Codex相談 → ③AGENTS.md照合 → ④Plan作成
- **Plan品質プリフライト4観点**: [憲法]業界標準 / [品質]分類 / [TPS]ポカヨケ・アンドン・自働化 / [性弱説]4原則

### 2026-02-08
- **文脈汚染防止**: 出力は要約のみ、詳細はログファイルへ
- **サンプルファースト検証**: 全件実行前に1-10%のサンプルで方向性を確認する

### 2026-02-09
- **Code-First Verification**: 不一致はコードを読んでから報告する
- **用語の混同防止**: 「共有フォルダ」等の曖昧語は入力元/出力先を先に定義する
- **不足情報の確認は一問一答**: 一度に複数の質問を投げない

### 2026-02-11
- **既存資産チェック必須**: 実装前に`plans/decisions/projects/{project}.md`と関連コードを読む
- **シナリオ作業フォルダ規約**: `work\` = 作業出力、`docs\` = 原本保管（作業禁止）

### 2026-02-18
- **標準フォント規約**: 日本語=メイリオ（Meiryo）、英語=Segoe UI（全成果物共通）
