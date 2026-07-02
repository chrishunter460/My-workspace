---
type: domain-model-table
table: dim_township
extends: _base.geography.geo_spatial._dim_boundary
table_type: dimension
primary_key: [township_code]
optional: true

schema:
  - [township_code, string, false, "PK - 2-digit township code"]
  - [township_name, string, true, "Township name"]
  - [centroid_lat, double, true, "Centroid latitude", {format: decimal}]
  - [centroid_lon, double, true, "Centroid longitude", {format: decimal}]
  - [area_sqmi, double, true, "Area in square miles", {format: decimal}]
  - [geography_id, integer, true, "FK to geospatial.dim_geography (Cook County)", {fk: geospatial.dim_geography.geography_id, derived: "ABS(HASH(CONCAT('COUNTY_', '17031')))"}]
  - [geometry, string, true, "Township boundary WKT"]

measures:
  - [township_count, count_distinct, township_code, "Number of townships", {format: "#,##0"}]
---

## Township Dimension

Cook County's 38 townships — property tax administration units.
