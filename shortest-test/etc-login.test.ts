import { shortest } from "@antiwork/shortest";

// ETCサイトログインテスト
shortest("ETCサイトにログインする", {
  // 自然言語でテストを記述
  // Shortestが適切な要素を見つけて操作してくれる
})
  .expect("ログインページが表示される")
  .expect("ログインIDの入力欄がある")
  .expect("パスワードの入力欄がある");

shortest("ログインIDとパスワードを入力してログインする")
  .given("ログインページにいる")
  .when("ログインID欄に環境変数ETC_LOGIN_IDの値を入力する")
  .when("パスワード欄に環境変数ETC_PASSWORDの値を入力する")
  .when("ログインボタンをクリックする")
  .expect("マイページが表示される");

shortest("ZIPファイルのダウンロードリンクを確認する")
  .given("ログイン済みでマイページにいる")
  .expect(".zipを含むリンクが存在する");
