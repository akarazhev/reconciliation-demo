select * from {{ ref('discrepancies') }}
where cause is null
   or explanation is null
   or cause not in ('duplicate', 'missing_in_ledger', 'missing_at_platform', 'unbooked', 'fee', 'partial',
                    'fx', 'amount_mismatch', 'payout_mismatch', 'in_transit', 'missing_deposit',
                    'unexpected_deposit', 'ambiguous_deposit', 'unbooked_return', 'opening_in_transit')
