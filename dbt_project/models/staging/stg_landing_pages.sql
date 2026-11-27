select landing_page_id, path, page_type from {{ source('raw', 'landing_pages') }}
