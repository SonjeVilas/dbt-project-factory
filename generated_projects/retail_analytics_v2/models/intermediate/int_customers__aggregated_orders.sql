/*
    Model: int_customers__aggregated_orders
    Layer: intermediate
    Materialization: ephemeral
    Grain: One row per customer who has placed at least one order (customer_id).

    Purpose:
      Calculates customer lifetime aggregate metrics across all orders, including
      total order count, cumulative gross spend, first order date, and most recent order date.

    Key Assumptions:
      - Orders lacking an assigned customer_id are filtered out.
      - Total spend is coalesced to 0.00 to guarantee non-null numeric measures.
*/

{{ config(
    materialized='ephemeral',
    tags=['intermediate', 'customers', 'orders']
) }}

with orders as (
    select *
    from {{ ref('stg_ecom__orders') }}
),

customer_order_metrics as (
    select
        customer_id,
        count(order_id)::number(18, 0) as total_orders,
        coalesce(sum(total_amount), 0.00)::number(22, 2) as total_spend,
        min(order_date) as first_order_date,
        max(order_date) as most_recent_order_date
    from orders
    where customer_id is not null
    group by
        customer_id
),

final as (
    select
        customer_id,
        total_orders,
        total_spend,
        first_order_date,
        most_recent_order_date
    from customer_order_metrics
)

select * from final
