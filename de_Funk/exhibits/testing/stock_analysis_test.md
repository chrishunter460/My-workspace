---
title: Stock Price Analysis
models:
  - securities.stocks
  - corporate.entity
filters:
  ticker:
    source: securities.stocks.ticker
    type: select
    multi: true
    default:
      - AAPL
      - MSFT
      - GOOGL
    sort_by_measure: securities.stocks.market_cap
    context_filters: true
  sector:
    source: corporate.entity.sector
    type: select
    multi: false
  date:
    source: temporal.date
    type: date_range
    default:
      from: current_date - 500
controls:
  - id: stock-charts
    dimensions:
      - securities.stocks.ticker
      - corporate.entity.sector
      - corporate.entity.industry
    measures:
      - - securities.stocks.adjusted_close
        - $2
        - avg
      - - securities.stocks.volume
        - number
        - sum
      - - securities.stocks.high
        - $2
        - max
      - - securities.stocks.low
        - $2
        - min
      - - securities.stocks.open
        - $2
        - avg
  - id: stock-pivot
    dimensions:
      - corporate.entity.sector
      - corporate.entity.industry
      - securities.stocks.ticker
    cols:
      - temporal.year
      - temporal.quarter
      - corporate.entity.sector
    measures:
      - - securities.stocks.adjusted_close
        - $2
        - avg
      - - securities.stocks.volume
        - number
        - sum
      - - securities.stocks.high
        - $2
        - max
      - - securities.stocks.low
        - $2
        - min
      - - securities.stocks.market_cap
        - $B
        - avg
    sort_order:
      - asc
      - desc
---

# Stock Price Analysis

Use the sidebar controls to configure dimensions, columns, and measures for each exhibit.

---

## Key Metrics

```de_funk
type: cards.metric
data:
  metrics:
    - [avg_close,  securities.stocks.adjusted_close,  avg,  "$2",    Avg Close]
    - [total_vol,  securities.stocks.volume,           sum,  number,  Total Volume]
    - [high_52w,   securities.stocks.high,             max,  "$2",    52w High]
    - [low_52w,    securities.stocks.low,              min,  "$2",    52w Low]
```

---

## Price Chart

```de_funk
type: plotly.line
data:
  x: temporal.date
formatting:
  title: Price Chart
  height: 420
  show_legend: true
config:
  config_ref: stock-charts
  page_filters:
    ignore: [sector]
```

---

## Sector × Year Pivot

```de_funk
type: table.pivot
data:
  totals: {rows: true, cols: true}
formatting:
  title: Stock Pivot
config:
  config_ref: stock-pivot
```

---

## Companies by Sector

```de_funk
type: plotly.bar
data:
  x: corporate.entity.sector
  y: securities.stocks.ticker
  aggregation: count_distinct
formatting:
  title: Number of Companies by Sector
  height: 350
config:
  page_filters:
    ignore: ["*"]
```

---

## Price Distribution

```de_funk
type: plotly.box
data:
  category: temporal.date
  open:  securities.stocks.open
  high:  securities.stocks.high
  low:   securities.stocks.low
  close: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: OHLC Distribution by Sector over Time
  height: 420
```

---

## Data Table

```de_funk
type: table.data
data:
  columns:
    - [date,   temporal.date]
    - [ticker, securities.stocks.ticker]
    - [close,  securities.stocks.adjusted_close, null, "$2",    Close]
    - [open,   securities.stocks.open,           null, "$2",    Open]
    - [high,   securities.stocks.high,           null, "$2",    High]
    - [low,    securities.stocks.low,            null, "$2",    Low]
    - [volume, securities.stocks.volume,         null, number, Volume]
  sort_by: temporal.date
  sort_order: desc
formatting:
  page_size: 20
  download: true
```
