---
type: domain-model-source
source: community_areas
extends: _base.geography.geo_spatial
maps_to: dim_community_area
from: bronze.chicago_community_areas
domain_source: "'chicago'"

aliases:
  - [boundary_id, "ABS(HASH(CONCAT('COMMUNITY_AREA', '_', CAST(area_numbe AS STRING))))"]
  - [boundary_type, "'COMMUNITY_AREA'"]
  - [boundary_code, "CAST(area_numbe AS STRING)"]
  - [boundary_name, community]
  - [parent_boundary_id, "null"]
  - [centroid_lat, "CAST(get_json_object(the_geom, '$.coordinates[0][0][0][1]') AS DOUBLE)"]
  - [centroid_lon, "CAST(get_json_object(the_geom, '$.coordinates[0][0][0][0]') AS DOUBLE)"]
  - [geom_wkt, the_geom]
  - [area_sqmi, shape_area]
  - [population, "null"]
---

## Community Areas
77 community area boundaries. Static reference.
