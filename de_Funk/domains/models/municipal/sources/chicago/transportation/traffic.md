---
type: domain-model-source
source: traffic
extends: _base.transportation.traffic
maps_to: fact_traffic
from: bronze.chicago_traffic
domain_source: "'chicago'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [segment_id, segmentid]
  - [timestamp, last_updated]
  - [date_id, "CAST(DATE_FORMAT(last_updated, 'yyyyMMdd') AS INT)"]
  - [speed, current_speed]
  - [congestion_level, "null"]
---

## Traffic
Traffic congestion data by road segment.
