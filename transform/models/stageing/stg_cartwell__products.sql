-- You have 20 products.
-- You have 43 days of files.
-- That means your RAW table has 860 rows (20 x 43).
-- But for our staging model, we don't want 860 rows. 
-- We only want the 20 latest products.
with source as (
    select * from {{ source('cartwell', 'products') }}
),

renamed as (
    select
        record:product_id::string as product_id,
        record:name::string as name,
        record:category::string as category,
        record:price::number(10,2) as price,
        _source_file,
        _loaded_at
    from source
)

select * from renamed
-- The Snowflake Trick:
qualify rank() over (partition by product_id order by _loaded_at desc) = 1
-- QUALIFY = WHERE for window functions
-- SQL doesn't allow window functions in WHERE.
-- if we dont use we have to write another cte for latest recoreds then do where rnk=1 