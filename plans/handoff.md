# handoff.md（短く・上書き前提）

## Current focus
- **ai-subscription-dashboard**: **キャンセル済み**。MYSELF revert完了 @8。OpenAI APIキーのConfig手動削除が残。
- **archi-16w トレーニングアプリ**: **@92デプロイ済み**。今週のミニテスト表示修正、Gemini AIアドバイス強化完了。
- **claude-mem**: 永続メモリプラグインをインストール済み（ワーカー port 37777）

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
- 現在: **@92**
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
