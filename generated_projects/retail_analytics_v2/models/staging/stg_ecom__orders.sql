/*
  Model: stg_ecom__orders
  Layer: Staging
  Grain: One row per sales order (order_id)
  Description: Standardized order headers with normalized status strings, typed transaction
               dates, and standardized amounts. Validates lifecycle statuses and deduplicates
               by latest order date.
*/

{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'orders']
) }}

with source as (
    select * from {{ source('ecom', 'orders') }}
),

filtered_and_deduped as (
    select
        order_id,
        customer_id,
        order_date,
        status,
        total_amount
    from source
    where order_id is not null
      and upper(trim(status)) in ('PENDING', 'COMPLETED', 'CANCELLED')
    qualify row_number() over (
        partition by order_id
        order by order_date desc nulls last
    ) = 1
),

transformed as (
    select
        cast(order_id as number(38,0)) as order_id,
        cast(customer_id as number(38,0)) as customer_id,
        cast(order_date as date) as order_date,
        upper(trim(status)) as status,
        coalesce(cast(total_amount as number(10,2)), 0.00) as total_amount,
        current_timestamp()::timestamp_ltz as standard_timestamp
    from filtered_and_deduped
)

select
    order_id,
    customer_id,
    order_date,
    status,
    total_amount,
    standard_timestamp
from transformed