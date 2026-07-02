---
type: domain-model-source
source: police_beats
extends: _base.geography.geo_spatial
maps_to: dim_patrol_area
from: bronze.chicago_police_beats
domain_source: "'chicago'"

aliases:
  - [boundary_id, "ABS(HASH(CONCAT('PATROL_AREA', '_', CAST(beat_num AS STRING))))"]
  - [boundary_type, "'PATROL_AREA'"]
  - [boundary_code, "CAST(beat_num AS STRING)"]
  - [boundary_name, "CONCAT('Beat ', CAST(beat_num AS STRING))"]
  - [parent_boundary_id, "ABS(HASH(CONCAT('PATROL_DISTRICT_', CAST(district AS STRING))))"]
  - [centroid_lat, "CAST(get_json_object(the_geom, '$.coordinates[0][0][0][1]') AS DOUBLE)"]
  - [centroid_lon, "CAST(get_json_object(the_geom, '$.coordinates[0][0][0][0]') AS DOUBLE)"]
  - [geom_wkt, the_geom]
  - [district, "CAST(district AS STRING)"]
  - [beat_code, beat]
  - [sector, sector]
  - [population, "null"]
---

## Police Beats
~280 patrol area boundaries with district hierarchy.
