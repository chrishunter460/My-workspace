---
type: api-endpoint
provider: Alpha Vantage
endpoint_id: listing_status

# API Configuration
endpoint_pattern: ""
method: GET
format: csv
auth: inherit
response_key: null

# Query Parameters
default_query:
  function: LISTING_STATUS
  state: active
required_params: []

# Pagination
pagination_type: none
bulk_download: true

# Metadata
domain: securities
legal_entity_type: vendor
subject_entity_tags: [corporate]
data_tags: [reference, bulk, tickers]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Single API call returns all US tickers - CSV format"

# Storage Configuration
bronze: alpha_vantage
partitions: [asset_type]
write_strategy: upsert
key_columns: [ticker]
date_column: null

# Schema
# Format: [field_name, type, source_field, nullable, description, {options}]
# Options: transform, coerce, expr, default
schema:
  # Core fields
  - [ticker, string, symbol, false, "Stock ticker symbol"]
  - [security_name, string, name, true, "Security name"]
  - [exchange_code, string, exchange, true, "Primary exchange"]
  - [asset_type, string, assetType, true, "Stock, ETF, etc."]

  # Date fields
  - [ipo_date, date, ipoDate, true, "IPO date", {transform: "to_date(yyyy-MM-dd)"}]
  - [delisting_date, date, delistingDate, true, "Delisting date (if state=delisted)", {transform: "to_date(yyyy-MM-dd)"}]

  # Status
  - [status, string, status, true, "Active or Delisted"]
---

## Description

Returns all active (or delisted) US stock listings in a single API call. This is the **primary ticker discovery endpoint** for seeding the Bronze layer with all available tickers before detailed ingestion.

**Critical for ingestion**: Use this endpoint first to get the universe of tickers, then iterate through them for OVERVIEW, prices, etc.

## Request Notes

- **CSV Format**: Returns CSV, not JSON - needs different parsing
- **state parameter**: `active` (default) or `delisted`
- **Single call**: Returns all ~12,000+ US tickers in one API call
- **Light on details**: Only basic info - use OVERVIEW for full company data

### Example Response (CSV)

```csv
symbol,name,exchange,assetType,ipoDate,delistingDate,status
AAPL,Apple Inc,NYSE,Stock,1980-12-12,,Active
MSFT,Microsoft Corporation,NASDAQ,Stock,1986-03-13,,Active
```

## Homelab Usage

```bash
# Seed all US tickers (run once, then periodically)
python -m scripts.seed.seed_tickers --storage-path /shared/storage

# Use with scripts/ingest for ticker discovery
python -m scripts.ingest.run_bronze_ingestion --endpoints listing_status
```

## Known Quirks

1. **CSV not JSON**: Must parse as CSV, not JSON
2. **No CIK**: CIK not included - must call OVERVIEW per ticker
3. **No market cap**: Basic info only - no fundamentals
4. **Includes OTC**: May include OTC/pink sheet tickers
5. **AssetType mapping**: Returns "Stock", "ETF" - map to internal asset_type
