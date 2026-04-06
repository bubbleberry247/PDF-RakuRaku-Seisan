"""Deterministic invoice reconciliation: detect and auto-fix line total vs invoice total mismatches.

Two rounding modes:
  - per_line: round tax per line item (simpler, common in small invoices)
  - invoice_level: round tax once per tax-rate group, then apportion via largest-remainder (large invoices)

Usage:
    from tools.common.reconcile import reconcile_invoice
    result = reconcile_invoice(df, mode='invoice_level', tolerance=Decimal('1'))
"""
from decimal import Decimal, ROUND_HALF_UP, getcontext
import pandas as pd
import time

getcontext().prec = 28


def D(x):
    """Convert to Decimal safely."""
    return Decimal(str(x)) if not isinstance(x, Decimal) else x


def norm_currency(s):
    """Normalize currency string to Decimal."""
    if pd.isna(s):
        return Decimal(0)
    return D(str(s).replace('¥', '').replace('￥', '').replace(',', '').replace('，', '').strip())


def round_yen(x):
    """Round to nearest yen (half-up)."""
    return x.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def compute_per_line(row, rounding=True):
    """Compute net, tax, total for a single line item."""
    qty = D(row.get('qty', 1))
    unit = D(row.get('unit_price', 0))
    disc = D(row.get('discount', 0))
    net = qty * unit - disc
    tax_rate = D(row.get('tax_rate', 0))
    tax = net * tax_rate
    if rounding:
        tax = round_yen(tax)
    return net, tax, net + tax


def distribute_by_largest_remainder(components, target_sum):
    """Distribute rounding difference using largest-remainder method."""
    floored = [c.quantize(Decimal('1'), rounding=ROUND_HALF_UP) for c in components]
    floor_sum = sum(floored)
    delta = int(target_sum - floor_sum)
    fracs = [(i, (components[i] - floored[i])) for i in range(len(components))]
    fracs.sort(key=lambda x: x[1], reverse=True)
    adjust = [0] * len(components)
    for k in range(abs(delta)):
        idx = fracs[k % len(components)][0]
        adjust[idx] += 1 if delta > 0 else -1
    return [floored[i] + Decimal(adjust[i]) for i in range(len(components))]


def reconcile_invoice(df, mode='per_line', tolerance=Decimal('1')):
    """Reconcile extracted row totals against computed expected totals.

    Args:
        df: DataFrame with columns: qty, unit_price, discount, tax_rate, extracted_row_total
        mode: 'per_line' (round per row) or 'invoice_level' (round per tax-rate group)
        tolerance: maximum acceptable difference per row (in yen)

    Returns:
        dict with keys: rows (DataFrame), per_row_match_rate, invoice_total_extracted,
        invoice_total_expected, total_EM, processing_seconds
    """
    t0 = time.time()
    df2 = df.copy()
    df2['qty'] = df2.get('qty', 1).fillna(1)
    for c in ['unit_price', 'discount', 'tax_rate', 'extracted_row_total']:
        df2[c] = df2[c].apply(norm_currency) if c in df2.columns else Decimal(0)

    if mode == 'per_line':
        expected_rows = []
        for _, r in df2.iterrows():
            net, tax, tot = compute_per_line(r, rounding=True)
            expected_rows.append((net, tax, tot))
        df2['expected_total'] = [t for (_, _, t) in expected_rows]
    else:
        df2['net'] = df2.apply(
            lambda r: D(r['qty']) * D(r['unit_price']) - D(r['discount']), axis=1
        )
        expected_totals = [Decimal(0)] * len(df2)
        for rate, group in df2.groupby('tax_rate'):
            nets = group['net'].tolist()
            sum_nets = sum(nets)
            raw_tax = [n * D(rate) for n in nets]
            total_tax = round_yen(sum_nets * D(rate))
            if sum(raw_tax) == 0:
                apportioned = [Decimal(0)] * len(raw_tax)
            else:
                ideal = [(r / sum(raw_tax) * total_tax) for r in raw_tax]
                apportioned = distribute_by_largest_remainder(ideal, total_tax)
            for idx, (_, val) in enumerate(group.iterrows()):
                ridx = val.name
                expected_totals[ridx] = round_yen(nets[idx] + apportioned[idx])
        df2['expected_total'] = expected_totals

    df2['delta'] = df2.apply(
        lambda r: D(r.get('extracted_row_total', 0)) - D(r['expected_total']), axis=1
    )
    df2['flag'] = df2['delta'].abs() > D(tolerance)

    per_row_match_rate = 1 - (df2['flag'].sum() / len(df2))
    invoice_total_extracted = sum(df2['extracted_row_total'])
    invoice_total_expected = sum(df2['expected_total'])
    total_em = 1 if invoice_total_extracted == invoice_total_expected else 0

    return {
        'rows': df2,
        'per_row_match_rate': float(per_row_match_rate),
        'invoice_total_extracted': float(invoice_total_extracted),
        'invoice_total_expected': float(invoice_total_expected),
        'total_EM': total_em,
        'processing_seconds': time.time() - t0,
    }


if __name__ == '__main__':
    data = [
        {'qty': 1, 'unit_price': '1000', 'discount': '0', 'tax_rate': '0.10', 'extracted_row_total': '1100'},
        {'qty': 2, 'unit_price': '500', 'discount': '0', 'tax_rate': '0.10', 'extracted_row_total': '1100'},
        {'qty': 1, 'unit_price': '300', 'discount': '0', 'tax_rate': '0.08', 'extracted_row_total': '324'},
    ]
    df = pd.DataFrame(data)
    res = reconcile_invoice(df, mode='invoice_level', tolerance=Decimal('1'))
    print('per_row_match_rate', res['per_row_match_rate'])
    print('invoice_total_extracted', res['invoice_total_extracted'], 'expected', res['invoice_total_expected'])
    print('total_EM', res['total_EM'], 'secs', round(res['processing_seconds'], 3))
