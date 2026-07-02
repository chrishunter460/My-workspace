---
title: Data Table Tests
models: [securities.stocks]
filters:
  ticker: {source: securities.stocks.ticker, type: select, multi: true, default: [AAPL, MSFT]}
  date:   {source: temporal.date, type: date_range, default: {from: current_date - 30}}
---

# Data Table Tests

Tests for `table.data` — column tuples, format overrides, sort, download.

---

## OHLCV Table (sorted by date desc)

```de_funk
type: table.data
data:
  columns:
    - [ticker,  securities.stocks.ticker]
    - [date,    temporal.date,          null, date]
    - [open,    securities.stocks.open,            null, $]
    - [high,    securities.stocks.high,            null, $]
    - [low,     securities.stocks.low,             null, $]
    - [close,   securities.stocks.adjusted_close,  null, $,    Close]
    - [volume,  securities.stocks.volume,          null, $K,   Volume]
  sort_by:    temporal.date
  sort_order: desc
formatting:
  title: OHLCV Data
  page_size: 25
  download: true
```

---

## Minimal Columns (uses model format defaults)

```de_funk
type: table.data
data:
  columns:
    - [ticker, securities.stocks.ticker]
    - [date,   temporal.date]
    - [close,  securities.stocks.adjusted_close]
    - [volume, securities.stocks.volume]
formatting:
  title: Minimal — uses model defaults
  page_size: 20
```

---

## High Volume Days (isolated filter)

```de_funk
type: table.data
data:
  columns:
    - [ticker, securities.stocks.ticker]
    - [date,   temporal.date,          null, date]
    - [close,  securities.stocks.adjusted_close,  null, $]
    - [volume, securities.stocks.volume,          null, number]
  sort_by:    securities.stocks.volume
  sort_order: desc
formatting:
  title: Top Volume Days (all tickers, last 30 days)
  page_size: 50
  download:  true
config:
  page_filters:
    ignore: [ticker]
```
