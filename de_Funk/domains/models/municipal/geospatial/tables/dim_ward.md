---
type: domain-model-table
table: dim_ward
extends: _base.geography.geo_spatial._dim_boundary
table_type: dimension
primary_key: [ward_id]
unique_key: [ward_number]

schema:
  - [ward_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('CHICAGO_WARD_', boundary_code)))"}]
  - [ward_number, integer, false, "Ward number (1-50)", {derived: "CAST(boundary_code AS INT)"}]
  - [alderman, string, true, "Current alderman name"]
  - [centroid_lat, double, true, "Centroid latitude", {format: decimal}]
  - [centroid_lon, double, true, "Centroid longitude", {format: decimal}]
  - [area_sqmi, double, true, "Area in square miles", {format: decimal}]
  - [geom_wkt, string, true, "Boundary geometry as WKT"]
  - [municipality_id, integer, false, "FK to municipal.entity.dim_municipality", {fk: municipal.entity.dim_municipality.municipality_id, derived: "ABS(HASH(CONCAT('CITY_', 'Chicago')))"}]
  - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

measures:
  - [ward_count, count_distinct, ward_id, "Number of wards", {format: "#,##0"}]
---

## Ward Dimension

Chicago's 50 city wards — political districts that change with redistricting every 10 years.
