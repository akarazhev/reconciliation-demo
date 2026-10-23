{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check'], severity = 'warn') }}
-- The customer's check: every value the same on both sides.
select * from {{ ref('load_value_diff') }}
