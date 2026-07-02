---
type: domain-model-table
table: dim_patrol_area
extends: _base.geography.geo_spatial._dim_boundary
table_type: dimension
primary_key: [beat_id]
unique_key: [beat_number]

schema:
  - [beat_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('CHICAGO_BEAT_', boundary_code)))"}]
  - [beat_number, string, false, "Beat number", {derived: "boundary_code"}]
  - [district_id, integer, false, "FK to dim_patrol_district", {fk: dim_patrol_district.district_id, derived: "ABS(HASH(CONCAT('CHICAGO_DIST_', district)))"}]
  - [district_number, string, false, "Parent district number", {derived: "district"}]
  - [centroid_lat, double, true, "Centroid latitude", {format: decimal}]
  - [centroid_lon, double, true, "Centroid longitude", {format: decimal}]
  - [geom_wkt, string, true, "Boundary geometry as WKT"]
  - [municipality_id, integer, false, "FK to municipal.entity.dim_municipality", {fk: municipal.entity.dim_municipality.municipality_id, derived: "ABS(HASH(CONCAT('CITY_', 'Chicago')))"}]
  - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

measures:
  - [beat_count, count_distinct, beat_id, "Number of patrol areas", {format: "#,##0"}]
---

## Patrol Area Dimension

~280 patrol sub-areas within Chicago's patrol districts.
