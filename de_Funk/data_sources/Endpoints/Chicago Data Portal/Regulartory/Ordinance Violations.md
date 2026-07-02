---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: ordinance_violations

# API Configuration
endpoint_pattern: /resource/6br9-quuz.json
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
data_tags: [violation, ordinance, geospatial, time-series, administrative]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Ordinance violations filed with Dept of Administrative Hearings. Currently includes Dept of Buildings violations."

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [case_id, violation_code]
date_column: violation_date

# Schema
schema:
  - [case_id, string, case_id, false, "Case identifier"]
  - [case_number, string, case_number, true, "Case number"]
  - [violation_code, string, violation_code, true, "Violation code"]
  - [violation_description, string, violation_description, true, "Violation description"]
  - [violation_date, date, violation_date, true, "Violation date", {transform: "to_date(yyyy-MM-dd)"}]
  - [respondent, string, respondent, true, "Respondent (pipe-separated if multiple)"]
  - [address, string, address, true, "Property address"]
  - [disposition, string, disposition, true, "Case disposition"]
  - [disposition_date, date, disposition_date, true, "Disposition date", {transform: "to_date(yyyy-MM-dd)"}]
  - [fine_amount, double, fine_amount, true, "Fine amount", {coerce: double}]
  - [latitude, double, latitude, true, "Latitude"]
  - [longitude, double, longitude, true, "Longitude"]
---

## Description

List of ordinance violations filed with the Department of Administrative Hearings. This data set reflects violations brought before the Chicago Department of Administrative Hearings. It does not reflect violations brought before the Circuit Court of Cook County. Each row of data represents a unique violation. Multiple violations may be associated with a single case. The most recent status of the case is shown in the dataset and is updated daily. Hearing date corresponds to the date of the most recent hearing. Each case often consists of multiple hearings and may encounter continuances due to various circumstances before a final disposition is rendered. The case disposition, date of the disposition, and any applicable fines and administrative costs are listed when the case is fully completed. The latest hearing status or disposition reflects the condition of the property at that time and may not reflect the current condition of the property. When multiple respondents are cited, each respondent is separated by a pipe ("|") character. Respondents sometimes are added to cases for technical legal reasons so are not necessarily the parties believed to have committed the violations. This dataset currently lists violations issued by the Department of Buildings. Additional ordinance violations will be added over time. Therefore, it is advisable to use the department-specific filtered view listed under the More Views button for purposes that require only one department's violations.

**Note: For questions related to a specific violation or code requirements, please contact the department that issued the violation notice. For questions regarding the hearings process, a hearing date, or a hearing disposition, please contact the Department of Administrative Hearings.** Contact information can be found under "Government" at the top of [https://www.chicago.gov](https://www.chicago.gov/). For questions related to using the dataset, please use the Contact Dataset Owner button below.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.