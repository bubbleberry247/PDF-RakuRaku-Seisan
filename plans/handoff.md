# handoff.md（短く・上書き前提）

## Current focus
- **シナリオ55（振込Excel転記）**: 業務フロー分析・ヒアリング確認完了。email_notifier.py実装済み。overflow reporting追加済み。
- **archi-16w トレーニングアプリ**: **@95デプロイ済み**。userKeyベースロール判定、復元コード数字4桁化。
- **ai-subscription-dashboard**: **キャンセル済み**。

## シナリオ55 振込Excel転記（2026-02-05）

### Done
- 業務フロー不明点10項目の洗い出し・ヒアリング確認完了
- 振り分けルール5分類の確定（会計区分廃止/支払日グループ/経費種類/同一支払先/振込手数料）
- email_notifier.py新規作成（Outlook COM送信、LOCAL→karimistk@gmail.com、PROD→config MAIL_ADDRESS）
- main.pyにメール通知ステップ[5/6]統合、--no-mailフラグ追加
- 按分処理=A（全額1行転記）、空行不足=C（レポート出力）の方針確定
- overflow_suppliers追跡とレポート/メール出力を実装
- **rakuraku_scraper.py isdigitバグ修正**: 📎/⚠アイコン付き伝票の取りこぼし解消（+107件回復）
- **DOM抽出→Excel転記 検証完了（R7.11月分サンプル6行）**:
  - RPA対象5行: C列・I列とも100%一致
  - isdigit修正前は88.1%→修正後100%（対象行のみ）
  - 非対象: Row 323 ㈱庭昭（都度振込=RPA対象外）
  - excel_writer.pyのPass1-3マッチ+空き行書き込みで全117件を処理可能
- **_reset_amounts() MergedCell修正**: `isinstance(cell, MergedCell)` チェック追加
- **結合テスト完了（R7.11月分 445件）**: エラー0、オーバーフロー0、Truth Row(117,119,551)一致、庭昭正しく除外
- **R7.10月分パイプラインテスト完了（247件→128件処理）**: エラー0、オーバーフロー0、転記合計17,287,489円
- **_is_approved() 確定済バグ修正**: `確定済`ステータス未認識 → 条件追加（確定済111件の取りこぼし解消）
- **詳細検索パネル折りたたみ修正**: `search_with_filters()` 新メソッド追加（会社+日付を1回の検索で送信）
- **要件定義書§7の未確認項目**: 確定済み（6799統一、分岐なし、タイミング=必要時修正）
- **要件定義書の文字化け修正**: 修正済み（6行: L82-84, L149-150, L540）
- **テンプレート行侵食バグ修正**: `_reserved_supplier_rows`で入力データの支払先行を保護（Pass2の行盗み防止）
- **summary_hint matching追加**: `find_supplier_row()`にC列(摘要)マッチング追加（同一支払先の行割当改善）
- **E2Eテスト R7.10月分完了**: 62.5% → 78.1%（コードバグ起因の不一致は0件）
- **R7.11月分回帰テスト**: エラー0、オーバーフロー0、Truth Row全一致（リグレッションなし）
- **本番コードパス検証完了**: `scrape_payment_requests()` → `search_with_filters()` → `extract_payment_data()` 正常動作（38件取得、日付フィルタ100%正確）
- **本番パイプライン結合テスト完了**: 38件→31総合振込処理、エラー0、オーバーフロー0、R7.10月分比較25/32 (78.1%)
- **Sabastian Design調査完了**: 楽楽精算に存在しない（全社Nov28/会社300 Nov全月/会社300日付なし、全て0件）→ 手動追加と判明

- **実書き込みテスト完了（dry_run=False）**: 全251行セル比較、I列一致率94.8%（不一致13件=全て都度振込除外/手動追加/データ差異）
- **ワークマン調査完了**: 楽楽精算に2件（42,200+5,000=47,200）、実Excelは5,000のみ→担当者が手動調整
- **PROD環境main.pyテスト完了**: 設定読込→スクレイプ→転記の全ステップ正常動作。エラー0、31件転記成功
- **preflight_check.py作成・検証完了**: LOCAL環境で全チェックPASS（Python/依存/設定/Excel/マスタ/資格情報/データDir）

