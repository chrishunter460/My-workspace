---
title: Heatmap Tests
models: [securities.stocks, corporate.entity]
filters:
  ticker: {source: securities.stocks.ticker, type: select, multi: true, default: [AAPL, MSFT, GOOGL, AMZN, NVDA]}
---

# Heatmap Tests

Tests for `plotly.heatmap` — monthly matrix, color scales, show_values.

---

## Monthly Avg Close Heatmap (Year × Month)

```de_funk
type: plotly.heatmap
data:
  x: temporal.month
  y: temporal.year
  z: securities.stocks.adjusted_close
  aggregation: avg
formatting:
  title: Avg Close by Year × Month
  color_palette: blues
  height: 400
```

---

## Volume Heatmap with Values

```de_funk
type: plotly.heatmap
data:
  x: temporal.month
  y: securities.stocks.ticker
  z: securities.stocks.volume
  aggregation: sum
formatting:
  title: Monthly Volume by Ticker
  color_palette: greens
  show_values: true
  height: 450
```

---

## Red-Blue Color Scale (diverging)

```de_funk
type: plotly.heatmap
data:
  x: temporal.year
  y: securities.stocks.ticker
  z: securities.stocks.adjusted_close
  aggregation: avg
formatting:
  title: Avg Close Heatmap (diverging)
  color_palette: rdbu
  reverse_scale: false
  height: 400
```
