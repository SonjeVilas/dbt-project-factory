# retail_analytics_v2

## Project Overview
`retail_analytics_v2` is a production-grade dbt analytics engineering project built on Snowflake (`ECOM_DB`). It establishes a robust, reliable data pipeline that transforms raw e-commerce operational data into clean, conformed dimensional and factual models optimized for executive dashboarding, marketing analytics, sales operations, and customer 360 analysis.

## Prerequisites
- **Database:** Snowflake (`ECOM_DB`)
- **Orchestration / Tooling:** dbt-core (v1.8+ recommended) with the `dbt-snowflake` adapter.
- **Source Schema:** `RAW` containing `CUSTOMERS`, `ORDERS`, and `ORDER_ITEMS`.

## Setup Instructions
1. Clone the repository and navigate to the project root:
   ```bash
   cd retail_analytics_v2
   ```
2. Configure your `profiles.yml` (refer to `profiles.yml.example` for environment variable bindings):
   ```bash
   cp profiles.yml.example ~/.dbt/profiles.yml
   ```
3. Install project dependencies:
   ```bash
   dbt deps
   ```
4. Validate your connection and configuration:
   ```bash
   dbt debug
   ```
5. Run the transformation pipeline:
   ```bash
   dbt run
   ```
6. Execute automated data quality tests:
   ```bash
   dbt test
   ```

## Model Layers

### 1. Staging Layer (`models/staging/`)
- **Materialization:** View
- **Schema:** `staging`
- **Purpose:** 1:1 reflections of raw source tables. Handles data type casting, null filtering on primary keys, string sanitization (trimming, title-casing names, lowercasing emails), status normalization, and deduplication.
- **Models:** `stg_ecom__customers`, `stg_ecom__orders`, `stg_ecom__order_items`.

### 2. Intermediate Layer (`models/intermediate/`)
- **Materialization:** Ephemeral
- **Schema:** `intermediate` (compiled inline as CTEs)
- **Purpose:** Business logic aggregation and reshaping. Computes customer-level lifetime order metrics (total orders, total spend, first and most recent order dates).
- **Models:** `int_customers__aggregated_orders`.

### 3. Marts Layer (`models/marts/`)
- **Materialization:** Table (`dim_customers`) / Incremental Merge (`fct_orders`)
- **Schema:** `marts`
- **Purpose:** Business-facing star schema models. `dim_customers` serves as the conformed customer dimension with lifetime aggregates; `fct_orders` acts as the core transactional fact table enriched with customer details and completion flags.
- **Models:** `dim_customers`, `fct_orders`.

## High-Level DAG Summary
```
source('ecom', 'customers') ──> stg_ecom__customers ──┐
                                                   ├──> dim_customers
int_customers__aggregated_orders ──────────────────┘
  ▲
  │
source('ecom', 'orders')     ──> stg_ecom__orders     ──┬
                                                   ├──> fct_orders
source('ecom', 'customers') ──> stg_ecom__customers ──┘

source('ecom', 'order_items') ──> stg_ecom__order_items
```

## Contribution Guidelines
- Adhere to the established naming conventions (`stg_`, `int_`, `dim_`, `fct_`).
- Every new column must be documented in the corresponding `schema.yml` file with appropriate tests (`unique`, `not_null`, `relationships`, `accepted_values`).
- Ensure all models pass `dbt test` successfully prior to submitting pull requests.