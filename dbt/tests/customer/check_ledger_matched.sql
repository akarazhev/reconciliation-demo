{{ config(severity = 'warn') }}
-- Every ledger sale and refund is matched with the platform.
select * from {{ ref('discrepancies') }} where level = 'operation' and kind in ('sale', 'refund')
