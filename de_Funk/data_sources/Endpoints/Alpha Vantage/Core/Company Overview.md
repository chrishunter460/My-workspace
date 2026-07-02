---
type: api-endpoint
provider: Alpha Vantage
endpoint_id: company_overview

# API Configuration
endpoint_pattern: ""
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  function: OVERVIEW
required_params: [symbol]

# Pagination
pagination_type: none
bulk_download: false

# Spark JSON Reading
json_structure: object
json_structure_comment: "Flat object with company fields. Direct struct access in Spark."

# Raw JSON Schema for explicit Spark reading (avoids schema inference)
# Format: [field_name, type] - defines the response object fields
# All fields are strings since Alpha Vantage returns strings (type coercion happens in normalization)
raw_schema:
  - [Symbol, string]
  - [AssetType, string]
  - [Name, string]
  - [Description, string]
  - [CIK, string]
  - [Exchange, string]
  - [Currency, string]
  - [Country, string]
  - [Sector, string]
  - [Industry, string]
  - [Address, string]
  - [OfficialSite, string]
  - [FiscalYearEnd, string]
  - [LatestQuarter, string]
  - [MarketCapitalization, string]
  - [EBITDA, string]
  - [PERatio, string]
  - [PEGRatio, string]
  - [BookValue, string]
  - [DividendPerShare, string]
  - [DividendYield, string]
  - [EPS, string]
  - [RevenuePerShareTTM, string]
  - [ProfitMargin, string]
  - [OperatingMarginTTM, string]
  - [ReturnOnAssetsTTM, string]
  - [ReturnOnEquityTTM, string]
  - [RevenueTTM, string]
  - [GrossProfitTTM, string]
  - [DilutedEPSTTM, string]
  - [QuarterlyEarningsGrowthYOY, string]
  - [QuarterlyRevenueGrowthYOY, string]
  - [AnalystTargetPrice, string]
  - [AnalystRatingStrongBuy, string]
  - [AnalystRatingBuy, string]
  - [AnalystRatingHold, string]
  - [AnalystRatingSell, string]
  - [AnalystRatingStrongSell, string]
  - [TrailingPE, string]
  - [ForwardPE, string]
  - [PriceToSalesRatioTTM, string]
  - [PriceToBookRatio, string]
  - [EVToRevenue, string]
  - [EVToEBITDA, string]
  - [Beta, string]
  - [52WeekHigh, string]
  - [52WeekLow, string]
  - [50DayMovingAverage, string]
  - [200DayMovingAverage, string]
  - [SharesOutstanding, string]
  - [SharesFloat, string]
  - [PercentInsiders, string]
  - [PercentInstitutions, string]
  - [DividendDate, string]
  - [ExDividendDate, string]

# Metadata
domain: securities
legal_entity_type: vendor
subject_entity_tags: [corporate]
data_tags: [reference, fundamentals]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "One API call per ticker - no bulk endpoint"

# Storage Configuration
bronze: alpha_vantage
partitions: []
write_strategy: upsert
key_columns: [cik]
date_column: null

