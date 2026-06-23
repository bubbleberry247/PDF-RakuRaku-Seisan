from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: probe_s55_xlwings_workbook_20260622.py SOURCE_XLSX", file=sys.stderr)
        return 2

    source = Path(argv[1])
    if not source.exists():
        print(f"probe: source missing: {source}", file=sys.stderr, flush=True)
        return 1

    dest = Path(r"C:\tmp") / f"s55_xlwings_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    print(f"probe: copy {source} -> {dest}", flush=True)
    shutil.copy2(source, dest)

    print("probe: before xlwings import", flush=True)
    import xlwings as xw

    print("probe: before app", flush=True)
    app = xw.App(visible=False)
    app.display_alerts = False
    workbook = None
    try:
        print("probe: before open", flush=True)
        workbook = app.books.open(str(dest.resolve()))
        print(f"probe: opened sheets={len(workbook.sheets)} names={[s.name for s in workbook.sheets][:5]}", flush=True)

        sheet_names = [s.name for s in workbook.sheets]
        if "RPAテンプレ" in sheet_names:
            print("probe: before copy RPAテンプレ", flush=True)
            workbook.sheets["RPAテンプレ"].api.Copy(After=workbook.sheets[-1].api)
            copied = workbook.sheets[-1]
            copied.name = "RPA_PROBE"
            print(f"probe: copied sheet={copied.name} sheets={len(workbook.sheets)}", flush=True)
        else:
            print("probe: RPAテンプレ not found", flush=True)

        print("probe: before close without save", flush=True)
        workbook.close()
        workbook = None
        print(f"probe: done dest={dest}", flush=True)
        return 0
    finally:
        if workbook is not None:
            workbook.close()
        app.quit()
        print("probe: app quit", flush=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
