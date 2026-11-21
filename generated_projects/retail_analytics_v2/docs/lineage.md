# Data Lineage & Transformation Narrative

This document outlines the data flow and transformation logic within **retail_analytics_v2**, tracing data from raw source ingestion in Snowflake through staging, intermediate rollups, and final analytical marts.

---

## 1. Raw Source Layer (`ECOM_DB.RAW`)
The pipeline ingests operational data from three core source tables:
- **`CUSTOMERS`**: Account profile registrations.
- **`ORDERS`**: Transaction header records.
- **`ORDER_ITEMS`**: Line-item granularity products per order.

---

## 2. Staging Layer (`staging`)
The staging layer cleanses and standardizes raw data on a 1:1 table basis without performing business entity joins or cross-table aggregations. Materialized as lightweight **views**:
- **`stg_ecom__customers`**: Casts identifiers, trims and title-cases first and last names via `INITCAP(TRIM())`, lowercases emails, and filters out records missing a `customer_id`. Deduplicates based on creation timestamp.
- **`stg_ecom__orders`**: Casts transaction dates and amounts, normalizes status values to uppercase (`PENDING`, `COMPLETED`, `CANCELLED`), and rejects unassigned order IDs.
- **`stg_ecom__order_items`**: Typecasts keys and computes extended line-item totals (`quantity * unit_price`).

---

## 3. Intermediate Layer (`intermediate`)
Materialized as **ephemeral** models (compiled inline as CTEs), this layer bridges staging outputs to dimensional requirements:
- **`int_customers__aggregated_orders`**: Groups staged orders by `customer_id` to compute lifetime metrics: `total_orders`, `total_spend`, `first_order_date`, and `most_recent_order_date`.

---

## 4. Marts Layer (`marts`)
The consumption layer provides high-performance, conformed star-schema models for analytics and downstream systems:
- **`dim_customers`**: Materialized as a **table**. Performs a left join between `stg_ecom__customers` and `int_customers__aggregated_orders`. This guarantees that all customers—including those with zero orders—are retained with default spend and order counts.
- **`fct_orders`**: Materialized incrementally using a **merge strategy** on `order_id`. Captures order transactions, enriches them with customer attributes, and derives an `is_completed` boolean flag based on order status.

---

## Summary of Data Quality & Integrity
Automated tests validate each layer:
- Primary keys are tested for `unique` and `not_null` constraints.
- Foreign keys enforce referential integrity across staging and mart relationships.
- Status columns are restricted via `accepted_values` tests to prevent invalid state corruption.