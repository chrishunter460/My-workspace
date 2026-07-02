---
type: api-endpoint
provider: Cook County Data Portal
endpoint_id: assessed_values

# API Configuration
endpoint_pattern: /resource/uzyt-m557.json
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
domain: finance
legal_entity_type: county
subject_entity_tags: [county, property]
data_tags: [property-tax, parcel, assessment, time-series]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Assessed values 1999-present. Three stages: mailed, certified, BOR certified."

# Storage Configuration
bronze: cook_county
partitions: [year]
write_strategy: upsert
key_columns: [pin, year, stage_name]
date_column: null

# Schema
schema:
  - [pin, string, pin, false, "14-digit Parcel Index Number", {transform: "zfill(14)"}]
  - [year, int, year, false, "Assessment year"]
  - [township_code, string, township_code, true, "Township code"]
  - [class, string, class, true, "Property class code"]
  - [stage_name, string, stage_name, true, "Assessment stage (mailed/certified/bor)"]
  - [av_land, double, av_land, true, "Land assessed value", {coerce: double}]
  - [av_bldg, double, av_bldg, true, "Building assessed value", {coerce: double}]
  - [av_tot, double, av_tot, true, "Total assessed value", {coerce: double}]
---

## Description

Land, building, and total assessed values for all Cook County parcels, from 1999 to present. The Assessor's Office uses these values for reporting, evaluating assessment performance over time, and research.  
  
When working with Parcel Index Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded.  
  
This data is parcel-level. Each row contains the assessed values for a single PIN for a single year. Important notes:

- Assessed values are available in three stages: 1) mailed, these are the initial values estimated by the Assessor's Office and mailed to taxpayers. 2) certified, these are values after the Assessor's Office closes appeals. 3) Board of Review certified, these are values after the Board of Review closes appeals.
  
- The values in this data are assessed values, NOT market values. Assessed values must be adjusted by their [level of assessment](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf) to arrive at market value. Note that levels of assessment have changed throughout the time period covered by this data set.
  
- This data set will be updated roughly contemporaneously (monthly) with the [Assessor's website](https://www.cookcountyassessor.com/) as values are mailed and certified. However, note that there may be small discrepancies between the Assessor's site and this data set, as each pulls from a slightly different system. If you find a discrepancy, please email the Data Department using the contact link below.
  
- This dataset contains data for the current tax year, which may not yet be complete or final. Assessed values for any given year are subject to change until [review and certification of values by the Cook County Board of Review](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines), though there are a few rare circumstances where values may change for the current or past years after that.
  
- Rowcount for a given year is final once the Assessor [has certified the assessment roll](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines) all townships.
  
- Current property class codes, their levels of assessment, and descriptions can be found [on the Assessor's website](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf). Note that class codes details can change across time.

For more information on the sourcing of attached data and the preparation of this dataset, see the [Assessor's Standard Operating Procedures for Open Data](https://github.com/ccao-data/wiki/blob/master/SOPs/Open-Data.md) on GitHub.  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.