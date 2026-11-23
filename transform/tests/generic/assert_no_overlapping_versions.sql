-- Fails if a customer's time periods overlap.
-- A customer cannot have 2 versions active at the same time.
select 
    a.customer_id, 
    a.valid_from as earlier_valid_from, 
    a.valid_to as earlier_valid_to, 
    b.valid_from as later_valid_from
from {{ ref('dim_customers_t2') }} as a
join {{ ref('dim_customers_t2') }} as b
    on a.customer_id = b.customer_id 
    and a.valid_from < b.valid_from
where coalesce(a.valid_to, '9999-12-31'::timestamp) > b.valid_from