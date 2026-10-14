with operation as (
    select
        dataset, 'operation' as level, cause, key, kind,
        amount_ledger, amount_platform,
        cast(null as decimal(18, 2)) as amount_payout, cast(null as decimal(18, 2)) as amount_bank,
        difference, rest_ledger, rest_platform
    from {{ ref('matches') }}
    where cause is not null
),
payout as (
    select
        dataset, 'payout', 'payout_mismatch', payout_id, 'payout',
        cast(null as decimal(18, 2)), amount_lines, amount_payout, cast(null as decimal(18, 2)),
        difference, cast(null as decimal(18, 2)), cast(null as decimal(18, 2))
    from {{ ref('payout_checks') }}
    where difference <> 0
),
bank as (
    select
        dataset, 'bank', cause, key, 'payout',
        cast(null as decimal(18, 2)), cast(null as decimal(18, 2)), amount_payout, amount_bank,
        difference, cast(null as decimal(18, 2)), cast(null as decimal(18, 2))
    from {{ ref('bank_matches') }}
    where cause is not null
),
all_rows as (
    select * from operation
    union all
    select * from payout
    union all
    select * from bank
)
select
    dataset || '|' || level || '|' || cause || '|' || key || '|' || kind as discrepancy_id,
    dataset, level, cause, key, kind,
    amount_ledger, amount_platform, amount_payout, amount_bank,
    difference,
    case when cause = 'in_transit' then 'timing' when difference < 0 then 'short' else 'over' end as effect,
    case cause
        when 'duplicate' then 'Booked twice in the ledger; the platform has it once.'
        when 'missing_in_ledger' then 'On the platform, not in the ledger.'
        when 'missing_at_platform' then 'In the ledger, not on the platform.'
        when 'unbooked' then 'Platform charge not booked in the ledger.'
        when 'fee' then case when coalesce(amount_ledger, 0) = 0
                             then 'Platform fee not booked in the ledger.'
                             else 'Platform fee differs from the booked fee.' end
        when 'partial' then 'Platform refunded less than the ledger booked.'
        when 'fx' then 'Customer paid in another currency; the books likely used another rate.'
        when 'amount_mismatch' then case when level = 'bank'
                                         then 'Deposit amount differs from the payout.'
                                         when {{ same_digits('rest_ledger', 'rest_platform') }}
                                         then 'Amounts differ; no other cause found. Digits transposed: likely a manual edit.'
                                         else 'Amounts differ; no other cause found.' end
        when 'payout_mismatch' then 'Payout amount differs from the sum of its lines.'
        when 'in_transit' then 'September payout booked by the bank in October.'
        when 'missing_deposit' then 'Payout not found in the bank statement.'
        when 'unexpected_deposit' then 'Bank deposit with no matching payout.'
        when 'ambiguous_deposit' then 'Several candidates with the same amount; not matched automatically.'
    end as explanation
from all_rows
