---
type: domain-model-source
source: iucr_codes
extends: _base.public_safety.crime
maps_to: dim_crime_type
from: bronze.chicago_iucr_codes
domain_source: "'chicago'"

aliases:
  - [crime_type_id, "ABS(HASH(CONCAT(iucr, '_', COALESCE(index_code, 'UNK'))))"]
  - [iucr_code, iucr]
  - [primary_type, primary_description]
  - [description, secondary_description]
  - [is_index_crime, "CASE WHEN index_code = 'I' THEN true ELSE false END"]
  - [is_active, "CASE WHEN active = 'Y' THEN true ELSE false END"]
---

## IUCR Codes
Crime type classification reference. Maps IUCR codes to categories.
