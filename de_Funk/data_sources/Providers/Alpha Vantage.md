---
type: api-provider
provider_id: alpha_vantage
provider: Alpha Vantage

# API Configuration
api_type: rest
base_url: https://www.alphavantage.co/query
homepage: https://www.alphavantage.co/documentation/

# Authentication
auth_model: api-key
env_api_key: ALPHA_VANTAGE_API_KEYS

# Rate Limiting
rate_limit_per_sec: 1.0
rate_limit_comment: "Conservative: 60/min (1.0/sec) - headroom below premium 75/min. Free tier: 5/min (0.0833/sec), 25/day"

# Default Headers (API key passed as query param, not header)
default_headers: {}

# Provider-specific settings
provider_settings:
  ticker_source: seed
  ticker_source_options: [market_cap, seed]
  ticker_source_comment: "How to select tickers: 'market_cap' = ranked by market cap from company_reference, 'seed' = use ticker_seed table"
  us_exchanges: [NYSE, NASDAQ, NYSEAMERICAN, NYSEMKT, BATS, NYSEARCA]
  us_exchanges_comment: "Filter to US exchanges for company data. Foreign exchanges may lack OVERVIEW data."
  save_raw: false
  save_raw_comment: "Save raw API responses to raw/alpha_vantage/{endpoint}/{ticker}.json before transformation"

# Endpoints to ingest (configured in run_config.json)
endpoints:
  - time_series_daily
  - company_overview
  - income_statement
  - balance_sheet
  - cash_flow
  - earnings
  - dividends
  - splits
endpoints_comment: "Available: time_series_daily, time_series_daily_adjusted, company_overview, global_quote, income_statement, balance_sheet, cash_flow, earnings, dividends, splits"

# Models Fed (Silver layer)
models:
  - stocks
  - company
  - options
  - etf

# Metadata
category: commercial
legal_entity_type: vendor
data_domains: [securities, fundamentals, technicals, options]
data_tags: [time-series, daily, market-data, reference]
status: active
bulk_download: false
last_verified:
last_reviewed:
notes:
---

## Description

Alpha Vantage provides stock market data including real-time and historical prices, company fundamentals (income statements, balance sheets, cash flows), technical indicators, options chains, and ETF profiles. It is the sole securities provider for de_Funk v2.0+.

## API Notes

- **Single Base URL**: All endpoints use query parameter differentiation (`function=OVERVIEW`, `function=TIME_SERIES_DAILY`, etc.)
- **API Key**: Passed as `apikey` query parameter (not header)
- **Response Format**: JSON by default, some endpoints return CSV (listing_status, earnings_calendar)
- **Error Handling**: Errors don't use HTTP status codes - check for `"Error Message"` key in JSON response

### Rate Limits

| Tier | Calls/Minute | Calls/Day | Cost |
|------|--------------|-----------|------|
| Free | 5 | 25 | $0 |
| Premium | 75 | Unlimited | ~$50/mo |

### Key Endpoints by Category

| Category | Endpoints | Bronze Tables |
|----------|-----------|---------------|
| Core | company_overview, listing_status, global_quote | company_reference, securities_reference |
| Prices | time_series_daily, time_series_daily_adjusted | securities_prices_daily |
| Fundamentals | income_statement, balance_sheet, cash_flow, earnings | income_statements, balance_sheets, cash_flows, earnings |
| Corporate Actions | dividends, splits | dividends, splits |
| Options | historical_options, realtime_options | historical_options |
| ETFs | etf_profile | etf_profiles |
| Technical | technical_sma, technical_rsi, technical_macd | (computed on demand) |

### Endpoint Details

#### Core Endpoints
- **listing_status**: Returns CSV of all active US tickers (~12,000+). Use for ticker discovery.
- **company_overview**: Company fundamentals with SEC CIK for linkage. One call per ticker.

#### Price Endpoints
- **time_series_daily**: Full historical OHLCV (20+ years). One call per ticker.
- **time_series_daily_adjusted**: Includes split/dividend adjustments.

#### Fundamental Endpoints
All return quarterly and annual data. One call per ticker per endpoint.

#### Corporate Action Endpoints
- **dividends**: Historical and declared dividend distributions
  - Fields: ex_dividend_date, dividend_amount, record_date, payment_date, declaration_date
  - API: `function=DIVIDENDS&symbol={ticker}`
- **splits**: Historical stock split events
  - Fields: effective_date, split_from, split_to (e.g., 1:4 for 4-for-1)
  - API: `function=SPLITS&symbol={ticker}`

### Bronze Tables

| Table | Source Endpoint | Partitions | Key Fields |
|-------|-----------------|------------|------------|
| `securities_reference` | listing_status | `snapshot_dt`, `asset_type` | ticker, name, exchange, asset_type, cik |
| `company_reference` | company_overview | `snapshot_dt` | ticker, cik, sector, industry, market_cap |
| `securities_prices_daily` | time_series_daily | `trade_date`, `asset_type` | ticker, trade_date, open, high, low, close, volume |
| `income_statements` | income_statement | `fiscal_year` | ticker, fiscal_date, revenue, net_income, eps |
| `balance_sheets` | balance_sheet | `fiscal_year` | ticker, fiscal_date, total_assets, total_liabilities |
| `cash_flows` | cash_flow | `fiscal_year` | ticker, fiscal_date, operating_cf, investing_cf |
| `earnings` | earnings | `fiscal_year` | ticker, fiscal_date, reported_eps, estimated_eps |
| `dividends` | dividends | `ex_dividend_date` | ticker, ex_dividend_date, dividend_amount, payment_date |
| `splits` | splits | `effective_date` | ticker, effective_date, split_from, split_to |

### Recommended Cadence

| Data Type | Frequency | Notes |
|-----------|-----------|-------|
| Prices | Daily | After market close |
| Fundamentals | Weekly | New filings irregular |
| Reference | Weekly | Ticker changes rare |
| Dividends/Splits | Weekly | Corporate actions less frequent |

## Homelab Usage Notes

- **Ingestion Cadence**: Daily for prices, weekly for fundamentals
- **Ticker Discovery**: Use `listing_status` endpoint first to get all active US tickers
- **CIK Extraction**: OVERVIEW endpoint provides SEC CIK for company linkage
- **Retry Strategy**: Exponential backoff on rate limit errors (429-equivalent in JSON)

### Raw Data Dump

To save raw API responses before transformation (useful for debugging or reprocessing):

```python
from datapipelines.providers.alpha_vantage import create_alpha_vantage_provider
from pathlib import Path

# Pass storage_path to constructor to enable raw layer (automatic when set)
provider = create_alpha_vantage_provider(spark, repo_root, storage_path=Path("/shared/storage"))
provider.set_tickers(["AAPL", "MSFT"])

# Responses saved to: /shared/storage/raw/alpha_vantage/{endpoint}/{ticker}.json
```

Or via ingestion script:
```bash
python -m scripts.ingest.run_bronze_ingestion --save-raw --max-tickers 10
```

## Known Quirks

1. **Numeric Fields as Strings**: Many numeric fields returned as strings, including `"None"` for nulls
2. **No Bulk Endpoints**: One API call per ticker for most endpoints (no batch)
3. **OVERVIEW Gaps**: Non-US tickers often missing OVERVIEW data
4. **CSV Endpoints**: `listing_status` and `earnings_calendar` return CSV, not JSON
5. **AssetType Values**: Returns "Common Stock", "ETF", "Mutual Fund" (needs mapping)
6. **Rate Limit Response**: Returns JSON with error message, not HTTP 429
