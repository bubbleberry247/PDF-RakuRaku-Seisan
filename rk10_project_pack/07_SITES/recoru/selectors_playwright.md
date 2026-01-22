# Playwright selectors: recoru

## 安定セレクタ（A11y）
- Role/Name（getByRole / getByLabel / getByText）優先
- DOM順依存を避ける（first() 乱用禁止、キー抽出→最大/最新選択）

## 完了保証
- ダウンロード：downloadイベント + 保存後ファイル存在 + サイズ>0
- 画面操作：要素の可視/活性/オーバーレイ消滅待ちを成功条件に含める

## 失敗時フォールバック
- 親スコープで絞る（行/カード/モーダル）
- frameLocator（フレームがある場合）
- 最終手段：RK10側のUI操作/画像照合

