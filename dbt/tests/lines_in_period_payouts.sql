-- Every September line belongs to a September payout (spec §4, periods); otherwise the bridge
-- would hide money in the gap between the platform and payout levels.
select l.*
from {{ ref('platform_lines') }} as l
where l.payout_id not in (select payout_id from {{ ref('payout_checks') }})
