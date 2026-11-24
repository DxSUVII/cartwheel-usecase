-- If this returns 0 rows, it proves our Point-in-Time joins are 100% accurate!
select 
    f.order_id, 
    f.line_number, 
    f.unit_price, 
    p.price as t2_price_at_order_time
from {{ ref('fct_order_lines') }} f
join {{ ref('dim_products_t2') }} p
    on f.product_id = p.product_id
    and f.order_ts >= p.valid_from
    and f.order_ts < coalesce(p.valid_to, '9999-12-31'::timestamp)
where f.unit_price != p.price