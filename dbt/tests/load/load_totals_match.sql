{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check'], severity = 'warn') }}
-- The customer's check: rows and amounts the same on both sides, by entity and period.
select * from {{ ref('load_totals') }}
where source_rows <> target_rows or source_amount <> target_amount
