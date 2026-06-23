from __future__ import annotations

import sys


def main() -> int:
    print("probe: before xlwings import", flush=True)
    import xlwings as xw

    print("probe: before app", flush=True)
    app = xw.App(visible=False)
    try:
        print("probe: app ok", flush=True)
    finally:
        app.quit()
        print("probe: quit ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
