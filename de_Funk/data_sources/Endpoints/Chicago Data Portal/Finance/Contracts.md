---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: contracts

# API Configuration
endpoint_pattern: /resource/rsxa-ify5.json
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
data_tags: [spending, contracts, procurement]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "City contracts and modifications since 1993"

# Storage Configuration
bronze: chicago
partitions: []
write_strategy: upsert
key_columns: [purchase_order_contract_number, specification_number]
date_column: start_date

# Schema
schema:
  - [contract_number, string, purchase_order_contract_number, false, "Contract identifier"]
  - [specification_number, string, specification_number, true, "Specification number"]
  - [vendor_name, string, vendor_name, true, "Vendor/contractor name"]
  - [description, string, purchase_order_description, true, "Contract description"]
  - [award_amount, double, award_amount, true, "Award amount in dollars", {coerce: double}]
  - [start_date, date, start_date, true, "Contract start date", {transform: "to_date(yyyy-MM-dd)"}]
  - [end_date, date, end_date, true, "Contract end date", {transform: "to_date(yyyy-MM-dd)"}]
  - [procurement_type, string, procurement_type, true, "Type of procurement"]
  - [department, string, department, true, "City department"]
---

## Description
Contracts and modifications awarded by the City of Chicago since 1993. This data is currently maintained in the City’s Financial Management and Purchasing System (FMPS), which is used throughout the City for contract management and payment.

  
Blanket vs. Standard Contracts: Only blanket contracts (contracts for repeated purchases) have FMPS end dates. Standard contracts (for example, construction contracts) terminate upon completion and acceptance of all deliverables. These dates are tracked outside of FMPS.  
  
Negative Modifications: Some contracts are modified to delete scope and money from a contract. These reductions are indicated by negative numbers in the Award Amount field of this dataset.  
  
Data Owner: Procurement Services.  
Time Period: 1993 to present.  
Frequency: Data is updated daily.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
