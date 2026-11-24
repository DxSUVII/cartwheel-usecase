-- Fails if a refund exists for an order that is NOT cancelled
select 
    t.transaction_id, 
    t.type, 
    o.status as order_status
from {{ ref('stg_cartwell__transactions') }} t
join {{ ref('stg_cartwell__orders') }} o 
    on t.order_id = o.order_id
where t.type = 'refund' 
  and o.status != 'cancelled'