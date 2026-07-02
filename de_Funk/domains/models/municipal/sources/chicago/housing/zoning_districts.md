---
type: domain-model-source
source: zoning_districts
extends: _base.geography.geo_spatial
maps_to: dim_zoning_district
from: bronze.chicago_zoning_districts
domain_source: "'chicago'"

aliases:
  - [boundary_id, "ABS(HASH(CONCAT('ZONING_DISTRICT', '_', zone_class)))"]
  - [boundary_type, "'ZONING_DISTRICT'"]
  - [boundary_code, zone_class]
  - [boundary_name, zone_type]
  - [parent_boundary_id, "null"]
  - [centroid_lat, "CAST(get_json_object(the_geom, '$.coordinates[0][0][0][1]') AS DOUBLE)"]
  - [centroid_lon, "CAST(get_json_object(the_geom, '$.coordinates[0][0][0][0]') AS DOUBLE)"]
  - [geom_wkt, the_geom]
  - [area_sqmi, shape_area]
  - [ordinance_date, ordinance_date]
  - [population, "null"]
---

## Zoning Districts
Zoning classification boundaries (residential, commercial, manufacturing, planned development).
