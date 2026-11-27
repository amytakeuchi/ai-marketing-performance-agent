select distinct platform, is_paid from {{ ref('stg_campaigns') }}
