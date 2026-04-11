# Test Plan — Scenario 12/13 MVP

**作成日**: 2026-02-19
**作成者**: T3 (QA)
**バージョン**: 1.0
**参照**: scope_freeze.md, rule_book.md, imp_001_report.md

---

## 0. テスト環境

| 項目 | 値 |
|------|-----|
| Config | `tool_config_test.json` |
| 対象フォルダ | `\\seikyu.tic@tokai-ic.co.jp\受信トレイ\RK用` |
| 保存先 | `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\RK.Mock\saved` |
| PDF出力先 | `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\RK.Mock\printed_pdf` |
| FlagStatus操作 | `use_flag_status: false`, `mark_flag_on_success: false`（Outlook変更なし） |
| 作業ディレクトリ | `C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools` |

### テスト環境の制約事項

- テスト用 config では `use_flag_status: false` のため、FlagStatus フィルタリング（TC-101〜103）は**コードレビューでの検証**が主、または prod config での限定テストが必要
- テスト用 config では `mark_flag_on_success: false` のため、FlagStatus 更新（TC-401〜402）も同様
- Outlook COM 接続が必要。COM エラー発生時は Blocked とする

### 実行コマンド（固定）

```bash
# Stage 1: スキャンのみ（Outlook読取のみ、ファイル変更なし）
cd C:\ProgramData\RK10\Robots\12・13受信メールのPDFを保存・一括印刷\tools
python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --scan-only

# Stage 2: dry-run（処理シミュレーション、ファイル書込なし）
python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run

# Stage 3: 実行（テスト環境にファイル保存）
python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --execute
```

---

## 1. FlagStatus フィルタ

> **注意**: テスト config では `use_flag_status: false` のため、FlagStatus フィルタは無効化されている。
> 以下のテストケースは prod config（`use_flag_status: true`）でのテスト、またはコードレビューで検証する。
> 根拠コード: `outlook_save_pdf_and_batch_print.py` Line 3159-3170

```
TC-101: NoFlag(0) のメールが処理対象になること
条件: FlagStatus=0 のメールが受信トレイに存在する。prod config（use_flag_status: true）を使用。
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_prod.json --scan-only
期待結果: FlagStatus=0 のメールが scan 結果に表示される
確認方法: scan-only のログ出力で対象メール一覧を確認。FlagStatus=0 のメールが含まれていること
```

```
TC-102: Flagged(2) のメールがスキップされること
条件: FlagStatus=2 のメールが受信トレイに存在する。prod config（use_flag_status: true）を使用。
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_prod.json --scan-only
期待結果: FlagStatus=2 のメールが scan 結果に含まれない
確認方法: scan-only のログ出力で FlagStatus=2 のメールが除外されていること
```

```
TC-103: Complete(1) のメールがスキップされること
条件: FlagStatus=1 のメールが受信トレイに存在する。prod config（use_flag_status: true）を使用。
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_prod.json --scan-only
期待結果: FlagStatus=1 のメールが scan 結果に含まれない
確認方法: scan-only のログ出力で FlagStatus=1 のメールが除外されていること
```

---

## 2. 命名（リネーム）

```
TC-201: filename-first で正常命名されること（Pattern A: 完全形）
条件: 添付ファイル名が `{業者名}_{日付}_{金額}_{工事名}.pdf` 形式のメールが存在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run
期待結果: ファイル名パースが成功し、テンプレート `{vendor}_{issue_date}_{amount_comma}_{project}.pdf` に従ってリネームされる
確認方法: dry-run ログで rename 結果を確認。4フィールド（vendor, issue_date, amount_comma, project）が全て埋まっていること
```

```
TC-202: filename-first で正常命名されること（Pattern B: 工事名なし）
条件: 添付ファイル名が `{業者名}_{日付}_{金額}.pdf` 形式（3セグメント）のメールが存在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run
期待結果: vendor, issue_date, amount_comma が取得され、project は空欄でリネームされる。`要確認_` は付与されない
確認方法: dry-run ログで rename 結果を確認。project が空でも命名成功として処理されていること
```

```
TC-203: OCR フォールバックが動作すること
条件: ファイル名パースが失敗する添付ファイル（スキャナー自動命名など Pattern D）が存在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run
期待結果: ファイル名パース失敗後、PDF テキスト抽出または OCR にフォールバックし、情報が取得される
確認方法: dry-run ログで fallback (PDF text / OCR) の実行が記録されていること
```

```
TC-204: 要確認_ prefix が付与される条件
条件: vendor/issue_date/amount のいずれかが全ソース（ファイル名・PDF・OCR）から取得不可の添付ファイルが存在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run
期待結果: ファイル名の先頭に `要確認_` が付与される。取得できたフィールドは埋まる（例: `要確認_不明_20260125_91,450_.pdf`）
確認方法: dry-run ログで `要確認_` 付きファイル名が生成されていること。コード参照: Line 695 `_build_review_filename()`
```

