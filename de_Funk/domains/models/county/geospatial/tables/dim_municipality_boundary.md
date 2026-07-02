---
type: domain-model-table
table: dim_municipality_boundary
extends: _base.geography.geo_spatial._dim_boundary
table_type: dimension
primary_key: [municipality_id]
optional: true

schema:
  - [municipality_id, string, false, "PK"]
  - [municipality_name, string, true, "City/village name"]
  - [municipality_type, string, true, "city, village, town, unincorporated"]
  - [township_code, string, true, "Primary township"]
  - [area_sqmi, double, true, "Area in square miles", {format: decimal}]
  - [is_chicago, boolean, true, "Is City of Chicago", {derived: "municipality_name = 'Chicago'"}]
  - [geography_id, integer, true, "FK to geospatial.dim_geography (county)", {fk: geospatial.dim_geography.geography_id, derived: "ABS(HASH(CONCAT('COUNTY_', '17031')))"}]
  - [entity_municipality_id, integer, true, "FK to municipal.entity.dim_municipality (nullable — only for tracked municipalities)", {fk: municipal.entity.dim_municipality.municipality_id}]
  - [geometry, string, true, "Municipality boundary WKT"]

measures:
  - [municipality_count, count_distinct, municipality_id, "Number of municipalities", {format: "#,##0"}]
---

## Municipality Boundary Dimension

130+ municipalities within Cook County (cities, villages, unincorporated areas). Spatial polygon boundaries — distinct from the entity `dim_municipality` which tracks legal identity.

### Linkage

- `geography_id` → `geospatial.dim_geography` (Cook County row) — ties all boundaries to the foundation geographic hierarchy
- `entity_municipality_id` → `municipal.entity.dim_municipality` — links tracked municipalities (e.g., Chicago) to their entity record. Null for municipalities not in the municipal entity federation.
