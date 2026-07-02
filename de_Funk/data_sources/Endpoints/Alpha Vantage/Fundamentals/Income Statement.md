---
type: api-endpoint
provider: Alpha Vantage
endpoint_id: income_statement

# API Configuration
endpoint_pattern: ""
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  function: INCOME_STATEMENT
required_params: [symbol]

# Pagination
pagination_type: none
bulk_download: false

# Spark JSON Reading
json_structure: array_reports
json_structure_comment: "Contains annualReports and quarterlyReports arrays. Requires union + explode in Spark."

# Raw JSON Schema for explicit Spark reading (avoids schema inference)
# Format: [field_name, type] - defines the report record fields (inside arrays)
# All fields are strings since Alpha Vantage returns strings (type coercion happens in normalization)
raw_schema:
  - [fiscalDateEnding, string]
  - [reportedCurrency, string]
  - [grossProfit, string]
  - [totalRevenue, string]
  - [costOfRevenue, string]
  - [costofGoodsAndServicesSold, string]
  - [operatingIncome, string]
  - [sellingGeneralAndAdministrative, string]
  - [researchAndDevelopment, string]
  - [operatingExpenses, string]
  - [depreciation, string]
  - [depreciationAndAmortization, string]
  - [investmentIncomeNet, string]
  - [netInterestIncome, string]
  - [interestIncome, string]
  - [interestExpense, string]
  - [nonInterestIncome, string]
  - [otherNonOperatingIncome, string]
  - [interestAndDebtExpense, string]
  - [incomeBeforeTax, string]
  - [incomeTaxExpense, string]
  - [netIncomeFromContinuingOperations, string]
  - [comprehensiveIncomeNetOfTax, string]
  - [netIncome, string]
  - [ebit, string]
  - [ebitda, string]

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

  # Revenue and gross profit
  - [gross_profit, long, grossProfit, true, "Gross profit", {coerce: long}]
  - [total_revenue, long, totalRevenue, true, "Total revenue", {coerce: long}]
  - [cost_of_revenue, long, costOfRevenue, true, "Cost of revenue", {coerce: long}]
  - [cost_of_goods_sold, long, costofGoodsAndServicesSold, true, "COGS", {coerce: long}]

  # Operating income and expenses
  - [operating_income, long, operatingIncome, true, "Operating income", {coerce: long}]
  - [sg_and_a, long, sellingGeneralAndAdministrative, true, "SG&A expenses", {coerce: long}]
  - [research_and_development, long, researchAndDevelopment, true, "R&D expenses", {coerce: long}]
  - [operating_expenses, long, operatingExpenses, true, "Total operating expenses", {coerce: long}]
  - [depreciation, long, depreciation, true, "Depreciation", {coerce: long}]
  - [depreciation_and_amortization, long, depreciationAndAmortization, true, "D&A", {coerce: long}]

  # Interest and investment income
  - [investment_income_net, long, investmentIncomeNet, true, "Net investment income", {coerce: long}]
  - [net_interest_income, long, netInterestIncome, true, "Net interest income", {coerce: long}]
  - [interest_income, long, interestIncome, true, "Interest income", {coerce: long}]
  - [interest_expense, long, interestExpense, true, "Interest expense", {coerce: long}]
  - [non_interest_income, long, nonInterestIncome, true, "Non-interest income", {coerce: long}]
  - [other_non_operating_income, long, otherNonOperatingIncome, true, "Other non-op income", {coerce: long}]
  - [interest_and_debt_expense, long, interestAndDebtExpense, true, "Interest and debt expense", {coerce: long}]

  # Net income
  - [income_before_tax, long, incomeBeforeTax, true, "Pre-tax income", {coerce: long}]
  - [income_tax_expense, long, incomeTaxExpense, true, "Income tax expense", {coerce: long}]
  - [net_income_from_continuing_ops, long, netIncomeFromContinuingOperations, true, "Net income from continuing ops", {coerce: long}]
  - [comprehensive_income, long, comprehensiveIncomeNetOfTax, true, "Comprehensive income", {coerce: long}]
  - [net_income, long, netIncome, true, "Net income", {coerce: long}]

  # EBIT/EBITDA
  - [ebit, long, ebit, true, "EBIT", {coerce: long}]
  - [ebitda, long, ebitda, true, "EBITDA", {coerce: long}]

  # Metadata (generated by ingestion pipeline)
  - [ingestion_timestamp, timestamp, _generated, false, "When data was ingested"]
  - [snapshot_date, date, _generated, false, "Date of ingestion snapshot"]
---

## Description

Annual and quarterly income statement data including revenue, expenses, and net income. The API returns both `annualReports` and `quarterlyReports` arrays in a single response.

Used by the `company` Silver model for financial analysis.

## Request Notes

- Returns both annual (last 5 years) and quarterly (last 20 quarters) reports
- All numeric values returned as strings (including "None" for nulls)
- Currency is reported in `reportedCurrency` field

## Homelab Usage

```bash
# Ingest income statements for specific tickers
python -m scripts.ingest.run_bronze_ingestion --endpoints income_statement --tickers AAPL MSFT
```

## Known Quirks

1. **String numerics**: All financial figures are strings - convert to long
2. **"None" strings**: Null values represented as string "None"
3. **Varying fields**: Some fields may be missing depending on company type
4. **Historical depth**: Annual goes back ~5 years, quarterly ~5 years
