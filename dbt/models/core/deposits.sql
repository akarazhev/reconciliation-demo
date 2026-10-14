select
    bank.dataset,
    bank.transaction_id as deposit_id,
    bank.booking_date as booked_on,
    cast(bank.amount as decimal(18, 2)) as amount,
    bank.currency,
    bank.reference
from {{ ref('stg_bank') }} as bank
join {{ ref('datasets') }} as d
  on d.dataset = bank.dataset
 and upper(bank.counterparty) = upper(d.bank_counterparty)
