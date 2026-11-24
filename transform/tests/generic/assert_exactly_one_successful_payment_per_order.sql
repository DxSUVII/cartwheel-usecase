-- Fails if an order does not have exactly one successful payment
select 
    order_id, 
    count(*) as successful_payments
from {{ ref('stg_cartwell__transactions') }}
where status = 'success' 
  and type = 'payment'
group by order_id
having count(*) != 1