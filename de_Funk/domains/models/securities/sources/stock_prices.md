---
type: domain-model-source
source: stock_prices
extends: _base.finance.securities
maps_to: fact_stock_prices
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

## Stock Prices
Stock-specific daily OHLCV price data mapping to fact_stock_prices table.
