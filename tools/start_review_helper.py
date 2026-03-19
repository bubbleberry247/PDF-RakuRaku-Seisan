"""review_helper 起動スクリプト。

config/env.txt の値（PROD / LOCAL）で save_dir を切り替える。
  PROD  : tool_config_prod.json の save_dir（UNC パス）をそのまま使用
  LOCAL : シナリオフォルダ配下の output/請求書【現場】 を使用
未指定・不正値の場合は即終了（fail fast）。
payment_month は config.py が自動計算する（今月 → 翌月末支払い）。
"""
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCENARIO_DIR = Path(__file__).resolve().parent.parent
ENV_TXT = SCENARIO_DIR / "config" / "env.txt"

# --- env.txt 読み取り ---
if not ENV_TXT.exists():
    print(f"ERROR: {ENV_TXT} が見つかりません。LOCAL または PROD を記載してください。")
    sys.exit(1)

env_mode = ENV_TXT.read_text(encoding="utf-8").strip().upper()

if env_mode == "PROD":
    # tool_config_prod.json の save_dir（UNC パス）を使用。環境変数は設定しない。
    print(f"[env] PROD モード — save_dir は tool_config_prod.json から読み込みます")
elif env_mode == "LOCAL":
    local_save_dir = SCENARIO_DIR / "output" / "請求書【現場】"
    os.environ["REVIEW_HELPER_SAVE_DIR"] = str(local_save_dir)
    print(f"[env] LOCAL モード — save_dir: {local_save_dir}")
else:
    print(f"ERROR: config/env.txt の値が不正です（'{env_mode}'）。PROD または LOCAL を記載してください。")
    sys.exit(1)

# REVIEW_HELPER_PAYMENT_MONTH は未設定 → config.py が自動計算

sys.path.insert(0, str(SCENARIO_DIR / "tools"))

import uvicorn
from review_helper.main import create_app

print(f"URL      : http://127.0.0.1:8021")

app = create_app()
uvicorn.run(app, host="127.0.0.1", port=8021)
