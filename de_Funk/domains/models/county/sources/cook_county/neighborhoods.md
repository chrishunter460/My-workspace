---
type: domain-model-source
source: neighborhoods
extends: _base.geography.geo_spatial
maps_to: dim_neighborhood
from: bronze.cook_county_neighborhood_boundaries
domain_source: "'cook_county'"

aliases:
  - [boundary_id, "ABS(HASH(CONCAT('NEIGHBORHOOD', '_', CAST(neighborhood_id AS STRING))))"]
  - [boundary_type, "'NEIGHBORHOOD'"]
  - [boundary_code, "CAST(neighborhood_id AS STRING)"]
  - [boundary_name, "CONCAT('Neighborhood ', CAST(neighborhood_id AS STRING))"]
  - [parent_boundary_id, "null"]
  - [nbhd_code, "CAST(neighborhood_id AS STRING)"]
  - [township_code, township_code]
  - [centroid_lat, "CAST(get_json_object(the_geom, '$.coordinates[0][0][0][1]') AS DOUBLE)"]
  - [centroid_lon, "CAST(get_json_object(the_geom, '$.coordinates[0][0][0][0]') AS DOUBLE)"]
  - [geom_wkt, the_geom]
  - [area_sqmi, "null"]
  - [population, "null"]
---

## Neighborhoods
~200 assessor-defined neighborhood boundaries used for property valuation.
