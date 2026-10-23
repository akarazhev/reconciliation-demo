{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check'], severity = 'error') }}
-- Found = planted, row for row (spec §6). NULL column names and differences compare as equal.
with found as (
    select dataset, entity, cause, key, column_name, difference from {{ ref('load_discrepancies') }}
),
planted as (
    select dataset, entity, cause, key, column_name, difference from {{ ref('load_truth') }}
)
select
    coalesce(f.dataset, p.dataset) as dataset,
    coalesce(f.entity, p.entity) as entity,
    coalesce(f.cause, p.cause) as cause,
    coalesce(f.key, p.key) as key,
    coalesce(f.column_name, p.column_name) as column_name,
    f.difference as found_difference,
    p.difference as planted_difference
from found as f
full outer join planted as p
  on f.dataset = p.dataset and f.entity = p.entity and f.cause = p.cause and f.key = p.key
 and f.column_name is not distinct from p.column_name and f.difference is not distinct from p.difference
where f.key is null or p.key is null
