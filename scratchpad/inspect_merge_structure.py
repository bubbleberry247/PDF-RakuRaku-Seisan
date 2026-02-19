"""
Diagnostic script to inspect merge structure of RPAテンプレ vs GT sheets.
"""

import sys
import xlwings as xw

# UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

EXCEL_PATH = r"C:\Users\masam\Desktop\KeyenceRK\ロボット作成資料\55_RPA1_5M_v3_20260211.xlsx"


def inspect_sheet_merges(sheet_name: str, check_rows: tuple[int, int], is_template: bool = False):
    """Inspect merge structure for a specific sheet."""
    print(f"\n{'=' * 80}")
    print(f"Sheet: {sheet_name}")
    print(f"{'=' * 80}\n")

    app = xw.App(visible=False)
    try:
        wb = app.books.open(EXCEL_PATH)
        try:
            sheet = wb.sheets[sheet_name]
        except KeyError:
            print(f"Sheet '{sheet_name}' not found in workbook")
            wb.close()
            return

        start_row, end_row = check_rows

        # Check specific rows in B and I columns
        print(f"Row-by-row check (rows {start_row}-{end_row}):")
        print("-" * 80)

        for col_letter in ["B", "I"]:
            print(f"\nColumn {col_letter}:")
            for row in range(start_row, end_row + 1):
                cell = sheet.range(f"{col_letter}{row}")
                is_merged = cell.api.MergeCells

                if is_merged:
                    merge_area = cell.api.MergeArea.Address
                    value = cell.value
                    print(f"  {col_letter}{row}: MERGED (area={merge_area}), value={repr(value)}")
                else:
                    value = cell.value
                    print(f"  {col_letter}{row}: NOT merged, value={repr(value)}")

        # List ALL merged ranges involving B column (first 20)
        print(f"\n{'=' * 80}")
        print("ALL merged ranges in column B (first 20):")
        print("-" * 80)

        b_merges = []
        checked_ranges = set()

        # Scan column B rows 1-1000
        for row in range(1, 1001):
            cell = sheet.range(f"B{row}")
            if cell.api.MergeCells:
                merge_area = cell.api.MergeArea.Address
                if merge_area not in checked_ranges:
                    checked_ranges.add(merge_area)
                    value = cell.value
                    b_merges.append((merge_area, value))
                    if len(b_merges) >= 20:
                        break

        for i, (area, value) in enumerate(b_merges, 1):
            print(f"{i}. {area} = {repr(value)}")

        # List ALL merged ranges involving I column (first 20)
        print(f"\n{'=' * 80}")
        print("ALL merged ranges in column I (first 20):")
        print("-" * 80)

        i_merges = []
        checked_ranges = set()

        # Scan column I rows 1-1000
        for row in range(1, 1001):
            cell = sheet.range(f"I{row}")
            if cell.api.MergeCells:
                merge_area = cell.api.MergeArea.Address
                if merge_area not in checked_ranges:
                    checked_ranges.add(merge_area)
                    value = cell.value
                    i_merges.append((merge_area, value))
                    if len(i_merges) >= 20:
                        break

        for i, (area, value) in enumerate(i_merges, 1):
            print(f"{i}. {area} = {repr(value)}")

        # Autofilter range
        print(f"\n{'=' * 80}")
        print("Autofilter range:")
        print("-" * 80)

        try:
            if sheet.api.AutoFilter:
                filter_range = sheet.api.AutoFilter.Range.Address
                print(f"Autofilter: {filter_range}")
            else:
                print("No autofilter set")
        except Exception as e:
            print(f"Error checking autofilter: {e}")

        wb.close()
    finally:
        app.quit()


def main():
    print("Merge Structure Diagnostic Report")
    print("=" * 80)

    # Inspect RPAテンプレ
    inspect_sheet_merges("RPAテンプレ", (13, 22), is_template=True)

    # Inspect R7.12月分 (GT)
    inspect_sheet_merges("R7.12月分", (15, 24), is_template=False)

    # Inspect RPA1_R7.12月分 (generated)
    inspect_sheet_merges("RPA1_R7.12月分", (13, 22), is_template=False)

    print(f"\n{'=' * 80}")
    print("Diagnostic complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
