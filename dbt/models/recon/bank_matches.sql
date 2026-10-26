-- Bank level (spec §5.3): by the payout id in the reference first, then by amount within the
-- window. Both methods require one candidate on each side; ambiguous references never fall back
-- to amount matching (macros/bank_match.sql). Difference = bank minus payout.
-- Payouts the month before left out of the bank (in transit, missing or ambiguous; demo 1, October) come from
-- that month's own output, the opening list, and are matched too, at the amount of the platform's payout record.
-- Each was not in the bank at the start (+ payout); then it arrives, arrives with another amount, is booked after
-- this period or never. opening_payouts_match_records checks the list against the records. Without a list, none.
with payouts as (
    select payout_id, paid_on, amount_payout as amount, false as earlier
    from {{ ref('payout_checks') }}
    union all
    select o.key, coalesce(p.paid_on, cast('{{ var("period_start") }}' as date)), coalesce(p.amount, -o.difference), true
    from {{ ref('stg_opening') }} as o
    left join {{ ref('payouts') }} as p on p.payout_id = o.key
    where o.level = 'bank'
),
deposits as (
    select deposit_id, booked_on, amount, reference
    from {{ ref('deposits') }}
    where booked_on between cast('{{ var("period_start") }}' as date) and cast('{{ var("statement_end") }}' as date)
),
{{ bank_match_ctes() }},
rows as (
    select
        p.payout_id as key,
        p.amount as amount_payout,
        d.amount as amount_bank,
        d.booked_on,
        case when d.booked_on > cast('{{ var("period_end") }}' as date) then 'in_transit'
             when d.amount <> p.amount then 'amount_mismatch' end as cause,
        case when d.booked_on > cast('{{ var("period_end") }}' as date) then -p.amount
             else d.amount - p.amount end as difference
    from matched as m
    join payouts as p on p.payout_id = m.payout_id
    join deposits as d on d.deposit_id = m.deposit_id

    union all

    -- an earlier payout was not in the bank at the start; the rows above and below say what became of it
    select p.payout_id, p.amount, cast(null as decimal(18, 2)), cast(null as date), 'opening_in_transit', p.amount
    from payouts as p
    where p.earlier

    union all

    select
        p.payout_id,
        p.amount,
        cast(null as decimal(18, 2)),
        cast(null as date),
        case when p.payout_id in (select payout_id from reference_candidates)
                  or p.payout_id in (select payout_id from candidates) then 'ambiguous_deposit'
             else 'missing_deposit' end,
        -p.amount
    from payouts as p
    where p.payout_id not in (select payout_id from matched)

    union all

    select
        d.deposit_id,
        cast(null as decimal(18, 2)),
        d.amount,
        d.booked_on,
        case when d.deposit_id in (select deposit_id from reference_candidates)
                  or d.deposit_id in (select deposit_id from candidates) then 'ambiguous_deposit'
             else 'unexpected_deposit' end,
        d.amount
    from deposits as d
    where d.deposit_id not in (select deposit_id from matched)
      and d.booked_on <= cast('{{ var("period_end") }}' as date)
)
select
    '{{ var("dataset") }}' as dataset,
    key,
    cast(amount_payout as decimal(18, 2)) as amount_payout,
    cast(amount_bank as decimal(18, 2)) as amount_bank,
    booked_on,
    cause,
    cast(difference as decimal(18, 2)) as difference
from rows
