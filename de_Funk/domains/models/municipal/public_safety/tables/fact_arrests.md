---
type: domain-model-table
table: fact_arrests
extends: _base.public_safety.crime._fact_arrests
table_type: fact
primary_key: [arrest_id]
partition_by: [year]

schema:
  - [arrest_id, integer, false, "PK", {derived: "ABS(HASH(arrest_key))"}]
  - [incident_id, integer, true, "FK to fact_crimes", {fk: fact_crimes.incident_id}]
  - [crime_type_id, integer, false, "FK to dim_crime_type", {fk: dim_crime_type.crime_type_id, derived: "ABS(HASH(CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))))"}]
  - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(arrest_date, 'yyyyMMdd') AS INT)"}]
  - [beat, string, true, "Police beat"]
  - [district, string, true, "Police district"]
  - [ward, integer, true, "City ward"]
  - [community_area, integer, true, "Community area"]
  - [year, integer, false, "Arrest year"]
  - [arrest_key, string, true, "Unique arrest identifier"]

measures:
  - [total_arrests, count_distinct, arrest_id, "Total arrests", {format: "#,##0"}]
---

## Arrests Fact Table

Chicago arrest records linked to crime incidents.
