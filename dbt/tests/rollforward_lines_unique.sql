{{ config(enabled = var('opening', false)) }}
-- One row per line: in the opening list (level, key, kind) and in the roll-forward (key, kind). Two copies of a
-- line would each match the recomputed amount in rollforward_lines_match and repeat on the page.
select 'opening' as source, level, key, kind, count(*) as n
from {{ ref('stg_opening') }}
group by level, key, kind
having count(*) > 1
union all
select 'rollforward', 'operation', key, kind, count(*)
from {{ ref('rollforward') }}
group by key, kind
having count(*) > 1
