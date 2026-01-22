# Site Profile: 楽楽精算 (rakuraku_seisan)

## 1. 対象範囲
- Base URL: (要記入: 貴社の楽楽精算URL)
- 主要画面: (要追記)
- 目的（自動化）: (要追記)

## 2. A11y診断（A/B/C）
- 判定: A（ログイン画面で確定）
- 根拠:
  - Agent Browser snapshot -c で、ログインフォーム要素が role/name として取得できる
  - 例（snapshot）:
    - text: ログインID / textbox
    - text: パスワード / textbox
    - button: ログイン## 3. 認証・セッション
- ログイン方式: SSO/IDPW(要確認)
- セッション維持の注意: (要確認)
- ブロック要因（CAPTCHA等）: (要確認)

## 4. 推奨ツール選定（壊れにくさ優先）
- Primary: Playwright
- Fallback: Agent Browser（探索/証跡） / RK10（認証や例外時の補完）
- 選定理由:
  - ログイン画面で role/name が明確で、Playwright の getByRole/getByLabel 適用が見込める
  - 待機設計（visible/overlay消滅/遷移確認）を Playwright 側で統制しやすい## 5. 成功条件（検証手段）
- 成功条件: (例：DLファイル名一致/件数一致/登録完了表示 等)
- 検証方法:
  - Playwright: wait条件 + 期待出力
  - Agent Browser: snapshot/screenshotで構造確認
  - RK10: フォルダ監視/画面状態確認

## 6. 既知の落とし穴
- ログイン後にSSO/MFA/CAPTCHAが出る場合、自動化難易度が上がる（要確認）
- ログイン後画面がSPA/フレーム構造の場合、frameLocator や待機設計が必要（要確認）## 7. 更新履歴
- last_verified: 2026-01-22
- 変更点: 初回作成（暫定プロファイル）

## 3. 認証・セッション
- ログイン方式: ID/PW（ログイン画面で確認）
- MFA/SSO/CAPTCHA: ログイン後遷移で要確認（現時点未確定）
- セッション維持の注意: タイムアウト時はログイン画面へ戻る可能性（要確認）

## 7. 更新履歴
- last_verified: 2026-01-22
- 変更点:
  - Agent Browser snapshot/screenshot によりログイン画面A11yを確認し、A判定に確定
  - 推奨PrimaryをPlaywrightに更新

