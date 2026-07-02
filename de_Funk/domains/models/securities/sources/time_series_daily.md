---
type: domain-model-source
source: time_series_daily
extends: _base.finance.securities
maps_to: fact_security_prices
from: bronze.alpha_vantage_time_series_daily_adjusted
domain_source: "'alpha_vantage'"

aliases:
  - [legal_entity_id, "null"]
  - [security_id, "ABS(HASH(ticker))"]
  - [price_id, "ABS(HASH(CONCAT(ticker, '_', trade_date)))"]
  - [ticker, ticker]
  - [trade_date, trade_date]
  - [date_id, "CAST(REGEXP_REPLACE(CAST(trade_date AS STRING), '-', '') AS INT)"]
  - [open, open]
  - [high, high]
  - [low, low]
  - [close, close]
  - [volume, volume]
  - [adjusted_close, adjusted_close]
---

## Time Series Daily
Daily OHLCV price data with adjusted close and split coefficients for all securities.
