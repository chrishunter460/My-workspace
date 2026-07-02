---
title: Financial Statements & Earnings
models: [corporate.finance, corporate.entity]
filters:
  sector: {source: corporate.entity.sector, type: select, multi: false}
  ticker: {source: corporate.entity.ticker, type: select, multi: true, default: [AAPL, MSFT, GOOGL], context_filters: true}
---

# Financial Statements & Earnings

Pivot tables for earnings reports and financial data with declarative formatting.

> **Pipeline rebuilt**: `fact_financial_statements` now has full FK coverage — `account_id`, `company_id`, `account_code`, `period_end_date_id` all populated. 86 GAAP accounts seeded in `dim_financial_account` covering all 79 Bronze line items across income statement, balance sheet, and cash flow.

---

## Earnings — EPS Summary

```de_funk
type: table.pivot
data:
  rows: corporate.entity.sector
  measures:
    - [avg_eps, corporate.finance.reported_eps, avg, $2, Reported EPS]
    - [avg_est, corporate.finance.estimated_eps, avg, $2, Estimated EPS]
    - [avg_surprise, corporate.finance.surprise_percentage, avg, "%", Surprise %]
    - [report_count, corporate.finance.earnings_id, count_distinct, number, Reports]
formatting:
  title: Earnings Summary by Sector
  format:
    avg_eps: {format: $2, color: "#e3f2fd"}
    avg_est: {format: $2, color: "#e8f5e9"}
    avg_surprise: {format: "%", color: "#fff8e1"}
    report_count: number
```

---

## Earnings — EPS by Sector

```de_funk
type: table.pivot
data:
  rows: corporate.entity.sector
  measures:
    - [avg_eps, corporate.finance.reported_eps, avg, $2, Avg EPS]
    - [avg_surprise, corporate.finance.surprise_percentage, avg, "%", Avg Surprise %]
    - [report_count, corporate.finance.earnings_id, count_distinct, number, Reports]
formatting:
  title: Earnings by Sector
  format:
    avg_eps: {format: $2, color: "#e3f2fd"}
    avg_surprise: {format: "%", color: "#e8f5e9"}
    report_count: number
```

---

## Earnings — EPS vs Estimates by Sector

```de_funk
type: table.pivot
data:
  rows: corporate.entity.sector
  layout: by_measure
  measures:
    - [avg_eps, corporate.finance.reported_eps, avg, $2, Reported]
    - [avg_est, corporate.finance.estimated_eps, avg, $2, Estimated]
    - [avg_surprise, corporate.finance.surprise_percentage, avg, "%", Surprise %]
formatting:
  title: Reported vs Estimated EPS by Sector
  format:
    avg_eps: {format: $2, color: "#e3f2fd"}
    avg_est: {format: $2, color: "#e8f5e9"}
    avg_surprise: {format: "%", color: "#fff8e1"}
```

---

## Company Fundamentals — Sector Summary

```de_funk
type: table.pivot
data:
  rows: corporate.entity.sector
  measures:
    - [company_count, corporate.entity.company_id, count_distinct, number, Companies]
    - [avg_eps, corporate.entity.eps, avg, $2, Avg EPS]
    - [avg_pe, corporate.entity.pe_ratio, avg, decimal2, Avg P/E]
    - [avg_margin, corporate.entity.profit_margin, avg, "%", Avg Margin]
    - [total_rev, corporate.entity.revenue_ttm, sum, $B, Total Revenue]
formatting:
  title: Sector Fundamentals
  format:
    avg_eps: {format: $2, color: "#e3f2fd"}
    avg_pe: {format: decimal2, color: "#fff3e0"}
    avg_margin: {format: "%", color: "#e8f5e9"}
    total_rev: {format: $B, color: "#f3e5f5"}
```

---

## Stock Price + EPS Side-by-Side

```de_funk
type: table.pivot
data:
  rows: corporate.entity.sector
  measures:
    - [avg_close, securities.stocks.adjusted_close, avg, $, Avg Close]
    - [avg_eps, corporate.entity.eps, avg, $2, Avg EPS]
    - [avg_pe, corporate.entity.pe_ratio, avg, decimal2, Avg P/E]
formatting:
  title: Price vs Earnings by Sector
  format:
    avg_close: {format: $, color: "#e3f2fd"}
    avg_eps: {format: $2, color: "#e8f5e9"}
    avg_pe: {format: decimal2, color: "#fff8e1"}
```

---

## KPI Cards — Financial Metrics

```de_funk
type: cards.metric
data:
  metrics:
    - [company_count, corporate.entity.company_id, count_distinct, number, Companies]
    - [avg_eps, corporate.finance.reported_eps, avg, $2, Avg EPS]
    - [avg_surprise, corporate.finance.surprise_percentage, avg, "%", Avg Earnings Surprise]
    - [avg_pe, corporate.entity.pe_ratio, avg, decimal2, Avg P/E Ratio]
formatting:
  format:
    avg_eps: $2
    avg_pe: decimal2
```
