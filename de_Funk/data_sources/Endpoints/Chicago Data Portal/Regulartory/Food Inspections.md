---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: food_inspections

# API Configuration
endpoint_pattern: /resource/4ijn-s7e5.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
  $order: inspection_date DESC
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: regulatory
legal_entity_type: municipal
subject_entity_tags: [municipal, facility]
data_tags: [inspection, health, food, geospatial, time-series]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Restaurant/food establishment inspections from 2010-present. CDPH Food Protection Program."

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [inspection_id]
date_column: inspection_date

# Schema
schema:
  - [inspection_id, string, inspection_id, false, "Inspection identifier"]
  - [dba_name, string, dba_name, true, "Doing business as name"]
  - [aka_name, string, aka_name, true, "Also known as name"]
  - [license_, string, license_, true, "License number"]
  - [facility_type, string, facility_type, true, "Type of facility"]
  - [risk, string, risk, true, "Risk level"]
  - [address, string, address, true, "Street address"]
  - [city, string, city, true, "City"]
  - [state, string, state, true, "State"]
  - [zip, string, zip, true, "ZIP code"]
  - [inspection_date, date, inspection_date, true, "Inspection date", {transform: "to_date(yyyy-MM-dd)"}]
  - [inspection_type, string, inspection_type, true, "Type of inspection"]
  - [results, string, results, true, "Inspection result (Pass/Fail/etc.)"]
  - [violations, string, violations, true, "Violation details"]
  - [latitude, double, latitude, true, "Latitude"]
  - [longitude, double, longitude, true, "Longitude"]
---



## Description
This information is derived from inspections of restaurants and other food establishments in Chicago from January 1, 2010 to the present. Inspections are performed by staff from the Chicago Department of Public Health’s Food Protection Program using a standardized procedure. The results of the inspection are inputted into a database, then reviewed and approved by a State of Illinois Licensed Environmental Health Practitioner (LEHP). For descriptions of the data elements included in this set, please click [here](https://data.cityofchicago.org/api/assets/BAD5301B-681A-4202-9D25-51B2CAE672FF).

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
