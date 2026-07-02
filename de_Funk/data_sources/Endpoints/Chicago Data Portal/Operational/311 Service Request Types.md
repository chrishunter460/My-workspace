---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: service_request_types

# API Configuration
endpoint_pattern: /resource/dgc7-2pdf.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 1000
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: operational
legal_entity_type: municipal
subject_entity_tags: [municipal]
data_tags: [service-requests, reference, categorical, 311]
status: active
update_cadence: irregular
last_verified:
last_reviewed:
notes: "Reference table of 311 service request types. Links to sr_type in service_requests_311."

# Storage Configuration
bronze: chicago
partitions: []
write_strategy: overwrite
key_columns: [sr_type]
date_column: null

# Schema
schema:
  - [sr_type, string, sr_type, false, "Service request type name"]
  - [sr_short_code, string, sr_short_code, true, "Short code for the request type"]
  - [department, string, department, true, "Responsible department"]
  - [description, string, description, true, "Description of the request type"]
---



## Description
Reference table containing all 311 service request types available in Chicago's 311 system. This lookup table links to the main 311 Service Requests dataset via the `sr_type` field.

Use this dataset to:
- Get a complete list of available service request types
- Look up which department handles each type
- Map short codes to full type names

## Request Notes
Small reference dataset (~200-300 rows). No pagination typically needed.

## Homelab Usage
- Load on initial setup and refresh periodically
- Join with `service_requests_311` on `sr_type` field

## Known Quirks
- Field names may vary slightly from main 311 dataset
- Some request types may be inactive but still present
