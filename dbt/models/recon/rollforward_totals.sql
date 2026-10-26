{{ config(enabled = var('opening', false)) }}
-- The roll-forward in five rows. Opening, period and closing are platform minus books; amount_check recomputes each
-- from all lines of every month (rollforward_lines_match checks the same line by line). Payouts not yet in the bank:
-- at the start, the opening list against the records, the platform's payouts before the period that no deposit
-- booked before it names (opening_payouts_match_records checks the same payout by payout); at the end, the bank
-- level alone (no check). The test rollforward_balances requires every check to agree.
with lines as (
    select occurred_on as on_date, amount from {{ platform_ref('lines') }}
    union all
    select booked_on, -amount from {{ ref('stg_ledger') }}
),
bank as (
    select cause, difference from {{ ref('discrepancies') }} where level = 'bank'
),
unsettled as (
    select amount from {{ ref('unsettled_payouts') }}
),
start_ as (select cast('{{ var("period_start") }}' as date) as d),
end_ as (select cast('{{ var("period_end") }}' as date) as d),
rows as (
    select 1 as step, 'opening' as label,
           (select sum(opening) from {{ ref('rollforward') }}) as amount,
           (select sum(amount) from lines where on_date < (select d from start_)) as amount_check
    union all
    select 2, 'period',
           (select sum(period) from {{ ref('rollforward') }}),
           (select sum(amount) from lines where on_date between (select d from start_) and (select d from end_))
    union all
    select 3, 'closing',
           (select sum(closing) from {{ ref('rollforward') }}),
           (select sum(amount) from lines where on_date <= (select d from end_))
    union all
    select 4, 'in_transit_opening',
           (select -sum(difference) from {{ ref('stg_opening') }} where level = 'bank'),
           (select sum(amount) from unsettled)
    union all
    select 5, 'in_transit_closing',
           (select -sum(difference) from bank where cause = 'in_transit'),
           null
)
select
    '{{ var("dataset") }}' as dataset, step, label,
    cast(coalesce(amount, 0) as decimal(18, 2)) as amount,
    cast(case when step = 5 then null else coalesce(amount_check, 0) end as decimal(18, 2)) as amount_check
from rows
