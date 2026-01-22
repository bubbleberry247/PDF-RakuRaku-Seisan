# Site Profile: レコル（RecoRu） (recoru)

## 1. 対象範囲
- Base URL: (要記入: RecoRuログインURL)
- 主要画面: (要追記)
- 目的（自動化）: (要追記)

## 2. A11y診断（A/B/C）
- 判定: B(暫定)
- 根拠（短く）: 暫定。Agent Browser の snapshot -c と Playwright getByRole 可否で確定する。
  - role/name/labelの品質: (要確認)
  - 同名要素の有無: (要確認)
  - frame/shadow/canvas有無: (要確認)
  - 動的DOM差し替え（SPA度）: (要確認)

## 3. 認証・セッション
- ログイン方式: ID/PW or SSO(要確認)
- セッション維持の注意: (要確認)
- ブロック要因（CAPTCHA等）: (要確認)

## 4. 推奨ツール選定（壊れにくさ優先）
- Primary: API(あるなら) / Playwright
- Fallback: RK10
- 選定理由: API併用が強い領域。UIは帳票DL/一覧操作が中心ならPlaywrightで安定化可能。

## 5. 成功条件（検証手段）
- 成功条件: (例：DLファイル名一致/件数一致/登録完了表示 等)
- 検証方法:
  - Playwright: wait条件 + 期待出力
  - Agent Browser: snapshot/screenshotで構造確認
  - RK10: フォルダ監視/画面状態確認

## 6. 既知の落とし穴
- よくある失敗: (要追記)
- 待機ポイント: (要追記)
- 例外処理（リトライ/復旧）: (要追記)

## 7. 更新履歴
- last_verified: 2026-01-22
- 変更点: 初回作成（暫定プロファイル）
