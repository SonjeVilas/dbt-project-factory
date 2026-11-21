/*
    Model: dim_customers
    Layer: marts
    Materialization: table
    Grain: One row per customer (customer_id)

    Purpose: Conformed customer dimension joining sanitized customer attributes
             from staging with aggregated lifetime order metrics from intermediate layer.
             Implements SCD Type 1 full overwrite via table recreation.
*/

{{ config(
    materialized='table',
    schema='marts',
    tags=['marts', 'core', 'dimension', 'customers']
) }}

with customers as (

    select
        customer_id,
        first_name,
        last_name,
        email,
        created_at
    from {{ ref('stg_ecom__customers') }}

),

aggregated_orders as (

    select
        customer_id,
        total_orders,
        total_spend
    from {{ ref('int_customers__aggregated_orders') }}

),

enriched as (

    select
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email,
        c.created_at,
        coalesce(a.total_orders, 0)::number(18, 0) as total_orders,
        coalesce(a.total_spend, 0.00)::number(22, 2) as total_spend,
        current_timestamp()::timestamp_ltz as standard_timestamp
    from customers as c
    left join aggregated_orders as a
        on c.customer_id = a.customer_id

),

final as (

    select
        customer_id,
        first_name,
        last_name,
        email,
        created_at,
        total_orders,
        total_spend,
        standard_timestamp
    from enriched

)

select * from final
