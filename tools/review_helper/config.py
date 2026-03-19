"""Configuration loader for review_helper."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class ReviewHelperConfig:
    queue_base_dir: Path
    manifest_path: Path
    ocr_cache_dir: Path
    project_master_path: Path
    save_dir: Path
    payment_month: str
    port: int = 8021
    tools_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)


def _auto_payment_month() -> str:
    """Current month M -> 'YYYY.M月分(YYYY.{M+1}末支払い)'."""
    today = date.today()
    y, m = today.year, today.month
    # next month for payment
    if m == 12:
        pay_y, pay_m = y + 1, 1
    else:
        pay_y, pay_m = y, m + 1
    return f"{y}.{m}月分({pay_y}.{pay_m}末支払い)"


def _find_project_master(config_dir: Path) -> Path:
    """Auto-detect project_master_v*.xlsx, falling back to project_master.xlsx."""
    versioned = sorted(config_dir.glob("project_master_v*.xlsx"))
    if versioned:
        return versioned[-1]
    fallback = config_dir / "project_master.xlsx"
    return fallback


def load_config(config_path: Path | None = None) -> ReviewHelperConfig:
    """Read tool_config_prod.json and build ReviewHelperConfig."""
    tools_dir = Path(__file__).resolve().parent.parent
    config_dir = tools_dir.parent / "config"

    if config_path is None:
        config_path = config_dir / "tool_config_prod.json"

    with config_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    # Environment variable overrides for local dev/testing
    save_dir = Path(os.environ.get("REVIEW_HELPER_SAVE_DIR", raw["save_dir"]))
    artifact_dir = Path(raw.get("artifact_dir", tools_dir.parent / "artifacts"))
    payment_month = os.environ.get("REVIEW_HELPER_PAYMENT_MONTH", "") or _auto_payment_month()

    manifest_path = artifact_dir / "processed_attachments_manifest.jsonl"
    ocr_cache_dir = artifact_dir / ".ocr_cache"
    project_master_path = _find_project_master(config_dir)
    queue_base_dir = save_dir / payment_month / "要確認"

    return ReviewHelperConfig(
        queue_base_dir=queue_base_dir,
        manifest_path=manifest_path,
        ocr_cache_dir=ocr_cache_dir,
        project_master_path=project_master_path,
        save_dir=save_dir,
        payment_month=payment_month,
        port=8021,
        tools_dir=tools_dir,
    )
