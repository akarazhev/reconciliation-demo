{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check'], severity = 'error') }}
-- As many differences of each cause as were planted.
with found as (
    select dataset, cause, count(*) as found from {{ ref('load_discrepancies') }} group by dataset, cause
),
planted as (
    select dataset, cause, count(*) as planted from {{ ref('load_truth') }} group by dataset, cause
)
select coalesce(f.dataset, p.dataset) as dataset, coalesce(f.cause, p.cause) as cause, f.found, p.planted
from found as f
full outer join planted as p on f.dataset = p.dataset and f.cause = p.cause
where f.found is distinct from p.planted
