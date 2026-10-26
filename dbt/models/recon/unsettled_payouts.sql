{{ config(enabled = var('opening', false)) }}
-- From the records alone, not from last month's output: last month's bank level recomputed with its own rules
-- (macros/bank_match.sql) over its own statement window (statement_end of the opening_from row in datasets.csv),
-- then cut at this period's start. A payout for operations before the period is unsettled unless it is matched
-- to a deposit booked before the period. The opening list must name exactly these, at these amounts
-- (opening_payouts_match_records).
with window_ as (
    select s.statement_end
    from {{ ref('datasets') }} as d
    join {{ ref('datasets') }} as s on s.dataset = d.opening_from
    where d.dataset = '{{ var("dataset") }}'
),
payouts as (
    select payout_id, paid_on, amount
    from {{ ref('payouts') }}
    where period_to < cast('{{ var("period_start") }}' as date)
),
deposits as (
    select deposit_id, booked_on, amount, reference
    from {{ ref('deposits') }}
    where booked_on <= (select cast(statement_end as date) from window_)
),
{{ bank_match_ctes() }}
select p.payout_id, p.amount
from payouts as p
left join matched as m on m.payout_id = p.payout_id
left join deposits as d on d.deposit_id = m.deposit_id
where m.payout_id is null
   or d.booked_on >= cast('{{ var("period_start") }}' as date)
