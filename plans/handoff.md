# Handoff — 2026-04-01

## セッション概要
建設許可管理アプリv6実装 → デプロイ → Gmail新着処理 → ビューワー構築 → ページ単位タグ付け

---

## 完了タスク

### 1. v6 全10ステップ実装・デプロイ
- **Step 1**: db.gs — UserAccess/AuthLogシート定義追加
- **Step 2**: auth.gs — OAuth 2.0認証モジュール新規作成（430行）
- **Step 3**: Code2.gs — doGet 7段階OAuthルーティング
- **Step 4**: index.html — ログイン画面 + 認証フロー（Bug3: iOS Safari localStorage対策）
- **Step 5**: api.gs — 全API認証ガード + clientUserKey
- **Step 6**: AUTH_MODE=HYBRID設定
- **Step 7**: 29業種タグ表示（般=青, 特=ピンク）— ドットから短いラベルタグに改善
- **Step 8**: CSVエクスポート（apiExportCsv、BOM付きUTF-8）
- **Step 9**: ハード削除（admin限定、2段階確認、LockService、スナップショット監査）
- **5バグ対策全適用**: Bug1(\u003c), Bug2(clientUserKey優先), Bug3(localStorage), Bug4(ScriptApp URL), Bug5(renderButton)

### 2. デプロイ問題の解決
- `appsscript.json`にwebapp設定追加（executeAs: USER_DEPLOYING, access: ANYONE）
- clasp deployだけでは認可が通らない → GASエディタから「デプロイを管理」→新バージョン→デプロイで解決
- HYBRID モードでOAuth未設定時、GASセッション情報をserverAuthResultに渡すよう修正

### 3. NOT_FOUND 3社修正
- **タイト(C0041)**: OCR誤読（チルト→タイト）→ fetch_status=DUPLICATE_DELETE
- **中根一仁(C0009)**: 代表者名誤認 → fetch_status=PERSON_NAME_DELETE
- **トーケン(C0028)**: 正しいデータ(62352)がrow12に既存。誤番号行(26325)をマーク
- **ホワイトリスト方式**: fetch_status=OKのみダッシュボード表示（Codex推奨）

### 4. Gmail新着メール取得
- 9件のメール → 16ファイルをdata/inbox/に保存
- OCR処理: OK 3件（尾崎鋼業、愛知ベース工業、谷野宮組）、SKIP 8件（決算書等）

### 5. ビューワーv2構築（ページ単位タグ付け対応）
- 3ペインレイアウト（ファイルリスト / PDF画像 / OCRデータ編集）
- ページごとにドキュメント種別タグ付け（10種類、色付きバッジ）
- page_tags.csv / permit_ocr_overrides.csv でデータ永続化

### 6. ユーザーが手動タグ付け・OCRデータ入力済み（4社）
- 井上商会: 特-7 第36304号, 2030/11/24, 6業種
- 伊藤建設: 特-3 第44613号, 2026/12/14, 5業種
- 石田産業: 般-7 第20127号, 2030/10/16, 6業種
- 前畑工務店: 般-3 第50825号, 2026/6/12, 1業種

---

## ファイルの場所（全パス）

### construction-permit-trackerリポジトリ
```
C:\ProgramData\Generative AI\Github\construction-permit-tracker\
├── src\
│   ├── Code2.gs          ← doGet OAuthルーティング（修正済み）
│   ├── auth.gs           ← 新規: OAuth 2.0認証モジュール
│   ├── api.gs            ← 認証ガード + CSVエクスポート + ハード削除API
│   ├── db.gs             ← UserAccess/AuthLogシート追加
│   ├── logic.gs          ← ensureUser_ + hardDeleteCompany_ + ホワイトリスト
│   ├── index.html        ← ログイン画面 + 業種タグ + CSV + ハード削除UI
│   ├── appsscript.json   ← webapp設定 + oauthScopes
│   ├── fix_notfound.gs   ← NOT_FOUND修正用GAS関数
│   ├── staging_viewer.py ← ビューワーv2（ページ単位タグ付け）
│   ├── ocr_permit.py     ← OCRスクリプト（GPT-4o Vision）
│   └── fetch_gmail.py    ← Gmail取得スクリプト
├── data\
│   ├── inbox\            ← Gmail取得した生ファイル（処理前はここ）
│   └── processed\
│       ├── success\      ← OCR成功PDF（3件）
│       │   ├── 20260401_002018_御取引条件等説明書_有限会社尾﨑鋼業.pdf
│       │   ├── 20260401_002026_御取引条件等説明書_愛知ベース工業株式会社.pdf
│       │   └── 20260401_002028_建設業許可証_20260319.pdf（谷野宮組）
│       └── skip\         ← OCRスキップPDF（8件: 決算書、会社案内等）
├── output\
│   ├── staging_permits_20260401_002329.csv  ← OCR結果CSV
│   ├── page_tags.csv                        ← ページ別ドキュメントタイプ（手動タグ）
│   └── permit_ocr_overrides.csv             ← 手動入力OCRデータ（4社分）
└── config.json           ← Gmail/OpenAI/Sheets設定
```

