---
type: domain-base
model: commercial_parcel
version: 3.0
description: "Commercial property fields — auto-absorbed into _base.property.parcel wide table"
extends: _base.property.parcel
subset_of: _base.property.parcel
subset_value: COMMERCIAL

# Single source of truth for commercial fields
# These are auto-absorbed into _dim_parcel as nullable columns with {subset: COMMERCIAL}
canonical_fields:
  - [commercial_sqft, double, nullable: true, description: "Commercial floor area in square feet"]
  - [commercial_units, integer, nullable: true, description: "Number of commercial units"]
  - [residential_units, integer, nullable: true, description: "Number of residential units (mixed-use buildings)"]
  - [space_type, string, nullable: true, description: "OFFICE, RETAIL, MIXED_USE, WAREHOUSE"]
  - [floors, integer, nullable: true, description: "Number of floors"]

# Measures auto-absorbed into _dim_parcel.measures with {subset: COMMERCIAL}
measures:
  - [avg_commercial_sqft, avg, commercial_sqft, "Average commercial sq ft", {format: "#,##0"}]
  - [total_commercial_units, sum, commercial_units, "Total commercial units", {format: "#,##0"}]

domain: property
tags: [base, template, property, commercial, wide-table]
status: active
---

## Commercial Parcel Base Template

Single source of truth for commercial-specific fields. The parent `_base.property.parcel` auto-absorbs these `canonical_fields` and `measures` into `_dim_parcel` via the `subset_of` mechanism.

### Commercial Fields

| Field | Type | Description |
|-------|------|-------------|
| commercial_sqft | double | Commercial floor area in square feet |
| commercial_units | integer | Number of commercial units |
| residential_units | integer | Residential units in mixed-use buildings |
| space_type | string | OFFICE, RETAIL, MIXED_USE, WAREHOUSE |
| floors | integer | Number of floors |
