---
type: domain-model-table
table: dim_facility
extends: _base.regulatory.inspection._dim_facility
table_type: dimension
transform: aggregate
from: bronze.chicago_food_inspections
group_by: [license]
primary_key: [facility_id]

schema:
  - [facility_id, integer, false, "PK", {derived: "ABS(HASH(CAST(license AS STRING)))"}]
  - [facility_code, string, false, "License number", {derived: "FIRST(CAST(license AS STRING))"}]
  - [facility_name, string, true, "Business name", {derived: "FIRST(dba_name)"}]
  - [facility_type, string, true, "Facility type", {derived: "FIRST(facility_type)"}]
  - [risk_level, string, true, "Risk level", {derived: "FIRST(risk)"}]
  - [address, string, true, "Address", {derived: "FIRST(address)"}]
  - [city, string, true, "City", {derived: "FIRST(city)"}]
  - [state, string, true, "State", {derived: "FIRST(state)"}]
  - [zip, string, true, "ZIP code", {derived: "FIRST(zip)"}]
  - [latitude, double, true, "Latitude", {derived: "FIRST(CAST(latitude AS DOUBLE))", format: decimal}]
  - [longitude, double, true, "Longitude", {derived: "FIRST(CAST(longitude AS DOUBLE))", format: decimal}]
  # ward and community_area not available in chicago_food_inspections bronze data

measures:
  - [facility_count, count_distinct, facility_id, "Facilities", {format: "#,##0"}]
---

## Facility Dimension

Food establishments aggregated by license number.
