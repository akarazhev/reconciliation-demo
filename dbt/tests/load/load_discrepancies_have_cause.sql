{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check'], severity = 'error') }}
-- Every difference has a known cause and an explanation.
select dataset, entity, key, column_name, cause, explanation
from {{ ref('load_discrepancies') }}
where explanation is null
   or cause is null
   or cause not in ('batch_boundary_loss', 'deleted_left_behind', 'duplicate_after_rerun', 'missing_in_target',
                    'extra_in_target', 'duplicate_in_target', 'truncated_decimal', 'timezone_shift',
                    'whitespace_to_null', 'schema_drift', 'payment_wrong_invoice', 'changed_not_exported',
                    'late_item_not_updated', 'value_mismatch')
