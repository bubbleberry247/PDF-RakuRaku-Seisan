from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPORT_DIR = Path(
    r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan"
    r"\plans\reports\s55_v2_current_safe_recheck_20260622"
)
ROBOT_DIR = Path(r"C:\ProgramData\RK10\Robots\55 １５日２５日末日振込エクセル作成")
MAIN = ROBOT_DIR / "tools" / "main.py"
INPUT_CSV = ROBOT_DIR / "data" / "payment_requests" / "payment_matujitsu_test.UNVERIFIED.csv"
STDOUT_PATH = REPORT_DIR / "s55_v2_full_dryrun.stdout.txt"


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-X",
        "utf8",
        str(MAIN),
        "--env",
        "LOCAL",
        "--payment-date",
        "25日",
        "--company-code",
        "300",
        "--template-version",
        "v2",
        "--skip-scrape",
        "--input-csv",
        str(INPUT_CSV),
        "--dry-run",
        "--no-processed-log",
        "--no-mail",
    ]

    print("s55 full dry-run capture")
    print(f"stdout: {STDOUT_PATH}")
    print("command:")
    print("  " + " ".join(f'"{part}"' if " " in part else part for part in command))

    with STDOUT_PATH.open("w", encoding="utf-8", errors="replace") as out:
        completed = subprocess.run(
            command,
            stdout=out,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1200,
            check=False,
        )

    print(f"returncode: {completed.returncode}")
    tail = STDOUT_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
    print("--- stdout tail ---")
    for line in tail:
        print(line)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
