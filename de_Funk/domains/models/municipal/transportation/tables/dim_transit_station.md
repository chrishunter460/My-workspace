---
type: domain-model-table
table: dim_transit_station
extends: _base.transportation.transit._dim_transit_station
table_type: dimension
primary_key: [station_id]

schema:
  - [station_id, integer, false, "PK", {derived: "CAST(map_id AS INT)"}]
  - [station_name, string, false, "Station name", {derived: "station_descriptive_name"}]
  - [lines, string, true, "Rail lines served"]
  - [ada_accessible, boolean, true, "ADA accessible", {derived: "ada"}]
  - [latitude, double, true, "Latitude"]
  - [longitude, double, true, "Longitude"]

measures:
  - [station_count, count_distinct, station_id, "Number of stations", {format: "#,##0"}]
---

## Transit Station Dimension

CTA L train stations with line and accessibility info.
