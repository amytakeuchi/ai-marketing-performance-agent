-- Orders carry the last-click campaign. Unknown campaign ids are mapped to UNATTRIBUTED and flagged.
select
    o.order_id,
    o.order_ts,
    o.order_ts::date                                   as date_day,
    o.customer_id,
    coalesce(c.campaign_id, 'UNATTRIBUTED')            as campaign_id,
    (c.campaign_id is null and o.campaign_id <> 'UNATTRIBUTED') as is_orphan_campaign,
    o.revenue,
    o.is_new_customer
from {{ source('raw', 'orders') }} o
left join {{ source('raw', 'campaigns') }} c on c.campaign_id = o.campaign_id
