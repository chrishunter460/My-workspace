---
type: domain-model-source
source: food_inspections
extends: _base.regulatory.inspection
maps_to: fact_food_inspections
from: bronze.chicago_food_inspections
domain_source: "'chicago'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [inspection_id, "ABS(HASH(CAST(inspection_id AS STRING)))"]
  - [facility_id, "ABS(HASH(CAST(license AS STRING)))"]
  - [inspection_type_id, "ABS(HASH(inspection_type))"]
  - [inspection_date, inspection_date]
  - [date_id, "CAST(DATE_FORMAT(inspection_date, 'yyyyMMdd') AS INT)"]
  - [year, year]
  - [result, results]
  - [violations, violations]
  - [address, address]
  - [license_num, license]
  - [aka_name, aka_name]
  - [city, city]
  - [state, state]
  - [zip, zip]
  - [latitude, latitude]
  - [longitude, longitude]
  - [facility_name, dba_name]
  - [facility_type, facility_type]
  - [risk_level, risk]
  - [ward, "CAST(NULL AS INT)"]
  - [inspection_type, inspection_type]
---

## Food Inspections
Inspection results for food establishments. Pass/fail/conditional outcomes with violation details.