- **tkinter GUIランチャー作成**: launcher.py新規（~350行）、環境/支払日/ドライラン選択、リアルタイムログ、実行履歴
- **--autoフラグ追加・メール制御再設計**: 手動=完了メールなし、--auto=完了メール送信、--no-mail=全抑制
- **バッチファイル2種作成**: run_55.bat（GUI起動）、run_55_auto.bat（自動実行用）
- **GUI起動テスト完了**: スクリーンショットで表示確認済み

- **自動実行の本番品質化（2026-02-06）**:
  - main.py: print()→logger.info()統合（ログファイル7行→27行、全操作詳細記録）
  - main.py: --autoモードでメール失敗時にexit code 1を返す（アンドン原則）
  - main.py: auto_detect_payment_type()に当日実行ガード追加（同日/過去日→ValueError）
  - run_55_auto.bat: Python PATH検証、stdout/stderrリダイレクト、exit code伝搬
  - コンソールハンドラを raw format に変更（GUI/CLI表示はそのまま、タイムスタンプはファイルのみ）

- **インストーラー作成（2026-02-06）**:
  - setup_prod.py: Phase 1 preflight + Phase 2 ショートカット（2フェーズ構成）
  - install.bat: ダブルクリックで実行（管理者権限不要）
  - --uninstallオプション（ショートカット削除）
  - 本番環境セットアップ手順書Excel出力済み
- **タスクスケジューラ不要の決定（2026-02-06）**: 手動GUI実行に統一。Phase 3削除済み。
- **scenario55_rules.md作成（2026-02-06）**: セッション開始時に読む業務ルール集約ファイル（~60行）
- **ドキュメント一括修正（2026-02-06）**: タスクスケジューラ記述を全削除
  - 要件定義書 v1.4→v1.5: 運用要件を「手動GUI実行」に変更
  - 工程手順書 v1.3→v1.4: §6を「GUI手動実行手順」に書き換え
  - セットアップ手順書Excel: Step 5（タスクスケジューラ）削除、6→5ステップ
  - run_55_auto.bat/main.py: スケジューラ関連コメント削除

- **コードレビュー＋修正（2026-02-06）**: Opus 4.6 + Codex協働レビュー
  - **C1 [FIXED]**: `--no-mail`でもエラー通知を送る（アンドン原則遵守）main.py:483-496
  - **C2 [FIXED]**: account_guesser.py NFC→NFKC統一（build_payment_masterと整合）
  - **C3 [FIXED]**: preflight_check.py config変数スコープ修正
  - **H1 [FIXED]**: rakuraku_scraper.py 裸except→except Exception（4箇所）
  - **H3 [FIXED]**: launcher.py:7, main.py:444 タスクスケジューラ残存参照削除
  - **H5 [FIXED]**: --autoモードで0件→RuntimeError（スクレイプ失敗検知）
  - **照合ステップ [NEW]**: excel_writer.py verify_writes()追加、main.py Step4をread-back照合に置換
    - 書き込み後にI列を読み戻し、件数・金額・行単位で照合
    - 不一致→RuntimeError→エラー通知メール（アンドン）
    - ドライラン時はスキップ

### Remaining（本番PC作業のみ）

開発機で実行可能なタスクは全て完了。以下は本番PCでの作業。

#### Step 1: インストーラー実行
```bash
ダブルクリック: install.bat
```
- Pre-flight全項目OK → デスクトップショートカット作成

#### Step 2: Dry-run テスト（GUIから）
- デスクトップの「振込Excel転記」ショートカットをダブルクリック
- 環境=PROD、支払日=自動判定、ドライラン=ON で実行
- エラー0、オーバーフロー0を確認

#### Step 3: 実書き込み（GUIから、ドライランOFF）
- GUIから環境=PROD、ドライラン=OFF で実行
- Excelファイルを開いて転記内容を目視確認

#### Step 4: RK10シナリオ修正（移行期間対応）
- Python呼び出しに `--no-mail` を追加（メール二重送信防止）
- GUI定着後にRK10シナリオは廃止予定

