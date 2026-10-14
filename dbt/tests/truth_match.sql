-- Found = planted, row for row (spec §6). Together with truth_unique an extra instance fails.
with found as (
    select level, cause, key, kind, difference from {{ ref('discrepancies') }}
),
planted as (
    select level, cause, key, kind, difference from {{ ref('stg_truth') }}
)
select
    coalesce(f.level, p.level) as level,
    coalesce(f.cause, p.cause) as cause,
    coalesce(f.key, p.key) as key,
    coalesce(f.kind, p.kind) as kind,
    f.difference as found_difference,
    p.difference as planted_difference
from found as f
full outer join planted as p
  on f.level = p.level and f.cause = p.cause and f.key = p.key and f.kind = p.kind and f.difference = p.difference
where f.key is null or p.key is null
