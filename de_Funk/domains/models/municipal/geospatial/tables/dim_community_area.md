---
type: domain-model-table
table: dim_community_area
extends: _base.geography.geo_spatial._dim_boundary
table_type: dimension
primary_key: [community_area_id]
unique_key: [area_number]

schema:
  - [community_area_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('CHICAGO_CA_', boundary_code)))"}]
  - [area_number, integer, false, "Community area number (1-77)", {derived: "CAST(boundary_code AS INT)"}]
  - [community_name, string, false, "Community area name", {derived: "boundary_name"}]
  - [centroid_lat, double, true, "Centroid latitude", {format: decimal}]
  - [centroid_lon, double, true, "Centroid longitude", {format: decimal}]
  - [area_sqmi, double, true, "Area in square miles", {format: decimal}]
  - [geom_wkt, string, true, "Boundary geometry as WKT"]
  - [municipality_id, integer, false, "FK to municipal.entity.dim_municipality", {fk: municipal.entity.dim_municipality.municipality_id, derived: "ABS(HASH(CONCAT('CITY_', 'Chicago')))"}]
  - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

measures:
  - [community_area_count, count_distinct, community_area_id, "Number of community areas", {format: "#,##0"}]
  - [total_area_sqmi, sum, area_sqmi, "Total area in square miles", {format: "#,##0.0"}]
---

## Community Area Dimension

Chicago's 77 community areas — stable boundaries since the 1920s, ideal for longitudinal analysis.
