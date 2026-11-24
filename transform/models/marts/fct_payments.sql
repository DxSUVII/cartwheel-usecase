{{ config(materialized='table') }}

with transactions as (
    select * from {{ ref('stg_cartwell__transactions') }}
),

orders as (
    select * from {{ ref('stg_cartwell__orders') }}
),

-- Calculate the total by summing up the order lines
order_totals as (
    select
        order_id,
        sum(quantity * unit_price) as order_total 
        -- NOTE: If your column is named 'price' instead of 'unit_price', change it here!
    from {{ ref('stg_cartwell__order_lines') }}
    group by order_id
)

select
    t.transaction_id,
    t.order_id,
    t.type,
    t.method,
    t.status as payment_status,
    t.amount,
    o.customer_id,
    o.order_status,
    ot.order_total
from transactions t
join orders o
    on t.order_id = o.order_id
join order_totals ot
    on t.order_id = ot.order_id