"""Tests for reconcile.py and reconcile_gate.py."""
import pytest
import pandas as pd
from decimal import Decimal

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.common.reconcile import reconcile_invoice, norm_currency, round_yen, D
from tools.common.reconcile_gate import check_invoice_balance, ReconciliationError


class TestNormCurrency:
    def test_yen_symbol(self):
        assert norm_currency('¥1,234') == Decimal('1234')

    def test_fullwidth_yen(self):
        assert norm_currency('￥5,678') == Decimal('5678')

    def test_none(self):
        assert norm_currency(None) == Decimal(0)

    def test_plain_number(self):
        assert norm_currency('1000') == Decimal('1000')


class TestRoundYen:
    def test_half_up(self):
        assert round_yen(Decimal('100.5')) == Decimal('101')
        assert round_yen(Decimal('100.4')) == Decimal('100')


class TestReconcilePerLine:
    def test_exact_match(self):
        data = [
            {'qty': 1, 'unit_price': '1000', 'discount': '0', 'tax_rate': '0.10', 'extracted_row_total': '1100'},
        ]
        res = reconcile_invoice(pd.DataFrame(data), mode='per_line')
        assert res['total_EM'] == 1
        assert res['per_row_match_rate'] == 1.0

    def test_mismatch_detected(self):
        # delta=2 (> tolerance=1) → flag must be raised
        # Note: delta=1 equals tolerance boundary (not strictly greater), so use delta=2
        data = [
            {'qty': 1, 'unit_price': '1000', 'discount': '0', 'tax_rate': '0.10', 'extracted_row_total': '1098'},
        ]
        res = reconcile_invoice(pd.DataFrame(data), mode='per_line')
        assert res['total_EM'] == 0
        assert res['rows']['flag'].any()


class TestReconcileInvoiceLevel:
    def test_three_lines(self):
        data = [
            {'qty': 1, 'unit_price': '1000', 'discount': '0', 'tax_rate': '0.10', 'extracted_row_total': '1100'},
            {'qty': 2, 'unit_price': '500', 'discount': '0', 'tax_rate': '0.10', 'extracted_row_total': '1100'},
            {'qty': 1, 'unit_price': '300', 'discount': '0', 'tax_rate': '0.08', 'extracted_row_total': '324'},
        ]
        res = reconcile_invoice(pd.DataFrame(data), mode='invoice_level', tolerance=Decimal('1'))
        assert res['per_row_match_rate'] == 1.0


class TestReconcileGate:
    def test_pass(self):
        data = [
            {'qty': 1, 'unit_price': '1000', 'discount': '0', 'tax_rate': '0.10', 'extracted_row_total': '1100'},
        ]
        result = check_invoice_balance(pd.DataFrame(data), invoice_id='test001')
        assert result['total_EM'] == 1

    def test_fail_raises(self):
        data = [
            {'qty': 1, 'unit_price': '1000', 'discount': '0', 'tax_rate': '0.10', 'extracted_row_total': '999'},
        ]
        with pytest.raises(ReconciliationError, match='JIDOKA-STOP'):
            check_invoice_balance(pd.DataFrame(data), invoice_id='test002')
