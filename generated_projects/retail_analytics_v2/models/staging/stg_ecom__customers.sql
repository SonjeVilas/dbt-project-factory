/*
  Model: stg_ecom__customers
  Layer: Staging
  Grain: One row per customer account (customer_id)
  Description: Cleansed and standardized customer records with standardized name casing,
               lowercased emails, and null IDs filtered. Deduplicates records per customer_id
               by retaining the most recently created record.
*/

{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'customers']
) }}

with source as (
    select * from {{ source('ecom', 'customers') }}
),

filtered_and_deduped as (
    select
        customer_id,
        first_name,
        last_name,
        email,
        created_at
    from source
    where customer_id is not null
    qualify row_number() over (
        partition by customer_id
        order by created_at desc nulls last
    ) = 1
),

transformed as (
    select
        cast(customer_id as number(38,0)) as customer_id,
        coalesce(initcap(trim(first_name)), 'Unknown') as first_name,
        coalesce(initcap(trim(last_name)), 'Unknown') as last_name,
        lower(trim(email)) as email,
        cast(created_at as timestamp_ntz) as created_at,
        current_timestamp()::timestamp_ltz as standard_timestamp
    from filtered_and_deduped
)

select
    customer_id,
    first_name,
    last_name,
    email,
    created_at,
    standard_timestamp
from transformed