{{ config(enabled = var('opening', false)) }}
-- Roll-forward (demo 1, October): every line the platform and the books disagree on, from the opening list
-- through this period to its end. Opening is last month's output; period is this month's operation level.
with opening as (
    select key, kind, cause, difference, month from {{ ref('stg_opening') }}
),
period as (
    select key, kind, cause, difference from {{ ref('discrepancies') }} where level = 'operation'
)
select
    '{{ var("dataset") }}' as dataset,
    coalesce(o.key, p.key) as key,
    coalesce(o.kind, p.kind) as kind,
    o.cause as cause_opening,
    p.cause as cause_period,
    coalesce(o.month, strftime(cast('{{ var("period_end") }}' as date), '%Y-%m')) as since,
    cast(coalesce(o.difference, 0) as decimal(18, 2)) as opening,
    cast(coalesce(p.difference, 0) as decimal(18, 2)) as period,
    cast(coalesce(o.difference, 0) + coalesce(p.difference, 0) as decimal(18, 2)) as closing
from opening as o
full outer join period as p on o.key = p.key and o.kind = p.kind
