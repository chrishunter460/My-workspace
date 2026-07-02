---
type: api-endpoint
provider: Alpha Vantage
endpoint_id: historical_options

# API Configuration
endpoint_pattern: ""
method: GET
format: json
auth: inherit
response_key: data

# Query Parameters
default_query:
  function: HISTORICAL_OPTIONS
required_params: [symbol]

# Pagination
pagination_type: none
bulk_download: false

# Metadata
domain: securities
legal_entity_type: vendor
subject_entity_tags: [corporate]
data_tags: [options, time-series, greeks, derivatives]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Premium endpoint - requires paid subscription"

# Storage Configuration
bronze: alpha_vantage
partitions: [underlying_ticker, expiration_date]
write_strategy: upsert
key_columns: [contract_id, trade_date]
date_column: trade_date

# Schema
# Format: [field_name, type, source_field, nullable, description, {options}]
# Options: transform, coerce, expr, default
schema:
  # Contract identification
  - [contract_id, string, contractID, false, "Unique option contract ID"]
  - [underlying_ticker, string, symbol, false, "Underlying stock ticker"]

  # Dates
  - [trade_date, date, date, false, "Trading date", {transform: "to_date(yyyy-MM-dd)"}]
  - [expiration_date, date, expiration, false, "Option expiration date", {transform: "to_date(yyyy-MM-dd)"}]

  # Contract specs
  - [strike, double, strike, false, "Strike price", {coerce: double}]
  - [option_type, string, type, false, "call or put"]

  # Pricing (require coercion)
  - [last_price, double, last, true, "Last traded price", {coerce: double}]
  - [mark, double, mark, true, "Mark price (mid)", {coerce: double}]
  - [bid, double, bid, true, "Bid price", {coerce: double}]
  - [ask, double, ask, true, "Ask price", {coerce: double}]

  # Volume and interest
  - [volume, long, volume, true, "Trading volume", {coerce: long}]
  - [open_interest, long, open_interest, true, "Open interest", {coerce: long}]

  # Greeks
  - [implied_volatility, double, implied_volatility, true, "Implied volatility", {coerce: double}]
  - [delta, double, delta, true, "Delta Greek", {coerce: double}]
  - [gamma, double, gamma, true, "Gamma Greek", {coerce: double}]
  - [theta, double, theta, true, "Theta Greek (time decay)", {coerce: double}]
  - [vega, double, vega, true, "Vega Greek (volatility sensitivity)", {coerce: double}]
  - [rho, double, rho, true, "Rho Greek (interest rate sensitivity)", {coerce: double}]
---

## Description

Historical options chain data including strike prices, expiration dates, bid/ask spreads, Greeks (delta, gamma, theta, vega), and implied volatility.

**Premium Endpoint**: Requires paid Alpha Vantage subscription.

## Request Notes

- Returns full options chain for specified underlying
- Optional `date` parameter for historical snapshots
- Greeks calculated using Black-Scholes model

## Homelab Usage

```bash
# Ingest options for specific underlyings
python -m scripts.ingest.run_bronze_ingestion --endpoints historical_options --tickers AAPL SPY
```

## Known Quirks

1. **Premium only**: Requires paid subscription
2. **Large responses**: Full chain can be thousands of contracts
3. **Greeks freshness**: Greeks recalculated at market close
4. **Expiration cycles**: Weekly and monthly expirations included
5. **Historical depth**: Depends on subscription tier
