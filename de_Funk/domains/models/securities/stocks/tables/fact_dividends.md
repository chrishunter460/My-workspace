---
type: domain-model-table
table: fact_dividends
table_type: fact
extends: _base.finance.corporate_action._fact_dividends
primary_key: [dividend_id]
partition_by: [ex_dividend_date_id]

schema:
  - [dividend_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', CAST(ex_dividend_date AS STRING))))"}]
  - [security_id, integer, false, "FK to dim_stock", {fk: dim_stock.security_id, derived: "ABS(HASH(ticker))"}]
  - [ex_dividend_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(REGEXP_REPLACE(CAST(ex_dividend_date AS STRING), '-', '') AS INT)"}]
  - [payment_date_id, integer, true, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [dividend_amount, double, false, "Dividend per share", {format: $}]
  - [record_date, date, true, "Record date", {format: date}]
  - [payment_date, date, true, "Payment date", {format: date}]
  - [declaration_date, date, true, "Declaration date", {format: date}]
  - [dividend_type, string, true, "regular, special, stock"]

measures:
  - [total_dividends, sum, dividend_amount, "Total dividends", {format: "$#,##0.00"}]
  - [avg_dividend, avg, dividend_amount, "Average dividend", {format: "$#,##0.00"}]
  - [dividend_count, count_distinct, dividend_id, "Dividend events", {format: "#,##0"}]
---

## Dividends Fact Table

Dividend distribution history from DIVIDENDS endpoint.
