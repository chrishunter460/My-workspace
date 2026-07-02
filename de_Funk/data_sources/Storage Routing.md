---
type: storage-routing
version: "2.6"
description: "Storage layer routing configuration - defines where data lives and how it's partitioned"

# Default storage format for all layers
defaults:
  format: delta
  comment: "Delta Lake provides ACID, time travel, and schema evolution"

# Storage root paths
roots:
  bronze: storage/bronze
  silver: storage/silver

  # Silver model roots
  core_silver: storage/silver/core
  company_silver: storage/silver/company
  stocks_silver: storage/silver/stocks
  options_silver: storage/silver/options
  etfs_silver: storage/silver/etfs
  futures_silver: storage/silver/futures

  # Legacy v1.x roots (deprecated)
  equity_silver: storage/silver/equity
  corporate_silver: storage/silver/corporate
  forecast_silver: storage/silver/forecast
  macro_silver: storage/silver/macro
  city_finance_silver: storage/silver/city_finance
---

## Overview

This file defines the storage routing configuration for the de_Funk data platform. It specifies:
- Where Bronze (raw) and Silver (modeled) data is stored
- Partitioning strategies for efficient queries
- Write strategies (append, upsert, overwrite)
- Key columns for deduplication

## Bronze Tables

Bronze tables store raw data from API providers before transformation.

```yaml
tables:
  # Seed tables
  calendar_seed:
    root: bronze
    path: calendar_seed
    partitions: []
    comment: "Calendar seed data (2000-2050)"

  ticker_seed:
    root: bronze
    path: ticker_seed
    partitions: [asset_type]
    write_strategy: overwrite
    comment: "Seeded tickers from LISTING_STATUS API"

  # Securities reference (from LISTING_STATUS)
  securities_reference:
    root: bronze
    path: securities_reference
    partitions: [asset_type]
    write_strategy: upsert
    key_columns: [ticker]
    comment: "Basic ticker info - all 12k+ US tickers"

  # Company reference (from OVERVIEW)
  company_reference:
    root: bronze
    path: company_reference
    partitions: []
    write_strategy: upsert
    key_columns: [cik]
    comment: "Company fundamentals - CIK as primary key"

  # Daily prices (from TIME_SERIES_DAILY)
  securities_prices_daily:
    root: bronze
    path: securities_prices_daily
    partitions: []
    write_strategy: append
    key_columns: [ticker, trade_date]
    date_column: trade_date
    comment: "Daily OHLCV - append for immutable time-series"

  # Financial statements (from INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW, EARNINGS)
  income_statements:
    root: bronze
    path: income_statements
    partitions: [report_type]
    write_strategy: upsert
    key_columns: [ticker, fiscal_date_ending, report_type]
    date_column: fiscal_date_ending

  balance_sheets:
    root: bronze
    path: balance_sheets
    partitions: [report_type]
    write_strategy: upsert
    key_columns: [ticker, fiscal_date_ending, report_type]
    date_column: fiscal_date_ending

  cash_flows:
    root: bronze
    path: cash_flows
    partitions: [report_type]
    write_strategy: upsert
    key_columns: [ticker, fiscal_date_ending, report_type]
    date_column: fiscal_date_ending

  earnings:
    root: bronze
    path: earnings
    partitions: [report_type]
    write_strategy: upsert
    key_columns: [ticker, fiscal_date_ending, report_type]
    date_column: fiscal_date_ending

  # Options (from HISTORICAL_OPTIONS)
  historical_options:
    root: bronze
    path: historical_options
    partitions: [underlying_ticker, expiration_date]
    write_strategy: upsert
    key_columns: [contract_id, trade_date]
    date_column: trade_date

  # BLS Economic data
  bls_unemployment:
    root: bronze
    path: bls/unemployment
    partitions: [year]

  bls_cpi:
    root: bronze
    path: bls/cpi
    partitions: [year]

  bls_employment:
    root: bronze
    path: bls/employment
    partitions: [year]

  bls_wages:
    root: bronze
    path: bls/wages
    partitions: [year]

  # Chicago Data Portal
  chicago_unemployment:
    root: bronze
    path: chicago/unemployment
    partitions: [date]

  chicago_building_permits:
    root: bronze
    path: chicago/building_permits
    partitions: [issue_date]

  chicago_business_licenses:
    root: bronze
    path: chicago/business_licenses
    partitions: [start_date]

  chicago_economic_indicators:
    root: bronze
    path: chicago/economic_indicators
    partitions: [date]
```

## Silver Tables

Silver tables contain transformed, modeled data ready for analytics.

```yaml
silver_tables:
  # Company model
  dim_company:
    root: silver
    path: company/dims/dim_company

  dim_exchange:
    root: silver
    path: company/dims/dim_exchange

  fact_prices:
    root: silver
    path: company/facts/fact_prices

  # Equity model (v1.x legacy)
  dim_equity:
    root: equity_silver
    path: dims/dim_equity

  fact_equity_prices:
    root: equity_silver
    path: facts/fact_equity_prices
    partitions: [trade_date]
```

## Write Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `append` | Add new rows only | Immutable time-series (prices) |
| `upsert` | Update existing + insert new | Reference data (tickers, companies) |
| `overwrite` | Replace entire table | Full refresh (seeds) |

## Partition Guidelines

- **Time-series data**: Partition by date for efficient range queries
- **Reference data**: Partition by asset_type for filtered reads
- **Financial statements**: Partition by report_type (annual/quarterly)
