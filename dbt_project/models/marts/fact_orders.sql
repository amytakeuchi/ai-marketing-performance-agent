-- grain: one row per order (last-click attributed)
select order_id, order_ts, date_day, customer_id, campaign_id, is_orphan_campaign, revenue, is_new_customer
from {{ ref('stg_orders') }}
