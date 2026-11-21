/*
  Model: stg_ecom__order_items
  Layer: Staging
  Grain: One row per order line item (item_id)
  Description: Standardized order line items with explicit key casting and calculated line-item
               total monetary value. Rejects null primary keys and missing parent order references.
*/

{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'order_items']
) }}

with source as (
    select * from {{ source('ecom', 'order_items') }}
),

filtered_and_deduped as (
    select
        item_id,
        order_id,
        product_id,
        quantity,
        unit_price
    from source
    where item_id is not null
      and order_id is not null
    qualify row_number() over (
        partition by item_id
        order by order_id asc
    ) = 1
),

transformed as (
    select
        cast(item_id as number(38,0)) as item_id,
        cast(order_id as number(38,0)) as order_id,
        cast(product_id as number(38,0)) as product_id,
        coalesce(cast(quantity as number(38,0)), 0) as quantity,
        coalesce(cast(unit_price as number(10,2)), 0.00) as unit_price,
        cast(
            coalesce(cast(quantity as number(38,0)), 0) * coalesce(cast(unit_price as number(10,2)), 0.00)
            as number(16,2)
        ) as item_total,
        current_timestamp()::timestamp_ltz as standard_timestamp
    from filtered_and_deduped
)

select
    item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    item_total,
    standard_timestamp
from transformed