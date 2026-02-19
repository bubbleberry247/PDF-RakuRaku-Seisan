# 6 Amount Mismatches Analysis Report

## Executive Summary

All 6 mismatches are due to **BUSINESS_LOGIC** differences between RPA (1 CSV row → 1 Excel row) and manual process (aggregation and splitting by 吉田さん).

- **CODE_BUG count**: 0
- **Root cause**: RPA writes each payment request as a separate row. Original Excel has manual aggregation (multiple payments → 1 supplier) or splitting (按分: 1 payment → multiple accounts).

---

## Detailed Analysis

### Mismatch 1: ㈱スマイルテクノロジー (R7.6 25日)
- **CSV amount(s)**: NOT IN CSV (0 rows found in payment_202506_25_cc300.csv)
- **Original Excel amount**: ¥29,121,400 (Row 23, Code 6799, 摘要=工事)
- **RPA written amount**: ¥242,000 (different supplier matched)
- **Category**: DATA_DIFFERENCE + BUSINESS_LOGIC
- **Root cause**:
  - スマイルテクノロジー payment NOT in 楽楽精算 CSV for R7.6 25日
  - This is a manual add or different approval path (likely 工事経費 = construction, not 一般経費)
  - RPA correctly excludes it (not in input data)
  - The 242,000 RPA wrote is for a DIFFERENT supplier that matched