---

## 3. 振り分け（routing）

```
TC-301: モビテック系キーワードで モビテック/ に振り分けられること
条件: 添付ファイル名・工事名・件名・業者名のいずれかに「モビテック」「シン・テクニカルセンター」「3329」を含むメールが存在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run
期待結果: 当該PDFの保存先が `{save_dir}\モビテック\` 配下になる
確認方法: dry-run ログで routing 結果が「モビテック」サブフォルダであることを確認
```

```
TC-302: 中村系キーワードで 中村/ に振り分けられること
条件: 添付ファイル名・工事名・件名・業者名のいずれかに「中村」「中島三丁目」「3285」を含むメールが存在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run
期待結果: 当該PDFの保存先が `{save_dir}\中村\` 配下になる
確認方法: dry-run ログで routing 結果が「中村」サブフォルダであることを確認
```

```
TC-303: いずれにもマッチしない場合 その他/ に振り分けられること
条件: モビテック系・中村系いずれのキーワードも含まないメールが存在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run
期待結果: 当該PDFの保存先が `{save_dir}\その他\` 配下になる
確認方法: dry-run ログで routing 結果が「その他」サブフォルダであることを確認。config `fallback_subdir: "その他"` に一致
```

---

## 4. FlagStatus 更新

> **注意**: テスト config では `mark_flag_on_success: false` のため、FlagStatus 更新は実行されない。
> 以下のテストケースはコードレビューで検証する。
> 根拠コード: `outlook_save_pdf_and_batch_print.py` Line 3452-3460

```
TC-401: 全添付PDF処理成功時に FlagStatus=2 がセットされること
条件: 複数添付PDFを持つメールが全て正常処理される。prod config（mark_flag_on_success: true）を使用。
手順: (コードレビュー) Line 3452-3460 を確認: 全PDF処理成功時に `it.FlagStatus = 2` が実行される
期待結果: FlagStatus が 0 から 2 に変更される
確認方法: コード Line 3452-3460 で `it.FlagStatus = 2` の条件分岐を確認。全添付成功の判定ロジックを検証
```

```
TC-402: 一部失敗時は FlagStatus が変更されないこと
条件: 複数添付PDFのうち一部が処理失敗する。prod config（mark_flag_on_success: true）を使用。
手順: (コードレビュー) Line 3452-3460 を確認: 部分失敗時は FlagStatus 変更がスキップされる
期待結果: FlagStatus が 0 のまま変更されない
確認方法: コード Line 3452-3460 で部分成功/失敗時の分岐を確認。Rule D3「処理失敗時は変更しない」に一致すること
```

---

## 5. スキップ対象の扱い

```
TC-501: URL-only メールがスキップされること（エラーにならないこと）
条件: 添付ファイルがなく、本文にURLのみを含むメール（キョーワWebサービスのダウンロードURL通知等）が受信トレイに存在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --scan-only
期待結果: URL-only メールが処理対象から除外される。エラーにならずスキップされる
確認方法: scan-only ログで該当メールがスキップとして記録されること。`fail_on_url_only_mail: false` の動作確認。コード参照: Line 3507
```

```
TC-502: ZIP添付がスキップされること（[MVP-SKIP] ログ）
条件: ZIP ファイルが添付されたメールが受信トレイに存在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run
期待結果: ZIP 添付がスキップされ、`[MVP-SKIP]` を含むログが出力される。エラーにならない
確認方法: dry-run ログで `[MVP-SKIP]` メッセージを検索。`enable_zip_processing: false` の動作確認。コード参照: Line 3266
```

```
TC-503: 暗号化PDFがスキップされること（[MVP-SKIP] ログ）
条件: パスワード付き（暗号化）PDFが添付されたメール（HENNGE経由等）が受信トレイに存在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run
期待結果: 暗号化PDFがスキップされ、`[MVP-SKIP]` を含むログが出力される。エラーにならない
確認方法: dry-run ログで `[MVP-SKIP]` メッセージを検索。`enable_pdf_decryption: false` の動作確認。コード参照: Line 2579
```

---

## 6. 要確認_ ファイルの後工程

```
TC-601: 要確認_ ファイルの振り分けが止まらないこと
条件: `要確認_` prefix が付与されたファイルが生成される状況（TC-204 と連動）
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --execute
期待結果: `要確認_` 付きファイルも通常のルーティング処理（モビテック/中村/その他への振り分け）が実行される
確認方法: RK.Mock/saved 配下のサブフォルダに `要確認_` 付きファイルが保存されていることを確認
```

