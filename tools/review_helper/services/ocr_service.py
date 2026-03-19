"""OCR service: vision_ocr wrapper with sha256-based caching."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..schemas import OcrResult

logger = logging.getLogger(__name__)


class OcrService:
    def __init__(self, cache_dir: Path):
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, sha256: str) -> Path:
        return self._cache_dir / f"{sha256}.json"

    def extract(
        self,
        pdf_path: Path,
        sha256: str,
        sender_hint: str | None = None,
        subject_hint: str | None = None,
    ) -> OcrResult:
        # 1. Check cache
        cp = self._cache_path(sha256)
        if cp.exists():
            try:
                data = json.loads(cp.read_text("utf-8"))
                return OcrResult(cached=True, **{k: v for k, v in data.items() if k in OcrResult.model_fields})
            except Exception:
                pass

        # 2. Run OCR via vision_ocr (lazy import - it's on sys.path via main.py)
        try:
            from vision_ocr import extract as _vision_extract

            result = _vision_extract(
                pdf_path=str(pdf_path),
                provider="openai",
                sender_hint=sender_hint or "",
                subject_hint=subject_hint or "",
            )
            # result is a VisionOcrResult dataclass - convert to dict
            if hasattr(result, "__dict__"):
                raw = {k: v for k, v in result.__dict__.items() if not k.startswith("_")}
            elif hasattr(result, "model_dump"):
                raw = result.model_dump()
            else:
                raw = dict(result)

            # Map fields
            # project_hint: vision_ocr が工事名を返すフィールド名は実装依存のため複数候補を試みる
            _ph = (raw.get("construction_name") or raw.get("project_name")
                   or raw.get("project") or raw.get("site_name") or "")
            ocr = OcrResult(
                vendor=str(raw.get("vendor") or "") or None,
                issue_date=str(raw.get("issue_date") or "") or None,
                amount=str(raw.get("amount")) if raw.get("amount") is not None else None,
                amount_total=str(raw.get("amount_total")) if raw.get("amount_total") is not None else None,
                invoice_no=str(raw.get("invoice_no") or "") or None,
                project_hint=str(_ph).strip() or None,
                provider=str(raw.get("provider") or raw.get("source") or "openai"),
                confidence=str(raw.get("confidence") or ""),
                cached=False,
            )

            # 3. Save to cache
            cache_data = {k: v for k, v in ocr.model_dump().items() if k != "cached"}
            cp.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")

            return ocr

        except ImportError:
            logger.warning("vision_ocr not available on sys.path")
            return OcrResult(error="vision_ocr not available")
        except Exception as e:
            logger.exception("OCR extraction failed")
            return OcrResult(error=str(e))