### 元ファイル（ダウンロード）
```
C:\Users\owner\Downloads\145社_許可一覧.xlsx  ← 145社マスタ（50社OK + 95社NOT_FOUND）
```

### GASデプロイ
```
Deploy ID: AKfycbwYJIHfhZ6HBzfNlv2MRl1H3ZqaVMzYBv9KOIMebrQGJ5ftAl3rNymX1KmjjtVtagn1
URL: https://script.google.com/macros/s/AKfycbwYJIHfhZ6HBzfNlv2MRl1H3ZqaVMzYBv9KOIMebrQGJ5ftAl3rNymX1KmjjtVtagn1/exec
Spreadsheet ID: 1FEj9OOz_NsFCDPd5eiYLrawB9x_Y5BI6cKOI3rtZlwA
GAS Script ID: 1o3hSn6ae07OcIeNByJeYXEiGCJbkC5q1V5bIjmvvDDnD4Kk7gNb90Y0I
```

---

## ユーザーの不満と指示の経緯（詳細）

### 1. 業種表示の見づらさ
- **不満**: 29個のドット（●）が並んでいて、どれがどの業種かわからない
- **指示**: 見やすい方法を提案して
- **対応**: 案A（タグ方式）を選択 → 保有業種のみ短いラベル表示（般=青, 特=ピンク）
- **追加不満**: 色の違いの理由がどこにも書いてない → ヘッダーに凡例追加

### 2. NOT_FOUND会社がダッシュボードに残る
- **不満**: 過去に原因特定・修正スクリプト作成済みなのにまだ表示されている
- **指示**: 過去の履歴を探して対処して
- **背景**: fix_mlit_permits.py, rebuild_company_master.pyが未実行だった
- **対応**: gspreadでfetch_statusを直接修正 → ホワイトリスト方式（OK以外非表示）
- **Codex助言**: ブラックリスト→ホワイトリスト方式に変更（将来の漏れ防止）

### 3. CSVエクスポートが動かない
- **不満**: ボタンを押してもダウンロードされない
- **原因**: GAS iframe内でBlobダウンロードが制限される
- **対応**: data URIフォールバック + 新ウィンドウ表示のフォールバック追加

### 4. ビューワーの機能不足（最大の不満）
- **不満1**: シンプルビューワーでPDFが表示されない → base64埋め込み方式の問題 → /pdfエンドポイント方式に変更
- **不満2**: 1つのPDF（22ページ）に複数書類が含まれるのに、ファイル単位でしかタグ付けできない
- **指示**: 旧ビューワー（viewer.html）のようなページ単位のタグ付けが必要
- **不満3**: 一括編集ができない（Shift+クリックで範囲選択→一括タグ付け）← 未実装
- **不満4**: OCRが全然されていない → ページタグ付けとOCR実行が連動していない
- **指示**: 「建設業許可証」タグのページだけOCR実行する仕組みが必要 ← 未実装
- **最終指示**: このリポジトリではなく別リポジトリで再処理したい

### 5. 過去の記録を読まない問題
- **不満**: NOT_FOUND 3社について「既知タスクです」とコードも記録も読まずに回答した
- **指摘**: Gate 4違反（一次ソース未確認）
- **教訓**: セッション開始時にdecisions.mdとmemory/を読む必須アクションを飛ばした

### 6. 自動でやってほしい
- **不満**: 手動操作の指示が多すぎる（GASエディタでデプロイを管理→鉛筆→...）
- **指示**: 「じどうでやって」「SKILLつかって」「GPT5.4に相談して」
- **教訓**: clasp CLIだけでは解決できないGAS固有の制約がある（認可フロー等）

---

## 未完了・次回タスク

### 優先度高
1. **別リポジトリでGmail新着処理を再構築** — ユーザーが現リポジトリでの処理に不満
2. **ビューワー一括編集機能** — Shift+クリック範囲選択→一括タグ付け
3. **ページ単位OCR実行** — 「建設業許可証」タグページのみGPT-4o VisionでOCR
4. **4社の手入力データをスプレッドシートに同期** — permit_ocr_overrides.csv → MLITPermits

### 優先度中
5. **OAuth設定** — GCP Client ID/Secret作成 → HYBRID→OAUTH_REQUIRED移行
6. **藤田さんへの確認依頼** — 94社の許可番号確認（庭昭のように許可不要な会社の分類）
7. **月次レポートメール実装**

### 参照ファイル
- decisions: `plans/decisions/projects/construction-permit-tracker.md`
- memory: `C:\Users\owner\.claude\projects\...\memory\project_construction_permit_tracker.md`
- doboku auth.gs参照: `C:\ProgramData\Generative AI\Github\doboku-14w-training\src\auth.gs`
