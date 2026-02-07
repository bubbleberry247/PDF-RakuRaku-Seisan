# Scenario 55: 振込Excel転記 — Project Decisions

> Append-only. Per-project decision log for Scenario 55.
> Reusable domain knowledge is in `.claude/skills/scenario-55/SKILL.md`.

---

## 2026-01-20: Initial requirements confirmed

**ヒアリング結果**: 吉田さん・瀬戸さんとの打ち合わせで要件確定。
楽楽精算→Excel転記の自動化。15日/25日/末日払い。勘定奉行入力前データ生成が目的。
出力先はユニオン共有→MINISV経理フォルダに変更。完了通知メール新規実装必要。

## 2026-02-04: Template master design decided

**テンプレートマスタ設計**: supplier_template_master.csv/json で支払先→行番号マッピング。
短期マスタ（12ヶ月）と長期マスタ（全期間）の2層構成。
科目推定は5段階カスケード（補正テーブル→最頻出→類似→辞書→デフォルト8440）。

## 2026-02-05: R7.10 verification completed

**DOM抽出→Excel行 再現性検証**: R7.10月分40データ行 vs 楽楽精算130件。
マッチ率34/40=85%。未マッチ6件は総合振込対象外（都度振込/口座振替）。
フィールド別: B(支払先)97%, C(摘要)53%, D(店)91%, E(科目)97%, F(科目コード)94%, I(支払額)97%。

**実書き込みテスト R7.10**: I列 238/251 (94.8%), B列 246/251 (98.0%), C列 230/251 (91.6%)。
I列不一致13件 = 都度振込除外5 + 手動追加1(Sabastian) + データ差異2(ワークマン) + 未登録空行5。
**コードバグ起因のI列不一致: 0件。**

**都度振込の結論**: R7.10に5件存在。吉田さんが手動追加したもの。ExcelWriterの除外動作は正しい。

**ワークマン差異**: 楽楽精算に42,200円+5,000円の2件あり、Excelには5,000円のみ。
担当者が42,200円を手動調整（削除 or 別シート移動）。コードバグではない。

**PROD環境テスト**: 38件取得→31件転記、エラー0、オーバーフロー0。PROD Excelパスは開発機からアクセス不可。

## 2026-02-05: Development milestone reached

**開発機での全タスク完了**。本番PCでの3ステップのみ残存:
1. `python tools\preflight_check.py --env PROD`
2. `python tools\main.py --env PROD --dry-run --payment-date 末日 --no-mail`
3. `python tools\main.py --env PROD --payment-date 末日 --no-mail`（実書き込み）

## 2026-02-06: GUI launcher and auto mode added

tkinter GUIランチャー + 自動実行モード（--auto）作成。
install.bat でPython依存関係の自動インストール対応。

## 2026-02-07: Historical data testing completed

**R7.11 dry-run**: 320 records, 17.5M+ yen, zero errors.
15日=15件(2 unregistered), 25日=60件(4 unregistered), 末日=245件(87 unregistered).

**R7.10 dry-run**: 308 records, 37.5M+ yen, zero errors.
15日=10件(all skipped), 25日=48件(4 written, 3 unregistered), 末日=219件(23 written, 86 unregistered).

## 2026-02-07: Company code 300 root cause identified

**問題**: テストで4倍のレコードが取得される事象が発生。
**根本原因**: CSVに会社コード列がないため、スクレイピング時に会社コード300フィルタを適用しないと全社データが混入する。
**教訓**: ポカヨケ（レコード上限チェック等）は対症療法。根本原因はスクレイピング時のフィルタ適用を必須にすること。
