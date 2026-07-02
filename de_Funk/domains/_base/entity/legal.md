---
type: domain-base
model: legal_entity
version: 1.0
description: "Legal entities - companies, municipalities, agencies with legal standing"
extends: _base._base_.entity

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [legal_entity_id, integer, nullable: false, description: "Primary key"]
  - [legal_name, string, nullable: false, description: "Official legal name"]
  - [entity_type, string, nullable: false, description: "COMPANY, MUNICIPALITY, AGENCY, NONPROFIT"]
  - [jurisdiction, string, nullable: true, description: "Governing jurisdiction (state, country)"]
  - [tax_id, string, nullable: true, description: "Tax identification number (EIN, FEIN)"]
  - [cik, string, nullable: true, description: "SEC Central Index Key (public companies)"]
  - [incorporation_state, string, nullable: true, description: "State of incorporation"]
  - [is_active, boolean, nullable: false, description: "Currently operating"]

tables:
  _dim_legal_entity:
    type: dimension
    primary_key: [legal_entity_id]
    unique_key: [legal_name, entity_type]

    # [column, type, nullable, description, {options}]
    schema:
      - [legal_entity_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(entity_type, '_', legal_name)))"}]
      - [legal_name, string, false, "Official name"]
      - [entity_type, string, false, "Discriminator", {enum: [COMPANY, MUNICIPALITY, AGENCY, NONPROFIT]}]
      - [jurisdiction, string, true, "Governing jurisdiction"]
      - [tax_id, string, true, "Tax ID (EIN)"]
      - [cik, string, true, "SEC CIK"]
      - [incorporation_state, string, true, "State of incorporation"]
      - [is_active, boolean, false, "Currently operating", {default: true}]

    measures:
      - [entity_count, count_distinct, legal_entity_id, "Number of legal entities", {format: "#,##0"}]

behaviors: []  # Pure entity — no temporal, geo, federation, or subset capabilities

domain: entity
tags: [base, template, entity, legal]
status: active
---

## Legal Entity Base Template

Any entity with legal standing. Companies, municipalities, agencies.

### Entity Types

| Type | Description | Example |
|------|-------------|---------|
| COMPANY | Corporation or LLC | Apple Inc. |
| MUNICIPALITY | City/town government | City of Chicago |
| AGENCY | Government agency | EPA, CTA |
| NONPROFIT | Tax-exempt organization | United Way |

### Usage

```yaml
extends: _base.entity.legal
```
