---
type: domain-model-source
source: stock_listing
extends: _base.finance.securities
maps_to: dim_stock
from: bronze.alpha_vantage_listing_status
domain_source: "'alpha_vantage'"
filter: "asset_type = 'stocks'"

aliases:
  - [stock_id, "ABS(HASH(CONCAT('STOCK_', ticker)))"]
  - [security_id, "ABS(HASH(ticker))"]
  - [company_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [ticker, ticker]
  - [security_name, security_name]
  - [asset_type, asset_type]
  - [exchange_code, exchange_code]
  - [exchange_id, "ABS(HASH(exchange_code))"]
  - [is_active, "delisting_date IS NULL"]
  - [ipo_date, ipo_date]
  - [delisting_date, delisting_date]
---

## Stock Listing
Stock equities filtered from listing_status (asset_type = 'stocks'). Maps to dim_stock for the stocks domain model.
