---
type: domain-base
model: tax_district
version: 1.0
description: "Tax districts - geographic zones with associated tax rates"
extends: _base._base_.entity

canonical_fields:
  - [tax_district_id, integer, nullable: false, description: "Primary key"]
  - [tax_code, string, nullable: false, description: "Tax district code"]
  - [tax_district_name, string, nullable: true, description: "District name"]
  - [municipality, string, nullable: true, description: "Municipality name"]
  - [total_rate, "decimal(10,6)", nullable: true, description: "Combined tax rate"]

tables:
  _dim_tax_district:
    type: dimension
    primary_key: [tax_district_id]
    unique_key: [tax_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [tax_district_id, integer, false, "PK", {derived: "ABS(HASH(tax_code))"}]
      - [tax_code, string, false, "Tax district code", {unique: true}]
      - [tax_district_name, string, true, "District name"]
      - [municipality, string, true, "Municipality name"]
      - [total_rate, "decimal(10,6)", true, "Combined tax rate"]
      - [equalization_factor, "decimal(10,6)", true, "State equalization factor (by township/year)"]

    measures:
      - [district_count, count_distinct, tax_district_id, "Number of tax districts", {format: "#,##0"}]
      - [avg_tax_rate, avg, total_rate, "Average tax rate", {format: "#,##0.000000"}]

graph:
  edges: []

behaviors: []  # Pure entity — tax classification dimension only

domain: property
tags: [base, template, property, tax]
status: active
---

## Tax District Base Template

Geographic zones with associated tax rates. Used to link property assessments (county) to property tax ledger entries (municipal).

### Cross-Domain Bridge

```
County Property                    Municipal Finance
dim_parcel.tax_code ──→ dim_tax_district ←── fact_property_tax.tax_district_id
```

### Usage

```yaml
extends: _base.property.tax_district
```
