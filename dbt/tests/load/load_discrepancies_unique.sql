{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check'], severity = 'error') }}
-- One row per dataset, entity, cause, key and column (spec §5.3).
select dataset, entity, cause, key, column_name, count(*) as copies
from {{ ref('load_discrepancies') }}
group by dataset, entity, cause, key, column_name
having count(*) > 1
