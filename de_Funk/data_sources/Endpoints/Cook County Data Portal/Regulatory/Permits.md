---
type: api-endpoint
provider: Cook County Data Portal
endpoint_id: permits

# API Configuration
endpoint_pattern: /resource/6yjf-dfxs.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
  $order: date_issued DESC
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: regulatory
legal_entity_type: county
subject_entity_tags: [county, property]
data_tags: [permits, parcel, construction, time-series]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Historical permit data from municipalities. Includes open/pending permits."

# Storage Configuration
bronze: cook_county
partitions: [year]
write_strategy: upsert
key_columns: [pin, permit_number, date_issued]
date_column: date_issued

# Schema
schema:
  - [pin, string, pin, false, "14-digit Parcel Index Number", {transform: "zfill(14)"}]
  - [permit_number, string, permit_number, true, "Permit number"]
  - [date_issued, date, date_issued, true, "Issue date", {transform: "to_date(yyyy-MM-dd)"}]
  - [date_submitted, date, date_submitted, true, "Submission date", {transform: "to_date(yyyy-MM-dd)"}]
  - [work_description, string, work_description, true, "Work description"]
  - [permit_amount, double, permit_amount, true, "Permit amount", {coerce: double}]
  - [job_code, string, job_code, true, "Job code"]
  - [status, string, status, true, "Permit status (open/closed)"]
---

## Description

Historical permit data submitted by municipalities to the Cook County Assessor's Office.  
  
When working with Parcel Index Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded.  
  
Additional notes:

  
- Almost all of the data in this dataset, such as address, estimated date of completion, work description, and permit amount, is data submitted by municipalities to the CCAO. The CCAO verifies or corrects the PIN number, determines whether the work is assessable, updates the status of CCAO workflows (e.g., open or closed), and sets the recheck year.
  
  
- In addition to permits that are already closed, this dataset includes permits that are **currently open or pending**. These permits are not final and are subject to change.
  
- Data will be updated monthly.

  
- Rows are unique by the combination of "pin", "permit_number", and "date_issued".
  
- Job codes and improvement codes are not correct in all cases. Consider "work_description" to be the canonical description of the work that the permit describes.
  
- In many past cases permits have been submitted in irreconcilably different formats by different municipalities, or not at all. As such, this dataset does not represent the complete universe of permits in all municipalities, but rather represents the universe of permits that the CCAO knows about.
  
- Each row represents a parcel and a permit that is associated with that parcel. Permits may be associated with multiple parcels, and parcels may be associated with multiple permits.
  
- "date_issued" is more reliable than "date_submitted". Prefer "date_issued" when making temporal comparisons between parcels.
  
- Data for the current tax year may not yet be complete or final.
  
  
For more information on the sourcing of attached data and the preparation of this dataset, see the [Assessor's Standard Operating Procedures for Open Data](https://github.com/ccao-data/wiki/blob/master/SOPs/Open-Data.md) on GitHub.  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.