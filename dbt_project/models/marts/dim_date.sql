select
    d::date                                   as date_day,
    date_trunc('week', d)::date               as week_start,
    date_trunc('month', d)::date              as month_start,
    to_char(d, 'YYYY-MM')                     as year_month,
    extract(isodow from d)::int               as day_of_week,
    extract(isodow from d) >= 6               as is_weekend
from generate_series(
    (select min(date_day) from {{ ref('stg_ad_performance') }}),
    (select max(date_day) from {{ ref('stg_ad_performance') }}),
    interval '1 day') as d
