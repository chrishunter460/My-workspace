---
title: Pivot Table Tests
models: [securities.stocks, corporate.entity]
filters:
  sector: {source: corporate.entity.sector, type: select, multi: false}
  date:   {source: temporal.date, type: date_range, default: {from: year_start}}
---

# Pivot Table Tests

Tests for `table.pivot` — by_dimension, by_measure, binning, windows, formatting.

---

## Standard Pivot — Sector × Year

```de_funk
type: table.pivot
data:
  rows: corporate.entity.sector
  cols: temporal.year
  measures:
    - [avg_close, securities.stocks.adjusted_close, avg, $, Avg Close]
  totals: {rows: true, cols: true}
formatting:
  title: Avg Close by Sector × Year
```

---

## by_measure Layout with Windows + Formatting

```de_funk
type: table.pivot
data:
  rows:   temporal.year
  cols:   [corporate.entity.sector]
  layout: by_measure
  measures:
    - [total_vol,  securities.stocks.volume,          sum,  number, Total Volume]
    - [avg_close,  securities.stocks.adjusted_close,  avg,  $,      Avg Close]
    - [yoy_vol,    {fn: pct_delta, of: total_vol},  null, "%", Volume YoY]
  windows:
    - [close_yoy, avg_close, pct_change, Close YoY]
  totals: {rows: true}
  sort:
    rows: {order: desc}
formatting:
  title: Annual Volume + Close (by_measure)
  format:
    total_vol: {format: number, color: "#e8f0fe"}
    avg_close: {format: $, color: "#ffffff"}
    close_yoy: {format: "%", color: "#e8f5e9"}
  defaults:
    window_color: "#fff8e1"
```

---

## Binned Pivot — Volume by Price Range Bucket

```de_funk
type: table.pivot
data:
  rows:   securities.stocks.adjusted_close
  cols:   []
  layout: by_measure
  buckets:
    securities.stocks.adjusted_close: {bins: [0, 50, 100, 200, 500, 1000]}
  measures:
    - [ticker_count, securities.stocks.ticker, count_distinct, number, Tickers]
    - [total_vol,    securities.stocks.volume, sum,            $K,     Total Volume]
  totals: {rows: true}
formatting:
  title: Tickers and Volume by Price Bucket
  format:
    ticker_count: {format: number}
    total_vol: {format: $K, color: "#e8f0fe"}
```

---

## Per-Measure Color Banding

```de_funk
type: table.pivot
data:
  rows: corporate.entity.sector
  cols: temporal.year
  measures:
    - [avg_close, securities.stocks.adjusted_close, avg, $, Avg Close]
    - [total_vol, securities.stocks.volume,         sum, number, Total Volume]
  totals: {rows: true, cols: true}
formatting:
  title: Sector Performance (color banding)
  format:
    avg_close: {format: $, color: "#e3f2fd"}
    total_vol: {format: number, color: "#fff8e1"}
  defaults:
    font_size: 13px
```

---

## by_measure — Measures as Spanners (default 2D)

```de_funk
type: table.pivot
data:
  rows: temporal.year
  cols: corporate.entity.sector
  layout: by_measure
  measures:
    - [total_vol, securities.stocks.volume, sum, number, Total Volume]
    - [avg_close, securities.stocks.adjusted_close, avg, $, Avg Close]
  windows:
    - [vol_yoy, total_vol, pct_change, Volume YoY]
  totals: {rows: true}
formatting:
  title: Sector Volume + Close (grouped by measure)
  format:
    vol_yoy: {format: "%", color: "#e8f5e9"}
```

---

## by_column — Dimensions as Spanners

```de_funk
type: table.pivot
data:
  rows: temporal.year
  cols: corporate.entity.sector
  layout: by_column
  measures:
    - [total_vol, securities.stocks.volume, sum, number, Total Volume]
    - [avg_close, securities.stocks.adjusted_close, avg, $, Avg Close]
  totals: {rows: true}
formatting:
  title: Sector Volume + Close (grouped by sector)
```

---

## Pivot with Exhibit-Level Filter

```de_funk
type: table.pivot
data:
  rows: corporate.entity.sector
  cols: temporal.year
  measures:
    - [avg_close, securities.stocks.adjusted_close, avg, $, Avg Close]
  totals: {rows: true}
config:
  page_filters:
    ignore: ["*"]
  filters:
    temporal.year: [2023, 2024]
formatting:
  title: 2023–2024 Only (ignores page filters)
```

---

## Format Short Form (format code only, no color)

```de_funk
type: table.pivot
data:
  rows: corporate.entity.sector
  measures:
    - [avg_close, securities.stocks.adjusted_close, avg, null, Avg Close]
    - [total_vol, securities.stocks.volume,         sum, null, Total Volume]
formatting:
  title: Short-form format override
  format:
    avg_close: $
    total_vol: number
```
