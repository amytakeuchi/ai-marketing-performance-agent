select
    c.customer_id,
    c.first_order_ts,
    coalesce(cp.campaign_id, 'UNATTRIBUTED') as acquisition_campaign_id
from {{ ref('stg_customers') }} c
left join {{ ref('dim_campaign') }} cp on cp.campaign_id = c.acquisition_campaign_id
