---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: budget_revenue

# API Configuration
endpoint_pattern: /resource/{view_id}.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
required_params: [view_id]

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: finance
legal_entity_type: municipal
subject_entity_tags: [municipal]
data_tags: [budget, public, annual, revenue, taxes]
status: active
update_cadence: annual
last_verified:
last_reviewed:
notes: "Multiple view_ids by year - iterate over view_id table below"

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [fund_code, revenue_source_code]
date_column: null

# Schema
schema:
  - [year, int, _param, false, "Budget year (from view_id mapping)"]
  - [fund_code, string, fund_code, true, "Fund code"]
  - [fund_description, string, fund_description, true, "Fund description"]
  - [revenue_source_code, string, revenue_source_code, true, "Revenue source code"]
  - [revenue_source_description, string, revenue_source_description, true, "Revenue source description"]
  - [amount, double, amount, true, "Budgeted revenue amount", {coerce: double}]
---

## Description
  
The Annual Appropriation Ordinance is the final City operating budget as approved by the City Council. It reflects the City’s operating budget at the beginning of the fiscal year on January 1
  
This dataset contains the revenue detail portion of the Ordinance for Local funds. “Local” funds are all funds, other than grant funds, used by the City for non-capital operations - including, but not limited to, the Corporate Fund, Water Fund, Midway and O’Hare Airport funds, Vehicle Tax Fund, and the Library Fund.

## Available Years

| Year | view_id | Format | Notes |
|----|----|----|----|
| 2026 | 6694-f78c | JSON | provisional |
| 2025 | e5cq-t86i | JSON | provisional |
| 2024 | rmi8-cugu | JSON | provisional |


## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
