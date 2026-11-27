-- The mart must carry exactly the revenue in fact_orders (nothing dropped by joins).
select abs((select sum(revenue) from {{ ref('mart_campaign_daily') }})
         - (select sum(revenue) from {{ ref('fact_orders') }})) as diff
where abs((select sum(revenue) from {{ ref('mart_campaign_daily') }})
        - (select sum(revenue) from {{ ref('fact_orders') }})) > 0.01
