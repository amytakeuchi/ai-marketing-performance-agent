-- De-duplicates the ad-platform feed (grain: date x campaign) and flags what it removed.
with ranked as (
    select *,
        row_number() over (partition by date, campaign_id order by date) as rn,
        count(*)     over (partition by date, campaign_id)              as copies
    from {{ source('raw', 'ad_performance') }}
)
select
    date as date_day, campaign_id, impressions, clicks, spend,
    platform_reported_conversions, platform_reported_revenue,
    (copies > 1)    as had_duplicate,
    (clicks is null) as clicks_missing
from ranked where rn = 1
