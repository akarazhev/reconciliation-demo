{{ config(enabled = var('opening', false)) }}
-- From the records alone, not from last month's output: the platform's payouts for operations before the period
-- that the bank level's own rules (macros/bank_match.sql) do not match to a deposit booked before the period. The
-- opening list must name exactly these, at these amounts (opening_payouts_match_records).
with payouts as (
    select payout_id, paid_on, amount
    from {{ ref('payouts') }}
    where period_to < cast('{{ var("period_start") }}' as date)
),
deposits as (
    select deposit_id, booked_on, amount, reference
    from {{ ref('deposits') }}
    where booked_on < cast('{{ var("period_start") }}' as date)
),
{{ bank_match_ctes() }}
select payout_id, amount
from payouts
where payout_id not in (select payout_id from matched)
