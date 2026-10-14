with f as (select cause, count(*) as n from {{ ref('discrepancies') }} group by cause),
     p as (select cause, count(*) as n from {{ ref('stg_truth') }} group by cause)
select coalesce(f.cause, p.cause) as cause, f.n as found, p.n as planted
from f
full outer join p on f.cause = p.cause
where f.n is distinct from p.n
