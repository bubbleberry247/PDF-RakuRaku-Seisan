# Scenario 55: 振込Excel転記 Skill

## Overview
楽楽精算の支払依頼データを総合振込計上・支払伝票Excelへ自動転記するロボット。
Python + Playwright で構築（RK10不使用）。勘定奉行入力前のデータ生成が目的。

## Keywords
シナリオ55, 振込, Excel転記, 楽楽精算, 支払依頼, 総合振込, 勘定奉行, 支払伝票

---

## 1. Business Rules (confirmed via interviews with 吉田さん・瀬戸さん)

| Rule | Detail |
|------|--------|
| Payment groups | 15日/25日/末日（支払予定日で判定） |
| Accounting | 全件「未払費用」（前払/当月区分は廃止済み） |
| Transfer fees | 全件「当方負担」（2026年1月統一） |
| 按分 | RPAは1支払先1行で転記。按分は吉田さんが手動分割 |
| Overflow | 書ける分だけ書く。残りはメールで報告 |
| 承認ステータス | 確認済/確認/確定待 = 承認済（対象）。承認依頼中X/Y = 未承認（除外） |
| 支払方法 | 総合振込 = RPA対象。都度振込/口座振替 = 除外（手動処理） |
| Company code 300 | **必ずスクレイピング時に適用**（CSVには会社コード列なし） |

## 2. 3-Layer Data Judgment

```
Layer 1 (Entry filter):
  承認済み + 支払予定日一致 + 一般経費のみ

Layer 2 (Ops judgment):
  3営業日前までに承認済 → 一括（RPA対象）
  それ以降 → 都度振込（手動）

Layer 3 (RPA judgment):
  テンプレートマスタにあり → 黒字（自動転記）
  マスタなし → 赤字（A列=6799, 要確認）
```

## 3. Excel Structure

- **2行1セット**: 奇数行=本体（RPA書込対象）、偶数行=税（RPA書込禁止）
- **RPA書込列**: A(業者番号), B(支払先), C(摘要), E(科目), F(科目コード), I(支払額), J(支払先計=I)
- **RPA書込禁止列**: D(店) — 吉田さんが手動設定、G(税) — RPAがクリア(None)して残さない
- **数式列**: H列（絶対に上書きしない）
- **ブロック境界**: ヘッダテキスト検出（固定行番号ではない）
  - `15日支払小計`、`25日支払小計`、`末日支払小計`

## 4. Template Master Design

| Source | Fields |
|--------|--------|
| Template master | A(業者番号), E(科目), F(科目コード) |
| NOT in template | D(店) — 部門・案件で変動するため |
| NOT in template | G(税) — 計算値 |

**科目推定の優先順位**:
1. 補正テーブル（手動上書き）
2. 最頻出科目（過去データ統計）
3. 類似支払先マッチ
4. キーワード辞書
5. デフォルト: 消耗品費(8440)

## 5. Config Files

```
C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成\
├── config\
│   ├── env.txt                           (PROD/LOCAL)
│   ├── RK10_config_LOCAL.xlsx
│   ├── RK10_config_PROD.xlsx
│   ├── supplier_template_master.csv      (short-term 12mo)
│   ├── supplier_template_master.json
│   ├── supplier_template_master_long.csv (all-time)
│   ├── supplier_template_master_long.json
│   ├── shiharai_kamoku_master.csv        (支払先→科目)
│   ├── supplier_threshold_rules.json     (資産閾値)
│   └── card_master.csv                   (法人カード→dept_code)
├── tools\
│   ├── main.py         CLI entry (--env, --dry-run, --payment-date, --company-code 300)
│   ├── launcher.py     tkinter GUI
│   ├── rakuraku_scraper.py    Playwright scraping
│   ├── excel_writer.py        Excel write + verify_writes() [v1 only]
│   ├── excel_writer_v2.py     Excel write (xlwings COM for source_excel_path mode)
│   ├── email_notifier.py      Outlook COM notification
│   ├── account_guesser.py     科目推定
│   ├── preflight_check.py     PROD deploy pre-check
│   ├── test_past_month.py     historical data testing
│   └── scrape_past_month.py   historical data scraping
└── docs\
    └── 55 総合振込計上・支払伝票.xlsx   (template)
```

## 6. PROD Paths

- **Write target**: `\\192.168.1.251\TIC-mainSV\【個人使用フォルダ】\管理部\・𠮷田\総合振込計上・支払伝票.xlsx`
- **Read-only**: `\\172.20.0.70\ユニオン共有★公開フォルダ\...`
- **Note**: IP addresses may change (UTM replacement pending by ラディックス)

## 7. Key Verification Results

