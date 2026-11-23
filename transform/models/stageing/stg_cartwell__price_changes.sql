with source as (
    select * from {{ source('cartwell', 'price_changes') }}
),

renamed as (
    select
        record:product_id::string as product_id,
        record:old_price::number(10,2) as old_price,
        record:new_price::number(10,2) as new_price,
        record:effective_at::timestamp as effective_at
    from source
)

select * from renamed