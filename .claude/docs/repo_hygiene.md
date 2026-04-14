# リポジトリ衛生ルール（正本 / WIP / 生成物）

AGENTS.md から退避。常時ロード対象外。

## 1) 正本（GitHubにコミットしてよいもの）
- `rk10_project_pack/`：ナレッジ正本
- `plans/`：意思決定・引継ぎ・運用ログ
- `tools/`：再利用スクリプトの最終版のみ（1目的=1ファイル名）
- `.claude/skills/`：共有スキル（SKILL.md 等）

## 2) WIP（GitHubにコミットしない）
- `_wip/`, `docs/_wip/`, `tools/_wip/`：試行錯誤・一時退避（.gitignore対象）
- `docs/screenshots/`：自動生成スクリーンショット（連番増加のため禁止）
- バイナリ・zip・重い依存物は原則コミット禁止
- `.claude/settings.local.json`：ローカル専用設定（コミット禁止）

## 3) 証跡例外
条件: ①個人情報なし ②説明的ファイル名 ③手順書からリンクされている

## 4) コミット前チェック
- `git status -sb` が意図した正本の変更のみ
- 生成物・秘密情報が含まれていないこと

## 改善タスクの標準フォーマット
```
- Current（現状）:
- Problem（困りごと）:
- Target（狙う状態）:
- Change（今回"変える"こと）:
- Verification（測り方/検証コマンド）:
- Safety（例外時の停止/通知/リラン安全）:
- Next（うまくいかない場合の次の一手）:
```
