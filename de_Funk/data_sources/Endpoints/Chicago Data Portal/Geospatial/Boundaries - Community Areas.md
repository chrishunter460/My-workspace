---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: community_areas

# API Configuration
endpoint_pattern: /resource/igwz-8jzy.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 100
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: geospatial
legal_entity_type: municipal
subject_entity_tags: [municipal, geographic-area]
data_tags: [boundaries, geospatial, reference, neighborhoods]
status: active
update_cadence: irregular
last_verified:
last_reviewed:
notes: "77 Chicago community area boundaries. Stable since 1920s."

# Storage Configuration
bronze: chicago
partitions: []
write_strategy: overwrite
key_columns: [area_numbe]
date_column: null

# Schema
schema:
  - [area_numbe, int, area_numbe, false, "Community area number (1-77)"]
  - [community, string, community, true, "Community area name"]
  - [area_num_1, int, area_num_1, true, "Alternate area number"]
  - [shape_area, double, shape_area, true, "Shape area (sq feet)"]
  - [shape_len, double, shape_len, true, "Shape perimeter (feet)"]
  - [the_geom, string, the_geom, true, "GeoJSON geometry"]
---



## Description

Community area boundaries in Chicago.  
  
This dataset is in a format for spatial datasets that is inherently tabular but allows for a map as a derived view. Please click the indicated link below for such a map.  

Community areas have a wikipedia [page ](https://en.wikipedia.org/wiki/Community_areas_in_Chicago)

## Request Notes


## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.