select customer_id, first_order_ts, acquisition_campaign_id from {{ source('raw', 'customers') }}
