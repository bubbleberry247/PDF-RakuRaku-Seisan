# 最後の10行レビュー入口 2026-06-23

## 目的

全シナリオの安全実行・費用証跡・RKS関連証跡をCodexが自動確認し、最後の10行の operator_result/reviewer/reviewed_at を記録するための入口です。
目視確認は必須にしません。固定安全ランナーが成功し、latest evidence file が実在する場合は CodexAutoEvidenceCheck として OK を記録できます。

## まず開く

- 同じフォルダの 01_OPEN_FINAL_OPERATOR_REVIEW_10_ROWS.bat を開く。
- C/E配布先の最上位では ★★★最後の10行レビュー_ここだけ開く.bat を開く。
- Codex自動確認で直接進める場合は、C/E配布先の最上位で ★★★残10行を入力する.bat を開く。
- この入口BATは配置先を基準に相対パスで開くため、Eドライブ配布先ではE側コピーを開く。

## 手順

1. 01_OPEN_FINAL_OPERATOR_REVIEW_10_ROWS.bat、または最上位の ★★★最後の10行レビュー_ここだけ開く.bat を開く。
2. Edgeで remaining_operator_decision_brief.html と minimum_operator_review_input.html が開き、minimum_operator_review_input_20260623 フォルダも開く。
3. 目視なしで進める場合は、C/E直下の ★★★残10行を入力する.bat、または開いたフォルダ内の AUTO_FILL_AND_APPLY_FROM_CODEX_EVIDENCE_minimum_operator_review_input.bat を実行する。
4. 手動に戻す場合だけ、GUIDED_FILL_minimum_operator_review_input.bat またはHTMLで operator_result / reviewer / reviewed_at を入力する。
5. HTMLからCSVをダウンロードした場合は、開いている minimum_operator_review_input_20260623 フォルダ内の minimum_operator_review_input.csv として上書き保存する。
6. 作業リポジトリ側の同じフォルダで 02_APPLY_AFTER_10_ROWS_FILLED.bat を実行する。
7. goal_completion_gate.md.numbered と objective_completion_audit.md.numbered を確認する。

## 入力ルール

- operator_result: OK / NG / HOLD。
- reviewer: 確認した人または確認責任者名。
- reviewed_at: 例 2026-06-23T15:40:00。
- Codex自動確認の OK は、fixed safe-check summary が passed で、latest evidence file が実在することを条件にする。
- 手動で OK を入れる場合は、latest evidence を確認せずに OK を入れない。
- NG / HOLD は記録できるが、本番移行OK確定にはならない。

## 現在の状態

- 残10行は CodexAutoEvidenceCheck で自動OK記録済み。
- ★★★残10行を入力する.bat は、Codex自動確認の入口として扱う。
- GUIDED_FILL_minimum_operator_review_input.bat は、手動入力へ戻す場合だけ使う。
- C/E配布コピー側の 02_APPLY_AFTER_10_ROWS_FILLED.bat はレビュー/入力用として扱い、固定安全ランナーが無い環境では反映前に止まる。
- シナリオ43は別システム修正中のため目標スコープ外。承認扱いではない。

## 安全境界

- RK10 ButtonRunはしない。
- 本番書込、実メール、実印刷、最終申請、支払実行、有償Azure OCRはしない。
- SoftBank 51/52 は楽楽精算へ自動申請しない。作成資料 + 郵送請求の合算申請は担当者が手動で行う。
- RK10ライセンス画面が出た場合は、既定の RPA開発版AI付き のままラジオボタンを変更せずOKのみ押す。

## 注意

- Eドライブ配布先で開く場合、E側コピーのレビュー/入力ファイルを開く。
- 正本CSVへの反映と固定安全ランナー実行は、`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan` の作業リポジトリ側で行う。
- 実際の本番移行OK確定は、入力後に固定安全ランナーと完了監査が成功した場合のみ。
- この入口は承認値を自動作成しない。
