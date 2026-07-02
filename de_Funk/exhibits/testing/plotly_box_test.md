---
title: Box / OHLCV Chart Tests
models: [securities.stocks]
filters:
  ticker: {source: securities.stocks.ticker, type: select, multi: true, default: [AAPL, MSFT, GOOGL, AMZN]}
  date:   {source: temporal.date, type: date_range, default: {from: current_date - 365}}
---

# Box / OHLCV Chart Tests

Tests for `plotly.box` — OHLCV box and generic statistical box/violin.

---

## OHLCV Price Distribution by Ticker

```de_funk
type: plotly.box
data:
  category: securities.stocks.ticker
  open:  securities.stocks.open
  high:  securities.stocks.high
  low:   securities.stocks.low
  close: securities.stocks.adjusted_close
formatting:
  title: OHLCV Price Distribution by Ticker
  height: 450
```

---

## Generic Box — Volume Distribution by Ticker

```de_funk
type: plotly.box
data:
  category: securities.stocks.ticker
  y: securities.stocks.volume
formatting:
  title: Volume Distribution by Ticker
  height: 380
```

---

## Violin — Volume Distribution

```de_funk
type: plotly.box
data:
  category: securities.stocks.ticker
  y: securities.stocks.volume
formatting:
  title: Volume Distribution (Violin)
  box_mode: violin
  height: 380
```

---

## OHLCV — Custom Date Range (isolated)

```de_funk
type: plotly.box
data:
  category: securities.stocks.ticker
  open:  securities.stocks.open
  high:  securities.stocks.high
  low:   securities.stocks.low
  close: securities.stocks.adjusted_close
formatting:
  title: 2024 OHLCV Ranges
config:
  page_filters:
    ignore: ["*"]
  filters:
    temporal.date: {from: "2024-01-01", to: "2024-12-31"}
```
