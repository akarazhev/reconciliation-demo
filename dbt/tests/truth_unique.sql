select 'discrepancies' as source, discrepancy_id as id, count(*) as n
from {{ ref('discrepancies') }}
group by discrepancy_id
having count(*) > 1
union all
select 'truth', dataset || '|' || level || '|' || cause || '|' || key || '|' || kind, count(*)
from {{ ref('stg_truth') }}
group by 2
having count(*) > 1
