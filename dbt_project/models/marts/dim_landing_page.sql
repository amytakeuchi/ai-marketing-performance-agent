select landing_page_id, path, page_type from {{ ref('stg_landing_pages') }}
