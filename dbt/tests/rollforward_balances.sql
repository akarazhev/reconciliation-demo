{{ config(enabled = var('opening', false)) }}
-- Opening list = platform minus books before the period, recomputed from the lines; the same for the period and at
-- its end; every payout the opening list left in transit is accounted for this month (demo 1, October).
select * from {{ ref('rollforward_totals') }} where amount_check is not null and amount <> amount_check
