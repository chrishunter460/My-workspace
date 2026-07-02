---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: cta_bus_stops

# API Configuration
endpoint_pattern: /resource/qs84-j7wh.json
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
domain: transportation
legal_entity_type: municipal
subject_entity_tags: [municipal, infrastructure]
data_tags: [transit, geospatial, reference, cta, bus]
status: active
update_cadence: irregular
last_verified:
last_reviewed:
notes: "11,000+ CTA bus stops. Stop ID used for Bus Tracker. Also available as KMZ."

# Storage Configuration
bronze: chicago
partitions: []
write_strategy: overwrite
key_columns: [stop_id]
date_column: null

# Schema
schema:
  - [stop_id, string, stop_id, false, "Stop identifier"]
  - [stop_name, string, stop_name, true, "Stop name"]
  - [routes, string, routes, true, "Routes serving this stop"]
  - [latitude, double, latitude, true, "Latitude"]
  - [longitude, double, longitude, true, "Longitude"]
---

## Description

CTA Bus Stops - Point data representing over 11,000 CTA bus stops. The Stop ID is used to get Bus Tracker information. this information is currently stored as a .kmz [file](https://data.cityofchicago.org/Transportation/CTA-Bus-Stops-kml/84eu-buny/about_data).
  
Projected Coordinate System: NAD_1983_StatePlane_Illinois_East_FIPS_1201_Feet



## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.