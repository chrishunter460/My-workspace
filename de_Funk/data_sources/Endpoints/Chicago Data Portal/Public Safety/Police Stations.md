---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: police_stations

# API Configuration
endpoint_pattern: /resource/z8bn-74gv.json
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
domain: public-safety
legal_entity_type: municipal
subject_entity_tags: [municipal, facility]
data_tags: [police, geospatial, reference, facilities]
status: active
update_cadence: irregular
last_verified:
last_reviewed:
notes: "Police district station locations and contact information."

# Storage Configuration
bronze: chicago
partitions: []
write_strategy: overwrite
key_columns: [district]
date_column: null

# Schema
schema:
  - [district, string, district, false, "District number"]
  - [district_name, string, district_name, true, "District name"]
  - [address, string, address, true, "Station address"]
  - [city, string, city, true, "City"]
  - [state, string, state, true, "State"]
  - [zip, string, zip, true, "ZIP code"]
  - [phone, string, phone, true, "Phone number"]
  - [fax, string, fax, true, "Fax number"]
  - [tty, string, tty, true, "TTY number"]
  - [latitude, double, latitude, true, "Latitude"]
  - [longitude, double, longitude, true, "Longitude"]
---



## Description

Chicago Police district station locations and contact information. Details on are coverage and boundaries can be found in the police beats.


## Request Notes


## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.