#### 注意事項
- PROD Excel: `\\192.168.1.251\TIC-mainSV\【個人使用フォルダ】\管理部\・𠮷田\総合振込計上・支払伝票.xlsx`（開発機からアクセス不可）
- 楽楽精算URL: LOCAL/PRODとも同一
- 都度振込は対象外（正しく除外済み）
- 不一致13件（94.8%→100%ではない理由）: 都度振込除外5件、手動追加（Sabastian Design等）、担当者調整（ワークマン等）→全てコードバグ以外

### Key Files
- `c:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\scenario55_rules.md`（セッション開始時に必読）
- `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\tools\main.py`
- `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\tools\launcher.py`（NEW: tkinter GUI）
- `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\tools\excel_writer.py`
- `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\tools\email_notifier.py`
- `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\run_55.bat`（NEW: GUI起動用）
- `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\run_55_auto.bat`（NEW: 自動実行用）
- `C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\docs\55_振込Excel転記_要件定義書.md`

## ai-subscription-dashboard（2026-02-03 キャンセル）

### ステータス: キャンセル
- **理由**: Anthropic API課金自動取得不可（Admin APIキー必要）→ ユーザー「手動ならこのシステム必要ない」
- **実施済み**: webapp アクセス権 ANYONE_ANONYMOUS → MYSELF に変更、@8デプロイ
- **未処理**: ConfigシートのOPENAI_API_KEY行を手動削除（GASエディターのSpreadsheetから）

### Deployment
- **デプロイURL**: https://script.google.com/macros/s/AKfycbzS6hy14epqcDwwvnan6gvxBb-8zFbEhP_38jYoHfk6uP1fnI2m0xbVdt1BDIZm4NfnPg/exec
- **デプロイメントID**: AKfycbzS6hy14epqcDwwvnan6gvxBb-8zFbEhP_38jYoHfk6uP1fnI2m0xbVdt1BDIZm4NfnPg
- **Script ID**: 1oOl3Xoz5Cx56Kyzbdts8I3_vOKDC70AyIH9wA9JUkRkoze4RXn4qH718
- 現在: @8
- clasp deploy注意: 必ず `clasp deploy -i <deploymentId>` を使用

## archi-16w トレーニングアプリ（2026-02-03）

### Done (@94-@95): userKeyベースadmin + 復元コード数字化
- @94: requireActiveUser_をuserKeyフォールバック対応（非Workspaceユーザーにadmin/manager権限付与可能に）
- @94: apiGetHomeDataチーム構築をuserKeyベース検索に対応
- @95: 復元コードを英数6文字→数字4桁に変更、UI入力欄を数字キーボード対応

### Done (@89-@92): 今週のミニテスト修正 + AIアドバイス強化
- @89-@91: プログラム開始前は第1回を「今週のミニテスト」として表示、提出済みでも表示
- @92: Gemini AIアドバイスに資格試験勉強のコツを必須追加（過去問活用、暗記術、効率学習、モチベ維持等）

### Done (@78-@80): ダブルクリック防止 + UI改善
- @78-@79: submitTest/submitPracticeにダブルクリック防止（submittingフラグ）追加
- @80: 模試UIボタンに年度追加（「令和７年午前テスト」等）、左側ラベル削除
- @80: 弱点復習セクションに説明追加「弱点分野からランダムで１０問出題」、ボタン名「弱点復習」

### Done (@73-@77): UI改善 + パフォーマンス最適化
- @73: Homeタブ削除（冗長）、管理リンクをページ下部に移動（admin/manager専用）
- @74: CacheService導入（Config/TestPlan 5分、Questions 10分キャッシュ）、warmUp()関数追加
- @75: localStorage事前キャッシュ（Home画面の即時表示）
- @76: パフォーマンス計測ログ追加（[PERF] Cache HIT/MISS）
- @77: 回答後スクロール位置修正（上部ナビボタンが常に見える位置に）
- **手動設定必要**: GASエディターで時間ベーストリガーを設定（warmUp関数、5-10分間隔）

