---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: police_beats

# API Configuration
endpoint_pattern: /resource/n9it-hstw.json
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
domain: public-safety
legal_entity_type: municipal
subject_entity_tags: [municipal, geographic-area]
data_tags: [police, geospatial, reference, boundaries]
status: active
update_cadence: irregular
last_verified:
last_reviewed:
notes: "Current police beat boundaries. Historical beat boundaries available separately."

# Storage Configuration
bronze: chicago
partitions: []
write_strategy: overwrite
key_columns: [beat_num]
date_column: null

# Schema
schema:
  - [beat_num, string, beat_num, false, "Beat number"]
  - [beat, string, beat, true, "Beat identifier"]
  - [district, string, district, true, "Police district"]
  - [sector, string, sector, true, "Sector"]
  - [the_geom, string, the_geom, true, "GeoJSON geometry"]
---



## Description

Current police beat boundaries in Chicago. The data can be viewed on the Chicago Data Portal with a web browser. However, to view or use the files outside of a web browser, you will need to use compression software and special GIS software, such as ESRI ArcGIS (shapefile) or Google Earth (KML or KMZ), is required.

For simplicity grabbing only current beats, however a different set of beats where in place at different times.


## Request Notes


## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.