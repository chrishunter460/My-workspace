---
type: domain-base
model: geo_spatial
version: 1.0
description: "Spatial boundaries - community areas, wards, districts, census tracts"
extends: _base._base_.entity

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [boundary_id, integer, nullable: false, description: "Primary key"]
  - [boundary_type, string, nullable: false, description: "COMMUNITY_AREA, WARD, DISTRICT, CENSUS_TRACT, ZIP"]
  - [boundary_code, string, nullable: false, description: "Official code/number"]
  - [boundary_name, string, nullable: false, description: "Display name"]
  - [parent_boundary_id, integer, nullable: true, description: "Containing boundary (hierarchy)"]
  - [centroid_lat, double, nullable: true, description: "Centroid latitude"]
  - [centroid_lon, double, nullable: true, description: "Centroid longitude"]
  - [geom_wkt, string, nullable: true, description: "Boundary geometry as WKT"]
  - [area_sqmi, double, nullable: true, description: "Area in square miles"]
  - [population, long, nullable: true, description: "Population estimate"]

tables:
  _dim_boundary:
    type: dimension
    primary_key: [boundary_id]
    unique_key: [boundary_type, boundary_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [boundary_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(boundary_type, '_', boundary_code)))"}]
      - [boundary_type, string, false, "Classification", {enum: [COMMUNITY_AREA, WARD, DISTRICT, CENSUS_TRACT, ZIP, NEIGHBORHOOD]}]
      - [boundary_code, string, false, "Official code"]
      - [boundary_name, string, false, "Display name"]
      - [parent_boundary_id, integer, true, "Containing boundary", {fk: _dim_boundary.boundary_id}]
      - [centroid_lat, double, true, "Centroid latitude"]
      - [centroid_lon, double, true, "Centroid longitude"]
      - [geom_wkt, string, true, "Geometry (WKT)"]
      - [area_sqmi, double, true, "Area sq mi"]
      - [population, long, true, "Population"]

    measures:
      - [boundary_count, count_distinct, boundary_id, "Number of boundaries", {format: "#,##0"}]
      - [total_population, sum, population, "Total population", {format: "#,##0"}]

behaviors: []  # Pure entity — boundary dimension only

domain: geography
tags: [base, template, geography, spatial]
status: active
---

## Geo Spatial Base Template

Boundary/polygon data for spatial joins and geographic analysis. For point locations, see `geo_location.md`.

### Hierarchy

Boundaries can nest via `parent_boundary_id`:

```
City (boundary_type: CITY)
  Ward (boundary_type: WARD)
    Community Area (boundary_type: COMMUNITY_AREA)
      Census Tract (boundary_type: CENSUS_TRACT)
```

### Usage

```yaml
extends: _base.geography.geo_spatial
```
