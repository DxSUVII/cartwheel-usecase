-- If a customer buys a Shirt, Shoes, and a Bag, that is 1 Order, 
-- but 3 Rows in the RAW table. 
-- The order-level (order_id, customer_id, order_ts, order_status) repeats on all 3 rows

-- The receipt details
--      What was purchased?
--       How many?
--      At what price?
with source as (
    select * from {{ source('cartwell', 'orders') }}
),

renamed as (
    select
        record:order_id::string as order_id,
        record:line_number::int as line_number,
        record:product_id::string as product_id,
        record:quantity::int as quantity,
        record:unit_price::number(10,2) as unit_price,
        record:line_total::number(10,2) as line_total
    from source
)

select * from renamed