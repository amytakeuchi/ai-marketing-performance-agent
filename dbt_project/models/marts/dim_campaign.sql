select campaign_id, campaign_name, platform, funnel_stage, is_paid from {{ ref('stg_campaigns') }}
