---
type: domain-model-source
source: assessed_values
extends: _base.property.parcel
maps_to: fact_assessed_values
from: bronze.cook_county_assessed_values
domain_source: "'cook_county'"

aliases:
  # Available in bronze.cook_county_assessed_values:
  # pin, year, township_code, class, stage_name, av_land, av_bldg, av_tot
  - [legal_entity_id, "ABS(HASH(CONCAT('COUNTY_', 'Cook County')))"]
  - [parcel_id, "LPAD(CAST(pin AS STRING), 14, '0')"]
  - [year, year]
  - [date_id, "CAST(CONCAT(year, '0101') AS INT)"]
  - [assessment_stage, stage_name]
  - [assessed_value_land, av_land]
  - [assessed_value_building, av_bldg]
  - [assessed_value_total, av_tot]
  - [property_class, class]
  - [township_code, township_code]
---

## Assessed Values
Annual property assessed values 1999-present across assessment stages (mailed, certified, board-certified).
