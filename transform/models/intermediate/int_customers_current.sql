select * 
from {{ ref('int_customer_versions') }}
qualify rank() over (partition by customer_id order by updated_at desc) = 1

-- This model tries to find the "latest" version of every customer using RANK()