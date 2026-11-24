{{ config(materialized='table') }}

with versions as (
    select * from {{ ref('int_customer_versions') }}
),

with_validity as (
    select 
        *,
        updated_at as valid_from,
        lead(updated_at) over (
            partition by customer_id 
            order by updated_at
        ) as valid_to
    from versions
)

select 
    *,
    valid_to is null as is_current
from with_validity