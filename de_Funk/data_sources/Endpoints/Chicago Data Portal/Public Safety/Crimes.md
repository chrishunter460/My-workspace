---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: crimes

# API Configuration
endpoint_pattern: /resource/ijzp-q8t2.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
  $order: date DESC
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: public-safety
legal_entity_type: municipal
subject_entity_tags: [municipal, individual]
data_tags: [police, geospatial, crimes, time-series]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Crime incidents 2001-present, minus most recent 7 days. Block-level only."

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [id]
date_column: date

# Schema
schema:
  - [id, string, id, false, "Unique crime identifier"]
  - [case_number, string, case_number, true, "CPD case number"]
  - [date, timestamp, date, true, "Date/time of incident", {transform: "to_timestamp(yyyy-MM-dd'T'HH:mm:ss)"}]
  - [block, string, block, true, "Block-level address"]
  - [iucr, string, iucr, true, "Illinois Uniform Crime Reporting code"]
  - [primary_type, string, primary_type, true, "Primary crime type"]
  - [description, string, description, true, "Crime description"]
  - [location_description, string, location_description, true, "Location type"]
  - [arrest, boolean, arrest, true, "Whether arrest was made"]
  - [domestic, boolean, domestic, true, "Whether domestic-related"]
  - [beat, string, beat, true, "Police beat"]
  - [district, string, district, true, "Police district"]
  - [ward, int, ward, true, "City ward"]
  - [community_area, int, community_area, true, "Community area number"]
  - [fbi_code, string, fbi_code, true, "FBI crime code"]
  - [year, int, year, true, "Year of incident"]
  - [latitude, double, latitude, true, "Latitude"]
  - [longitude, double, longitude, true, "Longitude"]
---



## Description

This dataset reflects reported incidents of crime (with the exception of murders where data exists for each victim) that occurred in the City of Chicago from 2001 to present, minus the most recent seven days. Data is extracted from the Chicago Police Department's CLEAR (Citizen Law Enforcement Analysis and Reporting) system. In order to protect the privacy of crime victims, addresses are shown at the block level only and specific locations are not identified. Should you have questions about this dataset, you may contact the Data Fulfillment and Analysis Division of the Chicago Police Department at [DFA@ChicagoPolice.org](mailto:DFA@ChicagoPolice.org). 

Disclaimer: These crimes may be based upon preliminary information supplied to the Police Department by the reporting parties that have not been verified. The preliminary crime classifications may be changed at a later date based upon additional investigation and there is always the possibility of mechanical or human error. Therefore, the Chicago Police Department does not guarantee (either expressed or implied) the accuracy, completeness, timeliness, or correct sequencing of the information and the information should not be used for comparison purposes over time. The Chicago Police Department will not be responsible for any error or omission, or for the use of, or the results obtained from the use of this information. All data visualizations on maps should be considered approximate and attempts to derive specific addresses are strictly prohibited. The Chicago Police Department is not responsible for the content of any off-site pages that are referenced by or that reference this web page other than an official City of Chicago or Chicago Police Department web page. The user specifically acknowledges that the Chicago Police Department is not responsible for any defamatory, offensive, misleading, or illegal conduct of other users, links, or third parties and that the risk of injury from the foregoing rests entirely with the user. The unauthorized use of the words "Chicago Police Department," "Chicago Police," or any colorable imitation of these words or the unauthorized use of the Chicago Police Department logo is unlawful. This web page does not, in any way, authorize such use. Data are updated daily. To access a list of Chicago Police Department - Illinois Uniform Crime Reporting (IUCR) codes, go to [http://data.cityofchicago.org/Public-Safety/Chicago-Police-Department-Illinois-Uniform-Crime-R/c7ck-438e](http://data.cityofchicago.org/Public-Safety/Chicago-Police-Department-Illinois-Uniform-Crime-R/c7ck-438e)


## Request Notes


## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.