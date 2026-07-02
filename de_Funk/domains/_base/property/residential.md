---
type: domain-base
model: residential_parcel
version: 3.0
description: "Residential property fields — auto-absorbed into _base.property.parcel wide table"
extends: _base.property.parcel
subset_of: _base.property.parcel
subset_value: RESIDENTIAL

# Single source of truth for residential fields
# These are auto-absorbed into _dim_parcel as nullable columns with {subset: RESIDENTIAL}
canonical_fields:
  - [bedrooms, integer, nullable: true, description: "Number of bedrooms"]
  - [bathrooms, double, nullable: true, description: "Number of bathrooms (1.5, 2.5, etc.)"]
  - [stories, double, nullable: true, description: "Number of stories"]
  - [garage_spaces, integer, nullable: true, description: "Garage/parking spaces"]
  - [basement, string, nullable: true, description: "Basement type (FULL, PARTIAL, CRAWL, NONE)"]
  - [exterior_wall, string, nullable: true, description: "Exterior wall material"]

# Measures auto-absorbed into _dim_parcel.measures with {subset: RESIDENTIAL}
measures:
  - [avg_bedrooms, avg, bedrooms, "Average bedrooms", {format: "#,##0.0"}]
  - [avg_bathrooms, avg, bathrooms, "Average bathrooms", {format: "#,##0.0"}]

domain: property
tags: [base, template, property, residential, wide-table]
status: active
---

## Residential Parcel Base Template

Single source of truth for residential-specific fields. The parent `_base.property.parcel` auto-absorbs these `canonical_fields` and `measures` into `_dim_parcel` via the `subset_of` mechanism.

### How Auto-Absorption Works

1. This template declares `subset_of: _base.property.parcel` and `subset_value: RESIDENTIAL`
2. The parent's `subsets.pattern: wide_table` with `target_table: _dim_parcel` triggers absorption
3. Each `canonical_fields` entry becomes a nullable column on `_dim_parcel` with `{subset: RESIDENTIAL}`
4. Each `measures` entry is added to `_dim_parcel.measures` with `{subset: RESIDENTIAL}`

### Adding a Field

To add a new residential field (e.g., `pool_type`):
1. Add to `canonical_fields` above — that's it for the base layer
2. Add a source alias in the model's source file — maps bronze column name

### Residential Fields

| Field | Type | Description |
|-------|------|-------------|
| bedrooms | integer | Number of bedrooms |
| bathrooms | double | Number of bathrooms (allows 1.5, 2.5) |
| stories | double | Number of stories (allows 1.5, 2.5) |
| garage_spaces | integer | Garage or parking spaces |
| basement | string | FULL, PARTIAL, CRAWL, NONE |
| exterior_wall | string | Exterior wall material |
