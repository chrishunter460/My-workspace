---
type: api-endpoint
provider: Cook County Data Portal
endpoint_id: parcel_universe

# API Configuration
endpoint_pattern: /resource/nj4t-kc8j.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
  $order: year DESC
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: geospatial
legal_entity_type: county
subject_entity_tags: [county, property]
data_tags: [parcel, reference, geospatial, governmental]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Complete historic parcel universe with geographic, governmental, spatial data."

# Storage Configuration
bronze: cook_county
partitions: [year]
write_strategy: upsert
key_columns: [pin, year]
date_column: null

# Schema
schema:
  - [pin, string, pin, false, "14-digit Parcel Index Number", {transform: "zfill(14)"}]
  - [year, int, year, false, "Tax year"]
  - [township_code, string, township_code, true, "Township code"]
  - [class, string, class, true, "Property class code"]
  - [municipality, string, municipality, true, "Municipality name"]
  - [school_district, string, school_district, true, "School district"]
  - [park_district, string, park_district, true, "Park district"]
  - [latitude, double, latitude, true, "Centroid latitude"]
  - [longitude, double, longitude, true, "Centroid longitude"]
---

## Description

A complete, historic universe of Cook County parcels with attached geographic, governmental, and spatial data.  
  
When working with Parcel Index Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded.  
  
Additional notes:

- Non-taxing district data is attached via spatial join (st_contains) to each parcel's centroid.
  
- Tax district data (school district, park district, municipality, etc.) are attached by a parcel's assigned tax code.
  
- Centroids are based on [Cook County parcel shapefiles](https://datacatalog.cookcountyil.gov/Property-Taxation/ccgisdata-Parcel-2021/77tz-riq7).
  
- Older properties may be missing coordinates and thus also missing attached spatial data (usually they are missing a parcel boundary in the shapefile).
  
- Newer properties may be missing a mailing or property address, as they need to be assigned one by the postal service.
  
- This dataset contains data for the current tax year, which may not yet be complete or final. Assessed values for any given year are subject to change until [review and certification of values by the Cook County Board of Review](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines), though there are a few rare circumstances where values may change for the current or past years after that.
  
- Rowcount for a given year is final once the Assessor [has certified the assessment roll](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines) all townships.
  
- Data will be updated monthly.
  
- Depending on the time of year, some third-party and internal data will be missing for the most recent year. Assessments mailed this year represent values from last year, so this isn't an issue. By the time the Data Department models values for this year, those data will have populated.
  
- Current property class codes, their levels of assessment, and descriptions can be found [on the Assessor's website](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf). Note that class codes details can change across time.
  
- Due to discrepancies between the systems used by the Assessor and Clerk's offices, _tax_district_code_ is not currently up-to-date in this table.
  
- There are currently two different sources of parcel-level municipality available in this data set, and they will not always agree: tax and spatial records. Tax records from the Cook County Clerk indicate the municipality to which a parcel owner pays taxes, while spatial records, also from the Cook County Clerk, indicate the municipal boundaries within which a parcel lies.

  
For more information on the sourcing of attached data and the preparation of this dataset, see the [Assessor's Standard Operating Procedures for Open Data](https://github.com/ccao-data/wiki/blob/master/SOPs/Open-Data.md) on GitHub.  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.