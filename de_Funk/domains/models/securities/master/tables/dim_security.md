---
type: domain-model-table
table: dim_security
extends: _base.finance.securities._dim_security
table_type: dimension
primary_key: [security_id]
unique_key: [ticker]

schema:
  - [security_id, integer, false, "PK", {derived: "ABS(HASH(ticker))"}]
  - [ticker, string, false, "Trading symbol"]
  - [security_name, string, true, "Display name"]
  - [asset_type, string, false, "Security type", {enum: [stocks, etf, option, future, warrant, unit, rights]}]
  - [exchange_code, string, true, "Primary exchange"]
  - [currency, string, true, "Trading currency", {derived: "'USD'"}]
  - [is_active, boolean, true, "Currently trading", {derived: "delisting_date IS NULL"}]
  - [ipo_date, date, true, "IPO or listing date", {format: date}]
  - [delisting_date, date, true, "Delisting date", {format: date}]

measures:
  - [security_count, count_distinct, security_id, "Number of securities", {format: "#,##0"}]
  - [active_securities, expression, "SUM(CASE WHEN is_active THEN 1 ELSE 0 END)", "Active securities", {format: "#,##0"}]
---

## Security Dimension

Master security dimension from LISTING_STATUS -- all US-listed tickers.
