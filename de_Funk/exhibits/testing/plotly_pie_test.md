---
title: Pie Chart Tests
models: [securities.stocks, corporate.entity]
filters:
  date: {source: temporal.date, type: date_range, default: {from: current_date - 365}}
---

# Pie Chart Tests

Tests for `plotly.pie` — pie, donut, legend toggle.

---

## Market Cap by Sector (Pie)

```de_funk
type: plotly.pie
data:
  labels: corporate.entity.sector
  values: securities.stocks.market_cap
  aggregation: sum
formatting:
  title: Market Cap by Sector
  height: 450
config:
  page_filters:
    ignore: ["*"]
```

---

## Market Cap by Sector (Donut)

```de_funk
type: plotly.pie
data:
  labels: corporate.entity.sector
  values: securities.stocks.market_cap
  aggregation: sum
formatting:
  title: Market Cap by Sector (Donut)
  hole: 0.45
  height: 450
config:
  page_filters:
    ignore: ["*"]
```

---

## Volume by Ticker (no legend)

```de_funk
type: plotly.pie
data:
  labels: corporate.entity.sector
  values: securities.stocks.volume
  aggregation: sum
  sort: {by: y0, order: desc}
formatting:
  title: Volume by Sector
  show_legend: true
  hole: 0.3
  height: 420
```
