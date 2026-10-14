select
    '{{ var("dataset") }}' as dataset,
    payout_id,
    paid_on,
    period_from,
    period_to,
    cast(amount as decimal(18, 2)) as amount,
    currency
from {{ platform_ref('payouts') }}
