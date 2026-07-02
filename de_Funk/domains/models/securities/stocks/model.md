---
type: domain-model
model: securities.stocks
version: 3.1
description: "Stock equities with company linkage, technicals, dividends, and splits"
extends: [_base.finance.securities]
depends_on: [temporal, securities.master, corporate.entity]

sources_from: sources/
storage:
  format: delta
  silver:
    root: storage/silver/stocks/

graph:
  edges:
    - [prices_to_calendar, fact_stock_prices, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
    - [stock_to_security, dim_stock, securities.master.dim_security, [security_id=security_id], many_to_one, securities.master]
    - [stock_to_company, dim_stock, corporate.entity.dim_company, [company_id=company_id], many_to_one, corporate.entity, optional: true]
    - [stock_to_prices, dim_stock, fact_stock_prices, [security_id=security_id], one_to_many, stocks]
    - [prices_to_stock, fact_stock_prices, dim_stock, [security_id=security_id], many_to_one, null]
    - [dividends_to_stock, fact_dividends, dim_stock, [security_id=security_id], many_to_one, null]
    - [dividends_to_calendar, fact_dividends, temporal.dim_calendar, [ex_dividend_date_id=date_id], many_to_one, temporal]
    - [splits_to_stock, fact_splits, dim_stock, [security_id=security_id], many_to_one, null]
    - [splits_to_calendar, fact_splits, temporal.dim_calendar, [effective_date_id=date_id], many_to_one, temporal]
    - [technicals_to_stock, fact_stock_technicals, dim_stock, [security_id=security_id], many_to_one, null]
    - [stock_to_exchange, dim_stock, securities.master.dim_exchange, [exchange_id=exchange_id], many_to_one, securities.master]
  paths:
    company_to_dividends:
      steps:
        - {from: corporate.entity.dim_company, to: dim_stock, via: company_id}
        - {from: dim_stock, to: fact_dividends, via: security_id}
    prices_to_sector:
      steps:
        - {from: fact_stock_prices, to: dim_stock, via: security_id}

build:
  partitions: [date_id]
  sort_by: [security_id, date_id]
  optimize: true
  phases:
    1: { tables: [dim_stock] }
    2: { tables: [fact_stock_prices, fact_dividends, fact_splits] }
    3: { tables: [fact_stock_technicals] }  # depends on fact_stock_prices
  post_build:
    - id: enrich_market_cap
      type: computed_columns
      target: dim_stock
      merge_on: security_id
      columns:
        #  [id,                  domain.field or expression,                          options]
        - [shares_outstanding,   corporate.entity.shares_outstanding]                 # → dim_company via company_id
        - [latest_close,         securities.stocks.adjusted_close,                               {window: {fn: last_by, order_by: trade_date}}]
        - [market_cap,           "latest_close * shares_outstanding",                 {cast: long}]

measures:
  simple:
    - [stock_count, count_distinct, dim_stock.stock_id, "Number of stocks", {format: "#,##0"}]
    - [total_dividends, sum, fact_dividends.dividend_amount, "Total dividends paid", {format: "$#,##0.00"}]
    - [split_count, count_distinct, fact_splits.split_id, "Number of splits", {format: "#,##0"}]
  computed:
    - [avg_rsi, expression, "AVG(rsi_14)", "Average RSI", {format: "#,##0.00", source_table: fact_stock_technicals}]

metadata:
  domain: securities
  owner: data_engineering
status: active
---

## Stocks Model

Stock equities with company linkage, technical indicators, dividends, and splits.

### Build Order

```
temporal -> securities -> corporate.entity -> stocks
```

### Post-Build Enrichments

| Step | Target | What it computes |
|------|--------|-----------------|
| `enrich_market_cap` | `dim_stock` | `market_cap = latest_close × shares_outstanding` |

`enrich_market_cap` runs automatically after all phases complete. Join paths are resolved
from the model graph: `dim_stock → corporate.entity.dim_company` (via `company_id`) for
`shares_outstanding`; `fact_stock_prices → dim_stock` (via `security_id`) windowed to the
latest `trade_date` per stock for `latest_close`. `market_cap` is computed inline and
Delta MERGED into `dim_stock` on `security_id`.

Declared via `build.post_build` — no custom Python in this model.
