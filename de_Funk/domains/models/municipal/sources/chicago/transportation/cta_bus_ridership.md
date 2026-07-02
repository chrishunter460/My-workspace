---
type: domain-model-source
source: cta_bus_ridership
extends: _base.transportation.transit
maps_to: fact_bus_ridership
from: bronze.chicago_cta_bus_ridership_daily
domain_source: "'chicago'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [ridership_id, "ABS(HASH(CONCAT(route, '_', CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT))))"]
  - [station_id, "null"]
  - [route_id, route]
  - [date_id, "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"]
  - [year, "YEAR(date)"]
  - [transit_mode, "'BUS'"]
  - [rides, rides]
---

## CTA Bus Ridership
Daily route-level bus ridership by day type.
