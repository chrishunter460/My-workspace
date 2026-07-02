---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: cta_l_stops

# API Configuration
endpoint_pattern: /resource/8pix-ypme.json
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
domain: transportation
legal_entity_type: municipal
subject_entity_tags: [municipal, infrastructure]
data_tags: [transit, geospatial, reference, cta, rail]
status: active
update_cadence: irregular
last_verified:
last_reviewed:
notes: "L stop locations with station names and service availability."

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
  - [station_name, string, station_name, true, "Station name"]
  - [station_descriptive_name, string, station_descriptive_name, true, "Full station description"]
  - [map_id, string, map_id, true, "Map identifier"]
  - [ada, boolean, ada, true, "ADA accessible"]
  - [red, boolean, red, true, "Serves Red Line"]
  - [blue, boolean, blue, true, "Serves Blue Line"]
  - [green, boolean, g, true, "Serves Green Line"]
  - [brown, boolean, brn, true, "Serves Brown Line"]
  - [purple, boolean, p, true, "Serves Purple Line"]
  - [pink, boolean, pnk, true, "Serves Pink Line"]
  - [orange, boolean, o, true, "Serves Orange Line"]
  - [yellow, boolean, y, true, "Serves Yellow Line"]
  - [latitude, double, latitude, true, "Latitude"]
  - [longitude, double, longitude, true, "Longitude"]
---

## Description

This list of 'L' stops provides location and basic service availability information for each place on the CTA system where a train stops, along with formal station names and stop descriptions.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.