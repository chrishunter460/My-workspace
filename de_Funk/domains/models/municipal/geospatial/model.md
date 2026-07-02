---
type: domain-model
model: municipal.geospatial
version: 3.0
description: "Municipal geographic boundaries and hierarchies"
extends: [_base.geography.geo_spatial]
depends_on: [geospatial, municipal.entity]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/geospatial/

graph:
  edges:
    - [patrol_area_to_district, dim_patrol_area, dim_patrol_district, [district_id=district_id], many_to_one, null]
    - [community_to_entity, dim_community_area, municipal.entity.dim_municipality, [municipality_id=municipality_id], many_to_one, municipal.entity]
    - [ward_to_entity, dim_ward, municipal.entity.dim_municipality, [municipality_id=municipality_id], many_to_one, municipal.entity]
    - [district_to_entity, dim_patrol_district, municipal.entity.dim_municipality, [municipality_id=municipality_id], many_to_one, municipal.entity]
    - [community_to_foundation, dim_community_area, geospatial.dim_location, [location_id=location_id], many_to_one, geospatial]

build:
  partitions: []
  sort_by: [area_number, ward_number, district_id, beat_id]
  optimize: true
  phases:
    1: { tables: [dim_community_area, dim_ward, dim_patrol_district] }
    2: { tables: [dim_patrol_area] }

measures:
  simple:
    - [community_area_count, count_distinct, dim_community_area.community_area_id, "Number of community areas", {format: "#,##0"}]
    - [ward_count, count_distinct, dim_ward.ward_id, "Number of wards", {format: "#,##0"}]
    - [beat_count, count_distinct, dim_patrol_area.beat_id, "Number of patrol areas", {format: "#,##0"}]
    - [district_count, count_distinct, dim_patrol_district.district_id, "Number of patrol districts", {format: "#,##0"}]
    - [total_area_sqmi, sum, dim_community_area.area_sqmi, "Total area in square miles", {format: "#,##0.0"}]

metadata:
  domain: municipal
  subdomain: geospatial
status: active
---

## Municipal Geospatial Model

Geographic boundaries and hierarchies for a municipality. Entity sources in `sources/{entity}/` provide the boundary data.

### Geographic Units

| Unit | Count | Description |
|------|-------|-------------|
| Community Areas | 77 | Neighborhood boundaries (stable since 1920s) |
| Wards | 50 | Political districts (change with redistricting) |
| Patrol Districts | 22 | Patrol administrative districts |
| Patrol Areas | ~280 | Sub-district patrol areas |

### Hierarchy

```
City of Chicago
├── Community Areas (77) — stable for longitudinal analysis
├── Wards (50) — political representation (aldermen)
└── Patrol Hierarchy
    ├── Districts (22)
    └── Areas (~280)
```
