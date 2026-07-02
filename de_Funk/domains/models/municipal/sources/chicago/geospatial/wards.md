---
type: domain-model-source
source: wards
extends: _base.geography.geo_spatial
maps_to: dim_ward
from: bronze.chicago_wards
domain_source: "'chicago'"

aliases:
  - [boundary_id, "ABS(HASH(CONCAT('WARD', '_', CAST(ward AS STRING))))"]
  - [boundary_type, "'WARD'"]
  - [boundary_code, "CAST(ward AS STRING)"]
  - [boundary_name, "CONCAT('Ward ', CAST(ward AS STRING))"]
  - [parent_boundary_id, "null"]
  - [centroid_lat, "CAST(get_json_object(the_geom, '$.coordinates[0][0][0][1]') AS DOUBLE)"]
  - [centroid_lon, "CAST(get_json_object(the_geom, '$.coordinates[0][0][0][0]') AS DOUBLE)"]
  - [geom_wkt, the_geom]
  - [area_sqmi, st_area_sh]
  - [population, "null"]
---

## Wards
50 ward boundaries. Updated on redistricting cycles.
