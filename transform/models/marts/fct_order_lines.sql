{{ config(materialized='table') }}

with orders as (
    select * from {{ ref('stg_cartwell__orders') }}
),

order_lines as (
    select * from {{ ref('stg_cartwell__order_lines') }}
),

dim_products as (
    select * from {{ ref('dim_products_t2') }}
),

dim_customers as (
    select * from {{ ref('dim_customers_t2') }}
)

select
    ol.order_id,
    ol.line_number,
    ol.product_id,
    o.order_ts,
    o.customer_id,
    c.city as customer_city_at_order_time,
    p.price as unit_price,
    ol.quantity,
    ol.quantity * p.price as line_total

from order_lines ol
join orders o
    on ol.order_id = o.order_id
join dim_products p
    on ol.product_id = p.product_id
    and o.order_ts >= p.valid_from
    and o.order_ts < coalesce(p.valid_to, '9999-12-31'::timestamp)
join dim_customers c
    on o.customer_id = c.customer_id
    and o.order_ts >= c.valid_from
    and o.order_ts < coalesce(c.valid_to, '9999-12-31'::timestamp)