---
type: domain-model-table
table: dim_permit_type
extends: _base.housing.permit._dim_permit_type
table_type: dimension
transform: distinct
group_by: [permit_type]
primary_key: [permit_type_id]
unique_key: [permit_type]

schema:
  - [permit_type_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(permit_type, 'UNKNOWN')))"}]
  - [permit_type, string, false, "Type of permit"]
  - [permit_category, string, true, "Category", {derived: "CASE WHEN permit_type LIKE '%NEW%' THEN 'New Construction' WHEN permit_type LIKE '%RENOVATION%' OR permit_type LIKE '%ALTERATION%' THEN 'Alteration' WHEN permit_type LIKE '%DEMOLITION%' THEN 'Demolition' ELSE 'Other' END"}]

measures:
  - [permit_type_count, count_distinct, permit_type_id, "Number of permit types", {format: "#,##0"}]
---

## Permit Type Dimension

Distinct permit types from building permits.
