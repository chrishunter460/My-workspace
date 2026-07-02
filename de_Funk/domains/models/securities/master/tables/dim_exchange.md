---
type: domain-model-table
table: dim_exchange
extends: _base.finance.securities._dim_exchange
table_type: dimension
primary_key: [exchange_id]
unique_key: [exchange_code]

schema:
  - [exchange_id, integer, false, "PK", {derived: "ABS(HASH(exchange_code))"}]
  - [exchange_code, string, false, "MIC code (NYSE, NASDAQ, etc.)", {unique: true}]
  - [exchange_name, string, true, "Full exchange name"]
  - [country, string, true, "Country"]
  - [timezone, string, true, "Trading timezone"]
  - [is_active, boolean, true, "Currently operating", {default: true}]

measures:
  - [exchange_count, count_distinct, exchange_id, "Number of exchanges", {format: "#,##0"}]

seed:
  - {exchange_code: "NYSE", exchange_name: "New York Stock Exchange", country: "US", timezone: "America/New_York"}
  - {exchange_code: "NASDAQ", exchange_name: "NASDAQ Stock Market", country: "US", timezone: "America/New_York"}
  - {exchange_code: "AMEX", exchange_name: "NYSE American", country: "US", timezone: "America/New_York"}
  - {exchange_code: "BATS", exchange_name: "Cboe BZX Exchange", country: "US", timezone: "America/New_York"}
  - {exchange_code: "ARCA", exchange_name: "NYSE Arca", country: "US", timezone: "America/New_York"}
---

## Exchange Dimension

Stock exchanges where securities are listed. Shared reference dimension for all security types (stocks, ETFs, options, futures). Populated from distinct `exchange_code` values on `dim_security`, supplemented by seed data for display names and metadata.
