---
type: domain-model-table
table: dim_property_class
extends: _base.property.parcel._dim_property_class
table_type: dimension
transform: distinct
from: bronze.cook_county_assessed_values
group_by: [class]
primary_key: [property_class_id]
unique_key: [property_class_code]

schema:
  - [property_class_id, string, false, "PK - Property class code", {derived: "class"}]
  - [property_class_code, string, false, "Natural key (classification code)", {derived: "class"}]
  - [property_class_name, string, true, "Class description", {derived: "class"}]
  - [property_category, string, true, "Category rollup", {derived: "CASE WHEN class BETWEEN '200' AND '299' THEN 'RESIDENTIAL' WHEN class BETWEEN '500' AND '599' THEN 'COMMERCIAL' WHEN class BETWEEN '300' AND '399' THEN 'INDUSTRIAL' WHEN class IN ('0', '000', 'EX') THEN 'EXEMPT' ELSE 'OTHER' END", enum: [RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER]}]
  - [applicable_fields, string, true, "Subset fields populated for this class", {derived: "CASE WHEN class BETWEEN '200' AND '299' THEN 'bedrooms,bathrooms,stories,garage_spaces,basement,exterior_wall' WHEN class BETWEEN '500' AND '599' THEN 'commercial_sqft,commercial_units,residential_units,space_type,floors' WHEN class BETWEEN '300' AND '399' THEN 'industrial_sqft,loading_docks,ceiling_height,zoning_class' ELSE NULL END"}]
---

## Property Class Dimension (Field Dictionary)

Distinct property classification codes derived from assessed values data. Serves as the **field dictionary** for the wide `dim_parcel` table — `applicable_fields` tells the UI/query layer which subset columns are populated for each property class.

### Category Mapping (Cook County)

Cook County uses 3-digit numeric class codes. The `property_category` column rolls these into 5 standard categories:

| Code Range | Category | Applicable Fields |
|-----------|----------|-------------------|
| 200-299 | RESIDENTIAL | bedrooms, bathrooms, stories, garage_spaces, basement, exterior_wall |
| 300-399 | INDUSTRIAL | industrial_sqft, loading_docks, ceiling_height, zoning_class |
| 500-599 | COMMERCIAL | commercial_sqft, commercial_units, residential_units, space_type, floors |
| 0, 000, EX | EXEMPT | (none) |
| All other | OTHER | (none) |

### Source

Derived from `fact_assessed_values.property_class` using `SELECT DISTINCT class`. No separate source file — this is a data-derived dimension.
