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
- **RPA書込列**: C列（摘要）、I列（支払額）のみ
- **テンプレート補完列**: A/B/D/E/F（マスタにあれば自動、なければ空）
- **数式列**: H列/J列（絶対に上書きしない）
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
│   ├── excel_writer.py        Excel write + verify_writes()
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
| **Code bug count** | **0** | All mismatches = business judgment (manual adds, method exclusions) |

## 8. Known Issues

| Issue | Detail | Workaround |
|-------|--------|------------|
| 店コード (D列) | テンプレート固定値では限界（山庄=3部門使用） | 楽楽精算の部門情報から取得が望ましい |
| 摘要 (C列) | 53-60% match（手動書き換え前提） | DOM備考をデフォルト入力、人が修正 |
| Company code 300 | CSVに会社コード列なし | **スクレイピング時に必ず --company-code 300** |
| 都度振込 | Excelに存在するが楽楽精算経由ではない | 吉田さんが手動追加。RPAは正しく除外 |

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Records 4x too many | Company code filter missing | `--company-code 300` を必ず指定 |
| Excel formula broken | H列/J列を上書きした | RPA書込は奇数行のC/I列のみ |
| 都度振込がExcelにある | 正常（吉田さん手動追加） | RPAは正しく除外している |
| 0 entries found | 支払予定日に該当データなし | 支払日の自動判定ロジックを確認 |
| Unregistered supplier | テンプレートマスタに未登録 | A列=6799（赤字）で書込、要確認通知 |

## 10. CLI Reference

```bash
# Standard run (dry-run)
python main.py --env PROD --dry-run --payment-date 末日 --company-code 300

# Real write
python main.py --env PROD --payment-date 末日 --company-code 300

# GUI launcher
python launcher.py

# Historical testing
python test_past_month.py 2025-10 all --env LOCAL

# Pre-deploy check
python preflight_check.py --env PROD
```
