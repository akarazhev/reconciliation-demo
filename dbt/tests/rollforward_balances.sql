{{ config(enabled = var('opening', false)) }}
-- Opening list = platform minus books before the period, recomputed from the lines; the same at the period end
-- and for the payouts in transit (demo 1, October).
select * from {{ ref('rollforward_totals') }} where amount <> amount_from_lines
