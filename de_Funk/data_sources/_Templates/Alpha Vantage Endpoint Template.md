---
type: api-endpoint
provider: Alpha Vantage
endpoint_id:                            # Unique identifier (e.g., "time_series_daily_adjusted")

# API Configuration
endpoint_pattern: ""                    # Alpha Vantage uses query params, not path
method: GET
format: json
auth: inherit
response_key:                           # JSON key containing data (e.g., "Time Series (Daily)")

# Query Parameters
default_query:
  function:                             # Alpha Vantage function (e.g., TIME_SERIES_DAILY_ADJUSTED)
  outputsize: full                      # full | compact (last 100 data points)
  datatype: json
required_params: [symbol]               # Usually requires symbol/ticker

# Pagination
pagination_type: none                   # Alpha Vantage returns all data in single response
bulk_download: false                    # Not applicable - API-based per ticker

# Metadata
domain: securities                      # securities | fundamentals | forex | crypto
legal_entity_type: vendor
subject_entity_tags: [corporate]
data_tags: []                           # [time-series, daily, prices, fundamentals]
status: active
update_cadence: daily                   # daily | quarterly | irregular
last_verified:
last_reviewed:
notes: ""

# Storage Configuration
bronze:                                 # Bronze table name (e.g., "securities_prices_daily")
partitions: []                          # Usually partitioned by year/month in Silver
write_strategy: append                  # append for time-series, upsert for reference
key_columns: []                         # Primary key (e.g., [ticker, trade_date])
date_column:                            # Date column for incremental loads

# Schema
# Format: [field_name, type, source_field, nullable, description, {options}]
# Types: string | long | double | boolean | date | timestamp | int
#
# Alpha Vantage special source values:
#   - "_key" for dict key extraction (date from "Time Series (Daily)" keys)
#   - "_param" for request parameter injection (ticker from symbol param)
#   - "_generated" for pipeline-set fields (asset_type)
#   - "_computed" for calculated fields (year from trade_date)
#
# Common Alpha Vantage patterns:
#   - Dates from dict keys: {transform: "to_date(yyyy-MM-dd)"}
#   - All numeric values are strings: {coerce: double} or {coerce: long}
#   - Field names have numeric prefixes: "1. open", "2. high", etc.

schema:
  # Keys and identifiers
  - [trade_date, date, _key, false, "Trading date (from response dict key)", {transform: "to_date(yyyy-MM-dd)"}]
  - [ticker, string, _param, false, "Stock ticker (from request param)"]
  - [asset_type, string, _generated, false, "Asset type", {default: "stocks"}]

  # Computed partition columns
  - [year, int, _computed, false, "Year", {expr: "extract(year from trade_date)"}]

  # Data fields (note: Alpha Vantage returns strings, need coercion)
  - [open, double, "1. open", true, "Opening price", {coerce: double}]
  - [high, double, "2. high", true, "High price", {coerce: double}]
  - [low, double, "3. low", true, "Low price", {coerce: double}]
  - [close, double, "4. close", true, "Closing price", {coerce: double}]
  - [volume, double, "6. volume", true, "Trading volume", {coerce: double}]
---

## Description

What data this endpoint provides. Include data coverage and any limitations.

## Request Notes

- **Function**: `FUNCTION_NAME`
- **API Docs**: https://www.alphavantage.co/documentation/
- **Rate Limits**: Free tier = 5 calls/min, 500/day. Premium = 75 calls/min.
- **Output Size**: `full` = 20+ years, `compact` = last 100 data points

## Response Structure

```json
{
  "Meta Data": {
    "1. Information": "...",
    "2. Symbol": "IBM",
    "3. Last Refreshed": "2024-01-15"
  },
  "Time Series (Daily)": {
    "2024-01-15": {
      "1. open": "123.45",
      "2. high": "125.00",
      ...
    }
  }
}
```

## Homelab Usage

```bash
# Ingest prices for seeded tickers
./scripts/test/test_pipeline.sh --profile dev --max-tickers 100

# With financials
./scripts/test/test_pipeline.sh --profile dev --with-financials
```

## Known Quirks

- All numeric values returned as strings (need coercion)
- Field names have numeric prefixes ("1. open", "2. high")
- Rate limits are strict on free tier
- Some tickers return empty data (delisted, etc.)
