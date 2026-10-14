-- Operation level (spec §5.1). Exact pairs on (key, kind, amount) are taken by count first; the cause
-- is then assigned from the whole remainder of the (key, kind) pair, never from one leftover line.
with ledger as (
    select key, kind, amount, count(*) as n
    from {{ ref('ledger_lines') }}
    group by key, kind, amount
),
platform as (
    select key, kind, amount, count(*) as n, bool_or(customer_currency <> currency) as foreign_currency
    from {{ ref('platform_lines') }}
    group by key, kind, amount
),
amounts as (
    select
        coalesce(l.key, p.key) as key,
        coalesce(l.kind, p.kind) as kind,
        coalesce(l.amount, p.amount) as amount,
        coalesce(l.n, 0) as n_ledger,
        coalesce(p.n, 0) as n_platform,
        least(coalesce(l.n, 0), coalesce(p.n, 0)) as n_paired,
        coalesce(p.foreign_currency, false) as foreign_currency
    from ledger as l
    full outer join platform as p
      on l.key = p.key and l.kind = p.kind and l.amount = p.amount
),
pairs as (
    select
        key,
        kind,
        sum(amount * n_ledger) as amount_ledger,
        sum(amount * n_platform) as amount_platform,
        sum(n_ledger - n_paired) as left_ledger,
        sum(n_platform - n_paired) as left_platform,
        sum(amount * (n_ledger - n_paired)) as rest_ledger,
        sum(amount * (n_platform - n_paired)) as rest_platform,
        bool_and(n_ledger = n_paired or n_paired > 0) as ledger_rest_repeats_paired,
        bool_or(n_platform > n_paired and foreign_currency) as foreign_currency
    from amounts
    group by key, kind
)
select
    '{{ var("dataset") }}' as dataset,
    key,
    kind,
    cast(amount_ledger as decimal(18, 2)) as amount_ledger,
    cast(amount_platform as decimal(18, 2)) as amount_platform,
    cast(rest_ledger as decimal(18, 2)) as rest_ledger,
    cast(rest_platform as decimal(18, 2)) as rest_platform,
    cast(rest_platform - rest_ledger as decimal(18, 2)) as difference,
    case
        when left_ledger = 0 and left_platform = 0 then null
        when left_platform = 0 and ledger_rest_repeats_paired then 'duplicate'
        when left_platform = 0 then 'missing_at_platform'
        when left_ledger = 0 and kind = 'charge' then 'unbooked'
        when left_ledger = 0 and kind = 'fee' then 'fee'
        when left_ledger = 0 then 'missing_in_ledger'
        when rest_ledger = rest_platform then null
        when kind = 'fee' then 'fee'
        when kind = 'refund' and abs(rest_platform) < abs(rest_ledger) then 'partial'
        when foreign_currency then 'fx'
        else 'amount_mismatch'
    end as cause
from pairs
