select * from {{ ref('fact_ad_performance') }} where clicks > impressions
