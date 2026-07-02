---
type: domain-model-source
source: building_permits
extends: _base.housing.permit
maps_to: fact_building_permits
from: bronze.chicago_building_permits
domain_source: "'chicago'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [permit_id, "ABS(HASH(CAST(permit_number AS STRING)))"]
  - [permit_number, permit_number]
  - [permit_type_id, "ABS(HASH(permit_type))"]
  - [work_type_id, "ABS(HASH(work_description))"]
  - [application_start_date, application_start_date]
  - [issue_date, issue_date]
  - [date_id, "CAST(DATE_FORMAT(issue_date, 'yyyyMMdd') AS INT)"]
  - [year, year]
  - [address, "CONCAT(COALESCE(CAST(street_number AS STRING), ''), ' ', COALESCE(street_direction, ''), ' ', COALESCE(street_name, ''))"]
  - [street_number, street_number]
  - [street_direction, street_direction]
  - [street_name, street_name]
  - [ward, ward]
  - [community_area, community_area]
  - [latitude, latitude]
  - [longitude, longitude]
  - [total_fee, total_fee]
  - [permit_type, permit_type]
  - [work_description, work_description]
---

## Building Permits
Construction, renovation, and demolition permits with fees and estimated costs.
