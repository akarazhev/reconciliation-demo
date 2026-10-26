{{ config(enabled = var('opening', false)) }}
-- Payout by payout: the opening list names the payouts that the records leave out of the bank at the period start,
-- at the platform's amounts. A wrong id or amount in the list fails here instead of becoming a bank discrepancy.
with listed as (
    select key as payout_id, -difference as amount from {{ ref('stg_opening') }} where level = 'bank'
)
select coalesce(l.payout_id, u.payout_id) as payout_id, l.amount as listed, u.amount as recorded
from listed as l
full outer join {{ ref('unsettled_payouts') }} as u on u.payout_id = l.payout_id
where l.amount is distinct from u.amount
