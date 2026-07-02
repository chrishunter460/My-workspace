---
type: domain-base
model: industrial_parcel
version: 3.0
description: "Industrial property fields — auto-absorbed into _base.property.parcel wide table"
extends: _base.property.parcel
subset_of: _base.property.parcel
subset_value: INDUSTRIAL

# Single source of truth for industrial fields
# These are auto-absorbed into _dim_parcel as nullable columns with {subset: INDUSTRIAL}
canonical_fields:
  - [industrial_sqft, double, nullable: true, description: "Industrial floor area in square feet"]
  - [loading_docks, integer, nullable: true, description: "Number of loading docks"]
  - [ceiling_height, double, nullable: true, description: "Ceiling height in feet"]
  - [zoning_class, string, nullable: true, description: "Industrial zoning classification"]

# Measures auto-absorbed into _dim_parcel.measures with {subset: INDUSTRIAL}
measures:
  - [avg_industrial_sqft, avg, industrial_sqft, "Average industrial sq ft", {format: "#,##0"}]
  - [total_loading_docks, sum, loading_docks, "Total loading docks", {format: "#,##0"}]

domain: property
tags: [base, template, property, industrial, wide-table]
status: active
---

## Industrial Parcel Base Template

Single source of truth for industrial-specific fields. The parent `_base.property.parcel` auto-absorbs these `canonical_fields` and `measures` into `_dim_parcel` via the `subset_of` mechanism.

### Industrial Fields

| Field | Type | Description |
|-------|------|-------------|
| industrial_sqft | double | Industrial floor area in square feet |
| loading_docks | integer | Number of loading docks |
| ceiling_height | double | Ceiling height in feet |
| zoning_class | string | Industrial zoning classification code |
