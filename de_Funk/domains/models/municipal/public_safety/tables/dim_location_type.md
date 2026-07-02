---
type: domain-model-table
table: dim_location_type
extends: _base.public_safety.crime._dim_location_type
table_type: dimension
transform: distinct
group_by: [location_description]
primary_key: [location_type_id]
unique_key: [location_description]

schema:
  - [location_type_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(location_description, 'UNKNOWN')))"}]
  - [location_description, string, false, "Location description"]
  - [location_category, string, true, "Grouped category"]

measures:
  - [location_type_count, count_distinct, location_type_id, "Number of location types", {format: "#,##0"}]
---

## Location Type Dimension

Distinct location descriptions extracted from crime incidents.

### Not Geographic

`dim_location_type` classifies the *type* of place (STREET, APARTMENT, SIDEWALK, PARKING LOT, etc.), not the *where*. Geographic analysis for crimes uses:
- `ward` / `community_area` / `district` columns → geo dimension edges
- `latitude` / `longitude` → `location_id` FK to `geo_location._dim_location` (root event base)

This dimension answers "what kind of place?" not "where?"
