---
type: api-endpoint
provider: Alpha Vantage
endpoint_id: balance_sheet

# API Configuration
endpoint_pattern: ""
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  function: BALANCE_SHEET
required_params: [symbol]

# Pagination
pagination_type: none
bulk_download: false

# Spark JSON Reading
json_structure: array_reports
json_structure_comment: "Contains annualReports and quarterlyReports arrays. Requires union + explode in Spark."

# Metadata
domain: finance
legal_entity_type: vendor
subject_entity_tags: [corporate]
data_tags: [fundamentals, financial-statements, quarterly, annual]
status: active
update_cadence: quarterly
last_verified:
last_reviewed:
notes: "Returns both annualReports and quarterlyReports arrays"

# Storage Configuration
bronze: alpha_vantage
partitions: [report_type]
write_strategy: upsert
key_columns: [ticker, fiscal_date_ending, report_type]
date_column: fiscal_date_ending

# Facet Configuration - drives generic facet behavior
facet_config:
  response_arrays:
    annualReports: annual
    quarterlyReports: quarterly
  fixed_fields:
    ticker: symbol
    fiscal_date_ending: fiscalDateEnding
    reported_currency: reportedCurrency

# Schema
# Format: [field_name, type, source_field, nullable, description, {options}]
# Options: transform, coerce, expr, default
schema:
  # Identifiers
  - [ticker, string, symbol, false, "Stock ticker"]
  - [fiscal_date_ending, date, fiscalDateEnding, false, "End of fiscal period", {transform: "to_date(yyyy-MM-dd)"}]
  - [report_type, string, _generated, false, "annual or quarterly"]
  - [reported_currency, string, reportedCurrency, true, "Reporting currency"]

  # Assets
  - [total_assets, long, totalAssets, true, "Total assets", {coerce: long}]
  - [total_current_assets, long, totalCurrentAssets, true, "Current assets", {coerce: long}]
  - [cash_and_equivalents, long, cashAndCashEquivalentsAtCarryingValue, true, "Cash", {coerce: long}]
  - [cash_and_short_term_investments, long, cashAndShortTermInvestments, true, "Cash + short-term investments", {coerce: long}]
  - [inventory, long, inventory, true, "Inventory", {coerce: long}]
  - [current_net_receivables, long, currentNetReceivables, true, "Receivables", {coerce: long}]
  - [total_non_current_assets, long, totalNonCurrentAssets, true, "Non-current assets", {coerce: long}]
  - [property_plant_equipment, long, propertyPlantEquipment, true, "PP&E", {coerce: long}]
  - [accumulated_depreciation, long, accumulatedDepreciationAmortizationPPE, true, "Accumulated depreciation", {coerce: long}]
  - [intangible_assets, long, intangibleAssets, true, "Intangible assets", {coerce: long}]
  - [intangible_assets_ex_goodwill, long, intangibleAssetsExcludingGoodwill, true, "Intangibles ex goodwill", {coerce: long}]
  - [goodwill, long, goodwill, true, "Goodwill", {coerce: long}]
  - [investments, long, investments, true, "Total investments", {coerce: long}]
  - [long_term_investments, long, longTermInvestments, true, "Long-term investments", {coerce: long}]
  - [short_term_investments, long, shortTermInvestments, true, "Short-term investments", {coerce: long}]
  - [other_current_assets, long, otherCurrentAssets, true, "Other current assets", {coerce: long}]
  - [other_non_current_assets, long, otherNonCurrentAssets, true, "Other non-current assets", {coerce: long}]

  # Liabilities
  - [total_liabilities, long, totalLiabilities, true, "Total liabilities", {coerce: long}]
  - [total_current_liabilities, long, totalCurrentLiabilities, true, "Current liabilities", {coerce: long}]
  - [accounts_payable, long, currentAccountsPayable, true, "Accounts payable", {coerce: long}]
  - [deferred_revenue, long, deferredRevenue, true, "Deferred revenue", {coerce: long}]
  - [current_debt, long, currentDebt, true, "Current portion of debt", {coerce: long}]
  - [short_term_debt, long, shortTermDebt, true, "Short-term debt", {coerce: long}]
  - [total_non_current_liabilities, long, totalNonCurrentLiabilities, true, "Non-current liabilities", {coerce: long}]
  - [capital_lease_obligations, long, capitalLeaseObligations, true, "Capital lease obligations", {coerce: long}]
  - [long_term_debt, long, longTermDebt, true, "Long-term debt", {coerce: long}]
  - [current_long_term_debt, long, currentLongTermDebt, true, "Current portion of LT debt", {coerce: long}]
  - [long_term_debt_noncurrent, long, longTermDebtNoncurrent, true, "Non-current LT debt", {coerce: long}]
  - [short_long_term_debt_total, long, shortLongTermDebtTotal, true, "Total debt", {coerce: long}]
  - [other_current_liabilities, long, otherCurrentLiabilities, true, "Other current liabilities", {coerce: long}]
  - [other_non_current_liabilities, long, otherNonCurrentLiabilities, true, "Other non-current liabilities", {coerce: long}]

  # Equity
  - [total_shareholder_equity, long, totalShareholderEquity, true, "Shareholder equity", {coerce: long}]
  - [treasury_stock, long, treasuryStock, true, "Treasury stock", {coerce: long}]
  - [retained_earnings, long, retainedEarnings, true, "Retained earnings", {coerce: long}]
  - [common_stock, long, commonStock, true, "Common stock", {coerce: long}]
  - [shares_outstanding, long, commonStockSharesOutstanding, true, "Shares outstanding", {coerce: long}]

  # Metadata (generated by ingestion pipeline)
  - [ingestion_timestamp, timestamp, _generated, false, "When data was ingested"]
  - [snapshot_date, date, _generated, false, "Date of ingestion snapshot"]
---

## Description

Annual and quarterly balance sheet data including assets, liabilities, and shareholder equity. Returns both `annualReports` and `quarterlyReports` arrays.

## Request Notes

- All balance sheet items as of fiscal period end date
- Values in reporting currency (usually USD)

## Homelab Usage

```bash
python -m scripts.ingest.run_bronze_ingestion --endpoints balance_sheet --tickers AAPL MSFT
```

## Known Quirks

1. **String numerics**: All values as strings including "None"
2. **Field naming**: Some fields use camelCase with inconsistent patterns
3. **Missing fields**: Banks/financials have different field sets
