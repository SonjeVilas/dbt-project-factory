/*
    Model: fct_orders
    Layer: marts
    Materialization: incremental (merge strategy)
    Grain: One row per sales order transaction (order_id)

    Purpose: Transactional sales fact table capturing order header details,
             completion status boolean flag, and audit timestamp tracking.
             Supports incremental merge filtering on order_date.
*/

{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='order_id',
    schema='marts',
    tags=['marts', 'core', 'fact', 'orders']
) }}

with orders as (

    select
        order_id,
        customer_id,
        order_date,
        status,
        total_amount
    from {{ ref('stg_ecom__orders') }}
    {% if is_incremental() %}
        where order_date >= (select max(order_date) from {{ this }})
    {% endif %}

),

customers as (

    select
        customer_id
    from {{ ref('stg_ecom__customers') }}

),

enriched as (

    select
        o.order_id,
        o.customer_id,
        o.order_date,
        upper(trim(o.status)) as status,
        coalesce(o.total_amount, 0.00)::number(10, 2) as total_amount,
        case
            when upper(trim(o.status)) = 'COMPLETED' then true
            else false
        end as is_completed,
        current_timestamp()::timestamp_ltz as standard_timestamp
    from orders as o
    left join customers as c
        on o.customer_id = c.customer_id

),

final as (

    select
        order_id,
        customer_id,
        order_date,
        status,
        total_amount,
        is_completed,
        standard_timestamp
    from enriched

)

select * from final