### Done (@56-@63): 回答ボタン追加 + AIアドバイス完成
- @56: 全テストに回答取り消し/次へ/前へボタン追加
- @57-@60: AIアドバイスデバッグ修正（totalQuestions未定義、updateConfig INSERT、APIキー再登録）
- @61: result-advice表示位置移動（チャート直下）、Homeボタン緑化、updateTagStats_バグ修正
- @62: UrlFetchApp権限承認
- @63: debugメッセージ削除（クリーンアップ）
- **Gemini AIアドバイス**: 動作確認済み（Result画面チャート直下に表示）

### Done (@53-@54): UI改善7点 + Gemini AI学習アドバイス
- @53: テスト中タブナビ非表示、スクロール最上部、選択解除、Home緑ボタン、スクロールトップボタン左移動、エラーメッセージクリア、ミニテスト回数表示、Gemini AIアドバイス
- @54: setupGeminiKey()一時関数削除（クリーンアップのみ）

### Done (@50-@52): エラーハンドリング + ヘッダー修正

### Done (@38): doStartMock バリデーション追加

### imageUrl: 実行待ち
- `linkGitHubImages()` 関数がCode.gs:333に実装済み
- **次のアクション**: GASエディターから `linkGitHubImages` を手動実行

### Done (earlier @8-@37)
- ハイブリッド認証、ボタンサイズ、PICK回答取り消し、中断バッジ、モバイル修正、セクションルール、ナビポカヨケ、キャラクター、結果scroll-to-top、中断再開、タイマー、グリッド、カード再設計、分野別ミニテスト、GASプロジェクト移行など

## Pending（未着手）
1. **全テスト中断→再開フロー検証**: mock/mini/field/practice/testの全種別で中断→再開を実機検証
2. ~~**imageUrl**~~: **実行待ち**（linkGitHubImages関数をGASエディターから実行）
3. **エラー通知メール機能**: MailApp.sendEmail()でエラー時に開発者にメール通知（提案済み・未実装）

## Key Files
- `C:\ProgramData\Generative AI\Github\archi-16w-training\src\Code.gs`
- `C:\ProgramData\Generative AI\Github\archi-16w-training\src\api.gs`
- `C:\ProgramData\Generative AI\Github\archi-16w-training\src\logic.gs`
- `C:\ProgramData\Generative AI\Github\archi-16w-training\src\index.html`
- `C:\ProgramData\Generative AI\Github\archi-16w-training\src\db.gs`
- `C:\ProgramData\Generative AI\Github\archi-16w-training\.clasp.json` (新プロジェクト)

## Repo / Data
- リポジトリ: C:\ProgramData\Generative AI\Github\archi-16w-training\
- スプレッドシート: https://docs.google.com/spreadsheets/d/1tesaYYXP7hsZFbq03irX_MNGvb_TZyeG609QNOvU6WU/
- **デプロイURL**: https://script.google.com/macros/s/AKfycbxVu6IgDAj5lbx9KCVEwsTC-GdG1-H5oYAOotW0x7DdBesM2UrpNkF0KRhliPi0Q-zUcg/exec
- **デプロイメントID**: AKfycbxVu6IgDAj5lbx9KCVEwsTC-GdG1-H5oYAOotW0x7DdBesM2UrpNkF0KRhliPi0Q-zUcg
- 現在: **@95**
- **clasp deploy注意**: 必ず `clasp deploy -i <deploymentId>` を使用（-iなしだと新URLが生成される）
- **Config更新URL例**: `?action=updateConfig&key=TIME_LIMIT_MINUTES&value=60`

## Risks
- QuestionBank再インポート時にTestSetsを手動クリアする運用が必要（clearTestSets APIあり）
- ability問題が0件のため、全テストがknowledge問題のみで構成される（将来ability問題追加時に自動対応）
- 旧プロジェクトは200バージョン上限で更新不可（新プロジェクトを使用すること）

---

## 過去セッション要約

### 44A/44B（2026-01-30 セッション16）
- 44A: LOCAL 12/12成功、44B: URL修正後dry-run 10件検出成功
- OCR精度: ALL-3=93.2%（EasyOCR上限）、残NG 5件

### OCR改善（セッション12-15）
- C案(dotmatrix conf閾値)+B案(OCR文字置換)実施、スコア維持
