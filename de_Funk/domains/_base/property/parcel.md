---
type: domain-base
model: parcel
version: 3.0
description: "Property parcels - land records, assessments, and sales transactions"
extends: _base._base_.entity

# CANONICAL FIELDS — common fields only
# Subset-specific fields are defined in child templates (residential.md, commercial.md, industrial.md)
# and auto-absorbed into _dim_parcel via the subset_of mechanism
canonical_fields:
  - [parcel_id, string, nullable: false, description: "Primary key (PIN or parcel number)"]
  - [parcel_code, string, nullable: false, description: "Natural key (standardized PIN)"]
  - [property_class, string, nullable: true, description: "Property classification code"]
  - [property_category, string, nullable: true, description: "Category (denormalized from dim_property_class)"]
  - [township_code, string, nullable: true, description: "Township/municipality code"]
  - [neighborhood_code, string, nullable: true, description: "Neighborhood/area code"]
  - [year_built, integer, nullable: true, description: "Year of construction"]
  - [land_sqft, double, nullable: true, description: "Land area in square feet"]
  - [building_sqft, double, nullable: true, description: "Building area in square feet"]
  - [latitude, double, nullable: true, description: "Parcel centroid latitude"]
  - [longitude, double, nullable: true, description: "Parcel centroid longitude"]
  - [tax_code, string, nullable: true, description: "Tax district code"]

