# Site Profile: JAHIC WEB請求サービス (eco-serv_web_billing)

## 1. 対象範囲
- Base URL: https://rbbrier.eco-serv.jp/etc/mypage/
- 主要画面:
  - トップ: /etc/mypage/top
  - 明細確認: /etc/mypage/bapPublishedBillAppSearch
- 目的（自動化）:
  - 明細確認ページで最新ZIPをダウンロード（完了保証付き）

## 2. A11y診断（A/B/C）
- 判定: A（実質A）
- 根拠:
  - ダウンロードリンクは role=link（暗黙）で、Computed Accessible Name がファイル名（.zip）になる
  - aria-label等が無くても innerText から Name が算出され安定

## 3. 認証・セッション
- ログイン方式: ID/PW（現時点でMFA前提は未観測）
- セッション維持の注意: タイムアウト時はログイン画面へ戻る可能性。ログインフォームの可視で分岐推奨。

## 4. 推奨ツール選定（壊れにくさ優先）
- Primary: Playwright
- Fallback: Agent Browser（要素探索） / RK10（認証や例外時の補完）
- 選定理由:
  - A11yベースセレクタ（getByRole）が安定
  - downloadイベントで“ダウンロード完了保証”ができる
  - UI順序に依存しない最新判定（YYYYMM最大選択）が可能

## 5. 成功条件（検証手段）
- 成功条件:
  - zipファイルが指定フォルダに保存される
  - ファイル名が `*_YYYYMM.zip` 形式
- 検証方法:
  - Playwright: downloadイベント + saved file existence + サイズ>0
  - RK10: ダウンロードフォルダ監視（.crdownload消滅 + zip生成）

## 6. 既知の落とし穴
- “first()=最新”の前提は危険（ソート変更など）
  - 対策: NameからYYYYMMを抽出して最大を選ぶ
- クリック成功ではなく“成果物取得”を成功条件にする

## 7. 更新履歴
- last_verified: 2026-01-22
- 変更点: 初回登録
