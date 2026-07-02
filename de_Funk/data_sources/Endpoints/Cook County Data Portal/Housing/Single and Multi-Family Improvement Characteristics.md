---
type: api-endpoint
provider: Cook County Data Portal
endpoint_id: residential_characteristics

# API Configuration
endpoint_pattern: /resource/x54s-btds.json
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
domain: housing
legal_entity_type: county
subject_entity_tags: [county, property]
data_tags: [property-tax, residential, parcel, characteristics, reference]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Single/multi-family (<7 units) characteristics 1999-present. Improvement-level (per building)."

# Storage Configuration
bronze: cook_county
partitions: [year]
write_strategy: upsert
key_columns: [pin, year, improvement_number]
date_column: null

# Schema
schema:
  - [pin, string, pin, false, "14-digit Parcel Index Number", {transform: "zfill(14)"}]
  - [year, int, year, false, "Assessment year"]
  - [improvement_number, int, improvement_number, true, "Building number on parcel"]
  - [township_code, string, township_code, true, "Township code"]
  - [class, string, class, true, "Property class code"]
  - [sf, double, sf, true, "Square footage", {coerce: double}]
  - [num_bedrooms, int, num_bedrooms, true, "Number of bedrooms"]
  - [num_bathrooms, double, num_bathrooms, true, "Number of bathrooms", {coerce: double}]
  - [year_built, int, year_built, true, "Year built"]
---

## Description

Single and multi-family (less than 7 units) property characteristics collected and maintained by the Assessor's Office for all of Cook County, from 1999 to present. The office uses this data primarily for valuation and reporting.  
  
When working with Parcel Index Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded.  
  
Current property class codes, their levels of assessment, and descriptions can be found [on the Assessor's website](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf). Note that class codes details can change across time.  
  
This data is improvement-level - 'improvements' are individual buildings on a parcel. Each row in a given year corresponds to a building e.g. two rows for the same parcel in one year means a parcel has more than one building.  
  
Data will be updated monthly. Rowcount and characteristics for the current year are only final once the Assessor [has certified the assessment roll](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines) for all townships.  
  
Depending on the time of year, some third-party and internal data will be missing for the most recent year. Assessments mailed this year represent values from last year, so this isn't an issue. By the time the Data Department models values for this year, those data will have populated.  
  
NOTE: The Assessor's Office has recently changed the way Home Improvement Exemptions (HIEs) are tracked in its data. HIEs "freeze" a property's characteristics for a period of time with the intention of encouraging owners to improve their property without fear of assessment increases.  
  
Historically, the updated, "improved" characteristics were saved in a separate file. However, in more recent years, the improved characteristics are saved in the main characteristics file. As such, the records in this data set from before 2021 do NOT include HIE characteristic updates, while those after and including 2021 DO include those updates.  
  
For more information on HIEs, see the [Assessor's Data Department wiki](https://github.com/ccao-data/wiki/blob/master/Residential/Home-Improvement-Exemptions.md).  
  
For more information on how this data is used to estimate property values, see the Assessor's residential modeling code on GitHub.  
  
Township codes can be found [in the legend of this map](https://prodassets.cookcountyassessor.com/s3fs-public/page_comm/trimap.pdf).  
  
For more information on the sourcing of attached data and the preparation of this dataset, see the [Assessor's Standard Operating Procedures for Open Data](https://github.com/ccao-data/wiki/blob/master/SOPs/Open-Data.md) on GitHub.  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.