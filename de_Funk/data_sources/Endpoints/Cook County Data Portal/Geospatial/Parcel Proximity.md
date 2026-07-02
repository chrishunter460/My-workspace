---
type: api-endpoint
provider: Cook County Data Portal
endpoint_id: parcel_proximity

# API Configuration
endpoint_pattern: /resource/ydue-e5u3.json
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
domain: geospatial
legal_entity_type: county
subject_entity_tags: [county, property]
data_tags: [parcel, geospatial, proximity, reference]
status: active
update_cadence: yearly
last_verified:
last_reviewed:
notes: "10-digit parcels with distances to spatial features. Available mostly after 2012."

# Storage Configuration
bronze: cook_county
partitions: []
write_strategy: overwrite
key_columns: [pin10]
date_column: null

# Schema
schema:
  - [pin10, string, pin10, false, "10-digit PIN (building level)", {transform: "zfill(10)"}]
  - [year, int, year, true, "Data year"]
  - [dist_to_cta, double, dist_to_cta, true, "Distance to CTA station (m)", {coerce: double}]
  - [dist_to_metra, double, dist_to_metra, true, "Distance to Metra station (m)", {coerce: double}]
  - [dist_to_highway, double, dist_to_highway, true, "Distance to highway (m)", {coerce: double}]
  - [dist_to_park, double, dist_to_park, true, "Distance to park (m)", {coerce: double}]
---

## Description

Cook County 10-digit parcels with attached distances to various spatial features.  
  
When working with 10-digit Parcel Index Numbers (PINs) make sure to zero-pad them to 10 digits. Some datasets may lose leading zeros for PINs when downloaded. 10-digit PINs do not identify individual condominium units.  
  
Additional notes:

- Centroids are based on [Cook County parcel shapefiles](https://datacatalog.cookcountyil.gov/Property-Taxation/ccgisdata-Parcel-2021/77tz-riq7).
  
- Older properties may be missing coordinates and thus also missing attached spatial data (usually they are missing a parcel boundary in the shapefile).
  
- Attached spatial data does NOT all go back to 2000. It is only available for more recent years, primarily those after 2012.
  
- This dataset contains data for the current tax year, which may not yet be complete or final. Assessed values for any given year are subject to change until [review and certification of values by the Cook County Board of Review](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines), though there are a few rare circumstances where values may change for the current or past years after that.
  
- Rowcount for a given year is final once the Assessor [has certified the assessment roll](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines) all townships.
  
- Data will be updated annually as new parcel shapefiles are made available.

For more information on the sourcing of attached data and the preparation of this dataset, see the [Assessor's Standard Operating Procedures for Open Data](https://github.com/ccao-data/wiki/blob/master/SOPs/Open-Data.md) on GitHub.  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.