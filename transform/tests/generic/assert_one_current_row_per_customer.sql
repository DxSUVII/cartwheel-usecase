-- Fails for any customer that does not have exactly one current version.
-- For every customer, there must be:

-- ✅ Exactly 1 current record
select 
    customer_id, 
    count_if(is_current) as current_rows
from {{ ref('dim_customers_t2') }}
group by customer_id
having count_if(is_current) != 1