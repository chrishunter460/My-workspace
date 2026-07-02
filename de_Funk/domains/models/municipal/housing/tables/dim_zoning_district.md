---
type: domain-model-table
table: dim_zoning_district
extends: _base.geography.geo_spatial._dim_boundary
table_type: dimension
primary_key: [zone_class]

schema:
  - [zone_class, string, false, "Zoning classification"]
  - [zone_description, string, true, "Description"]
  - [zone_category, string, true, "Category", {derived: "CASE WHEN boundary_code LIKE 'R%' THEN 'Residential' WHEN boundary_code LIKE 'B%' THEN 'Business' WHEN boundary_code LIKE 'C%' THEN 'Commercial' WHEN boundary_code LIKE 'M%' THEN 'Manufacturing' WHEN boundary_code LIKE 'PD%' THEN 'Planned Development' ELSE 'Other' END"}]
  - [geometry, string, true, "District boundary WKT"]
---

## Zoning District Dimension

Chicago zoning classifications.
