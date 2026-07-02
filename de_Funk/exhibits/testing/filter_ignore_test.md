---
title: Filter Inheritance Tests
models: [securities.stocks, corporate.entity]
filters:
  ticker:  {source: securities.stocks.ticker,  type: select, multi: true,  default: [AAPL, MSFT, GOOGL], context_filters: true}
  sector:  {source: corporate.entity.sector, type: select, multi: false}
  date:    {source: temporal.date, type: date_range, default: {from: current_date - 90}}
---

# Filter Inheritance Tests

Tests for `page_filters.ignore` — partial ignore, full ignore, exhibit-level filters.

---

## Inherits All (default)

```de_funk
type: plotly.line
data:
  x: temporal.date
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: Inherits ticker + sector + date filters
```

---

## Ignores Sector Filter Only

```de_funk
type: plotly.line
data:
  x: temporal.date
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: Ignores sector — still filtered by ticker + date
config:
  page_filters:
    ignore: [sector]
```

---

## Ignores Ticker + Sector (keeps date)

```de_funk
type: plotly.line
data:
  x: temporal.date
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: Only date filter applied
config:
  page_filters:
    ignore: [ticker, sector]
```

---

## Fully Isolated (ignores all page filters)

```de_funk
type: plotly.line
data:
  x: temporal.date
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: TSLA only — ignores all page filters
config:
  page_filters:
    ignore: ["*"]
  filters:
    securities.stocks.ticker: [TSLA]
    temporal.date: {from: "2024-01-01"}
```

---

## Exhibit-Level Filter Stacks on Top of Page Filters

```de_funk
type: plotly.line
data:
  x: temporal.date
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: Page filters + additional NVDA filter
config:
  filters:
    securities.stocks.ticker: [NVDA]
```
