---
title: Metric Cards Tests
models: [securities.stocks, corporate.entity]
filters:
  ticker: {source: securities.stocks.ticker, type: select, multi: true, default: [AAPL, MSFT, GOOGL]}
  date:   {source: temporal.date, type: date_range, default: {from: current_date - 90}}
---

# Metric Cards Tests

Tests for `cards.metric` — tuple syntax, inline comments, omitted labels, layout.

---

## Stock Summary KPIs

```de_funk
type: cards.metric
data:
  metrics:
    - [avg_close,  securities.stocks.adjusted_close,  avg,  $,      Avg Close]
    - [total_vol,  securities.stocks.volume,          sum,  number, Total Volume]
    - [high_52w,   securities.stocks.high,            max,  $,      52w High]
    - [low_52w,    securities.stocks.low,             min,  $,      52w Low]
formatting:
  title: Price Summary
```

---

## Inline Comments (some metrics commented out)

```de_funk
type: cards.metric
data:
  metrics:
    - [avg_close,  securities.stocks.adjusted_close,  avg,  $,      Avg Close]    # avg close price
    - [total_vol,  securities.stocks.volume,          sum,  number, Total Volume]  # shares traded
    # - [high_52w,  securities.stocks.high,  max,  $,  52w High]                   # commented out
    - [low_52w,    securities.stocks.low,             min,  $,      52w Low]
formatting:
  title: Commented-out Metric
```

---

## Omitted Labels (key → display label)

```de_funk
type: cards.metric
data:
  metrics:
    - [avg_close,   securities.stocks.adjusted_close, avg, $]
    - [total_volume, securities.stocks.volume,        sum, number]
    - [high_52w,     securities.stocks.high,          max, $]
formatting:
  title: Keys as Labels (underscores become spaces)
```

---

## Isolated — Ignores All Page Filters

```de_funk
type: cards.metric
data:
  metrics:
    - [aapl_close,  securities.stocks.adjusted_close,  avg,  $,  AAPL Avg Close]
    - [aapl_vol,    securities.stocks.volume,          sum,  number, AAPL Volume]
formatting:
  title: AAPL Only (isolated)
config:
  page_filters:
    ignore: ["*"]
  filters:
    securities.stocks.ticker: [AAPL]
```

---

## 2-Column Layout

```de_funk
type: cards.metric
data:
  metrics:
    - [avg_close,  securities.stocks.adjusted_close,  avg,  $,      Avg Close]
    - [total_vol,  securities.stocks.volume,          sum,  number, Total Volume]
    - [high_52w,   securities.stocks.high,            max,  $,      52w High]
    - [low_52w,    securities.stocks.low,             min,  $,      52w Low]
    - [ticker_ct,  securities.stocks.ticker,          count_distinct, number, Tickers]
    - [avg_vol,    securities.stocks.volume,          avg,  $K,     Avg Volume]
formatting:
  title: 2-Column Layout
  columns: 2
```
