"""Hard gate wrapper: stops pipeline when reconciliation fails (TPS Pokayoke).

Usage in pipeline:
    from tools.common.reconcile_gate import check_invoice_balance
    check_invoice_balance(df, mode='per_line', tolerance=Decimal('1'))
    # Raises ReconciliationError if total_EM == 0
"""
from decimal import Decimal
from tools.common.reconcile import reconcile_invoice
import json
import os
from datetime import datetime


class ReconciliationError(Exception):
    """Raised when invoice reconciliation fails (Jidoka stop)."""
    pass


def check_invoice_balance(
    df,
    mode: str = 'per_line',
    tolerance: Decimal = Decimal('1'),
    invoice_id: str = 'unknown',
    log_dir: str | None = None,
) -> dict:
    """Run reconciliation and raise if totals don't match.

    Args:
        df: DataFrame with required columns
        mode: 'per_line' or 'invoice_level'
        tolerance: max acceptable delta per row
        invoice_id: identifier for logging
        log_dir: directory to save reconciliation logs (optional)

    Returns:
        reconciliation result dict (if passed)

    Raises:
        ReconciliationError: if total_EM == 0
    """
    result = reconcile_invoice(df, mode=mode, tolerance=tolerance)

    # Always log if log_dir provided
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = os.path.join(log_dir, f'reconcile_{invoice_id}_{ts}.json')
        log_data = {
            'invoice_id': invoice_id,
            'timestamp': ts,
            'mode': mode,
            'tolerance': str(tolerance),
            'per_row_match_rate': result['per_row_match_rate'],
            'invoice_total_extracted': result['invoice_total_extracted'],
            'invoice_total_expected': result['invoice_total_expected'],
            'total_EM': result['total_EM'],
            'processing_seconds': result['processing_seconds'],
            'flagged_rows': int(result['rows']['flag'].sum()),
        }
        # Add flagged row details
        flagged = result['rows'][result['rows']['flag']]
        if len(flagged) > 0:
            log_data['flagged_details'] = []
            for idx, row in flagged.iterrows():
                log_data['flagged_details'].append({
                    'row_index': int(idx),
                    'expected': str(row['expected_total']),
                    'extracted': str(row.get('extracted_row_total', 0)),
                    'delta': str(row['delta']),
                })
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

    # Hard gate: stop if totals don't match
    if result['total_EM'] == 0:
        delta = result['invoice_total_extracted'] - result['invoice_total_expected']
        flagged_count = int(result['rows']['flag'].sum())
        raise ReconciliationError(
            f"JIDOKA-STOP: Invoice {invoice_id} reconciliation failed. "
            f"Extracted={result['invoice_total_extracted']}, "
            f"Expected={result['invoice_total_expected']}, "
            f"Delta={delta}, Flagged rows={flagged_count}"
        )

    return result
