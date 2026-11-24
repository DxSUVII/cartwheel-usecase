with source as (
    select * from {{ source('cartwell', 'customer_updates') }}
),

renamed as (
    select
        record:customer_id::string as customer_id,
        record:first_name::string as first_name,
        record:last_name::string as last_name,
        {{ clean_email('record:email::string') }} as email,
        record:phone::string as phone,
        record:address.line1::string as address_line1,
        record:address.city::string as city,
        record:address.state::string as state,
        record:address.pincode::string as pincode,
        record:marketing_opt_in::boolean as marketing_opt_in,
        record:updated_at::timestamp as updated_at,
        _source_file,
        _loaded_at
    from source
)

select * from renamed