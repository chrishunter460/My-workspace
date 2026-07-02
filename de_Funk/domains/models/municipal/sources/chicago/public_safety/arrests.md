---
type: domain-model-source
source: arrests
extends: _base.public_safety.crime
maps_to: fact_arrests
from: bronze.chicago_arrests
domain_source: "'chicago'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [arrest_id, "ABS(HASH(CAST(cb_no AS STRING)))"]
  - [incident_id, "null"]
  - [crime_type_id, "ABS(HASH(CONCAT(charge_1_statute, '_', COALESCE(charge_1_type, 'UNK'))))"]
  - [date_id, "CAST(DATE_FORMAT(arrest_date, 'yyyyMMdd') AS INT)"]
  - [beat, beat]
  - [district, district]
  - [race, race]
  - [charge_statute, charge_1_statute]
  - [charge_description, charge_1_description]
  - [charge_type, charge_1_type]
  - [charge_class, charge_1_class]
  - [year, year]
  - [latitude, latitude]
  - [longitude, longitude]
---

## Arrests
Arrest records linked to crime incidents.
