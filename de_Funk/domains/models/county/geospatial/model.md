---
type: domain-model
model: county.geospatial
version: 4.0
description: "County geospatial boundaries and hierarchies"
extends: [_base.geography.geo_spatial]
depends_on: [geospatial, municipal.entity]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/county/{entity}/geospatial/

graph:
  edges:
    - [municipality_to_township, dim_municipality_boundary, dim_township, [township_code=township_code], many_to_one, null]
    - [neighborhood_to_township, dim_neighborhood, dim_township, [township_code=township_code], many_to_one, null]
    - [township_to_geography, dim_township, geospatial.dim_geography, [geography_id=geography_id], many_to_one, geospatial]
    - [boundary_to_geography, dim_municipality_boundary, geospatial.dim_geography, [geography_id=geography_id], many_to_one, geospatial]
    - [boundary_to_entity, dim_municipality_boundary, municipal.entity.dim_municipality, [entity_municipality_id=municipality_id], many_to_one, municipal.entity]

build:
  partitions: []
  optimize: true
  phases:
    1: { tables: [dim_township] }
    2: { tables: [dim_municipality_boundary, dim_neighborhood] }

measures:
  simple:
    - [township_count, count_distinct, dim_township.township_code, "Number of townships", {format: "#,##0"}]
    - [municipality_count, count_distinct, dim_municipality_boundary.municipality_id, "Number of municipalities", {format: "#,##0"}]
    - [total_area_sqmi, sum, dim_township.area_sqmi, "Total area in square miles", {format: "#,##0.0"}]

metadata:
  domain: county
  subdomain: geospatial
status: active
---

## County Geospatial Model

Geographic boundaries and hierarchies for a county. Connected to foundation geospatial via `geography_id` FK on townships and municipality boundaries.

### Geographic Units

| Unit | Count | Description |
|------|-------|-------------|
| Townships | 38 | Property tax administration units |
| Municipalities | 130+ | Cities, villages, towns (boundary polygons) |
| Neighborhoods | ~200 | Assessor valuation areas |

### Cross-Domain Linkage

```
dim_township ──geography_id──→ geospatial.dim_geography (Cook County)
dim_municipality_boundary ──geography_id──→ geospatial.dim_geography (Cook County)
dim_municipality_boundary ──entity_municipality_id──→ municipal.entity.dim_municipality
```
