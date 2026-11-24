{{ 
    config(
        materialized='incremental',
        unique_key='customer_id',
        on_schema_change='sync_all_columns'
    ) 
}}

-- We select from int_customers_current because it already has the latest version of each customer
SELECT 
    customer_id,
    first_name,
    last_name,
    email,
    phone,
    address_line1,
    city,
    state,
    pincode,
    marketing_opt_in,
    updated_at
FROM {{ ref('int_customers_current') }}

-- The incremental magic: 
-- If the table already exists, ONLY process rows that are NEW or UPDATED.
-- We do this by checking if the updated_at in our source is newer than what's already in the table.
{% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}