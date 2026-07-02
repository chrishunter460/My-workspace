---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: iucr_codes

# API Configuration
endpoint_pattern: /resource/c7ck-438e.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 1000
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: public-safety
legal_entity_type: municipal
subject_entity_tags: [municipal]
data_tags: [police, reference, categorical, crimes, codes]
status: active
update_cadence: irregular
last_verified:
last_reviewed:
notes: "IUCR codes used by CPD. 400+ codes divided into Index and Non-Index offenses."

# Storage Configuration
bronze: chicago
partitions: []
write_strategy: overwrite
key_columns: [iucr]
date_column: null

# Schema
schema:
  - [iucr, string, iucr, false, "4-digit IUCR code"]
  - [primary_description, string, primary_description, true, "Primary crime category"]
  - [secondary_description, string, secondary_description, true, "Secondary crime description"]
  - [index_code, string, index_code, true, "Index code (I=Index, N=Non-Index)"]
---



## Description

Illinois Uniform Crime Reporting (IUCR) codes are four digit codes that law enforcement agencies use to classify criminal incidents when taking individual reports. These codes are also used to aggregate types of cases for statistical purposes. In Illinois, the Illinois State Police establish IUCR codes, but the agencies can add codes to suit their individual needs. The Chicago Police Department currently uses more than 400 IUCR codes to classify criminal offenses, divided into “Index” and “Non-Index” offenses. Index offenses are the offenses that are collected nation-wide by the Federal Bureaus of Investigation’s Uniform Crime Reports program to document crime trends over time (data released semi-annually), and include murder, criminal sexual assault, robbery, aggravated assault & battery, burglary, theft, motor vehicle theft, and arson. Non-index offenses are all other types of criminal incidents, including vandalism, weapons violations, public peace violations, etc.

## Request Notes


## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.