---
type: domain-model-table
table: fact_feature_set
table_type: fact
primary_key: [feature_id]

schema:
  - [feature_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', CAST(date_id AS STRING))))"}]
  - [security_id, integer, false, "FK to dim_stock"]
  - [ticker, string, false, "Stock ticker"]
  - [date_id, integer, false, "Trading date"]
  - [close, double, true, "Closing price"]
  - [volume, long, true, "Trading volume"]
  - [avg_volume_30d, double, true, "30-day average volume", {indicator: {fn: moving_avg, window: 30, source: volume}}]
  - [pe_ratio, double, true, "Price to earnings ratio"]
  - [revenue_growth, double, true, "YoY revenue growth rate"]
  - [debt_equity_ratio, double, true, "Total debt / total equity"]
  - [price_to_book, double, true, "Price / book value per share"]
  - [next_30d_return, double, true, "Forward 30-day return (label)", {derived: "LEAD(close, 30) OVER (PARTITION BY security_id ORDER BY date_id) / close - 1"}]
---

## Feature Set

Joined stock prices with company financial ratios. Each row is one stock on one trading day
with both price features and fundamental features from the latest financial statements.

Source nodes:
- `securities.stocks.fact_stock_prices` → close, volume, security_id, date_id
- `corporate.finance.fact_financial_statements` → financial ratios joined via company_id

The `next_30d_return` column is the prediction label — computed as the forward 30-day
percentage return from the closing price.
