"""
Move RPA1_ sheets to the leftmost position in Excel workbook.
Orders sheets chronologically (R7.9, R7.10, R7.11, R7.12, R8.1).
"""
import sys
import re
import xlwings as xw

# Fix Windows encoding issues
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def extract_month_key(sheet_name: str) -> tuple[int, int]:
    """
    Extract year and month from sheet name like 'RPA1_R7.9月分'.
    Returns (year, month) for sorting. R7 = 令和7年 = 2025年.
    """
    match = re.search(r'R(\d+)\.(\d+)月分', sheet_name)
    if match:
        reiwa_year = int(match.group(1))
        month = int(match.group(2))
        western_year = 2018 + reiwa_year  # R1 = 2019
        return (western_year, month)
    return (9999, 99)  # Fallback for unmatched names


def move_rpa_sheets_to_left(file_path: str) -> None:
    """Move all RPA1_ sheets to the leftmost position in chronological order."""
    print(f"Opening workbook: {file_path}")

    # Open workbook (invisible)
    app = xw.App(visible=False)
    try:
        wb = app.books.open(file_path)

        # Get all sheet names
        all_sheets = [sheet.name for sheet in wb.sheets]
        print(f"\nTotal sheets: {len(all_sheets)}")
        print(f"Sheet order BEFORE move:\n{all_sheets[:10]}...")  # Show first 10

        # Find RPA1_ sheets
        rpa_sheets = [name for name in all_sheets if name.startswith("RPA1_")]
        print(f"\nFound {len(rpa_sheets)} RPA1_ sheets:")
        for name in rpa_sheets:
            print(f"  - {name}")

        if not rpa_sheets:
            print("No RPA1_ sheets found. Exiting.")
            wb.close()
            app.quit()
            return

        # Sort RPA1_ sheets chronologically
        # R7.9 (2025/9) → R7.10 (2025/10) → R7.11 (2025/11) → R7.12 (2025/12) → R8.1 (2026/1)
        rpa_sheets_sorted = sorted(rpa_sheets, key=extract_month_key)
        print(f"\nSorted RPA1_ sheets chronologically (will be moved in reverse order):")
        for name in rpa_sheets_sorted:
            year, month = extract_month_key(name)
            print(f"  - {name} ({year}/{month})")

        # Move sheets in REVERSE order so they end up in correct order at the left
        # (Moving to position 1 pushes previous sheets to the right)
        print("\nMoving sheets...")
        for sheet_name in reversed(rpa_sheets_sorted):
            sheet = wb.sheets[sheet_name]
            # Move to leftmost position (before the first sheet)
            sheet.api.Move(Before=wb.sheets[0].api)
            print(f"  Moved: {sheet_name}")

        # Get updated sheet order
        final_sheets = [sheet.name for sheet in wb.sheets]
        print(f"\nSheet order AFTER move:\n{final_sheets[:10]}...")  # Show first 10

        # Verify RPA1_ sheets are at the beginning
        rpa_sheets_final = [name for name in final_sheets if name.startswith("RPA1_")]
        print(f"\nRPA1_ sheets are now at positions: {[final_sheets.index(name) + 1 for name in rpa_sheets_final]}")

        # Save and close
        print("\nSaving workbook...")
        wb.save()
        wb.close()
        print("Done!")

    finally:
        app.quit()


if __name__ == "__main__":
    file_path = r"C:\Users\masam\Desktop\KeyenceRK\ロボット作成資料\55_RPA1_5M_v3_20260211.xlsx"
    move_rpa_sheets_to_left(file_path)
