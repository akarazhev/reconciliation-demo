select * from {{ ref('payout_checks') }} where difference <> 0
