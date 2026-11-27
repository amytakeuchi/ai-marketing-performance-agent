select date as date_day, campaign_id, landing_page_id, device,
       sessions, add_to_carts, checkouts, purchases
from {{ source('raw', 'web_analytics') }}
