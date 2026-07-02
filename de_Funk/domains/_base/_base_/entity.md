---
type: domain-base
model: entity
version: 1.0
description: "Root template for any identifiable thing - person, organization, place, account"

# CANONICAL FIELDS - the most fundamental attributes of any entity
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [entity_id, integer, nullable: false, description: "Surrogate primary key"]
  - [entity_code, string, nullable: false, description: "Natural key / business identifier"]
  - [entity_name, string, nullable: false, description: "Human-readable display name"]
  - [entity_type, string, nullable: false, description: "Discriminator for what kind of entity"]
  - [is_active, boolean, nullable: false, description: "Whether entity is currently valid"]

tables:
  _dim_entity:
    type: dimension
    primary_key: [entity_id]
    unique_key: [entity_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [entity_id, integer, false, "PK - surrogate", {derived: "ABS(HASH(entity_code))"}]
      - [entity_code, string, false, "Natural key"]
      - [entity_name, string, false, "Display name"]
      - [entity_type, string, false, "Discriminator"]
      - [is_active, boolean, false, "Currently valid", {default: true}]

    measures:
      - [entity_count, count_distinct, entity_id, "Number of entities", {format: "#,##0"}]
      - [active_count, expression, "SUM(CASE WHEN is_active THEN 1 ELSE 0 END)", "Active entities", {format: "#,##0"}]

behaviors: []

domain: _base
tags: [base, template, entity, root]
status: active
---

## Entity Base Template

The most fundamental base template. Every identifiable thing in the system is an entity.

### What Extends This

| Template | entity_type | Example entity_code |
|----------|-------------|---------------------|
| `_base.entity.legal` | COMPANY, MUNICIPALITY | CIK, FEIN |
| `_base.entity.organizational_entity` | DEPARTMENT, DIVISION | dept_code |
| `_base.accounting.chart_of_accounts` | ACCOUNT | account_code |
| `_base.accounting.fund` | FUND | fund_code |

### Key Design

All entity PKs are integers: `ABS(HASH(entity_code))`

This means any entity can be referenced by a single integer FK, enabling efficient joins across the entire domain hierarchy.
