-- Semantic-layer source model. grain: date_day x campaign_id.
-- All additive measures live here; ratio metrics (ROAS, CTR, ...) are always computed as
-- ratio-of-sums by the semantic layer, never averaged.
with keys as (
    select date_day, campaign_id from {{ ref('fact_ad_performance') }}
    union select date_day, campaign_id from {{ ref('fact_web_analytics') }}
    union select date_day, campaign_id from {{ ref('fact_orders') }}
),
web as (
    select date_day, campaign_id,
           sum(sessions) as sessions, sum(add_to_carts) as add_to_carts,
           sum(checkouts) as checkouts, sum(purchases) as purchases
    from {{ ref('fact_web_analytics') }} group by 1, 2
),
ord as (
    select date_day, campaign_id, count(*) as orders, sum(revenue) as revenue
    from {{ ref('fact_orders') }} group by 1, 2
)
select
    k.date_day, d.week_start, d.month_start, d.year_month,
    k.campaign_id, c.campaign_name, c.platform, c.funnel_stage, c.is_paid,
    (a.campaign_id is not null)                         as has_ad_data,
    coalesce(a.clicks_missing, false)                   as clicks_missing,
    coalesce(a.had_duplicate, false)                    as had_duplicate,
    coalesce(a.spend, 0)                                as spend,
    coalesce(a.impressions, 0)                          as impressions,
    a.clicks                                            as clicks,           -- NULL kept visible
    coalesce(a.platform_reported_conversions, 0)        as platform_reported_conversions,
    coalesce(a.platform_reported_revenue, 0)            as platform_reported_revenue,
    coalesce(w.sessions, 0)                             as sessions,
    coalesce(w.add_to_carts, 0)                         as add_to_carts,
    coalesce(w.checkouts, 0)                            as checkouts,
    coalesce(o.orders, 0)                               as orders,
    coalesce(o.revenue, 0)                              as revenue,
    coalesce(n.new_customers, 0)                        as new_customers
from keys k
join {{ ref('dim_campaign') }} c using (campaign_id)
join {{ ref('dim_date') }} d using (date_day)
left join {{ ref('fact_ad_performance') }} a using (date_day, campaign_id)
left join web w using (date_day, campaign_id)
left join ord o using (date_day, campaign_id)
left join {{ ref('fact_customer_acquisition') }} n using (date_day, campaign_id)
