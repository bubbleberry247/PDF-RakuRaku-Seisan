# Evidence: 決定ログサンプル

## 概要
`plans/decisions.md`に記録する決定・制約・知見のサンプル集。
ChatGPTプロジェクトでも同様の形式で記録を残すことを推奨。

---

## 記録フォーマット

```markdown
## YYYY-MM-DD

### [タグ] タイトル

**問題/背景:**
[何が問題だったか、なぜこの決定が必要だったか]

**解決策/決定:**
[どのように解決したか、何を決定したか]

**変更ファイル:**
- `C:\path\to\file1.ext`
- `C:\path\to\file2.ext`

**学び/注意点:**
[今後のために覚えておくべきこと]
```

---

## タグ一覧

| タグ | 用途 |
|------|------|
| `[CODE]` | コード変更・バグ修正 |
| `[CONFIG]` | 設定変更 |
| `[DATA]` | データ仕様・マスタ変更 |
| `[DOCS]` | ドキュメント更新 |
| `[PROCESS]` | 業務プロセス・運用変更 |
| `[KAIZEN]` | 改善・リファクタリング |

---

## サンプル記録

### 2026-01-15

#### [CODE][KAIZEN] シナリオ43 ZIP解凍パス修正

**問題:**
ZIP解凍後のフォルダパスがハードコードされており、月が変わると動作しない。

**解決策:**
動的にパスを生成するよう修正。

```csharp
// Before
var path = @"C:\work\202501";

// After
var path = $@"C:\work\{yyyyMM}";
```

**変更ファイル:**
- `C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス全国組合(ETC)最終の作成\scenario\43ETC_fixed_v3.rks`

**学び:**
- 日付・月に依存するパスは必ず変数化する

---

### 2026-01-16

#### [CODE] シナリオ43 XPath修正（React SPA対応）

**問題:**
ETCサイトのUI変更により、ZIPダウンロードリンクのXPath `//a[contains(@href, '.zip')]` が見つからない。

**調査結果:**
- ZIPダウンロードリンクにはhref属性がない（JavaScriptクリックハンドラで処理）
- HTML構造: `<a class="sc-gyycJP KKYCe"><div><div><p>file_202512.zip</p></div></div></a>`

**解決策:**
`<p>`タグ内の`.zip`テキストを検索し、親の`<a>`タグに移動するXPathに変更。

```
修正前: //a[contains(@href, '.zip')]
修正後: (//p[contains(text(), '.zip')]/ancestor::a)[1]
```

**テスト結果:** ✅ 成功
- ZIPダウンロード: 成功（13:01にダウンロード確認）
- シナリオ完走: エラーなしで最後まで実行

**学び:**
1. React SPAサイトのリンクはhref属性を持たないことがある
2. `contains(., '.zip')`より`contains(text(), '.zip')/ancestor::a`が確実

---

### 2026-01-17

#### [CODE][KAIZEN] RK10 XPath制限の発見

**問題:**
v41のXPath `(//p[contains(text(), '.zip')]/ancestor::a)[1]` がPlaywrightでは動作するが、RK10では動作しない。

**調査結果:**
RK10のXPath実装は以下の構文を**非サポート**:
| 構文 | 例 | RK10での動作 |
|------|-----|-------------|
| `ancestor::` | `/ancestor::a` | ❌ 非対応 |
| `descendant::` | `//a[descendant::p]` | ❌ 非対応 |
| `../../..` | `//p/../../../` | ❌ 非対応 |
| `contains(., ...)` | `contains(., '.zip')` | ❌ 非対応 |
| CSS Selector | `SyntaxType.CssSelector` | ❌ APIに存在しない |

**テストしたXPath（すべてRK10で失敗）:**
- v42: `(//a[descendant::p[contains(text(), '.zip')]])[1]`
- v43: `(//p[contains(text(), '.zip')]/../../..)[1]`
- v44: CSS Selector（ビルドエラー）
- v45: `//a[contains(@class, 'sc-gyycJP')]`

**確定解決策:**
Playwrightで直接ダウンロード

```python
async with page.expect_download() as download_info:
    zip_link = page.locator('a.sc-gyycJP').first
    await zip_link.click()
download = await download_info.value
await download.save_as(save_path)
```

**学び:**
1. RK10のXPath実装は標準XPathと大きく異なる
2. 複雑なDOM構造のサイトはPlaywright連携が有効
3. Bot検出対策も含めてPlaywrightが推奨

---

### 2026-01-18

#### [CONFIG] ブラウザ選択: Edge必須

**決定:**
シナリオ作成でブラウザを使用する際は**Edge**を使用すること。Chrome禁止。

**理由:**
- 社内PCの標準ブラウザがEdge
- RK10のブラウザ自動化がEdgeに最適化されている
- Chromeは別途インストールが必要で管理コスト増

---

### 2026-01-19

#### [DATA][KAIZEN] OCR精度改善手順の確立

**成果:**
認識精度 69.2% → 84.6% に改善

**確立した手順:**
1. **診断ログ強化で原因特定** - vendor空時に `line_info`, `line_count`, `image_height` を出力
2. **NG分析→対策決定** - raw_textに文字あり→パターン追加 / raw_text空→画像品質問題
3. **ファイル名抽出強化** - `vendor_keywords` にキーワード追加
4. **カスケードOCR** - `lite_mode=True` → 欠損時のみ `lite_mode=False` で再処理

**変更ファイル:**
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\pdf_ocr.py`
- `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\pdf_preprocess.py`

---

### 2026-01-20

#### [PROCESS] シナリオ55 ヒアリング要件確定

**確定した要件:**

| 項目 | 要件 | 備考 |
|------|------|------|
| **目的** | 楽楽精算→Excel転記の自動化（15日/25日/末日手引き） | 勤務区分確認前データ生成 |
| **入力データ** | 楽楽精算CSVデータ（明細プレビュー→データ抽出） | API無し |
| **マスタ照合** | 支払先→勘定科目の自動判定マスタを作成 | 例: 安城印刷㈱→広告宣伝費 |
| **確度による色分け** | 完全一致=黒字、推定/新規=**赤字** | 田胡さんが一目で確認・補正 |
| **既存ファイル継承** | 既存ファイルにシート追加（月次新規作成しない） | ✅現状実装で対応済み |
| **出力先** | ユニオン共有→**MINISV邨檎炊フォルダ** | 具体パス要確認 |

**現状実装との差分:**
| 機能 | 現状 | 要変更 |
|------|------|--------|
| マスタ照合（科目判定） | 支払先マッチングのみ | **★要追加** |
| 確度色分け | なし | **★要追加**（赤字=黄字） |
| 出力先 | ユニオン共有 | **★要変更**（MINISV） |

---

## 決定ログの運用ルール

### トリガー → アクション

| ユーザー発言 | 実施すること |
|---|---|
| 「できた」/「記憶して」 | `plans/decisions.md` に追記 |
| 「MDに書いて」 | `AGENTS.md` の `## Project Memory` に追記 |
| （ctx>=70%など） | `plans/handoff.md` を短く更新 |

### 記載原則

1. **append-only** - 追記が基本、過去は書き換えない
2. **日付セクション** - 今日の日付のセクションに追記。無ければ作成
3. **変更・撤回** - 新しい決定として追記し、Supersedes参照
4. **タグ付与** - [CODE][DATA][DOCS][CONFIG][PROCESS][KAIZEN]
5. **ファイル列挙** - 変更したファイルはフルパスで記載
