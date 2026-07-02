---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: wards

# API Configuration
endpoint_pattern: /resource/{view_id}.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 100
required_params: [view_id]

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: geospatial
legal_entity_type: municipal
subject_entity_tags: [municipal, geographic-area]
data_tags: [boundaries, geospatial, reference, political]
status: active
update_cadence: irregular
last_verified:
last_reviewed:
notes: "50 Chicago ward boundaries. Changes after Census redistricting. Multiple view_ids."

# Storage Configuration
bronze: chicago
partitions: []
write_strategy: overwrite
key_columns: [ward]
date_column: null

# Schema
schema:
  - [ward, int, ward, false, "Ward number (1-50)"]
  - [alderman, string, alderman, true, "Alderman name"]
  - [st_area_sh, double, st_area_sh, true, "Shape area (sq feet)"]
  - [st_length_, double, st_length_, true, "Shape perimeter (feet)"]
  - [the_geom, string, the_geom, true, "GeoJSON geometry"]
---

## Description

Ward boundaries in Chicago corresponding to the dates when a new City Council is sworn in, based on the immediately preceding elections. Neither this description nor the dataset should be relied upon in situations where legal precision is required.  
  
​​​​​This dataset is in a forma​​t for spatial datasets that is inherently tabular but allows for a map as a derived view. Please click the indicated link below for such a map.

Ward boundaries changed corresponding to census changes the prior wards were in effect May 2015 to May 2023. [prior bondaries](https://data.cityofchicago.org/Facilities-Geographic-Boundaries/WARDS_2015/k9yb-bpqx/about_data)

## Available wards boundaries

| Year | view_id | Format | Notes |
|----|----|----|----|
| 2023 | p293-wvbd | JSON | May 2023 - current |
| 2015 | k9yb-bpqx | JSON | May 2015 - May 2023 |


## Request Notes


## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.