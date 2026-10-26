-- Bank level (spec §5.3): by the payout id in the reference first, then by amount within the
-- window. Both methods require one candidate on each side; ambiguous references never fall back
-- to amount matching. Difference = bank minus payout.
-- A payout of an earlier period that the bank books in this one (demo 1, October) is matched too: its deposit
-- is in this period's bank total but the payout is not in this period's payouts, so it is timing, + deposit.
with payouts as (
    select payout_id, paid_on, amount_payout as amount, false as earlier
    from {{ ref('payout_checks') }}
    union all
    select payout_id, paid_on, amount, true
    from {{ ref('payouts') }}
    where period_to < cast('{{ var("period_start") }}' as date)
      and paid_on between cast('{{ var("period_start") }}' as date) and cast('{{ var("statement_end") }}' as date)
),
deposits as (
    select deposit_id, booked_on, amount, reference
    from {{ ref('deposits') }}
    where booked_on between cast('{{ var("period_start") }}' as date) and cast('{{ var("statement_end") }}' as date)
),
reference_candidates as (
    select p.payout_id, d.deposit_id
    from payouts as p
    join deposits as d on list_contains(regexp_extract_all(d.reference, '[A-Za-z0-9_-]+'), p.payout_id)
),
by_reference as (
    select payout_id, deposit_id
    from reference_candidates
    qualify count(*) over (partition by payout_id) = 1
        and count(*) over (partition by deposit_id) = 1
),
payouts_left as (
    select * from payouts where payout_id not in (select payout_id from reference_candidates)
),
deposits_left as (
    select * from deposits where deposit_id not in (select deposit_id from reference_candidates)
),
candidates as (
    select p.payout_id, d.deposit_id
    from payouts_left as p
    join deposits_left as d
      on d.amount = p.amount
     and d.booked_on - p.paid_on between 0 and {{ var('deposit_window_days') }}
),
payout_candidates as (
    select payout_id, count(*) as n from candidates group by payout_id
),
deposit_candidates as (
    select deposit_id, count(*) as n from candidates group by deposit_id
),
by_amount as (
    select c.payout_id, c.deposit_id
    from candidates as c
    join payout_candidates as pc on pc.payout_id = c.payout_id
    join deposit_candidates as dc on dc.deposit_id = c.deposit_id
    where pc.n = 1 and dc.n = 1
),
matched as (
    select * from by_reference
    union all
    select * from by_amount
),
rows as (
    select
        p.payout_id as key,
        p.amount as amount_payout,
        d.amount as amount_bank,
        d.booked_on,
        case when p.earlier or d.booked_on > cast('{{ var("period_end") }}' as date) then 'in_transit'
             when d.amount <> p.amount then 'amount_mismatch' end as cause,
        case when p.earlier then d.amount
             when d.booked_on > cast('{{ var("period_end") }}' as date) then -p.amount
             else d.amount - p.amount end as difference
    from matched as m
    join payouts as p on p.payout_id = m.payout_id
    join deposits as d on d.deposit_id = m.deposit_id
    -- an earlier payout booked after this period too belongs to neither total here
    where not (p.earlier and d.booked_on > cast('{{ var("period_end") }}' as date))

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
      and not p.earlier

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
