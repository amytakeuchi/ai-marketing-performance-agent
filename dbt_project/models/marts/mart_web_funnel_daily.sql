-- grain: date_day x campaign_id x landing_page_id x device (funnel drop-off analysis)
select w.date_day, w.campaign_id, c.campaign_name, c.platform, c.funnel_stage,
       w.landing_page_id, w.device,
       w.sessions, w.add_to_carts, w.checkouts, w.purchases
from {{ ref('fact_web_analytics') }} w
join {{ ref('dim_campaign') }} c using (campaign_id)
