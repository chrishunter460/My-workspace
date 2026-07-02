---
title: Scatter Chart Tests
models: [securities.stocks, corporate.entity]
filters:
  sector: {source: corporate.entity.sector, type: select, multi: false}
  date:   {source: temporal.date, type: date_range, default: {from: current_date - 365}}
---

# Scatter Chart Tests

Tests for `plotly.scatter` — basic scatter, bubble chart, color dimension.

---

## Volume vs Price Scatter

```de_funk
type: plotly.scatter
data:
  x: securities.stocks.volume
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: Volume vs Close Price
  height: 450
  opacity: 0.6
```

---

## Bubble Chart — Revenue vs Margin (sized by market cap)

```de_funk
type: plotly.scatter
data:
  x: corporate.entity.revenue
  y: corporate.entity.profit_margin
  size: corporate.entity.market_cap
  color: corporate.entity.sector
formatting:
  title: Revenue vs Margin (size = market cap)
  height: 500
config:
  page_filters:
    ignore: ["*"]
```

---

## Scatter with Custom Marker Size

```de_funk
type: plotly.scatter
data:
  x: securities.stocks.volume
  y: securities.stocks.adjusted_close
formatting:
  title: All Points (small markers)
  opacity: 0.4
  marker_size: 4
  height: 380
```
