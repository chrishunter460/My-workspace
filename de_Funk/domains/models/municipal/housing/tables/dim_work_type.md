---
type: domain-model-table
table: dim_work_type
extends: _base.housing.permit._dim_work_type
table_type: dimension
transform: distinct
group_by: [work_type]
primary_key: [work_type_id]
unique_key: [work_type]

schema:
  - [work_type_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(work_type, 'UNKNOWN')))"}]
  - [work_type, string, false, "Type of work"]
  - [work_category, string, false, "Category", {derived: "CASE WHEN work_type LIKE '%RESIDENTIAL%' THEN 'Residential' WHEN work_type LIKE '%COMMERCIAL%' THEN 'Commercial' ELSE 'Other' END"}]

measures:
  - [work_type_count, count_distinct, work_type_id, "Number of work types", {format: "#,##0"}]
---

## Work Type Dimension

Distinct work types from building permits.
