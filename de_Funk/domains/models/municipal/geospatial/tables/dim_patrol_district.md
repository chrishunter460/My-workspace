---
type: domain-model-table
table: dim_patrol_district
extends: _base.geography.geo_spatial._dim_boundary
table_type: dimension
primary_key: [district_id]
unique_key: [district_number]

schema:
  - [district_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('CHICAGO_DIST_', boundary_code)))"}]
  - [district_number, string, false, "District number", {derived: "boundary_code"}]
  - [district_name, string, true, "District name", {derived: "boundary_name"}]
  - [centroid_lat, double, true, "Centroid latitude", {format: decimal}]
  - [centroid_lon, double, true, "Centroid longitude", {format: decimal}]
  - [area_sqmi, double, true, "Area in square miles", {format: decimal}]
  - [geom_wkt, string, true, "Boundary geometry as WKT"]
  - [municipality_id, integer, false, "FK to municipal.entity.dim_municipality", {fk: municipal.entity.dim_municipality.municipality_id, derived: "ABS(HASH(CONCAT('CITY_', 'Chicago')))"}]
  - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

measures:
  - [district_count, count_distinct, district_id, "Number of patrol districts", {format: "#,##0"}]
---

## Patrol District Dimension

Chicago's 22 patrol administrative districts.
