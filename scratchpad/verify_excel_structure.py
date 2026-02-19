import xlwings as xw
import sys

OUTPUT = r"C:\Users\masam\Desktop\KeyenceRK\ロボット作成資料\55_RPA1_5M_v3_20260211.xlsx"

app = xw.App(visible=False)
try:
    wb = app.books.open(OUTPUT)

    # Check RPA1_R7.10月分
    sheet_name = "RPA1_R7.10月分"
    ws = wb.sheets[sheet_name]
    api = ws.api

    print(f"=== {sheet_name} ===")

    # 1. AutoFilter
    if api.AutoFilterMode:
        af = api.AutoFilter
        print(f"AutoFilter range: {af.Range.Address}")
        # Check filter criteria on each field
        for i in range(1, af.Filters.Count + 1):
            try:
                f = af.Filters(i)
                if f.On:
                    print(f"  Filter field {i}: Criteria1={f.Criteria1}")
            except:
                pass
    else:
        print("NO AutoFilter active!")

    # 2. Merge cells in B column (rows 17-30)
    print("\nMerge cells in B column (rows 17-30):")
    for row in range(17, 31):
        cell = ws.range(f"B{row}")
        if cell.api.MergeCells:
            merge_area = cell.api.MergeArea.Address
            print(f"  B{row}: merged -> {merge_area}")

    # 3. Merge cells in I column (rows 17-30)
    print("\nMerge cells in I column (rows 17-30):")
    for row in range(17, 31):
        cell = ws.range(f"I{row}")
        if cell.api.MergeCells:
            merge_area = cell.api.MergeArea.Address
            print(f"  I{row}: merged -> {merge_area}")

    # 4. Header rows 13-16
    print("\nHeader rows 13-16:")
    for row in range(13, 17):
        vals = []
        for col in range(1, 11):
            v = ws.range((row, col)).value
            if v:
                vals.append(f"{chr(64+col)}{row}={v}")
        print(f"  Row {row}: {vals}")

    # 5. Compare with GT sheet structure
    gt_name = "R7.10月分"
    gt = wb.sheets[gt_name]
    gt_api = gt.api

    print(f"\n=== {gt_name} (GT) ===")
    if gt_api.AutoFilterMode:
        af = gt_api.AutoFilter
        print(f"AutoFilter range: {af.Range.Address}")

    print("\nGT Merge cells in B column (rows 17-30):")
    for row in range(17, 31):
        cell = gt.range(f"B{row}")
        if cell.api.MergeCells:
            merge_area = cell.api.MergeArea.Address
            print(f"  B{row}: merged -> {merge_area}")

    # 6. Check sheet order (first 10 sheets)
    print("\nSheet order (first 10):")
    for i, s in enumerate(wb.sheets):
        if i >= 10:
            break
        print(f"  {i+1}. {s.name}")

    wb.close()
finally:
    app.quit()
