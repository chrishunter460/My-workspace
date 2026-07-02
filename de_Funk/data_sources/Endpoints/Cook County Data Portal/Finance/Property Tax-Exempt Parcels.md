---
type: api-endpoint
provider: Cook County Data Portal
endpoint_id: tax_exempt_parcels

# API Configuration
endpoint_pattern: /resource/vgzx-68gb.json
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
domain: finance
legal_entity_type: county
subject_entity_tags: [county, property]
data_tags: [property-tax, parcel, exempt, geospatial]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Tax-exempt parcels from Tax Year 2022+. Religious, charitable, educational, government."

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
  - [exempt_type, string, exempt_type, true, "Exemption type"]
  - [property_address, string, property_address, true, "Property address"]
  - [latitude, double, latitude, true, "Latitude"]
  - [longitude, double, longitude, true, "Longitude"]
---

## Description

Parcels with property tax-exempt status across all of Cook County per tax year, from Tax Year 2022 on, with geographic coordinates and addresses.  
  
Properties of religious, charitable, and educational organizations, as well as units of federal, state and local governments, can be eligible for exemption from property taxes. The Illinois Department of Revenue (IDOR) ultimately grants qualified organizations with property tax exempt status, with additional administration by the Board of Review and/or Assessor. Learn more [here](https://www.cookcountyboardofreview.com/what-we-do/property-tax-exemptions), and see the Assessor's guidance for religious organizations [here](https://www.cookcountyassessor.com/exemptions-religious-institutions).  
  
When working with Parcel Index Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded.  
  
Additional notes:

- Parcel entroids are based on [Cook County parcel shapefiles](https://datacatalog.cookcountyil.gov/Property-Taxation/ccgisdata-Parcel-2021/77tz-riq7).
  
- Newer properties may be missing a mailing or property address, as they need to be assigned one by the postal service.
  
- Exempt status for parcels changes regularly depending on the use and owner of a given parcel. Please contact [Assessor.Exempt@cookcountyil.gov](mailto:Assessor.Exempt@cookcountyil.gov) if you need additional information about parcels excluded from this dataset.
  
- Data will be updated monthly.
  
- This dataset contains data for the current tax year, which may not yet be complete or final. Assessed values and property tax-exempt status for any given year are subject to change until [review and certification of values by the Cook County Board of Review](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines), though there are a few rare circumstances where values may change for the current or past years after that.
  
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