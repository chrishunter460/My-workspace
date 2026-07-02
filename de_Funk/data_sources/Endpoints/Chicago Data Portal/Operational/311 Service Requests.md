---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: service_requests_311

# API Configuration
endpoint_pattern: /resource/v6vf-nfxy.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
  $order: created_date DESC
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: operational
legal_entity_type: municipal
subject_entity_tags: [municipal, individual]
data_tags: [service-requests, geospatial, time-series, 311]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "311 requests since 12/18/2018 (new system). LEGACY_RECORD indicates old system data."

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [sr_number]
date_column: created_date

# Schema
schema:
  - [sr_number, string, sr_number, false, "Service request number"]
  - [sr_type, string, sr_type, true, "Request type"]
  - [sr_short_code, string, sr_short_code, true, "Short code"]
  - [created_date, timestamp, created_date, true, "Created date", {transform: "to_timestamp(yyyy-MM-dd'T'HH:mm:ss)"}]
  - [closed_date, timestamp, closed_date, true, "Closed date", {transform: "to_timestamp(yyyy-MM-dd'T'HH:mm:ss)"}]
  - [status, string, status, true, "Request status"]
  - [street_address, string, street_address, true, "Street address"]
  - [city, string, city, true, "City"]
  - [zip_code, string, zip_code, true, "ZIP code"]
  - [ward, int, ward, true, "Ward number"]
  - [community_area, int, community_area, true, "Community area number"]
  - [latitude, double, latitude, true, "Latitude"]
  - [longitude, double, longitude, true, "Longitude"]
  - [legacy_record, boolean, legacy_record, true, "From old 311 system"]
---



## Description
311 Service Requests received by the City of Chicago. This dataset includes requests created after the launch of the new 311 system on 12/18/2018 and some records from the previous system, indicated in the LEGACY_RECORD column.

For purposes of all columns indicating geographic areas or locations, please note that requests of the type 311 INFORMATION ONLY CALL often are entered with the address of the City's 311 Center.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.