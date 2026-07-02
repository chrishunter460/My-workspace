---
type: api-endpoint
provider: Cook County Data Portal
endpoint_id: assessor_appeals

# API Configuration
endpoint_pattern: /resource/y282-6ig3.json
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
domain: regulatory
legal_entity_type: county
subject_entity_tags: [county, property]
data_tags: [appeals, parcel, assessment, time-series]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Assessor appeals 1999-present with pre/post values. Includes open appeals."

# Storage Configuration
bronze: cook_county
partitions: [year]
write_strategy: upsert
key_columns: [pin, year]
date_column: null

# Schema
schema:
  - [pin, string, pin, false, "14-digit Parcel Index Number", {transform: "zfill(14)"}]
  - [year, int, year, false, "Assessment year"]
  - [township_code, string, township_code, true, "Township code"]
  - [class, string, class, true, "Property class code"]
  - [mailed_tot, double, mailed_tot, true, "Mailed total AV", {coerce: double}]
  - [certified_tot, double, certified_tot, true, "Certified total AV", {coerce: double}]
  - [change, string, change, true, "Change/no change decision"]
  - [reason, string, reason, true, "Appeal reason"]
---

## Description

Land, building, and total assessed values, pre and post-appeal with the Cook County Assessor’s office, for all Cook County parcels, from 1999 to present. The Assessor's Office uses these values for reporting, evaluating assessment performance over time, and research.  
  
When working with Parcel Identification Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded.  
  
This data is parcel-level. Each row contains the assessed values for a single PIN for a single year pre and post-appeal. Important notes:

- This dataset includes appeal cases that are **currently open**. Data for these cases is not final and is subject to change.
  
- Each row includes two stages: 1) mailed, these are the initial assessed values (AVs) estimated by the Assessor's Office and mailed to taxpayers. The columns mailed_bldg, mailed_land, and mailed_tot are the AVs for the building, land, and total, at the mailed stage. 2) certified, these are values after the Assessor's Office closes appeals. The columns certified_bldg, certified_land, and certified_tot are the AVs for the building, land, and total, after the Assessor has completed appeal decisions.
  
- Values in this dataset are not final assessed values for a given year as they are still subject to change if a taxpayer appeals to the Cook County Board of Review. At present, this dataset does not contain appeal decisions from this final third stage. However, the final stage AVs and appeal decisions can be downloaded from the [Board of Review Appeal Decision History](https://datacatalog.cookcountyil.gov/Property-Taxation/Board-of-Review-Appeal-Decision-History/7pny-nedm) dataset.
  
- Due to the current transition from the county's legacy system to a modern system of record, appeal data is sparse prior to 2021. Values and change/no change decisions are available, but the reason, agent, and type fields will only be complete once the new system has been successfully batch updated with complete historical data.
  
- The values in this data are assessed values, NOT market values. Assessed values must be adjusted by their [level of assessment](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf) to arrive at market value. Note that levels of assessment have changed throughout the time period covered by this data set.
  
- This data set will be updated _monthly_ regardless of the [Assessor's mailing and certification schedule](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines). There may be small discrepancies between the Assessor's site and this data set, as each pulls from a slightly different system. If you find a discrepancy, please email the Data Department using the contact link below.
  
- This dataset contains data for the current tax year, which may not yet be complete or final. Assessed values for any given year are subject to change until [review and certification of values by the Cook County Board of Review](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines), though there are a few rare circumstances where values may change for the current or past years after that.
  
- Rowcount for a given year is final once the Assessor [has certified the assessment roll](https://www.cookcountyassessor.com/assessment-calendar-and-deadlines) all townships.
  
- Current property class codes, their levels of assessment, and descriptions can be found on [the Assessor's website](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf). Note that class codes details can change across time.
  

For more information on the preparation of this dataset, see the [Assessor's Standard Operating Procedures for Open Data](https://github.com/ccao-data/wiki/blob/master/SOPs/Open-Data.md) on GitHub.  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

_**Appeals for many years are currently missing from this dataset as we repopulate our system of record with updated records. We expect all missing appeals to be available again before the end of 2025. To the best of our knowledge, appeals from 2021 and after should continue to remain available throughout the update process.**_


## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.