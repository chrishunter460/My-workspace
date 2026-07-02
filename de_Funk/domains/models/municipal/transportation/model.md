---
type: domain-model
model: municipal.transportation
version: 3.0
description: "Municipal transit ridership and traffic data"
extends: [_base.transportation.transit, _base.transportation.traffic]
depends_on: [temporal, municipal.geospatial]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/transportation/

graph:
  # auto_edges: date_id→calendar (inherited from _base.transportation.transit via event)
  edges:
    - [rail_ridership_to_station, fact_rail_ridership, dim_transit_station, [station_id=station_id], many_to_one, null]

build:
  partitions: [year]
  optimize: true
  phases:
    1: { tables: [dim_transit_station] }
    2: { tables: [fact_rail_ridership, fact_bus_ridership, fact_traffic] }

measures:
  simple:
    - [total_rail_rides, sum, fact_rail_ridership.rides, "Total rail station entries", {format: "#,##0"}]
    - [avg_daily_rides, avg, fact_rail_ridership.rides, "Avg daily ridership", {format: "#,##0"}]
    - [station_count, count_distinct, dim_transit_station.station_id, "Number of transit stations", {format: "#,##0"}]
  computed:
    - [rides_per_station, expression, "total_rail_rides / station_count", "Rides per station", {format: "#,##0"}]

federation:
  enabled: true
  union_key: domain_source

metadata:
  domain: municipal
  subdomain: transportation
status: active
---

## Municipal Transportation Model

Transit ridership and traffic data.

### Notes

- L counts are station entries (turnstile passes), not boardings
