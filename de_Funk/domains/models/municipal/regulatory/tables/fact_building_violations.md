---
type: domain-model-table
table: fact_building_violations
extends: _base.regulatory.inspection._fact_violations
table_type: fact
primary_key: [violation_id]
partition_by: [year]

schema:
  - [violation_id, integer, false, "PK", {derived: "ABS(HASH(CAST(id AS STRING)))"}]
  - [violation_date, date, true, "Violation date", {format: date}]
  - [year, integer, true, "Year", {derived: "YEAR(violation_date)"}]
  - [address, string, true, "Address"]
  - [ward, integer, true, "Ward"]
  - [community_area, integer, true, "Community area"]
  - [status, string, true, "Open, Closed, Complied"]

measures:
  - [violation_count, count, violation_id, "Violations", {format: "#,##0"}]
---

## Building Violations Fact Table

Building code violations.
