-- Payout level (spec §5.2): the declared payout against the sum of its lines; September payouts only.
with lines as (
    select payout_id, sum(amount) as amount_lines
    from {{ ref('platform_lines') }}
    group by payout_id
)
select
    '{{ var("dataset") }}' as dataset,
    p.payout_id,
    p.paid_on,
    p.amount as amount_payout,
    cast(coalesce(l.amount_lines, 0) as decimal(18, 2)) as amount_lines,
    cast(p.amount - coalesce(l.amount_lines, 0) as decimal(18, 2)) as difference
from {{ ref('payouts') }} as p
left join lines as l on l.payout_id = p.payout_id
where p.period_from >= cast('{{ var("period_start") }}' as date)
  and p.period_to <= cast('{{ var("period_end") }}' as date)
