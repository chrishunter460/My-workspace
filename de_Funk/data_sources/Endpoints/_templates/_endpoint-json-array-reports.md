---
type: api-endpoint
provider: Provider Name
endpoint_id: endpoint_name

# API Configuration
endpoint_pattern: "/api/v1/reports"
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  function: REPORTS
required_params: [symbol]

# Pagination
pagination_type: none
bulk_download: false

# Spark JSON Reading
# array_reports = Contains named arrays (e.g., annualReports, quarterlyReports)
# Use when API returns: {"annualReports": [...], "quarterlyReports": [...]}
# Spark will explode each array and union with report_type column
json_structure: array_reports
json_structure_comment: "Contains annualReports and quarterlyReports arrays. Requires union + explode in Spark."

# Metadata
domain: finance
legal_entity_type: vendor
subject_entity_tags: [corporate]
data_tags: [fundamentals, reports, quarterly, annual]
status: active
update_cadence: quarterly
last_verified:
last_reviewed:
notes: "Returns both annual and quarterly reports in single call"

# Storage Configuration
bronze: provider_name/table_name
partitions: [report_type]
write_strategy: upsert
key_columns: [symbol, fiscal_date, report_type]
date_column: fiscal_date

# Schema
# Format: [field_name, type, source_field, nullable, description, {options}]
schema:
  # Symbol from request parameter
  - [symbol, string, _param, false, "Symbol from request param"]

  # Report type (generated during explode: 'annual' or 'quarterly')
  - [report_type, string, _generated, false, "Report type", {default: "annual"}]

  # Date fields
  - [fiscal_date, date, fiscalDateEnding, false, "Fiscal period end date", {transform: "to_date(yyyy-MM-dd)"}]
  - [reported_date, date, reportedDate, true, "Report filing date", {transform: "to_date(yyyy-MM-dd)"}]

  # Financial metrics (require coercion from string)
  - [revenue, double, totalRevenue, true, "Total revenue", {coerce: double}]
  - [gross_profit, double, grossProfit, true, "Gross profit", {coerce: double}]
  - [operating_income, double, operatingIncome, true, "Operating income", {coerce: double}]
  - [net_income, double, netIncome, true, "Net income", {coerce: double}]

  # Currency
  - [currency, string, reportedCurrency, true, "Reporting currency"]
---

## Description

Financial reports endpoint that returns arrays of annual and quarterly reports.

## API Notes

- Single call returns both annual and quarterly reports
- Reports are in separate arrays: `annualReports` and `quarterlyReports`
- All numeric values returned as strings (may include "None" for nulls)

### Example Response

```json
{
  "symbol": "AAPL",
  "annualReports": [
    {
      "fiscalDateEnding": "2023-09-30",
      "reportedCurrency": "USD",
      "totalRevenue": "383285000000",
      "grossProfit": "169148000000",
      "operatingIncome": "114301000000",
      "netIncome": "96995000000"
    }
  ],
  "quarterlyReports": [
    {
      "fiscalDateEnding": "2023-12-31",
      "reportedCurrency": "USD",
      "totalRevenue": "119575000000",
      "grossProfit": "54855000000",
      "operatingIncome": "40373000000",
      "netIncome": "33916000000"
    }
  ]
}
```

## Spark Reading Strategy

1. `spark.read.json()` reads all files
2. Explode `annualReports` array with `report_type='annual'`
3. Explode `quarterlyReports` array with `report_type='quarterly'`
4. Union both DataFrames
5. Apply field mappings and type coercions

## Homelab Usage

```bash
python -m scripts.ingest.run_bronze_ingestion --provider provider_name --endpoints endpoint_name
```

## Known Quirks

1. **"None" string values**: API returns literal "None" for nulls, use `try_cast()`
2. **Large numbers as strings**: All financials are string-encoded
3. **Dual arrays**: Must union annual and quarterly separately
