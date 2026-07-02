---
type: domain-model-table
table: dim_crime_type
extends: _base.public_safety.crime._dim_crime_type
table_type: dimension
primary_key: [crime_type_id]
unique_key: [iucr_code]

schema:
  - [crime_type_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(iucr, '_', COALESCE(index_code, 'UNK'))))"}]
  - [iucr_code, string, true, "IUCR code", {derived: "iucr"}]
  - [primary_type, string, false, "Primary crime type"]
  - [description, string, true, "Detailed description"]
  - [crime_category, string, true, "Category", {derived: "CASE WHEN primary_type IN ('HOMICIDE', 'ASSAULT', 'BATTERY', 'ROBBERY') THEN 'VIOLENT' WHEN primary_type IN ('THEFT', 'BURGLARY', 'MOTOR VEHICLE THEFT') THEN 'PROPERTY' ELSE 'OTHER' END"}]
  - [is_index_crime, boolean, true, "FBI Part I", {default: false}]

measures:
  - [crime_type_count, count_distinct, crime_type_id, "Number of crime types", {format: "#,##0"}]
---

## Crime Type Dimension

Populated from Chicago IUCR codes with FBI UCR cross-reference.
