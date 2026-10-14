select
    '{{ var("dataset") }}' as dataset,
    line_id,
    payout_id,
    key,
    kind,
    cast(amount as decimal(18, 2)) as amount,
    currency,
    occurred_on,
    customer_currency
from {{ platform_ref('lines') }}
where occurred_on between cast('{{ var("period_start") }}' as date) and cast('{{ var("period_end") }}' as date)
