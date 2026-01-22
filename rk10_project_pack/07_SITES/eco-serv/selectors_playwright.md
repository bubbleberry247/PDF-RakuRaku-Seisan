# Playwright selectors: eco-serv_web_billing

## 安定セレクタ（A11y）
- ZIPリンク候補
  - getByRole('link', { name: /\.zip$/ })
- 形式限定（誤爆低減）
  - getByRole('link', { name: /^\d+_\d+_.+_\d{6}\.zip$/ })

## 最新判定（DOM順依存を排除）
- allTextContents() でリンク名を取得 → /_(\d{6})\.zip$/ でYYYYMM抽出 → 最大値を選択

## 完了保証
- page.waitForEvent('download') を成功条件にする
- download.saveAs() 後に file exists & size > 0 を確認