```
TC-602: 要確認_ ファイルのPDF出力が止まらないこと
条件: `要確認_` prefix が付与されたファイルが生成される状況（TC-204 と連動）
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --execute
期待結果: `要確認_` 付きファイルも PDF出力先（`RK.Mock/printed_pdf`）にコピーされる
確認方法: RK.Mock/printed_pdf 配下に `要確認_` 付きファイルが存在することを確認
```

---

## 7. 追加テストケース（IMP-001 指摘事項）

```
TC-701: 件名フィルタ（allow regex）が正しく動作すること
条件: 件名に「請求」「請求書」「invoice」「パスワード」「HENNGE」「Web請求」を含むメールと含まないメールが混在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --scan-only
期待結果: 件名フィルタにマッチするメールのみが候補に含まれる
確認方法: scan-only ログで候補メール一覧を確認。フィルタ外のメールが含まれていないこと
```

```
TC-702: 複数添付メールが個別処理されること
条件: 1通のメールに複数のPDFが添付されている
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run
期待結果: 各添付PDFが個別にリネーム・振り分けされる（1メール = N個のPDF → N回の処理）
確認方法: dry-run ログで同一メールから複数のリネーム結果が出力されていること
```

```
TC-703: ✖/× マーク付きファイル名がスキップされること
条件: 添付ファイル名に `✖` または `×` を含むPDFが存在する
手順: python outlook_save_pdf_and_batch_print.py --config ..\config\tool_config_test.json --dry-run
期待結果: 当該ファイルがスキップされ、ログに記録される。エラーにならない
確認方法: dry-run ログでスキップ記録を確認。Rule E3 に一致すること
```

---

## テストケース一覧（サマリー）

| TC ID | カテゴリ | テストケース名 | 検証方法 |
|-------|---------|--------------|---------|
| TC-101 | FlagStatus | NoFlag(0) が処理対象 | prod config scan-only / コードレビュー |
| TC-102 | FlagStatus | Flagged(2) がスキップ | prod config scan-only / コードレビュー |
| TC-103 | FlagStatus | Complete(1) がスキップ | prod config scan-only / コードレビュー |
| TC-201 | 命名 | Pattern A 完全形リネーム | test config dry-run |
| TC-202 | 命名 | Pattern B 工事名なしリネーム | test config dry-run |
| TC-203 | 命名 | OCR フォールバック | test config dry-run |
| TC-204 | 命名 | 要確認_ prefix 付与 | test config dry-run |
| TC-301 | 振り分け | モビテック振り分け | test config dry-run |
| TC-302 | 振り分け | 中村振り分け | test config dry-run |
| TC-303 | 振り分け | その他振り分け | test config dry-run |
| TC-401 | FlagStatus更新 | 全成功で FlagStatus=2 | コードレビュー |
| TC-402 | FlagStatus更新 | 部分失敗で FlagStatus 不変 | コードレビュー |
| TC-501 | スキップ | URL-only スキップ | test config scan-only |
| TC-502 | スキップ | ZIP スキップ [MVP-SKIP] | test config dry-run |
| TC-503 | スキップ | 暗号化PDF スキップ [MVP-SKIP] | test config dry-run |
| TC-601 | 要確認_ | 振り分け継続 | test config execute |
| TC-602 | 要確認_ | PDF出力継続 | test config execute |
| TC-701 | 追加 | 件名フィルタ動作 | test config scan-only |
| TC-702 | 追加 | 複数添付個別処理 | test config dry-run |
| TC-703 | 追加 | ✖/× マーク スキップ | test config dry-run |

---

## テスト実行順序

1. **Round 1: scan-only**（QA-002）
   - TC-101〜103（FlagStatus: コードレビュー併用）
   - TC-501（URL-only スキップ）
   - TC-701（件名フィルタ）

2. **Round 2: dry-run**
   - TC-201〜204（命名）
   - TC-301〜303（振り分け）
   - TC-502〜503（ZIP/暗号化スキップ）
   - TC-702〜703（複数添付、✖マーク）

3. **Round 3: execute**（テスト環境）
   - TC-601〜602（要確認_ 後工程）
   - 全体統合テスト（保存先ファイル・フォルダ構成の目視確認）

4. **Round 4: コードレビュー**
   - TC-401〜402（FlagStatus更新ロジック）
   - TC-101〜103 の補完（FlagStatusフィルタロジック）

---

## Pass / Fail 判定基準

| 判定 | 条件 |
|------|------|
| **Pass** | 期待結果と完全一致、またはログ出力が仕様通り |
| **Fail** | 期待結果と不一致、エラー発生、またはスキップすべきものが処理される |
| **Blocked** | Outlook COM 接続不可、テストデータ不足、環境依存の問題 |
| **N/A** | テスト config の制約により実行不可（コードレビューで代替済み） |
