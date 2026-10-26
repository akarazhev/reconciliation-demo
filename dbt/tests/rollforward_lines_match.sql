{{ config(enabled = var('opening', false)) }}
-- Line by line (key and kind): the opening and the closing of the roll-forward equal platform minus books over all
-- lines before the period and up to its end. A wrong opening list fails here even when its total is right.
with lines as (
    select key, kind, occurred_on as on_date, amount from {{ platform_ref('lines') }}
    union all
    select key, kind, booked_on, -amount from {{ ref('stg_ledger') }}
),
recomputed as (
    select
        key, kind,
        sum(case when on_date < cast('{{ var("period_start") }}' as date) then amount else 0 end) as opening,
        sum(case when on_date <= cast('{{ var("period_end") }}' as date) then amount else 0 end) as closing
    from lines
    group by key, kind
)
select coalesce(r.key, c.key) as key, coalesce(r.kind, c.kind) as kind,
       r.opening, c.opening as opening_recomputed, r.closing, c.closing as closing_recomputed
from {{ ref('rollforward') }} as r
full outer join recomputed as c on c.key = r.key and c.kind = r.kind
where coalesce(r.opening, 0) <> coalesce(c.opening, 0)
   or coalesce(r.closing, 0) <> coalesce(c.closing, 0)
