---
type: api-endpoint
provider: Cook County Data Portal
endpoint_id: parcel_addresses

# API Configuration
endpoint_pattern: /resource/3723-97qp.json
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
data_tags: [parcel, address, reference]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Situs and mailing addresses. WARNING: Mailing addresses not updated since 2017."

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
  - [property_address, string, property_address, true, "Situs address"]
  - [property_city, string, property_city, true, "City"]
  - [property_zip, string, property_zip, true, "ZIP code"]
  - [mailing_address, string, mailing_address, true, "Mailing address (may be outdated)"]
  - [mailing_city, string, mailing_city, true, "Mailing city"]
  - [mailing_state, string, mailing_state, true, "Mailing state"]
  - [mailing_zip, string, mailing_zip, true, "Mailing ZIP"]
---

## Description

Situs and mailing addresses of Cook County parcels. Used by the Assessor's office to mail assessment notices.  
  
_**As of 2017 mailing addresses in this dataset are no longer being regularly updated. We are trying to figure out a solution to this problem.**_  
  
When working with Parcel Index Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded.  
  
Additional notes:  

- Mailing addresses can be out of date or fail to properly reflect deed transfers.
  
- Newer properties may be missing a mailing or property address, as they need to be assigned one by the postal service.
  
- This dataset contains data for the current tax year, which may not yet be complete or final. Assessed values for any given year are subject to change until [review and certification of values by the Cook County Board of Review](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines), though there are a few rare circumstances where values may change for the current or past years after that.
  
- Rowcount for a given year is final once the Assessor [has certified the assessment roll](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines) all townships.
  
- Data will be updated monthly.

For more information on the sourcing of attached data and the preparation of this dataset, see the [Assessor's Standard Operating Procedures for Open Data](https://github.com/ccao-data/wiki/blob/master/SOPs/Open-Data.md) on GitHub.  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.