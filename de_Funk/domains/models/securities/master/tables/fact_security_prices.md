---
type: domain-model-table
table: fact_security_prices
extends: _base.finance.securities._fact_prices
table_type: fact
primary_key: [price_id]
partition_by: [date_id]

schema:
  - [price_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', CAST(trade_date AS STRING))))"}]
  - [security_id, integer, false, "FK to dim_security", {fk: dim_security.security_id, derived: "ABS(HASH(ticker))"}]
  - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(REGEXP_REPLACE(CAST(trade_date AS STRING), '-', '') AS INT)"}]
  - [ticker, string, false, "Trading symbol"]
  - [trade_date, date, false, "Trading date", {format: date}]
  - [asset_type, string, false, "Asset type for partition pruning", {derived: "'stocks'"}]
  - [open, double, true, "Opening price", {format: $}]
  - [high, double, true, "High price", {format: $}]
  - [low, double, true, "Low price", {format: $}]
  - [close, double, false, "Closing price", {format: $}]
  - [volume, long, true, "Trading volume", {format: number}]
  - [adjusted_close, double, true, "Split/dividend adjusted close", {format: $}]

measures:
  - [avg_close, avg, close, "Average closing price", {format: "$#,##0.00"}]
  - [total_volume, sum, volume, "Total trading volume", {format: "#,##0"}]
  - [max_high, max, high, "Maximum high price", {format: "$#,##0.00"}]
  - [min_low, min, low, "Minimum low price", {format: "$#,##0.00"}]
  - [price_range, expression, "AVG(high - low)", "Average price range", {format: "$#,##0.00"}]
  - [trading_days, count_distinct, date_id, "Trading days", {format: "#,##0"}]
---

## Security Prices Fact Table

Unified OHLCV price data for all securities.
