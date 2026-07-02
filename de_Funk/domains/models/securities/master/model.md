---
type: domain-model
model: securities.master
version: 3.0
description: "Master securities domain - unified dimension and prices for all tradable instruments"
extends: [_base.finance.securities]
depends_on: [temporal]

sources_from: sources/
storage:
  format: delta
  silver:
    root: storage/silver/securities/

graph:
  edges:
    - [prices_to_calendar, fact_security_prices, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
    - [prices_to_security, fact_security_prices, dim_security, [security_id=security_id], many_to_one, null]
    - [security_to_exchange, dim_security, dim_exchange, [exchange_id=exchange_id], many_to_one, null]
    - [security_to_stock, dim_security, securities.stocks.dim_stock, [security_id=security_id], one_to_one, securities.stocks, optional: true]
    - [security_to_company, dim_security, corporate.entity.dim_company, [security_id=company_id], many_to_one, corporate.entity, optional: true]
  paths:
    security_prices_by_date:
      steps:
        - {from: temporal.dim_calendar, to: fact_security_prices, via: date_id}
        - {from: fact_security_prices, to: dim_security, via: security_id}
    prices_to_company:
      steps:
        - {from: fact_security_prices, to: dim_security, via: security_id}
        - {from: dim_security, to: securities.stocks.dim_stock, via: security_id}
        - {from: securities.stocks.dim_stock, to: corporate.entity.dim_company, via: company_id}

build:
  partitions: [date_id]
  sort_by: [security_id, date_id]
  optimize: true
  phases:
    1: { tables: [dim_security, dim_exchange] }
    2: { tables: [fact_security_prices] }

measures:
  simple:
    - [security_count, count_distinct, dim_security.security_id, "Number of securities", {format: "#,##0"}]
    - [avg_close, avg, fact_security_prices.close, "Average closing price", {format: "$#,##0.00"}]
    - [total_volume, sum, fact_security_prices.volume, "Total trading volume", {format: "#,##0"}]
    - [trading_days, count_distinct, fact_security_prices.date_id, "Trading days", {format: "#,##0"}]
  computed:
    - [active_securities, expression, "SUM(CASE WHEN is_active THEN 1 ELSE 0 END)", "Active securities", {format: "#,##0"}]

metadata:
  domain: securities
  owner: data_engineering
status: active
---

## Securities Master Model

Unified dimension and prices for all tradable instruments (~12,499 US tickers).

### Architecture

```
dim_security (MASTER) <-- fact_security_prices (unified OHLCV)
     ^ security_id FK
     |
  dim_stock, dim_etf, dim_option, dim_future (downstream)
```
