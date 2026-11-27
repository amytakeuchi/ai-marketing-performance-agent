-- grain: date_day x campaign_id ; new customers = first-ever orders
select date_day, campaign_id,
       count(*) filter (where is_new_customer)                  as new_customers,
       coalesce(sum(revenue) filter (where is_new_customer), 0) as new_customer_revenue
from {{ ref('fact_orders') }}
group by 1, 2
