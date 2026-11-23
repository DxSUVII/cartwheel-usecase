with source as (
    select * from {{ source('cartwell', 'transactions') }}
),

renamed as (
    select
        record:transaction_id::string as transaction_id,
        record:order_id::string as order_id,
        record:txn_ts::timestamp as txn_ts,
        record:type::string as type,
        record:method::string as method,
        record:amount::number(10,2) as amount,
        record:status::string as status,
        record:failure_reason::string as failure_reason
    from source
)

select * from renamed