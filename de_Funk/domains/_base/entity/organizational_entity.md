---
type: domain-base
model: organizational_entity
version: 1.0
description: "Organizational units - departments, divisions, bureaus within a legal entity"
extends: _base._base_.entity

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [org_unit_id, integer, nullable: false, description: "Primary key"]
  - [org_unit_code, string, nullable: false, description: "Department/division code"]
  - [org_unit_name, string, nullable: false, description: "Department/division name"]
  - [org_unit_type, string, nullable: false, description: "DEPARTMENT, DIVISION, BUREAU, OFFICE"]
  - [parent_org_unit_id, integer, nullable: true, description: "Parent unit for hierarchy"]
  - [legal_entity_id, integer, nullable: true, description: "FK to owning legal entity"]
  - [is_active, boolean, nullable: false, description: "Currently operational"]

tables:
  _dim_org_unit:
    type: dimension
    primary_key: [org_unit_id]
    unique_key: [org_unit_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [org_unit_id, integer, false, "PK", {derived: "ABS(HASH(org_unit_code))"}]
      - [org_unit_code, string, false, "Natural key"]
      - [org_unit_name, string, false, "Display name"]
      - [org_unit_type, string, false, "Classification", {enum: [DEPARTMENT, DIVISION, BUREAU, OFFICE]}]
      - [parent_org_unit_id, integer, true, "Self-referencing FK", {fk: _dim_org_unit.org_unit_id}]
      - [legal_entity_id, integer, true, "FK to legal entity", {fk: _base.entity.legal._dim_legal_entity.legal_entity_id}]
      - [is_active, boolean, false, "Currently operational", {default: true}]

    measures:
      - [org_unit_count, count_distinct, org_unit_id, "Number of org units", {format: "#,##0"}]

behaviors: []  # Pure entity — reference dimension only

domain: entity
tags: [base, template, entity, organizational]
status: active
---

## Organizational Entity Base Template

Departments, divisions, and bureaus within a legal entity. Supports hierarchy via `parent_org_unit_id`.

### Hierarchy Example

```
City of Chicago (legal entity)
  Police Department (DEPARTMENT)
    Bureau of Detectives (BUREAU)
    Bureau of Patrol (BUREAU)
  Streets & Sanitation (DEPARTMENT)
    Division of Street Operations (DIVISION)
```

### Usage

```yaml
extends: _base.entity.organizational_entity
```
