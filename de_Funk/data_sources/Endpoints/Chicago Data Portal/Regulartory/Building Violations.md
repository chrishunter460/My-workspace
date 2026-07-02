---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: building_violations

# API Configuration
endpoint_pattern: /resource/22u3-xenr.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
  $order: violation_date DESC
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: regulatory
legal_entity_type: municipal
subject_entity_tags: [municipal, property]
data_tags: [violation, inspection, geospatial, time-series]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Building violations from 2006-present. Historical data, not for real estate transactions."

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [id]
date_column: violation_date

# Schema
schema:
  - [id, string, id, false, "Violation identifier"]
  - [violation_last_modified_date, date, violation_last_modified_date, true, "Last modified", {transform: "to_date(yyyy-MM-dd)"}]
  - [violation_date, date, violation_date, true, "Violation date", {transform: "to_date(yyyy-MM-dd)"}]
  - [violation_code, string, violation_code, true, "Violation code"]
  - [violation_status, string, violation_status, true, "Violation status"]
  - [violation_description, string, violation_description, true, "Description"]
  - [violation_location, string, violation_location, true, "Location description"]
  - [property_group, string, property_group, true, "Property group"]
  - [address, string, address, true, "Property address"]
  - [latitude, double, latitude, true, "Latitude"]
  - [longitude, double, longitude, true, "Longitude"]
---



## Description
Violations issued by the Department of Buildings from 2006 to the present. Lenders and title companies, please note: These data are historical in nature and should not be relied upon for real estate transactions. For transactional purposes such as closings, please consult the title commitment for outstanding enforcement actions in the Circuit Court of Cook County or the Chicago Department of Administrative Hearings. Violations are always associated to an inspection and there can be multiple violation records to one inspection record. Related Applications: Building Data Warehouse [http://www.cityofchicago.org/city/en/depts/bldgs/provdrs/inspect/svcs/building_violationsonline.html](http://www.cityofchicago.org/city/en/depts/bldgs/provdrs/inspect/svcs/building_violationsonline.html). The information presented on this website is informational only and does not necessarily reflect the current condition of the building or property. The dataset contains cases where a respondent has been found to be liable as well as cases where the respondent has been found to be not liable.


## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
