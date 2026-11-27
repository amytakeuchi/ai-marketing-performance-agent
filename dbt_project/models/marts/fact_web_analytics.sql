-- grain: date_day x campaign_id x landing_page_id x device
select date_day, campaign_id, landing_page_id, device, sessions, add_to_carts, checkouts, purchases
from {{ ref('stg_web_analytics') }}
