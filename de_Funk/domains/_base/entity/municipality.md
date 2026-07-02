---
type: domain-base
model: municipality
version: 1.0
description: "Municipal entities - cities, counties, townships, special districts"
extends: _base.entity.legal

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [municipality_id, integer, nullable: false, description: "Primary key"]
  - [municipality_name, string, nullable: false, description: "Official name"]
  - [municipality_type, string, nullable: false, description: "CITY, COUNTY, TOWNSHIP, SPECIAL_DISTRICT"]
  - [fips_code, string, nullable: true, description: "Federal FIPS code"]
  - [state, string, nullable: true, description: "State"]
  - [population, integer, nullable: true, description: "Population estimate"]
  - [latitude, double, nullable: true, description: "Centroid latitude"]
  - [longitude, double, nullable: true, description: "Centroid longitude"]
  - [geography_id, integer, nullable: true, description: "FK to geospatial.dim_geography (county-level)"]
  - [is_active, boolean, nullable: false, description: "Currently operating"]

tables:
  _dim_municipality:
    type: dimension
    primary_key: [municipality_id]
    unique_key: [municipality_name, municipality_type]

    # [column, type, nullable, description, {options}]
    schema:
      - [municipality_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(municipality_type, '_', municipality_name)))"}]
      - [municipality_name, string, false, "Official name"]
      - [municipality_type, string, false, "Classification", {enum: [CITY, COUNTY, TOWNSHIP, SPECIAL_DISTRICT]}]
      - [fips_code, string, true, "Federal FIPS code"]
      - [state, string, true, "State"]
      - [population, integer, true, "Population estimate"]
      - [latitude, double, true, "Centroid latitude"]
      - [longitude, double, true, "Centroid longitude"]
      - [geography_id, integer, true, "FK to geospatial.dim_geography (county-level)", {fk: geospatial.dim_geography.geography_id}]
      - [is_active, boolean, false, "Currently operating", {default: true}]

    measures:
      - [municipality_count, count_distinct, municipality_id, "Number of municipalities", {format: "#,##0"}]

behaviors: []  # Pure entity — reference dimension only

domain: entity
tags: [base, template, entity, municipality, government]
status: active
---

## Municipality Base Template

Municipal entities with legal standing — cities, counties, townships, and special districts. Extends `_base.entity.legal` with government-specific fields.

### Inherited from Legal Entity

| Field | From |
|-------|------|
| legal_entity_id | `_base.entity.legal` |
| tax_id (FEIN) | `_base.entity.legal` |
| jurisdiction | `_base.entity.legal` |

### Municipality Types

| Type | Description | Example |
|------|-------------|---------|
| CITY | Incorporated city | City of Chicago |
| COUNTY | County government | Cook County |
| TOWNSHIP | Township government | Evanston Township |
| SPECIAL_DISTRICT | Special-purpose district | Chicago Transit Authority |

### Usage

```yaml
extends: _base.entity.municipality
```
