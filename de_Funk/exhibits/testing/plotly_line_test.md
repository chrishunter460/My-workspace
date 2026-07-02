---
title: Line Chart Tests
models: [securities.stocks, corporate.entity]
filters:
  ticker: {source: securities.stocks.ticker, type: select, multi: true, default: [AAPL, MSFT]}
  date:   {source: temporal.date, type: date_range, default: {from: current_date - 365}}
---

# Line Chart Tests

Tests for `plotly.line` — config_ref, filter inheritance, multi-series.

---

## Basic Line (inherits all filters)

```de_funk
type: plotly.line
data:
  x: temporal.date
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: Close Price (inherits ticker + date filters)
  height: 400
```

---

## Configurable Line (driven by controls)

```de_funk
type: plotly.line
data:
  x: temporal.date
formatting:
  title: Configurable Line
  height: 400
config:
  config_ref: controls
  page_filters:
    ignore: []
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
  title: AAPL + MSFT (isolated — exhibit-level filter only)
config:
  page_filters:
    ignore: ["*"]
  filters:
    securities.stocks.ticker: [AAPL, MSFT]
```

---

## Spline with Markers

```de_funk
type: plotly.line
data:
  x: temporal.date
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: Spline Close
  line_shape: spline
  markers: true
  height: 350
```
