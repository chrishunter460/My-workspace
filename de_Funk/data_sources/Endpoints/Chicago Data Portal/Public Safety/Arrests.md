---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: arrests

# API Configuration
endpoint_pattern: /resource/dpt3-jri9.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
  $order: arrest_date DESC
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: public-safety
legal_entity_type: municipal
subject_entity_tags: [municipal, individual]
data_tags: [police, geospatial, arrests, time-series]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Adult arrests only (18+). Up to 4 charges per record, ordered by severity."

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [cb_no]
date_column: arrest_date

# Schema
schema:
  - [cb_no, string, cb_no, false, "Central booking number"]
  - [arrest_date, timestamp, arrest_date, true, "Date/time of arrest", {transform: "to_timestamp(yyyy-MM-dd'T'HH:mm:ss)"}]
  - [race, string, race, true, "Race of arrestee"]
  - [charge_1_statute, string, charge_1_statute, true, "Primary charge statute"]
  - [charge_1_description, string, charge_1_description, true, "Primary charge description"]
  - [charge_1_type, string, charge_1_type, true, "Primary charge type"]
  - [charge_1_class, string, charge_1_class, true, "Primary charge class"]
  - [beat, string, beat, true, "Police beat"]
  - [district, string, district, true, "Police district"]
  - [year, int, year, true, "Year of arrest"]
  - [latitude, double, latitude, true, "Latitude"]
  - [longitude, double, longitude, true, "Longitude"]
---



## Description

Each record in this dataset shows information about an arrest executed by the Chicago Police Department (CPD). Source data comes from the CPD Automated Arrest application. This electronic application is part of the CPD CLEAR (Citizen Law Enforcement Analysis and Reporting) system, and is used to process arrests Department-wide.  
  
A more-detailed version of this dataset is available to media by request. To make a request, please email [dataportal@cityofchicago.org](mailto:dataportal@cityofchicago.org?subject=Arrests%20Access%20Request) with the subject line: **Arrests Access Request**. Access will require an account on this site, which you may create at [https://data.cityofchicago.org/signup](https://data.cityofchicago.org/signup). New data fields may be added to this public dataset in the future. Requests for individual arrest reports or any other related data other than access to the more-detailed dataset should be directed to [CPD](https://home.chicagopolice.org/services/adult-arrest-search/), through contact information on that site or a [Freedom of Information Act (FOIA)](http://www.chicago.gov/foia) request.  
  
The data is limited to adult arrests, defined as any arrest where the arrestee was 18 years of age or older on the date of arrest. The data excludes arrest records expunged by CPD pursuant to the Illinois Criminal Identification Act (20 ILCS 2630/5.2).  
  
Department members use charges that appear in Illinois Compiled Statutes or Municipal Code of Chicago. Arrestees may be charged with multiple offenses from these sources. Each record in the dataset includes up to four charges, ordered by severity and with CHARGE1 as the most severe charge. Severity is defined based on charge class and charge type, criteria that are routinely used by Illinois court systems to determine penalties for conviction. In case of a tie, charges are presented in the order that the arresting officer listed the charges on the arrest report. By policy, Department members are provided general instructions to emphasize seriousness of the offense when ordering charges on an arrest report.  
  
Each record has an additional set of columns where a charge characteristic (statute, description, type, or class) for all four charges, or fewer if there were not four charges, is concatenated with the | character. These columns can be used with the Filter function's "Contains" operator to find all records where a value appears, without having to search four separate columns.  
  
Users interested in learning more about CPD arrest processes can review current directives, using the CPD Automated Directives system ([http://directives.chicagopolice.org/directives/](http://directives.chicagopolice.org/directives/)). Relevant directives include:  
  
• Special Order S06-01-11 – CLEAR Automated Arrest System: describes the application used by Department members to enter arrest data.  
• Special Order S06-01-04 – Arrestee Identification Process: describes processes related to obtaining and using CB numbers.  
• Special Order S09-03-04 – Assignment and Processing of Records Division Numbers: describes processes related to obtaining and using RD numbers.  
• Special Order 06-01 – Processing Persons Under Department Control: describes required tasks associated with arrestee processing, include the requirement that Department members order charges based on severity.

## Request Notes


## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.