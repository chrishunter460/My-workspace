---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: payments

# API Configuration
endpoint_pattern: /resource/s4vu-giwb.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: finance
legal_entity_type: municipal
subject_entity_tags: [municipal, corporate]
data_tags: [spending, payments, vendors]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "All vendor payments 1996-present. Pre-2002 data rolled up to 2002."

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [voucher_number]
date_column: check_date

# Schema
schema:
  - [voucher_number, string, voucher_number, false, "Payment voucher number"]
  - [vendor_name, string, vendor_name, true, "Vendor name"]
  - [contract_number, string, contract_number, true, "Related contract number"]
  - [amount, double, amount, true, "Payment amount", {coerce: double}]
  - [check_date, date, check_date, true, "Payment date", {transform: "to_date(yyyy-MM-dd)"}]
  - [department, string, department_name, true, "City department"]
  - [description, string, description, true, "Payment description"]
---

## Description
All vendor payments made by the City of Chicago from 1996 to present. Payments from 1996 through 2002 have been rolled-up and appear as "2002." Total payment information is summarized for each vendor and contract number for data older than two years. These data are extracted from the City’s Vendor, Contract, and Payment Search.  
  
Time Period: 1996 to present.  
  
Frequency: Data is updated daily.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.