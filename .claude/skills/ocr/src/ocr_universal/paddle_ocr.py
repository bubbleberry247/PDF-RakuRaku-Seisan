"""
paddle_ocr.py — PaddleOCR wrapper for auxiliary text extraction

PaddleOCR 3.x でPDFページからテキストを抽出し、簡体字を日本語に変換して返す。
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_available() -> bool:
    """Check if PaddleOCR is installed."""
    try:
        from paddleocr import PaddleOCR
        return True
    except ImportError:
        return False


_ocr_instance = None

def _get_ocr():
    """Lazy-init singleton PaddleOCR instance."""
    global _ocr_instance
    if _ocr_instance is None:
        import os
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        from paddleocr import PaddleOCR
        _ocr_instance = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return _ocr_instance


def extract_text(pdf_path: str) -> str:
    """
    Extract full text from first page of PDF using PaddleOCR.

    Returns:
        Concatenated text lines (one per line), with simplified Chinese
        chars converted to Japanese equivalents for non-proper-noun text.
        Returns empty string if PaddleOCR is not available or fails.
    """
    if not _is_available():
        logger.warning("PaddleOCR not installed, skipping auxiliary OCR")
        return ""

    try:
        from .jp_norm import normalize_simplified_chinese

        ocr = _get_ocr()
        result = ocr.predict(pdf_path)

        lines = []
        for res in result:
            for text, score in zip(res["rec_texts"], res["rec_scores"]):
                text = text.strip()
                if text:
                    # Apply simplified Chinese conversion to OCR text
                    text = normalize_simplified_chinese(text)
                    lines.append(text)

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"PaddleOCR extraction failed: {e}")
        return ""
