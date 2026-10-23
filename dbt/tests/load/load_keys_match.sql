{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check'], severity = 'warn') }}
-- The customer's check: every key on both sides once. Fails on a damaged load, as it should.
select * from {{ ref('load_key_diff') }}