# Schema
# Format: [field_name, type, source_field, nullable, description, {options}]
# Options: transform, coerce, expr, default
schema:
  # Core identifiers
  - [ticker, string, Symbol, false, "Stock ticker symbol"]
  - [cik, string, CIK, true, "SEC Central Index Key (10 digits)", {transform: "zfill(10)"}]
  - [asset_type, string, AssetType, true, "Asset type (Common Stock, ETF, etc.)"]

  # Company info
  - [company_name, string, Name, true, "Company legal name"]
  - [description, string, Description, true, "Business description"]
  - [exchange_code, string, Exchange, true, "Primary exchange (NYSE, NASDAQ)"]
  - [currency, string, Currency, true, "Reporting currency", {default: "USD"}]
  - [country, string, Country, true, "Country of incorporation", {default: "US"}]
  - [sector, string, Sector, true, "GICS Sector"]
  - [industry, string, Industry, true, "GICS Industry"]
  - [address, string, Address, true, "Company address"]
  - [official_site, string, OfficialSite, true, "Company website"]
  - [fiscal_year_end, string, FiscalYearEnd, true, "Fiscal year end month"]
  - [latest_quarter, date, LatestQuarter, true, "Most recent quarter end", {transform: "to_date(yyyy-MM-dd)"}]

  # Market data
  - [market_cap, long, MarketCapitalization, true, "Market capitalization USD", {coerce: long}]
  - [shares_outstanding, long, SharesOutstanding, true, "Total shares outstanding", {coerce: long}]
  - [shares_float, long, SharesFloat, true, "Shares available for trading", {coerce: long}]
  - [percent_insiders, double, PercentInsiders, true, "Insider ownership %", {coerce: double}]
  - [percent_institutions, double, PercentInstitutions, true, "Institutional ownership %", {coerce: double}]

  # Valuation ratios
  - [pe_ratio, double, PERatio, true, "Price to earnings ratio", {coerce: double}]
  - [peg_ratio, double, PEGRatio, true, "Price/earnings to growth ratio", {coerce: double}]
  - [book_value, double, BookValue, true, "Book value per share", {coerce: double}]
  - [trailing_pe, double, TrailingPE, true, "Trailing P/E", {coerce: double}]
  - [forward_pe, double, ForwardPE, true, "Forward P/E", {coerce: double}]
  - [price_to_sales, double, PriceToSalesRatioTTM, true, "Price to sales ratio", {coerce: double}]
  - [price_to_book, double, PriceToBookRatio, true, "Price to book ratio", {coerce: double}]
  - [ev_to_revenue, double, EVToRevenue, true, "EV/Revenue", {coerce: double}]
  - [ev_to_ebitda, double, EVToEBITDA, true, "EV/EBITDA", {coerce: double}]
  - [beta, double, Beta, true, "Beta (volatility vs market)", {coerce: double}]

  # Dividends
  - [dividend_per_share, double, DividendPerShare, true, "Annual dividend per share", {coerce: double}]
  - [dividend_yield, double, DividendYield, true, "Dividend yield percentage", {coerce: double}]
  - [dividend_date, date, DividendDate, true, "Next dividend date", {transform: "to_date(yyyy-MM-dd)"}]
  - [ex_dividend_date, date, ExDividendDate, true, "Ex-dividend date", {transform: "to_date(yyyy-MM-dd)"}]

  # Earnings
  - [eps, double, EPS, true, "Earnings per share (TTM)", {coerce: double}]
  - [diluted_eps_ttm, double, DilutedEPSTTM, true, "Diluted EPS TTM", {coerce: double}]

  # Financial metrics
  - [ebitda, long, EBITDA, true, "EBITDA", {coerce: long}]
  - [revenue_ttm, long, RevenueTTM, true, "Trailing 12 month revenue", {coerce: long}]
  - [gross_profit_ttm, long, GrossProfitTTM, true, "Gross profit TTM", {coerce: long}]
  - [revenue_per_share, double, RevenuePerShareTTM, true, "Revenue per share TTM", {coerce: double}]

  # Margins and returns
  - [profit_margin, double, ProfitMargin, true, "Profit margin percentage", {coerce: double}]
  - [operating_margin, double, OperatingMarginTTM, true, "Operating margin TTM", {coerce: double}]
  - [return_on_assets, double, ReturnOnAssetsTTM, true, "Return on assets TTM", {coerce: double}]
  - [return_on_equity, double, ReturnOnEquityTTM, true, "Return on equity TTM", {coerce: double}]

  # Growth
  - [quarterly_earnings_growth, double, QuarterlyEarningsGrowthYOY, true, "Quarterly earnings growth YoY", {coerce: double}]
  - [quarterly_revenue_growth, double, QuarterlyRevenueGrowthYOY, true, "Quarterly revenue growth YoY", {coerce: double}]

  # Analyst data
  - [analyst_target_price, double, AnalystTargetPrice, true, "Analyst target price", {coerce: double}]
  - [analyst_rating_strong_buy, long, AnalystRatingStrongBuy, true, "Strong buy ratings", {coerce: long}]
  - [analyst_rating_buy, long, AnalystRatingBuy, true, "Buy ratings", {coerce: long}]
  - [analyst_rating_hold, long, AnalystRatingHold, true, "Hold ratings", {coerce: long}]
  - [analyst_rating_sell, long, AnalystRatingSell, true, "Sell ratings", {coerce: long}]
  - [analyst_rating_strong_sell, long, AnalystRatingStrongSell, true, "Strong sell ratings", {coerce: long}]

  # Price data
  - [week_52_high, double, 52WeekHigh, true, "52-week high", {coerce: double}]
  - [week_52_low, double, 52WeekLow, true, "52-week low", {coerce: double}]
  - [moving_avg_50, double, 50DayMovingAverage, true, "50-day moving average", {coerce: double}]
  - [moving_avg_200, double, 200DayMovingAverage, true, "200-day moving average", {coerce: double}]

  # Generated fields
  - [is_active, boolean, _generated, false, "Currently active", {default: true}]
  - [snapshot_date, date, _generated, false, "Date of snapshot"]
  - [ingestion_timestamp, timestamp, _generated, false, "When data was ingested"]
---

## Description

Company overview including sector, industry, market cap, PE ratio, and other fundamentals. The OVERVIEW endpoint provides comprehensive company data including the SEC CIK (Central Index Key) which enables linkage to SEC EDGAR filings.

This is the primary source for the `company` Silver model's `dim_company` dimension.

## Request Notes

- **One call per ticker**: No bulk endpoint available
- **Rate limit aware**: Respect 5 calls/min (free) or 75 calls/min (premium)
- **CIK Padding**: CIK should be zero-padded to 10 digits per SEC standard
- **Error detection**: Check for `"Error Message"` key in response


## Homelab Usage

```bash
# Ingest company data for specific tickers
python -m scripts.ingest.run_bronze_ingestion --endpoints company_overview --tickers AAPL MSFT GOOGL
```

## Known Quirks

1. **Numeric strings**: All numeric fields returned as strings, including `"None"` for nulls
2. **Non-US gaps**: Non-US tickers often missing OVERVIEW data entirely
3. **AssetType values**: Returns "Common Stock", "ETF", "Mutual Fund" (map to asset_type)
4. **CIK missing**: Some smaller companies lack CIK even when US-listed
5. **Data freshness**: Fundamentals may lag current quarter by weeks
