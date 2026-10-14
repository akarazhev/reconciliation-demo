select
    dataset,
    entry_id,
    key,
    kind,
    cast(amount as decimal(18, 2)) as amount,
    currency,
    booked_on
from {{ ref('stg_ledger') }}
where booked_on between cast('{{ var("period_start") }}' as date) and cast('{{ var("period_end") }}' as date)
