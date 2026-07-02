---
type: domain-model-table
table: fact_splits
table_type: fact
extends: _base.finance.corporate_action._fact_splits
primary_key: [split_id]
partition_by: [effective_date_id]

schema:
  - [split_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', CAST(effective_date AS STRING))))"}]
  - [security_id, integer, false, "FK to dim_stock", {fk: dim_stock.security_id, derived: "ABS(HASH(ticker))"}]
  - [effective_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(REGEXP_REPLACE(CAST(effective_date AS STRING), '-', '') AS INT)"}]
  - [effective_date, date, false, "Split effective date", {format: date}]
  - [split_factor, double, false, "Split ratio (e.g., 4.0 for 4:1)", {format: decimal2}]

measures:
  - [split_count, count_distinct, split_id, "Number of splits", {format: "#,##0"}]
  - [avg_split_ratio, avg, split_factor, "Average split ratio", {format: "#,##0.00"}]
---

## Splits Fact Table

Stock split history from SPLITS endpoint.
