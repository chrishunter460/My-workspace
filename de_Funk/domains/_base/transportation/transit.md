---
type: domain-base
model: transit
version: 1.1
description: "Public transit - stations, routes, and ridership data"
extends: _base._base_.event

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [station_id, integer, nullable: false, description: "PK for transit stations"]
  - [legal_entity_id, integer, nullable: true, description: "FK to owning transit authority"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [station_name, string, nullable: false, description: "Station display name"]
  - [transit_mode, string, nullable: false, description: "RAIL, BUS, SUBWAY, FERRY, LIGHT_RAIL"]
  - [line_name, string, nullable: true, description: "Route/line name(s)"]
  - [ada_accessible, boolean, nullable: true, description: "ADA accessible"]
  - [latitude, double, nullable: true, description: "Station latitude"]
  - [longitude, double, nullable: true, description: "Station longitude"]
  - [location_id, integer, nullable: true, description: "FK to geo_location._dim_location"]
  - [route_id, string, nullable: true, description: "Route identifier"]
  - [route_name, string, nullable: true, description: "Route display name"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar"]
  - [rides, long, nullable: false, description: "Ridership count"]

tables:
  _dim_transit_station:
    type: dimension
    primary_key: [station_id]
    unique_key: [station_name, transit_mode]

    # [column, type, nullable, description, {options}]
    schema:
      - [station_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(station_name, '_', transit_mode)))"}]
      - [station_name, string, false, "Display name"]
      - [transit_mode, string, false, "Mode", {enum: [RAIL, BUS, SUBWAY, FERRY, LIGHT_RAIL]}]
      - [line_name, string, true, "Route/line(s) served"]
      - [ada_accessible, boolean, true, "ADA accessible"]
      - [latitude, double, true, "Station latitude"]
      - [longitude, double, true, "Station longitude"]
      - [location_id, integer, true, "FK to geo_location._dim_location", {fk: "geo_location._dim_location.location_id", derived: "CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN ABS(HASH(CONCAT(CAST(latitude AS STRING), '_', CAST(longitude AS STRING)))) ELSE null END"}]
      - [is_active, boolean, false, "Currently operational", {default: true}]

    measures:
      - [station_count, count_distinct, station_id, "Number of stations", {format: "#,##0"}]

  _fact_ridership:
    type: fact
    primary_key: [ridership_id]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [ridership_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(COALESCE(CAST(station_id AS STRING), route_id), '_', CAST(date_id AS STRING))))"}]
      - [legal_entity_id, integer, true, "FK to owning transit authority"]
      - [domain_source, string, false, "Origin domain"]
      - [station_id, integer, true, "FK to _dim_transit_station (null for bus)", {fk: _dim_transit_station.station_id}]
      - [route_id, string, true, "Route identifier (null for rail)"]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [location_id, integer, true, "FK to geo_location._dim_location (from station lat/lon)", {fk: "geo_location._dim_location.location_id"}]
      - [year, integer, false, "Ridership year"]
      - [transit_mode, string, false, "RAIL, BUS, etc."]
      - [rides, long, false, "Ridership count"]

    measures:
      - [total_rides, sum, rides, "Total ridership", {format: "#,##0"}]
      - [avg_daily_rides, avg, rides, "Avg daily ridership", {format: "#,##0"}]

graph:
  # auto_edges inherited: date_id→calendar, location_id→location
  edges:
    - [ridership_to_station, _fact_ridership, _dim_transit_station, [station_id=station_id], many_to_one, null]

subsets:
  discriminator: _dim_transit_station.transit_mode
  description: "Transit ridership can be subset by transit mode"
  values:
    RAIL:
      description: "Heavy rail / metro"
      filter: "transit_mode = 'RAIL'"
    BUS:
      description: "Bus routes"
      filter: "transit_mode = 'BUS'"
    SUBWAY:
      description: "Underground rail"
      filter: "transit_mode = 'SUBWAY'"
    LIGHT_RAIL:
      description: "Streetcar / tram"
      filter: "transit_mode = 'LIGHT_RAIL'"
    FERRY:
      description: "Water transit"
      filter: "transit_mode = 'FERRY'"

behaviors:
  - temporal        # Inherited from event
  - geo_locatable   # Inherited from event
  - subsettable     # Has subsets: block (transit_mode discriminator)

domain: transportation
tags: [base, template, transportation, transit, ridership]
status: active
---

## Transit Base Template

Public transit ridership data. Supports multiple transit modes (rail, bus, subway) via the `transit_mode` discriminator on the fact table.

### Inherited from Event Base

| Field | Nullable | Purpose |
|-------|----------|---------|
| `legal_entity_id` | yes | FK to transit authority entity |
| `date_id` | no | FK to temporal.dim_calendar |
| `location_id` | yes | FK to geo_location._dim_location (from station lat/lon) |

### Transit Modes

| Mode | Description | Key |
|------|-------------|-----|
| RAIL | Heavy rail / metro | station_id |
| BUS | Bus routes | route_id |
| SUBWAY | Underground rail | station_id |
| LIGHT_RAIL | Streetcar / tram | station_id |
| FERRY | Water transit | station_id |

### Usage

```yaml
extends: _base.transportation.transit
```
