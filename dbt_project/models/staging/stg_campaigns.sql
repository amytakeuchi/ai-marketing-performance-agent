select campaign_id, campaign_name, platform, funnel_stage, true as is_paid
from {{ source('raw', 'campaigns') }}
union all
select 'UNATTRIBUTED', 'Unattributed / Direct / Organic', 'Non-paid', 'unattributed', false
