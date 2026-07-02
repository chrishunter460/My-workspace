---
type: domain-model-source
source: crimes
extends: _base.public_safety.crime
maps_to: fact_crimes
from: bronze.chicago_crimes
domain_source: "'chicago'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [incident_id, "ABS(HASH(case_number))"]
  - [case_number, case_number]
  - [date_id, "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"]
  - [year, year]
  - [block, block]
  - [beat, beat]
  - [district, district]
  - [ward, ward]
  - [community_area, community_area]
  - [latitude, latitude]
  - [longitude, longitude]
  - [arrest_made, arrest]
  - [domestic, domestic]
  - [crime_type_id, "ABS(HASH(CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))))"]
  - [location_type_id, "ABS(HASH(location_description))"]
  - [iucr_code, iucr]
  - [primary_type, primary_type]
  - [description, description]
  - [location_description, location_description]
---

## Crimes
Crime incident reports 2001-present. Includes IUCR code, location, arrest status.
