-- grain: date_day x campaign_id
select date_day, campaign_id, impressions, clicks, spend,
       platform_reported_conversions, platform_reported_revenue, had_duplicate, clicks_missing
from {{ ref('stg_ad_performance') }}
