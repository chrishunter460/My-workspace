---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: cta_l_ridership_daily

# API Configuration
endpoint_pattern: /resource/5neh-572f.json
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
domain: transportation
legal_entity_type: municipal
subject_entity_tags: [municipal, infrastructure]
data_tags: [transit, ridership, time-series, cta]
status: active
update_cadence: irregular
last_verified:
last_reviewed:
notes: "Daily L station ridership since 2001. W=Weekday, A=Saturday, U=Sunday/Holiday."

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [station_id, date]
date_column: date

# Schema
schema:
  - [station_id, string, station_id, false, "Station identifier"]
  - [stationname, string, stationname, true, "Station name"]
  - [date, date, date, true, "Date", {transform: "to_date(MM/dd/yyyy)"}]
  - [daytype, string, daytype, true, "Day type (W/A/U)"]
  - [rides, long, rides, true, "Total station entries", {coerce: long}]
---

## Description

This list shows daily totals of ridership, by station entry, for each 'L' station dating back to 2001. Dataset shows entries at all turnstiles, combined, for each station. Daytypes are as follows: W=Weekday, A=Saturday, U=Sunday/Holiday. See attached readme file for information on how these numbers are calculated.

Chicago Transit Authority

* About CTA ridership numbers *
Ridership statistics are provided on a system-wide and bus route/station-level basis. Ridership is primarily counted as boardings, that is, customers boarding a transit vehicle (bus or rail).  On the rail system, there is a distinction between station entries and total rides, or boardings. Datasets indicate such in their file name and description.

* How people are counted on the 'L' *
On the rail system, a customer is counted as an "entry" each time he or she passes through a turnstile to enter a station.  Customers are not counted as "entries" when they make a "cross-platform" transfer from one rail line to another, since they don't pass through a turnstile. Where the number given for rail is in "boardings," what's presented is a statistically valid estimate of the actual number of boardings onto the rail system. 

* How people are counted on buses *
Boardings are recorded using the bus farebox and farecard reader. In the uncommon situation when there is an operating error with the farebox and the onboard systems cannot determine on which route a given trip's boardings should be allocated, these boardings are tallied as Route 0 in some reports.  Route 1001 are shuttle buses used for construction or other unforeseen events.

* "Daytype" *
Daytype fields in the data are coded as "W" for Weekday, "A" for Saturday and "U" for Sunday/Holidays.  Note that New Year's Day, Memorial Day, Independence Day, Labor Day, Thanksgiving, and Christmas Day are considered as "Sundays" for the purposes of ridership reporting.  All other holidays are reported as the type of day they fall on.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.