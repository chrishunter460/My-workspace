---
type: api-endpoint
provider: Cook County Data Portal
endpoint_id: condo_characteristics

# API Configuration
endpoint_pattern: /resource/3r7i-mrz4.json
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
data_tags: [property-tax, residential, condominium, parcel, reference]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Condo unit characteristics 1999-present. Unit-level data. First 10 digits = building PIN."

# Storage Configuration
bronze: cook_county
partitions: [year]
write_strategy: upsert
key_columns: [pin, year]
date_column: null

# Schema
schema:
  - [pin, string, pin, false, "14-digit unit PIN", {transform: "zfill(14)"}]
  - [year, int, year, false, "Assessment year"]
  - [township_code, string, township_code, true, "Township code"]
  - [class, string, class, true, "Property class code"]
  - [pct_ownership, double, pct_ownership, true, "Percentage of ownership", {coerce: double}]
  - [unit_sf, double, unit_sf, true, "Unit square footage", {coerce: double}]
  - [building_sf, double, building_sf, true, "Building total SF", {coerce: double}]
  - [num_bedrooms, int, num_bedrooms, true, "Number of bedrooms"]
---

## Description

Residential condominium unit characteristics collected and maintained by the Assessor's office for all of Cook County, from 1999 to present. The office uses this data primarily for valuation, assessments, and reporting.  
  
When working with Parcel Index Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded.  
  
This data is unit-level. Each 14-digit PIN represents one condominium unit. The first 10 digits of each PIN are the condominium building. Additional notes:

- The Assessor's Office has historically not tracked any internal, unit-level characteristics for condominiums, including square footage, number of bedrooms, etc. In 2021, the office began to manually compile unit-level data from a variety of sources. The ultimate intention is to gather basic data on all condominium units in the county.
  
- As such, unit square footage, building total square footage, and unit number of bedrooms are only available on a per-triad basis after 2021. Future data updates will add these features for other areas.
  
- Condominiums are assessed based on their percentage of ownership. See the link below for more information on how this process works. The percentage of ownership for all units in a building should sum to 1. However, this may not always be the case in this data, since it does not include commercial units.
  
- Condominium parcels can also be parking areas, storage units, or common areas. Identifying these units can be challenging, and they are not valued using mass appraisal. The Assessor's Office has an ongoing effort to clean up and identify these unit records.
  
- Current property class codes, their levels of assessment, and descriptions can be found [on the Assessor's website](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf). Note that class codes details can change across time.
  
- Data will be updated monthly.
  
- Depending on the time of year, some third-party and internal data will be missing for the most recent year. Assessments mailed this year represent values from last year, so this isn't an issue. By the time the Data Department models values for this year, those data will have populated.
  
- Rowcount and characteristics for the current year are only final once the Assessor [has certified the assessment roll](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines) for all townships.

For more information on how this data is used to estimate condominium unit values, see the [Assessor's condominium modeling code](https://github.com/ccao-data/model-condo-avm) on GitHub.  
  
Township codes can be found [in the legend of this map](https://prodassets.cookcountyassessor.com/s3fs-public/page_comm/trimap.pdf).  
  
For more information on the sourcing of attached data and the preparation of this dataset, see the [Assessor's Standard Operating Procedures for Open Data](https://github.com/ccao-data/wiki/blob/master/SOPs/Open-Data.md) on GitHub.  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.