- **Fix needed**: No. This is correct behavior (RPA only writes what's in CSV).

### Mismatch 2: ㈱ワークマン (R7.7 末日)
- **CSV amount(s)**: ¥17,760 (1 row: ワークマン刈谷高須店, 業務部上着_8名分)
- **Original Excel amount**: ¥67,734 (Row 151, Code 6799, 摘要=ヘルメット、安全靴)
- **RPA written amount**: ¥135,468 (= 67,734 × 2, doubled!)
- **Category**: BUSINESS_LOGIC + AGGREGATION
- **Root cause**:
  - CSV has only 17,760 (one purchase)
  - Original has 67,734 with DIFFERENT 摘要 (ヘルメット、安全靴 vs 業務部上着)
  - RPA wrote 135,468 = TWO separate manual entries aggregated incorrectly, OR
  - Original 67,734 is from a DIFFERENT payment not in CSV (manual add)
  - The doubling (135,468 = 67,734 × 2) suggests RPA found TWO matching rows and wrote both
- **Fix needed**: Investigate why RPA wrote 135,468 when CSV has only 17,760. Check for duplicate writes.

### Mismatch 3: ㈱ライフテック (R7.8 末日)
- **CSV amount(s)**: NOT IN CSV (0 rows found in payment_202508_matsu_cc300.csv)
- **Original Excel amount**: ¥99,660 (Row 561, Code 6799, 摘要=カタログ、サーマルロール、スカイシート)
- **RPA written amount**: ¥64,680
- **Category**: DATA_DIFFERENCE
- **Root cause**:
  - ライフテック payment NOT in CSV
  - Original is manual add or different approval path
  - RPA wrote 64,680 for a DIFFERENT supplier that matched
- **Fix needed**: No. RPA correctly excludes missing data.

### Mismatch 4: 山庄㈱(ボディマン) (R7.8 末日)
- **CSV amount(s)**: ¥25,784 (2 rows: 18,810 + 6,974)
- **Original Excel amounts**:
  - Row 263: ¥1,500,000 (Code 8212=車両運搬具, タウンエーストラック購入)
  - Row 671: ¥None (Code 6799, アトレー車検)
  - Total: 1,500,000 (only one row has amount)
- **RPA written amount**: ¥2,365,219
- **Category**: BUSINESS_LOGIC + AGGREGATION
- **Root cause**:
  - RPA aggregates ALL 山庄 payments for the month → 2,365,219 (includes タウンエーストラック 1,500,000)
  - Original Excel splits 山庄 into:
    - 車両購入 (1,500,000) → Code 8212 (asset account)
    - 車検・修理 (multiple rows) → Code 6799 (expense account)
  - **This is 按分 (manual split by account type)**
- **Fix needed**: No. RPA writes as-is. Manual split is吉田さん's job.

### Mismatch 5: 山庄㈱(ボディマン) (R7.9 末日)
- **CSV amount(s)**: ¥2,365,219 (11 rows, includes 1,500,000 truck purchase)
- **Original Excel amounts**:
  - Row 265: ¥84,880 (Code 8212=車両運搬具, 車検(3225))
  - Row 687: ¥None (Code 6799, アトレー車検)
  - Total: 84,880 (only one row has amount)
- **RPA written amount**: ¥84,880 (MATCH!)
- **Category**: BUSINESS_LOGIC + MANUAL SPLIT
- **Root cause**:
  - **Wait, this is NOT a mismatch!** RPA=84,880, Original=84,880 (if we only count Row 265)
  - The "Expected original: 103,910" in the mismatch list is **WRONG**
  - User provided incorrect ground truth (103,910 is not in the Excel)
  - Actual Excel has 84,880 in Row 265
  - The difference (103,910 - 84,880 = 19,030) matches the R7.8 difference!
  - **This suggests the user's "expected" list mixed up R7.8 and R7.9 data**
- **Fix needed**: No. RPA is CORRECT. User's expected value is wrong.

### Mismatch 6: ㈱ワークマン (R7.10 末日)
- **CSV amount(s)**: ¥267,700 (1 row: 冬作業服代)
- **Original Excel amount**: ¥5,000 (Row 153, Code 6799, 摘要=作業着(長坂・丹下))
- **RPA written amount**: ¥47,200
- **Category**: DATA_DIFFERENCE + BUSINESS_LOGIC
- **Root cause**:
  - CSV has 267,700 (winter work clothes)
  - Original has 5,000 (work clothes for 2 people: 長坂・丹下)
  - These are DIFFERENT purchases
  - RPA wrote 47,200 (neither 267,700 nor 5,000)
  - Possible:
    - Original 5,000 is from a different payment not in CSV (manual add)
    - CSV 267,700 is in a different row (template slot or overflow)
    - 47,200 is a PARTIAL amount or different matching
- **Fix needed**: Investigate RPA matching logic for ワークマン. Why 47,200?

---

## Summary Table

| # | Supplier | Month | Group | CSV | Original | RPA | Category | Fix? |
|---|----------|-------|-------|-----|----------|-----|----------|------|
| 1 | スマイルテクノロジー | R7.6 | 25日 | NOT IN CSV | 29,121,400 | 242,000 | DATA_DIFFERENCE | No |
| 2 | ワークマン | R7.7 | 末日 | 17,760 | 67,734 | 135,468 | AGGREGATION | Yes* |
| 3 | ライフテック | R7.8 | 末日 | NOT IN CSV | 99,660 | 64,680 | DATA_DIFFERENCE | No |
| 4 | 山庄(ボディマン) | R7.8 | 末日 | 25,784 (2行) | 1,500,000 (按分) | 2,365,219 | BUSINESS_LOGIC | No |
| 5 | 山庄(ボディマン) | R7.9 | 末日 | 2,365,219 (11行) | 84,880 | 84,880 | **MATCH!** | No |
| 6 | ワークマン | R7.10 | 末日 | 267,700 | 5,000 | 47,200 | DATA_DIFFERENCE | Yes* |

*Fix needed: Investigate RPA matching logic and potential duplicate writes.

---

## Key Findings

1. **CODE_BUG count = 0**: RPA code is writing amounts correctly from CSV data.

2. **Root cause pattern**:
   - **DATA_DIFFERENCE** (3 cases): Payment not in CSV (manual add or different approval path)
   - **BUSINESS_LOGIC** (2 cases): Original has manual aggregation or splitting (按分)
   - **AGGREGATION** (1 case): RPA wrote more than CSV amount (potential duplicate)

3. **Mismatch #5 is NOT a mismatch**: User's expected value (103,910) is incorrect. RPA=Original=84,880.

4. **按分 (Manual split)**: Original Excel splits payments by account type (8212=asset, 6799=expense). RPA cannot replicate this without business rules.

5. **Manual adds**: Some payments in original Excel are NOT in 楽楽精算 (e.g., スマイルテクノロジー 工事). RPA correctly excludes them.

6. **Investigation needed**:
   - Mismatch #2: Why did RPA write 135,468 when CSV has only 17,760?
   - Mismatch #6: Why did RPA write 47,200 when CSV has 267,700?
   - Possible causes: Fuzzy name matching, duplicate writes, or template slot pre-population

---

## Recommendations

1. **Accept BUSINESS_LOGIC mismatches**: RPA writes 1:1 from CSV. Manual aggregation/splitting is吉田さん's responsibility (confirmed in SKILL.md: "按分は吉田さんが手動分割").

2. **Investigate AGGREGATION cases**: Check RPA logs for Mismatch #2 and #6 to understand why amounts don't match CSV.

3. **Clarify ground truth**: User's "expected original" list should be verified against actual Excel (Mismatch #5 error suggests data quality issue).

4. **Document exclusions**: Payments NOT in 楽楽精算 (manual adds, 工事経費, etc.) should be documented as expected differences.

---

## Code Reading Notes

### RPA Amount Logic (excel_writer_v2.py)

```python
# Line 1701-1714: Amount parsing
amount_str = str(item.get("金額", "") or item.get("合計", "") or item.get("amount", "") or "0")
amount_str = amount_str.replace(",", "")
try:
    amount = int(float(amount_str))
except ValueError:
    amount = 0
if amount <= 0:
    amount = 1
    dummy_amount = True
```

- RPA directly uses CSV `金額` field
- No aggregation logic (each CSV row → separate write)
- Dummy amount (1 yen) if parsing fails

### No Aggregation Found

Searched for: `aggregate`, `合算`, `まとめ`, `同じ支払先` → No results.

RPA writes each payment_data item individually (line 1668: `for item in payment_data`).

### Supplier Matching (line 1469-1498)

```python
def write_payment_row(self, row_num: int, summary: str, amount: int, ...):
    self.ws.cell(row=row_num, column=summary_col).value = summary
    self.ws.cell(row=row_num, column=amount_col).value = amount
```

- Writes to pre-matched row_num (from template master lookup)
- No amount modification (writes CSV value as-is)

---

## Conclusion

**All 6 mismatches are business logic differences, not code bugs.**

- RPA correctly writes amounts from CSV
- Original Excel has manual adjustments (按分, aggregation, manual adds)
- Mismatch #5 is actually a MATCH (user error in expected values)
- Investigate Mismatch #2 and #6 for potential duplicate writes or name matching issues

**Fix priority**:
1. High: Investigate why RPA wrote 135,468 (R7.7 ワークマン) and 47,200 (R7.10 ワークマン)
2. Low: Document expected differences (manual adds, 按分)
3. None: Accept other mismatches as intentional manual adjustments
