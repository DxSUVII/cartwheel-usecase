-- its just union of stg_cartwell__customers and stg_cartwell__customer_updates
-- added disticnt so we get  1 customer_id
with customers as (
    select 
        customer_id, first_name, last_name, email, phone, 
        address_line1, city, state, pincode, marketing_opt_in, 
        signup_at as updated_at 
    from {{ ref('stg_cartwell__customers') }}
),

updates as (
    select 
        customer_id, first_name, last_name, email, phone, 
        address_line1, city, state, pincode, marketing_opt_in, 
        updated_at 
    from {{ ref('stg_cartwell__customer_updates') }}
)

select distinct * from (
    select * from customers
    union all
    select * from updates
)