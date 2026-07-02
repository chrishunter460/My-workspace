---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: building_permits

# API Configuration
endpoint_pattern: /resource/ydr8-5enu.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
  $order: issue_date DESC
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: housing
legal_entity_type: municipal
subject_entity_tags: [municipal, property]
data_tags: [regulatory, permits, geospatial, time-series]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Building permits from 2006-present. Excludes voided/revoked permits."

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [id]
date_column: issue_date

# Schema
schema:
  - [id, string, id, false, "Permit identifier"]
  - [permit_number, string, permit_, true, "Permit number"]
  - [permit_type, string, permit_type, true, "Type of permit"]
  - [application_start_date, date, application_start_date, true, "Application date", {transform: "to_date(yyyy-MM-dd)"}]
  - [issue_date, date, issue_date, true, "Issue date", {transform: "to_date(yyyy-MM-dd)"}]
  - [work_description, string, work_description, true, "Description of work"]
  - [street_number, string, street_number, true, "Street number"]
  - [street_direction, string, street_direction, true, "Street direction"]
  - [street_name, string, street_name, true, "Street name"]
  - [community_area, int, community_area, true, "Community area number"]
  - [ward, int, ward, true, "Ward number"]
  - [total_fee, double, total_fee, true, "Total permit fee", {coerce: double}]
  - [latitude, double, latitude, true, "Latitude"]
  - [longitude, double, longitude, true, "Longitude"]
---

## Description

**Note, 10/15/2025:** We have added a PERMIT_CONDITION column.  
  
This dataset includes information about building permits issued by the City of Chicago from 2006 to the present, excluding permits that have been voided or revoked after issuance. Most types of permits are issued subject to payment of the applicable permit fee. Work under a permit may not begin until the applicable permit fee is paid.  
  
For more information about building permits, see [http://www.chicago.gov/permit](http://www.chicago.gov/permit).

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
