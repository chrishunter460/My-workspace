---
type: api-endpoint
provider: Cook County Data Portal
endpoint_id: neighborhood_boundaries

# API Configuration
endpoint_pattern: /resource/pcdw-pxtg.json
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
domain: geospatial
legal_entity_type: county
subject_entity_tags: [county, geographic-area]
data_tags: [boundaries, geospatial, reference, neighborhood]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Assessor neighborhood polygons. Represent housing submarkets, NOT Chicago community areas."

# Storage Configuration
bronze: cook_county
partitions: []
write_strategy: overwrite
key_columns: [neighborhood_id]
date_column: null

# Schema
schema:
  - [neighborhood_id, string, neighborhood_id, false, "Neighborhood identifier"]
  - [township_code, string, township_code, true, "Township code"]
  - [triad, string, triad, true, "Assessment triad"]
  - [the_geom, string, the_geom, true, "GeoJSON geometry"]
---

## Description

Neighborhood polygons used by the Cook County Assessor's Office for valuation and reporting. These neighborhoods are specific to the Assessor. They are intended to represent homogenous housing submarkets, NOT Chicago community areas or municipalities.  
  
These neighborhoods were reconstructed from individual parcels using spatial buffering and simplification. The full transformation script can be found on [the Assessor's GitHub](https://github.com/ccao-data/data-architecture/blob/master/aws-s3/scripts-ccao-data-warehouse-us-east-1/spatial-ccao-neighborhood.R).  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.