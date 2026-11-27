-- Attributed orders (paid campaigns) must equal funnel purchases, minus the 6 planted orphan orders
-- which are re-mapped to UNATTRIBUTED. Tolerance covers exactly that known defect.
select abs(o.n - w.n) as diff
from (select count(*) n from {{ ref('fact_orders') }} where campaign_id <> 'UNATTRIBUTED') o,
     (select sum(purchases) n from {{ ref('fact_web_analytics') }}) w
where abs(o.n - w.n) > 6
