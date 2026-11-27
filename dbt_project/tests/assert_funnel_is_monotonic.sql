select * from {{ ref('fact_web_analytics') }}
where purchases > checkouts or checkouts > add_to_carts or add_to_carts > sessions
