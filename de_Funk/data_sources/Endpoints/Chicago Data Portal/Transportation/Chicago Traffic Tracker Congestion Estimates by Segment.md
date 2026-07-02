---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: traffic_congestion_segments
enabled: false  # Large multi-year CSV dataset - disabled for dev testing

# API Configuration
endpoint_pattern: /resource/{view_id}.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
required_params: [view_id]

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: transportation
legal_entity_type: municipal
subject_entity_tags: [municipal, infrastructure]
data_tags: [traffic, geospatial, time-series, congestion]
status: active
update_cadence: irregular
last_verified:
last_reviewed:
notes: "Traffic congestion by segment. Multiple view_ids for date ranges. 10-min updates."

# Storage Configuration
bronze: chicago
partitions: [year]
write_strategy: upsert
key_columns: [segmentid, time]
date_column: time

# Schema
schema:
  - [segmentid, string, segmentid, false, "Segment identifier"]
  - [street, string, street, true, "Street name"]
  - [direction, string, direction, true, "Direction of traffic"]
  - [from_street, string, from_street, true, "From street"]
  - [to_street, string, to_street, true, "To street"]
  - [length, double, length, true, "Segment length in miles", {coerce: double}]
  - [speed, double, speed, true, "Estimated speed MPH", {coerce: double}]
  - [time, timestamp, time, true, "Observation time", {transform: "to_timestamp(yyyy-MM-dd'T'HH:mm:ss)"}]
  - [bus_count, int, bus_count, true, "Number of bus observations"]
---

## Description

This dataset contains the historical estimated congestion for over 1,000 traffic segments, starting in approximately 2/28/2018 and ending 9/8/2023. Older records are in [https://data.cityofchicago.org/d/77hq-huss](https://data.cityofchicago.org/d/77hq-huss). The most recent estimates for each segment are in [https://data.cityofchicago.org/d/n4j6-wkkf](https://data.cityofchicago.org/d/n4j6-wkkf).  
  
The Chicago Traffic Tracker estimates traffic congestion on Chicago’s arterial streets (non-freeway streets) in real-time by continuously monitoring and analyzing GPS traces received from Chicago Transit Authority (CTA) buses. Two types of congestion estimates are produced every 10 minutes: 1) by Traffic Segments and 2) by Traffic Regions or Zones. Congestion estimates by traffic segments gives observed speed typically for one-half mile of a street in one direction of traffic. Traffic Segment level congestion is available for about 300 miles of principal arterials.  
  
Congestion by Traffic Region gives the average traffic condition for all arterial street segments within a region. A traffic region is comprised of two or three community areas with comparable traffic patterns. 29 regions are created to cover the entire city (except O’Hare airport area). There is much volatility in traffic segment speed. However, the congestion estimates for the traffic regions remain consistent for a relatively longer period. Most volatility in arterial speed comes from the very nature of the arterials themselves. Due to a myriad of factors, including but not limited to frequent intersections, traffic signals, transit movements, availability of alternative routes, crashes, short length of the segments, etc. Speed on individual arterial segments can fluctuate from heavily congested to no congestion and back in a few minutes.  
  
The segment speed and traffic region congestion estimates together may give a better understanding of the actual traffic conditions.

## Available Years

| Year | view_id | Format | Notes |
|----|----|----|----|
| 2024 | 4g9f-3jbs | JSON | 2024 - current |
| 2018 | sxs8-h27x | JSON | 2018 - 2023 |


## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.