---
type: domain-model-source
source: municipalities
extends: _base.geography.geo_spatial
maps_to: dim_municipality_boundary
from: bronze.cook_county_municipalities
domain_source: "'cook_county'"

aliases:
  - [boundary_id, "ABS(HASH(CONCAT('MUNICIPALITY', '_', municipality_code)))"]
  - [boundary_type, "'MUNICIPALITY'"]
  - [boundary_code, municipality_code]
  - [boundary_name, municipality_name]
  - [parent_boundary_id, TBD]
  - [centroid_lat, TBD]
  - [centroid_lon, TBD]
  - [geom_wkt, the_geom]
  - [area_sqmi, TBD]
  - [population, TBD]
  - [geography_id, "ABS(HASH(CONCAT('COUNTY_', '17031')))"]
---

## Municipalities
130+ municipality boundaries within Cook County.
