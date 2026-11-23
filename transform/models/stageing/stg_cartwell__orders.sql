-- Grain: One row = One order

-- Keep only the order header information.
-- its unique
-- order_id	customer_id	order_ts	order_status
-- ORD-1	CUST-5	2026-10-01	PAID

with source as (
    select * from {{ source('cartwell', 'orders') }}
),

renamed as (
    select distinct
        record:order_id::string as order_id,
        record:customer_id::string as customer_id,
        record:order_ts::timestamp as order_ts,
        record:order_status::string as order_status
    from source
)

select * from renamed