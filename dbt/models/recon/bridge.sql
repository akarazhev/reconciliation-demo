-- Bridge by level (spec §5): ledger + operation differences = platform; + payout differences =
-- payouts; + bank differences = bank. Every total and every cause is one row.
with causes as (
    select dataset, level, cause, sum(difference) as amount
    from {{ ref('discrepancies') }}
    group by dataset, level, cause
),
totals as (
    select 1 as step, 'ledger' as label, sum(amount) as amount from {{ ref('ledger_lines') }}
    union all
    select 3, 'platform', sum(amount) from {{ ref('platform_lines') }}
    union all
    select 5, 'payouts', sum(amount_payout) from {{ ref('payout_checks') }}
    union all
    select 7, 'bank', sum(amount) from {{ ref('deposits') }}
    where booked_on between cast('{{ var("period_start") }}' as date) and cast('{{ var("period_end") }}' as date)
)
select
    '{{ var("dataset") }}' as dataset, step, 'total' as row_type, cast(null as varchar) as level, label,
    cast(coalesce(amount, 0) as decimal(18, 2)) as amount
from totals
union all
select
    dataset,
    case level when 'operation' then 2 when 'payout' then 4 else 6 end,
    'cause', level, cause,
    cast(amount as decimal(18, 2))
from causes
