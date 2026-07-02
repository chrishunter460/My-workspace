---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: budget_appropriations

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
data_tags: [budget, public, annual, appropriations]
status: active
update_cadence: annual
last_verified:
last_reviewed:
notes: "Multiple view_ids by year - iterate over view_id table below"

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [fund_code, department_code, appropriation_account]
date_column: null

# Schema
schema:
  - [year, int, _param, false, "Budget year (from view_id mapping)"]
  - [fund_code, string, fund_code, true, "Fund code"]
  - [fund_description, string, fund_description, true, "Fund description"]
  - [department_code, string, department_code, true, "Department code"]
  - [department_description, string, department_description, true, "Department name"]
  - [appropriation_account, string, appropriation_account, true, "Account code"]
  - [appropriation_account_description, string, appropriation_account_description, true, "Account description"]
  - [amount, double, amount, true, "Budgeted amount", {coerce: double}]
---

## Description
The Annual Appropriation Ordinance is the final City operating budget as approved by the City Council. It reflects the City’s operating budget at the beginning of the fiscal year on January 1.  
  
This dataset details the budgeted expenditures in the Ordinance and identifies them by department, appropriation account, and funding type: Local, Community Development Block Grant Program (CDBG), and other Grants. “Local” funds refer to those line items that are balanced with locally generated revenue sources, including but not limited to the Corporate Fund, Water Fund, Midway and O’Hare Airport funds, Vehicle Tax Fund, Library Fund and General Obligation Bond funds.

## Available Years

| Year | view_id | Format | Notes |
|----|----|----|----|
| 2026 | 6694-f78c | JSON | provisional |
| 2025 | t59y-fr3k | JSON | provisional |
| 2024 | x394-e874 | JSON | provisional |
| 2023 | xbjh-7zvh | JSON | provisional |
| 2022 | 2cr6-8u6w | JSON | provisional |
| 2021 | 6tbx-h7y2 | JSON | provisional |
| 2020 | fyin-2vyd | JSON | provisional |
| 2019 | h9rt-tsn7 | JSON | provisional |
| 2018 | 6g7p-xnsy | JSON | provisional |
| 2017 | 7jem-9wyw | JSON | provisional |
| 2016 | 36y7-5nnf | JSON | provisional |
| 2015 | qnek-cfpp | JSON | provisional |
| 2014 | ub6s-xy6e | JSON | provisional |
| 2013 | b24i-nwag | JSON | provisional |
| 2012 | 8ix6-nb7q | JSON | provisional |
| 2011 | drv3-jzqp | JSON | provisional |




## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
