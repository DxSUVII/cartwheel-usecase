{{ config(materialized='table') }}

with versions as (
    select * from {{ ref('int_customer_versions') }}
),

-- 1. Filter out any updates that happened AFTER our chosen date
filtered as (
    select *
    from versions
    where updated_at < dateadd(day, 1, '{{ var("as_of", "2026-11-12") }}'::date)
),

-- 2. Pick the latest version per customer among what's left
ranked as (
    select *,
        row_number() over (
            partition by customer_id 
            order by updated_at desc
        ) as rn
    from filtered
)

-- 3. Keep only the latest version (Rank 1)
select * 
from ranked
where rn = 1