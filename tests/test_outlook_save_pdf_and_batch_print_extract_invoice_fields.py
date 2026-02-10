import importlib.util
import sys
import unittest
from pathlib import Path


def _load_module() -> object:
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "tools" / "outlook_save_pdf_and_batch_print.py"
    spec = importlib.util.spec_from_file_location(
        "outlook_save_pdf_and_batch_print", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses (and other stdlib pieces) may look up the module in sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[call-arg]
    return module


MODULE = _load_module()


class TestExtractInvoiceFields(unittest.TestCase):
    def test_extract_invoice_fields_prefers_payment_decision_amount(self) -> None:
        # Arrange
        text = """
東海インフラ建設株式会社 御中
キョーワ株式会社 名古屋支店
請求年月日：2026/1/25
ご請求金額(税込) 314,333
支払決定金額 285,758
"""

        # Act
        fields = MODULE._extract_invoice_fields(  # type: ignore[attr-defined]
            text=text, company_deny_regex="東海インフラ建設株式会社"
        )

        # Assert
        self.assertIsNotNone(fields)
        assert fields is not None  # for type checkers
        self.assertEqual(fields.vendor, "キョーワ株式会社 名古屋支店")
        self.assertEqual(fields.issue_date, "20260125")
        self.assertEqual(fields.amount, 285_758)