| Test | Result | Notes |
|------|--------|-------|
| E2E dry_run R7.10 | 25/32 (78.1%) | Code bugs = 0 |
| Real write R7.10 | I列 238/251 (94.8%) | Mismatches = 都度振込5 + 手動追加1 + 担当者調整2 + 未登録空行5 |
| Real write R7.10 | B列 246/251 (98.0%) | |
| R7.10 DOM→Excel field match | B:97%, D:91%, E:97%, F:94%, I:97% | C(摘要):53% = expected (manual rewrite) |
| R7.11 cross-validation | 5/6 (83.3%) | Consistent with R7.10 |
| PROD code path | 38件→31件転記 | Error 0, overflow 0 |
| R7.12 live scraping + real write | 17/21 (81%) match + 3 unregistered | Code bugs = 0, amount match OK (963,860) |
| **Code bug count** | **0** | All mismatches = business judgment (manual adds, method exclusions) |
| R7.12 Dec write test | Block1: 3/4(75%), Block2: 10/18(56%) | RPA-only 6/10=template slots, 1=cross-section(S3), 3=new |
| R7.12 template slot | 158 zero-amount slots in Block2 | RPA correctly fills existing slots |
| R7.12 Dec bank holiday fix | 末日 0→29 records (12/31→12/30) | classify_payment_type_fixed() |
| v10 column rule test | D=None, G=None, I=amount, J=amount | autofilter A16:J758 preserved |
| **v11 xlwings integrity** | **Original sheets: 0 diffs** | openpyxlでは2,734 diffs → xlwingsで完全保持 |
| v11 H column formulas | 582 match, 0 diff | xlwings COM preserves all formulas |
| v11 RPA sheet creation | RPA_R7.11月分 created (79th sheet) | COM sheet copy via xlwings |
| **GT reproduction R7.9** | **32/33 (97%)** | Template fix: 安城印刷A=5101 |
| **GT reproduction R7.10** | **25/26 (96%)** | Template fix: 山庄E=車両運搬具, 川原E=管理諸費 |
| **GT reproduction R7.11** | **19/23 (83%)** | Remaining = data source gaps (4) + unregistered (2) |
| DOM smoke test | 6 headers verified | DOMStructureError on mismatch → email + stop |

## 8. Known Issues

| Issue | Detail | Workaround |
|-------|--------|------------|
| 部署 (E列) | 一覧テーブルに部署カラムなし（cells[7]=空） | **解決済**: card_master.csv で申請者名→部門コード逆引き（38名, 5部門）。不明時は「??不明」 |
| 摘要 (C列) | 53-60% match（手動書き換え前提） | DOM備考をデフォルト入力、人が修正 |
| Company code 300 | CSVに会社コード列なし | **スクレイピング時に必ず --company-code 300** |
| 都度振込 | Excelに存在するが楽楽精算経由ではない | 吉田さんが手動追加。RPAは正しく除外 |
| Dec bank holiday | 12/31年末年始は銀行休業日 → 末日=12/30 | **解決済**: `classify_payment_type()` に12月専用ロジック実装済み |
| 4セクション構造 | Block1(25日)+Block2(末日)+Section3(前払)+Section4(当月) | RPA対象はBlock1+Block2のみ。Section3/4は手動 |
| テンプレートスロット(I=0) | 原本Block2に158行の空スロット（業者名だけ登録） | **解決済**: RPA書込時に既存スロットを検出して活用 |
| autofilter消失 | `copy_worksheet()`後にautofilterが消える | **解決済**: `auto_filter.ref`を明示的にコピー |
| openpyxl破損 | openpyxlのload→saveが78シート×マージセルの複雑Excelを破損 | **解決済**: source_excel_pathモードでxlwings(COM)を使用 |

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Records 4x too many | Company code filter missing | `--company-code 300` を必ず指定 |
| Excel formula broken | H列を上書きした | H列は数式列 — 絶対に上書きしない。D(店)・G(税)もRPA書込禁止 |
| 都度振込がExcelにある | 正常（吉田さん手動追加） | RPAは正しく除外している |
| 0 entries found | 支払予定日に該当データなし | 支払日の自動判定ロジックを確認 |
| Unregistered supplier | テンプレートマスタに未登録 | A列=6799（赤字）で書込、要確認通知 |
| Elements not found in scraper | Rakuraku uses iframe/frame structure | Use page.frames iteration, not page.query_selector directly |
| DOMStructureError raised | Rakuraku UI updated, table column order changed | Update `EXPECTED_TABLE_HEADERS` in rakuraku_scraper.py to match new column positions |

## 10. CLI Reference

```bash
# Standard run (dry-run)
python main.py --env PROD --dry-run --payment-date 末日 --company-code 300

# Real write
python main.py --env PROD --payment-date 末日 --company-code 300

# Original copy + RPA sheet mode
python main.py --env PROD --payment-date 末日 --company-code 300 --source-excel "path	o\original.xlsx"

# GUI launcher
python launcher.py

# Historical testing
python test_past_month.py 2025-10 all --env LOCAL

# Pre-deploy check
python preflight_check.py --env PROD
```
