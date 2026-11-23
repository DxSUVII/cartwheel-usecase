-- Fails if a successful payment amount does not match its order's calculated total
with order_totals as (
    select
        order_id,
        sum(quantity * unit_price) as order_total
        -- NOTE: Change 'unit_price' to 'price' if your column is named 'price'
    from {{ ref('stg_cartwell__order_lines') }}
    group by order_id
)
select
    t.transaction_id,
    t.amount as payment_amount,
    ot.order_total
from {{ ref('stg_cartwell__transactions') }} t
join order_totals ot
    on t.order_id = ot.order_id
where upper(t.status) = 'SUCCESS'
  and upper(t.type) = 'PAYMENT'
  and t.amount != ot.order_total