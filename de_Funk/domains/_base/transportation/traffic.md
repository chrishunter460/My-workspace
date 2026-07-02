---
type: domain-base
model: traffic
version: 1.1
description: "Road traffic - segment speed, congestion, and flow observations"
extends: _base._base_.event

depends_on: [temporal]

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [segment_id, string, nullable: false, description: "Road segment identifier"]
  - [legal_entity_id, integer, nullable: true, description: "FK to owning jurisdiction"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [timestamp, timestamp, nullable: false, description: "Observation time"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar"]
  - [location_id, integer, nullable: true, description: "FK to geo_location._dim_location (segment centroid)"]
  - [speed, double, nullable: true, description: "Observed speed"]
  - [congestion_level, string, nullable: true, description: "Congestion classification"]

tables:
  _fact_traffic:
    type: fact
    primary_key: [segment_id, timestamp]

    # [column, type, nullable, description, {options}]
    schema:
      - [segment_id, string, false, "Road segment identifier"]
      - [legal_entity_id, integer, true, "FK to owning jurisdiction"]
      - [domain_source, string, false, "Origin domain"]
      - [timestamp, timestamp, false, "Observation time"]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(timestamp, 'yyyyMMdd') AS INT)"}]
      - [location_id, integer, true, "FK to geo_location._dim_location", {fk: "geo_location._dim_location.location_id"}]
      - [speed, double, true, "Observed speed"]
      - [congestion_level, string, true, "Congestion classification"]

    measures:
      - [avg_speed, avg, speed, "Average speed", {format: "#,##0.0"}]

graph:
  # auto_edges inherited: date_id→calendar, location_id→location
  edges: []

behaviors:
  - temporal        # Inherited from event
  - geo_locatable   # Inherited from event

domain: transportation
tags: [base, template, transportation, traffic, congestion]
status: active
---

## Traffic Base Template

Road traffic observations — segment-level speed and congestion data.

### Inherited from Event Base

| Field | Nullable | Purpose |
|-------|----------|---------|
| `legal_entity_id` | yes | FK to jurisdiction |
| `date_id` | no | FK to temporal.dim_calendar |
| `location_id` | yes | FK to geo_location._dim_location (segment centroid) |

### Traffic vs Transit

| | Traffic | Transit |
|---|---------|--------|
| **Subject** | Road segments | Stations / routes |
| **Grain** | Per-segment per-timestamp | Per-station/route per-day |
| **Metrics** | Speed, congestion | Ridership count |

### Usage

```yaml
extends: _base.transportation.traffic
```
