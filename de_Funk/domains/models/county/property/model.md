---
type: domain-model
model: county.property
version: 4.0
description: "County property assessments, parcels, and sales"
extends:
  - _base.property.parcel
  - _base.property.tax_district
depends_on: [temporal, county.geospatial]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/county/{entity}/property/

graph:
  # auto_edges: date_id→calendar (inherited from _base.property.parcel)
  edges:
    - [assessed_to_parcel, fact_assessed_values, dim_parcel, [parcel_id=parcel_id], many_to_one, null]
    - [assessed_to_calendar, fact_assessed_values, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
    - [sales_to_parcel, fact_parcel_sales, dim_parcel, [parcel_id=parcel_id], many_to_one, null]
    - [sales_to_calendar, fact_parcel_sales, temporal.dim_calendar, [sale_date_id=date_id], many_to_one, temporal]
    - [parcel_to_township, dim_parcel, county.geospatial.dim_township, [township_code=township_code], many_to_one, county.geospatial]
    - [parcel_to_tax_district, dim_parcel, dim_tax_district, [tax_code=tax_code], many_to_one, null]
    - [parcel_to_property_class, dim_parcel, dim_property_class, [property_class=property_class_code], many_to_one, null]
    - [assessment_to_property_class, fact_assessed_values, dim_property_class, [property_class=property_class_code], many_to_one, null]

  paths:
    assessment_to_tax_district:
      description: "Property tax calculation chain: assessment → parcel → tax district"
      steps:
        - {from: fact_assessed_values, to: dim_parcel, via: parcel_id}
        - {from: dim_parcel, to: dim_tax_district, via: tax_code}
    sale_to_township:
      description: "Sales by geographic area: sale → parcel → township"
      steps:
        - {from: fact_parcel_sales, to: dim_parcel, via: parcel_id}
        - {from: dim_parcel, to: county.geospatial.dim_township, via: township_code}
    parcel_class_to_tax:
      description: "Classification chain: parcel → property class + parcel → tax district"
      steps:
        - {from: dim_parcel, to: dim_property_class, via: property_class}
        - {from: dim_parcel, to: dim_tax_district, via: tax_code}

build:
  partitions: [year]
  sort_by: [parcel_id, year]
  optimize: true
  phases:
    1: { tables: [dim_property_class, dim_tax_district] }
    2: { tables: [dim_parcel] }
    3: { tables: [fact_assessed_values, fact_parcel_sales] }

measures:
  simple:
    - [parcel_count, count_distinct, dim_parcel.parcel_id, "Number of parcels", {format: "#,##0"}]
    - [total_assessed_value, sum, fact_assessed_values.assessed_value_total, "Total assessed value", {format: "$#,##0"}]
    - [avg_assessed_value, avg, fact_assessed_values.assessed_value_total, "Average assessed value", {format: "$#,##0"}]
    - [total_sales_volume, sum, fact_parcel_sales.sale_price, "Total sales volume", {format: "$#,##0"}]
    - [avg_sale_price, avg, fact_parcel_sales.sale_price, "Average sale price", {format: "$#,##0"}]
    - [sale_count, count, fact_parcel_sales.parcel_id, "Number of sales", {format: "#,##0"}]
  computed:
    - [median_sale_price, expression, "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sale_price)", "Median sale price", {format: "$#,##0", source_table: fact_parcel_sales}]

views:
  view_equalized_values:
    extends: _base.property.parcel._view_equalized_values
    assumptions:
      equalization_factor:
        source: dim_tax_district.equalization_factor
        join_on: [township_code=township_code, year=tax_year]
  view_estimated_tax:
    extends: _base.property.parcel._view_estimated_tax
    assumptions:
      total_rate:
        source: dim_tax_district.total_rate
        join_on: [tax_code=tax_code]
  view_township_summary:
    extends: _base.property.parcel._view_township_summary

metadata:
  domain: county
  subdomain: property
status: active
---

## County Property Model

Property assessments, parcels, and sales — wide table pattern.

### Key Concepts

**PIN Format**: 14-digit Parcel Index Number, must be zero-padded.

**Wide dim_parcel**: All property types in one table, partitioned by `property_category`. Type-specific columns (bedrooms, commercial_sqft, etc.) are null for non-matching categories. Delta Lake partition pruning makes `WHERE property_category = 'RESIDENTIAL'` fast.

**Build Order**: `dim_property_class` first (phase 1), then `dim_parcel` (phase 2, enriches property_category from dim_property_class), then facts (phase 3).

**Assessment Stages**:
1. `mailed` - Initial values sent to owners
2. `certified` - After Assessor appeals
3. `bor_certified` - After Board of Review appeals
