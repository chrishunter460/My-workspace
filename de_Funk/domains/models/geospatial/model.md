---
type: domain-model
model: geospatial
version: 4.0
description: "Foundation geographic reference — US administrative regions and point locations"
extends: _base.geography.geo_spatial
depends_on: []

sources_from: sources/
storage:
  format: delta
  silver:
    root: storage/silver/geospatial/

graph:
  edges:
    - [geography_hierarchy, dim_geography, dim_geography, [parent_geography_id=geography_id], many_to_one, null]

build:
  optimize: true
  phases:
    1: { tables: [dim_geography, dim_location] }

metadata:
  domain: geospatial
  owner: data_engineering
status: active
---

## Geospatial Model

Foundation geographic reference for all spatial analysis. Two clean dimensions:

- **dim_geography** — US administrative regions (states, counties) in a single denormalized table with self-referencing hierarchy
- **dim_location** — Point locations (addresses, coordinates) used by event facts via `location_id` FK

Other models link TO geospatial via `geography_id` (administrative regions) or `location_id` (point locations).
