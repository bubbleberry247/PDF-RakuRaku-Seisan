# -*- coding: utf-8 -*-
"""Scenario70 preflight checks."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common.credential_manager import get_credential, get_credential_value
from common.scenario70_config import DEFAULT_CONFIG_DIR, get_env, load_config

CREDENTIAL_TARGET_ALIASES = (
    "RK10_RakurakuSeisan",
    "楽楽精算",
)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _check_credentials(credential_name: str) -> bool:
    for target_name in (credential_name, *CREDENTIAL_TARGET_ALIASES):
        try:
            get_credential(target_name)
            return True
        except Exception:
            pass
    try:
        login_id = get_credential_value("ログインID　楽楽精算")
        password = get_credential_value("パスワード　楽楽精算")
        return bool(login_id and password)
    except Exception:
        return False


def _check_playwright() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401

        return True, "playwright.sync_api import OK"
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scenario70 preflight")
    parser.add_argument("--env", default=None)
    parser.add_argument("--config-dir", default=str(DEFAULT_CONFIG_DIR))
    args = parser.parse_args()

    config_dir = Path(args.config_dir)
    env_name = get_env(config_dir, args.env)
    config = load_config(config_dir, env_name)

    artifact_root = Path(config.get("ARTIFACT_ROOT", "")).expanduser()
    if not artifact_root:
        raise RuntimeError("ARTIFACT_ROOT is empty")
    preflight_dir = artifact_root / "preflight"
    _ensure_dir(preflight_dir)
    preflight_path = preflight_dir / f"preflight_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    checks = {
        "config_dir_exists": config_dir.exists(),
        "config_file_loaded": True,
        "base_url_present": bool(config.get("BASE_URL")),
        "department_code_present": bool(config.get("DEPARTMENT_CODE")),
        "transfer_source_present": bool(config.get("TRANSFER_SOURCE")),
        "credential_name_present": bool(config.get("CREDENTIAL_NAME")),
    }

    artifact_root.mkdir(parents=True, exist_ok=True)
    write_test = artifact_root / ".scenario70_write_test"
    write_test.write_text("ok", encoding="utf-8")
    write_test.unlink()
    checks["artifact_root_writable"] = True

    checks["credentials_available"] = _check_credentials(config.get("CREDENTIAL_NAME", "RK10_RakurakuSeisan"))
    playwright_ok, playwright_detail = _check_playwright()
    checks["playwright_available"] = playwright_ok

    payload = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "env_name": env_name,
        "config_dir": str(config_dir),
        "artifact_root": str(artifact_root),
        "checks": checks,
        "playwright_detail": playwright_detail,
    }
    preflight_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    required = [
        "config_dir_exists",
        "config_file_loaded",
        "base_url_present",
        "department_code_present",
        "transfer_source_present",
        "credential_name_present",
        "artifact_root_writable",
        "credentials_available",
        "playwright_available",
    ]
    ok = all(checks[key] for key in required)
    print(preflight_path)
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
