---
type: domain-model-source
source: cta_l_ridership
extends: _base.transportation.transit
maps_to: fact_rail_ridership
from: bronze.chicago_cta_l_ridership_daily
domain_source: "'chicago'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [ridership_id, "ABS(HASH(CONCAT(stationname, '_RAIL_', CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT))))"]
  - [station_id, "ABS(HASH(CONCAT(stationname, '_', 'RAIL')))"]
  - [route_id, "null"]
  - [date_id, "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"]
  - [year, "YEAR(date)"]
  - [transit_mode, "'RAIL'"]
  - [rides, rides]
---

## CTA L Ridership
Daily station-level ridership by day type (weekday, Saturday, Sunday/holiday) since 2001.
