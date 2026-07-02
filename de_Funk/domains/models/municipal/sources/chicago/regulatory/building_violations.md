---
type: domain-model-source
source: building_violations
extends: _base.regulatory.inspection
maps_to: fact_building_violations
from: bronze.chicago_building_violations
domain_source: "'chicago'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [violation_id, "ABS(HASH(CAST(id AS STRING)))"]
  - [violation_date, violation_date]
  - [date_id, "CAST(DATE_FORMAT(violation_date, 'yyyyMMdd') AS INT)"]
  - [last_modified_date, violation_last_modified_date]
  - [year, "YEAR(violation_date)"]
  - [violation_type, violation_code]
  - [violation_description, violation_description]
  - [status, violation_status]
  - [violation_location, violation_location]
  - [property_group, property_group]
  - [address, address]
  - [ward, "CAST(NULL AS INT)"]
  - [community_area, "CAST(NULL AS INT)"]
  - [latitude, latitude]
  - [longitude, longitude]
---

## Building Violations
Building code violation notices with status and address.
