# RK10シナリオ Skill - トリガー定義

## 自動起動キーワード

このスキルは以下のキーワードを含むユーザー入力で自動的に起動されます。

### 製品名・ツール名
- RK10
- RK-10
- Keyence
- キーエンス
- シナリオエディター

### ファイル形式
- .rks
- rksファイル
- Program.cs
- シナリオファイル

### 操作・機能
- シナリオ作成
- シナリオ編集
- シナリオ実行
- シナリオデバッグ
- RPA開発

### API・技術
- Keyence API
- ExcelAction
- FileAction
- pywinauto
- UIA

### エラー関連
- DISP_E_BADINDEX
- インデックスが無効
- シート選択エラー
- ビルドエラー
- ランタイムエラー

## 除外キーワード

以下のキーワードのみの場合は起動しない（他スキルの領域）:
- 楽楽精算（→ rakuraku skill）
- レコル（→ recoru skill）
- サイボウズ（→ cybozu skill）
- PDF OCR（→ pdf-ocr skill）

## 使用例

```
ユーザー: RK10のシナリオを修正したい
→ rk10-scenario スキル起動

ユーザー: .rksファイルの編集方法を教えて
→ rk10-scenario スキル起動

ユーザー: pywinautoでRK10を操作する方法
→ rk10-scenario スキル起動

ユーザー: Keyence APIのExcel操作
→ rk10-scenario スキル起動
```
