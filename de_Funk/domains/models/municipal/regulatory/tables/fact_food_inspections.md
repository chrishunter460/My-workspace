---
type: domain-model-table
table: fact_food_inspections
extends: _base.regulatory.inspection._fact_inspections
table_type: fact
primary_key: [inspection_id]
partition_by: [year]

schema:
  - [inspection_id, integer, false, "PK", {derived: "ABS(HASH(CAST(inspection_id AS STRING)))"}]
  - [facility_id, integer, true, "FK to dim_facility", {fk: dim_facility.facility_id, derived: "ABS(HASH(CAST(license_ AS STRING)))"}]
  - [inspection_type_id, integer, true, "FK to dim_inspection_type", {fk: dim_inspection_type.inspection_type_id, derived: "ABS(HASH(COALESCE(inspection_type, 'UNKNOWN')))"}]
  - [inspection_date, date, true, "Inspection date", {format: date}]
  - [year, integer, true, "Year", {derived: "YEAR(inspection_date)"}]
  - [result, string, true, "Pass, Fail, Pass w/ Conditions, etc."]
  - [violations, string, true, "Violation details"]

measures:
  - [inspection_count, count, inspection_id, "Inspections", {format: "#,##0"}]
  - [pass_count, expression, "SUM(CASE WHEN result = 'Pass' THEN 1 ELSE 0 END)", "Passed", {format: "#,##0"}]
  - [fail_count, expression, "SUM(CASE WHEN result = 'Fail' THEN 1 ELSE 0 END)", "Failed", {format: "#,##0"}]
---

## Food Inspections Fact Table

Food establishment inspection results.
