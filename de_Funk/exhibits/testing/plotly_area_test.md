---
title: Area Chart Tests
models: [securities.stocks, corporate.entity]
filters:
  ticker: {source: securities.stocks.ticker, type: select, multi: true, default: [AAPL, MSFT, GOOGL]}
  date:   {source: temporal.date, type: date_range, default: {from: current_date - 365}}
---

# Area Chart Tests

Tests for `plotly.area` — fill to zero, stacked area, opacity.

---

## Single Area (fill to zero)

```de_funk
type: plotly.area
data:
  x: temporal.date
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: Close Price (filled area)
  height: 420
  fill_mode: tozeroy
  opacity: 0.4
```

---

## Stacked Area by Sector (tonexty)

```de_funk
type: plotly.area
data:
  x: temporal.year
  y: securities.stocks.volume
  group_by: corporate.entity.sector
  aggregation: sum
formatting:
  title: Volume by Sector (Stacked)
  fill_mode: tonexty
  height: 450
config:
  page_filters:
    ignore: ["*"]
```

---

## Area with High Opacity

```de_funk
type: plotly.area
data:
  x: temporal.date
  y: securities.stocks.volume
  group_by: securities.stocks.ticker
  aggregation: sum
formatting:
  title: Volume Area (high opacity)
  opacity: 0.7
  height: 350
```
