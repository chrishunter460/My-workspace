---
type: domain-model-table
table: fact_business_licenses
extends: _base.regulatory.inspection._fact_licenses
table_type: fact
primary_key: [license_id]
partition_by: [year]

schema:
  - [license_id, integer, false, "PK", {derived: "ABS(HASH(CAST(id AS STRING)))"}]
  - [business_name, string, true, "Business name", {derived: "doing_business_as_name"}]
  - [issue_date, date, true, "Issue date", {format: date}]
  - [expiration_date, date, true, "Expiration date", {format: date}]
  - [year, integer, true, "Year issued", {derived: "YEAR(issue_date)"}]
  - [address, string, true, "Address"]
  - [ward, integer, true, "Ward"]
  - [community_area, integer, true, "Community area"]
  - [status, string, true, "License status"]
  - [license_description, string, true, "License type"]

measures:
  - [license_count, count, license_id, "Licenses", {format: "#,##0"}]
  - [active_licenses, expression, "SUM(CASE WHEN status = 'AAI' AND expiration_date > CURRENT_DATE THEN 1 ELSE 0 END)", "Active licenses", {format: "#,##0"}]
---

## Business Licenses Fact Table

Business licenses issued by the City of Chicago.
