{{ config(enabled = var('platform') == 'ozon') }}
-- Lines without a posting (storage, fines) are keyed '<code>:<date>', the key the books can know.
select
    a.line_id,
    p.payout_id,
    coalesce(a.posting_number, m.code || ':' || strftime(a.accrued_on, '%Y-%m-%d')) as key,
    case when m.kind is null then error('Unknown Ozon accrual type: ' || a.accrual_type) else m.kind end as kind,
    cast(a.amount as decimal(18, 2)) as amount,
    'RUB' as currency,
    a.accrued_on as occurred_on,
    'RUB' as customer_currency
from {{ ref('stg_ozon__accruals') }} as a
left join {{ ref('kind_map_ozon') }} as m on m.accrual_type = a.accrual_type
left join {{ ref('stg_ozon__payouts') }} as p on a.accrued_on between p.period_from and p.period_to
