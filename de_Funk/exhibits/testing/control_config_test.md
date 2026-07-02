---
title: Control Config Tests
models: [securities.stocks, corporate.entity]
filters:
  ticker: {source: securities.stocks.ticker, type: select, multi: true, default: [AAPL, MSFT]}
  date:   {source: temporal.date, type: date_range, default: {from: current_date - 90}}
controls:
  - id: controls
    dimensions: [securities.stocks.ticker, corporate.entity.sector]
    measures:   [securities.stocks.adjusted_close, securities.stocks.volume, securities.stocks.high, securities.stocks.low]
    sort_order: [asc, desc]
  - id: detail-controls
    sort_order: [asc, desc]
---

# Control Config Tests

Controls are defined in frontmatter and rendered in the sidebar.
Exhibits with `config_ref:` react to sidebar control changes.

---

## Chart Driven by Controls

```de_funk
type: plotly.line
data:
  x: temporal.date
formatting:
  title: Driven by Chart Controls
  height: 420
config:
  config_ref: controls
```

---

## Bar Driven by Same Controls

```de_funk
type: plotly.bar
data:
  x: temporal.year
formatting:
  title: Yearly Bars (same controls)
  height: 350
config:
  config_ref: controls
```

---

## Pivot Driven by Detail Controls

```de_funk
type: table.pivot
data:
  rows: corporate.entity.sector
  cols: temporal.year
  measures:
    - [avg_close, securities.stocks.adjusted_close, avg, $, Avg Close]
  totals: {rows: true, cols: true}
formatting:
  title: Pivot (driven by detail-controls)
config:
  config_ref: detail-controls
```
