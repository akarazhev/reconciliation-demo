{{ config(enabled = var('opening', false)) }}
-- The roll-forward in five rows, each with the same amount recomputed from all lines of every month: platform
-- minus books before the period, in it and up to its end; payouts not yet in the bank at both ends. The test
-- rollforward_balances requires each pair to agree, so a wrong opening list cannot hide.
with lines as (
    select occurred_on as on_date, amount from {{ platform_ref('lines') }}
    union all
    select booked_on, -amount from {{ ref('stg_ledger') }}
),
payouts as (
    select period_to, paid_on, amount from {{ platform_ref('payouts') }}
),
bank as (
    select difference from {{ ref('discrepancies') }} where level = 'bank' and cause = 'in_transit'
),
start_ as (select cast('{{ var("period_start") }}' as date) as d),
end_ as (select cast('{{ var("period_end") }}' as date) as d),
rows as (
    select 1 as step, 'opening' as label,
           (select sum(opening) from {{ ref('rollforward') }}) as amount,
           (select sum(amount) from lines where on_date < (select d from start_)) as amount_from_lines
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
           (select sum(difference) from bank where difference > 0),
           (select sum(amount) from payouts
            where period_to < (select d from start_) and paid_on >= (select d from start_))
    union all
    select 5, 'in_transit_closing',
           (select -sum(difference) from bank where difference < 0),
           (select sum(amount) from payouts
            where period_to <= (select d from end_) and paid_on > (select d from end_))
)
select
    '{{ var("dataset") }}' as dataset, step, label,
    cast(coalesce(amount, 0) as decimal(18, 2)) as amount,
    cast(coalesce(amount_from_lines, 0) as decimal(18, 2)) as amount_from_lines
from rows
