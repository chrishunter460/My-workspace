---
type: domain-model-table
table: fact_building_permits
extends: _base.housing.permit._fact_permits
table_type: fact
primary_key: [permit_id]
partition_by: [year]

schema:
  - [permit_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(permit_, 'UNKNOWN')))"}]
  - [permit_number, string, true, "Permit number", {derived: "permit_"}]
  - [permit_type_id, integer, true, "FK to dim_permit_type", {fk: dim_permit_type.permit_type_id, derived: "ABS(HASH(COALESCE(permit_type, 'UNKNOWN')))"}]
  - [work_type_id, integer, true, "FK to dim_work_type", {fk: dim_work_type.work_type_id, derived: "ABS(HASH(COALESCE(work_type, 'UNKNOWN')))"}]
  - [issue_date, date, true, "Date issued", {format: date}]
  - [year, integer, true, "Year issued", {derived: "YEAR(issue_date)"}]
  - [address, string, true, "Street address"]
  - [ward, integer, true, "City ward"]
  - [community_area, integer, true, "Community area number"]
  - [total_fee, "decimal(18,2)", true, "Permit fees collected", {format: $}]
  - [estimated_cost, "decimal(18,2)", true, "Estimated construction cost", {format: $}]
  - [latitude, double, true, "Latitude", {format: decimal}]
  - [longitude, double, true, "Longitude", {format: decimal}]

measures:
  - [permit_count, count, permit_id, "Number of permits", {format: "#,##0"}]
  - [total_fees, sum, total_fee, "Total fees", {format: "$#,##0"}]
  - [total_estimated_cost, sum, estimated_cost, "Total estimated cost", {format: "$#,##0"}]
---

## Building Permits Fact Table

Building permits issued by the City of Chicago.
