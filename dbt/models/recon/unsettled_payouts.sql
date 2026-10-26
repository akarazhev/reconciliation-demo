{{ config(enabled = var('opening', false)) }}
-- From the records alone, not from last month's output: the platform's payouts for operations before the period
-- that no bank deposit booked before the period names. The opening list must name exactly these, at these amounts.
with before_ as (
    select deposit_id, reference
    from {{ ref('deposits') }}
    where booked_on < cast('{{ var("period_start") }}' as date)
)
select p.payout_id, p.amount
from {{ ref('payouts') }} as p
where p.period_to < cast('{{ var("period_start") }}' as date)
  and not exists (
      select 1 from before_ as d
      where list_contains(regexp_extract_all(d.reference, '[A-Za-z0-9_-]+'), p.payout_id))
