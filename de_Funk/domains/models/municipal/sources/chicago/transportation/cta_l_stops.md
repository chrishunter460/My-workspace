---
type: domain-model-source
source: cta_l_stops
extends: _base.transportation.transit
maps_to: dim_transit_station
from: bronze.chicago_cta_l_stops
domain_source: "'chicago'"

aliases:
  - [station_id, "ABS(HASH(CONCAT(station_name, '_', 'RAIL')))"]
  - [station_name, station_name]
  - [transit_mode, "'RAIL'"]
  - [line_name, "'TBD'"]
  - [ada_accessible, ada]
  - [latitude, "CAST(get_json_object(location, '$.latitude') AS DOUBLE)"]
  - [longitude, "CAST(get_json_object(location, '$.longitude') AS DOUBLE)"]
---

## CTA L Stops
L train station reference data with line assignments and ADA accessibility.
