---
type: domain-model-table
table: fact_crimes
extends: _base.public_safety.crime._fact_crimes
table_type: fact
primary_key: [incident_id]
partition_by: [year]

schema:
  - [incident_id, integer, false, "PK", {derived: "ABS(HASH(case_number))"}]
  - [crime_type_id, integer, false, "FK to dim_crime_type", {fk: dim_crime_type.crime_type_id, derived: "ABS(HASH(CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))))"}]
  - [location_type_id, integer, true, "FK to dim_location_type", {fk: dim_location_type.location_type_id, derived: "ABS(HASH(COALESCE(location_description, 'UNKNOWN')))"}]
  - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"}]
  - [case_number, string, true, "CPD case number"]
  - [year, integer, false, "Incident year"]
  - [block, string, true, "Block-level address"]
  - [beat, string, true, "Police beat"]
  - [district, string, true, "Police district"]
  - [ward, integer, true, "City ward"]
  - [community_area, integer, true, "Community area number"]
  - [latitude, double, true, "Latitude", {format: decimal}]
  - [longitude, double, true, "Longitude", {format: decimal}]
  - [arrest_made, boolean, true, "Arrest was made", {default: false, derived: "arrest"}]
  - [domestic, boolean, true, "Domestic-related", {default: false}]
  - [updated_on, timestamp, true, "Last data update"]

measures:
  - [crime_count, count_distinct, incident_id, "Total crimes", {format: "#,##0"}]
  - [arrest_count, expression, "SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END)", "Crimes with arrest", {format: "#,##0"}]
  - [domestic_count, expression, "SUM(CASE WHEN domestic THEN 1 ELSE 0 END)", "Domestic crimes", {format: "#,##0"}]
  - [arrest_rate, expression, "100.0 * SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END) / COUNT(*)", "Arrest rate %", {format: "#,##0.0%"}]
---

## Crimes Fact Table

Chicago crime incidents 2001-present. Extends base crime template with Chicago-specific geography columns.
