---
type: domain-model-source
source: listing_status
extends: _base.finance.securities
maps_to: dim_security
from: bronze.alpha_vantage_listing_status
domain_source: "'alpha_vantage'"

aliases:
  - [security_id, "ABS(HASH(ticker))"]
  - [ticker, ticker]
  - [security_name, security_name]
  - [asset_type, asset_type]
  - [exchange_code, exchange_code]
  - [currency, "'USD'"]
  - [is_active, "delisting_date IS NULL"]
  - [ipo_date, ipo_date]
  - [delisting_date, delisting_date]
---

## Listing Status
All active and delisted US securities (~12,499 tickers). Primary source for the securities master dimension.
