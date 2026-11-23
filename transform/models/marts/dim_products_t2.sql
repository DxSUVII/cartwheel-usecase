{{ config(materialized='table') }}

with products as (
    select * from {{ ref('stg_cartwell__products') }}
),

-- 1. Deduplicate price changes in case the API sent the same change twice
price_changes as (
    select distinct 
        product_id, 
        effective_at, 
        old_price, 
        new_price
    from {{ ref('stg_cartwell__price_changes') }}
),

-- 2. Find the starting price for products that changed (the old_price of their very first change)
starting_prices as (
    select 
        product_id,
        old_price as price
    from price_changes
    qualify row_number() over (partition by product_id order by effective_at) = 1
),

-- 3. Combine the starting price and all subsequent changes into one timeline
all_price_events as (
    
    -- The starting price for products that DID change
    select 
        product_id, 
        price, 
        '2026-10-01'::timestamp as event_time
    from starting_prices

    union all

    -- The new prices from the changes
    select 
        product_id, 
        new_price as price, 
        effective_at as event_time
    from price_changes

    union all

    -- Products that NEVER changed at all
    select 
        p.product_id, 
        p.price, 
        '2026-10-01'::timestamp as event_time
    from products p
    where p.product_id not in (select product_id from price_changes)
),

-- 4. THE FIX: If there are still duplicates on (product_id, event_time), keep only one row
deduped_events as (
    select 
        product_id,
        price,
        event_time
    from all_price_events
    qualify row_number() over (partition by product_id, event_time order by event_time desc) = 1
),

-- 5. Use LEAD() to find the end date for each price
with_validity as (
    select 
        product_id, 
        price, 
        event_time as valid_from,
        lead(event_time) over (
            partition by product_id 
            order by event_time
        ) as valid_to
    from deduped_events
)

select 
    *,
    valid_to is null as is_current
from with_validity