tables:
  _dim_parcel:
    type: dimension
    primary_key: [parcel_id]
    unique_key: [parcel_code]
    partition_by: [property_category]

    # Common columns only — subset columns are auto-absorbed from child templates
    # that declare subset_of: _base.property.parcel
    # [column, type, nullable, description, {options}]
    schema:
      - [parcel_id, string, false, "PK (PIN)", {derived: "LPAD(REGEXP_REPLACE(pin, '[^0-9]', ''), 14, '0')"}]
      - [parcel_code, string, false, "Natural key"]
      - [property_class, string, true, "Classification code"]
      - [property_category, string, true, "Category (denormalized)", {enum: [RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER]}]
      - [township_code, string, true, "Township"]
      - [neighborhood_code, string, true, "Neighborhood"]
      - [year_built, integer, true, "Construction year"]
      - [land_sqft, double, true, "Land area sq ft"]
      - [building_sqft, double, true, "Building area sq ft"]
      - [latitude, double, true, "Centroid latitude"]
      - [longitude, double, true, "Centroid longitude"]
      - [tax_code, string, true, "Tax district"]

    measures:
      - [parcel_count, count_distinct, parcel_id, "Number of parcels", {format: "#,##0"}]

  _dim_property_class:
    type: dimension
    primary_key: [property_class_id]
    unique_key: [property_class_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [property_class_id, string, false, "PK (classification code)"]
      - [property_class_code, string, false, "Natural key"]
      - [property_class_name, string, true, "Description"]
      - [property_category, string, true, "RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER", {enum: [RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER]}]
      - [applicable_fields, string, true, "Comma-separated list of subset fields applicable to this class"]

    measures:
      - [class_count, count_distinct, property_class_id, "Property classes", {format: "#,##0"}]

  _fact_assessed_values:
    type: fact
    primary_key: [parcel_id, year, assessment_stage]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [parcel_id, string, false, "FK to dim_parcel", {fk: _dim_parcel.parcel_id}]
      - [year, integer, false, "Assessment year"]
      - [date_id, integer, false, "FK to calendar (Jan 1 of assessment year)", {fk: temporal.dim_calendar.date_id, derived: "CAST(CONCAT(year, '0101') AS INT)"}]
      - [assessment_stage, string, false, "Stage (mailed, certified, appeal)", {enum: [MAILED, CERTIFIED, BOARD_CERTIFIED, APPEAL]}]
      - [assessed_value_land, "decimal(18,2)", true, "Assessed value - land"]
      - [assessed_value_building, "decimal(18,2)", true, "Assessed value - building"]
      - [assessed_value_total, "decimal(18,2)", true, "Assessed value - total"]
      - [property_class, string, true, "Classification at assessment time"]
      - [township_code, string, true, "Township at assessment time"]

    measures:
      - [total_assessed_value, sum, assessed_value_total, "Total assessed value", {format: "$#,##0.00"}]
      - [avg_assessed_value, avg, assessed_value_total, "Average assessed value", {format: "$#,##0.00"}]
      - [assessment_count, count, parcel_id, "Assessment records", {format: "#,##0"}]

  _fact_parcel_sales:
    type: fact
    primary_key: [parcel_id, sale_date]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [parcel_id, string, false, "FK to dim_parcel", {fk: _dim_parcel.parcel_id}]
      - [sale_date, date, false, "Date of sale"]
      - [sale_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(sale_date, 'yyyyMMdd') AS INT)"}]
      - [year, integer, false, "Sale year", {derived: "YEAR(sale_date)"}]
      - [sale_price, "decimal(18,2)", true, "Sale price"]
      - [sale_type, string, true, "Transaction type"]

    measures:
      - [total_sales_volume, sum, sale_price, "Total sales volume", {format: "$#,##0.00"}]
      - [avg_sale_price, avg, sale_price, "Average sale price", {format: "$#,##0.00"}]
      - [sale_count, count, parcel_id, "Number of sales", {format: "#,##0"}]

subsets:
  discriminator: _dim_property_class.property_category
  pattern: wide_table
  target_table: _dim_parcel
  description: "Child templates with subset_of: _base.property.parcel have their canonical_fields and measures auto-absorbed into _dim_parcel as nullable columns with {subset: VALUE} metadata. dim_property_class.applicable_fields lists active fields per class."
  values:
    RESIDENTIAL:
      extends: _base.property.residential
      description: "Single-family, multi-family, condos"
      filter: "property_category = 'RESIDENTIAL'"
    COMMERCIAL:
      extends: _base.property.commercial
      description: "Office, retail, mixed-use"
      filter: "property_category = 'COMMERCIAL'"
    INDUSTRIAL:
      extends: _base.property.industrial
      description: "Manufacturing, warehouse, distribution"
      filter: "property_category = 'INDUSTRIAL'"
    EXEMPT:
      description: "Government, religious, educational"
      filter: "property_category = 'EXEMPT'"
    OTHER:
      description: "Vacant land, agricultural"
      filter: "property_category = 'OTHER'"

auto_edges:
  - [date_id, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]

behaviors:
  - temporal        # Has auto_edges for date_id → calendar
  - subsettable     # Has subsets: block (property_category discriminator)

graph:
  # auto_edges: date_id→calendar (assessed_values only; parcel_sales uses sale_date_id — explicit below)
  edges:
    - [assessment_to_parcel, _fact_assessed_values, _dim_parcel, [parcel_id=parcel_id], many_to_one, null]
    - [sale_to_parcel, _fact_parcel_sales, _dim_parcel, [parcel_id=parcel_id], many_to_one, null]
    - [sale_to_calendar, _fact_parcel_sales, temporal.dim_calendar, [sale_date_id=date_id], many_to_one, temporal]
    - [parcel_to_property_class, _dim_parcel, _dim_property_class, [property_class=property_class_code], many_to_one, null]
    - [assessment_to_property_class, _fact_assessed_values, _dim_property_class, [property_class=property_class_code], many_to_one, null]

views:
  _view_equalized_values:
    type: derived
    from: _fact_assessed_values
    join: [{table: _dim_tax_district, on: [tax_code=tax_code], fields: [equalization_factor]}]
    description: "Assessed values with equalization factor applied"
    assumptions:
      equalization_factor:
        type: "decimal(10,6)"
        default: 1.0
        description: "State equalization factor (by township/year)"
        source: "Joined from dim_tax_district or overridden per model"
    schema:
      - [parcel_id, string, false, "FK to dim_parcel"]
      - [year, integer, false, "Assessment year"]
      - [assessment_stage, string, false, "Stage"]
      - [assessed_value_total, "decimal(18,2)", false, "Raw assessed value"]
      - [equalization_factor, "decimal(10,6)", false, "Applied factor"]
      - [equalized_value_total, "decimal(18,2)", false, "Equalized assessed value", {derived: "assessed_value_total * equalization_factor"}]
    measures:
      - [total_equalized_value, sum, equalized_value_total, "Total equalized value", {format: "$#,##0.00"}]
      - [avg_equalized_value, avg, equalized_value_total, "Average equalized value", {format: "$#,##0.00"}]

  _view_estimated_tax:
    type: derived
    from: _view_equalized_values
    join: [{table: _dim_tax_district, on: [tax_code=tax_code], fields: [total_rate]}]
    description: "Estimated tax bills from equalized values and tax rates"
    assumptions:
      total_rate:
        type: "decimal(10,6)"
        default: null
        description: "Composite tax rate from all overlapping districts"
        source: "Joined from dim_tax_district"
    schema:
      - [parcel_id, string, false, "FK to dim_parcel"]
      - [year, integer, false, "Assessment year"]
      - [equalized_value_total, "decimal(18,2)", false, "Equalized value (from parent view)"]
      - [total_rate, "decimal(10,6)", false, "Composite tax rate"]
      - [estimated_tax, "decimal(18,2)", false, "Estimated tax bill", {derived: "equalized_value_total * total_rate"}]
    measures:
      - [total_estimated_tax, sum, estimated_tax, "Total estimated tax", {format: "$#,##0.00"}]
      - [avg_estimated_tax, avg, estimated_tax, "Average estimated tax", {format: "$#,##0.00"}]

  _view_township_summary:
    type: rollup
    from: _fact_assessed_values
    grain: [township_code, year, assessment_stage]
    description: "Township-level assessment summary"
    schema:
      - [township_code, string, false, "Township"]
      - [year, integer, false, "Assessment year"]
      - [assessment_stage, string, false, "Stage"]
      - [parcel_count, integer, false, "Parcels in township", {derived: "COUNT(DISTINCT parcel_id)"}]
      - [total_assessed_value, "decimal(18,2)", false, "Total assessed value", {derived: "SUM(assessed_value_total)"}]
      - [avg_assessed_value, "decimal(18,2)", false, "Average assessed value", {derived: "AVG(assessed_value_total)"}]

domain: property
tags: [base, template, property, parcel, assessment]
status: active
---

## Parcel Base Template

Property parcel data including land records, assessments, and sales. Parcel IDs (PINs) are standardized to 14-digit zero-padded format for cross-dataset joins.

### Wide Table with Auto-Absorption (v3.0)

Type-specific fields (residential, commercial, industrial) are **not listed** on this template. Instead, child templates that declare `subset_of: _base.property.parcel` have their `canonical_fields` and `measures` automatically absorbed into `_dim_parcel` as nullable columns with `{subset: VALUE}` metadata.

**To add a field to commercial properties:**
1. Add it to `_base/property/commercial.md` canonical_fields — done
2. Add the source alias in the model's source file — done

The loader handles everything else: the field appears on `_dim_parcel` as a nullable column with `{subset: COMMERCIAL}`.

**Loader behavior for `subsets.pattern: wide_table`:**
1. Scan for templates with `subset_of: _base.property.parcel`
2. For each child, read `subset_value` (e.g., `COMMERCIAL`)
3. Append child's `canonical_fields` to `_dim_parcel.schema` as nullable columns with `{subset: VALUE}`
4. Append child's `measures` to `_dim_parcel.measures` with `{subset: VALUE}`
5. Update `subsets.values.*.fields` from child canonical_fields

### Delta Lake Advantages

- **Partition pruning**: `WHERE property_category = 'RESIDENTIAL'` reads only residential partition
- **Null compression**: Columnar storage makes sparse columns essentially free
- **No join overhead**: All fields available without subset table joins
- **Schema evolution**: New property types add columns without breaking existing queries

### Assessment Stages

| Stage | Description |
|-------|-------------|
| MAILED | Initial mailed assessment |
| CERTIFIED | Certified by assessor |
| BOARD_CERTIFIED | Certified by board of review |
| APPEAL | Post-appeal value |

### Property Categories

```
RESIDENTIAL → fields from _base.property.residential
COMMERCIAL  → fields from _base.property.commercial
INDUSTRIAL  → fields from _base.property.industrial
EXEMPT      → no type-specific fields
OTHER       → no type-specific fields
```

### Views (Layered Calculations)

```
_fact_assessed_values (physical table)
     ↓ (join dim_tax_district for equalization_factor)
_view_equalized_values (adds equalized_value_total = assessed_value_total × equalization_factor)
     ↓ (join dim_tax_district for total_rate)
_view_estimated_tax (adds estimated_tax = equalized_value_total × total_rate)

_fact_assessed_values (physical table)
     ↓ (GROUP BY township_code, year, assessment_stage)
_view_township_summary (parcel_count, total_assessed_value, avg_assessed_value)
```

### Usage

```yaml
extends: _base.property.parcel
```
