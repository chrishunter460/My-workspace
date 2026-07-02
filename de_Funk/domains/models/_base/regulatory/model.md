---
type: domain-model
model: regulatory_federation
version: 1.0
description: "Federated union of inspection, violation, and license data across municipalities"

extends: [_base.regulatory.inspection]
depends_on: [municipal_regulatory]

federation:
  union_key: domain_source
  children:
    - {model: municipal_regulatory, domain_source: chicago}

tables:
  v_all_inspections:
    type: fact
    description: "All food inspections across federated municipalities"
    union_of:
      - municipal_regulatory.fact_food_inspections
    primary_key: [inspection_id]
    partition_by: [year]
    schema: inherited

  v_all_building_violations:
    type: fact
    description: "All building violations across federated municipalities"
    union_of:
      - municipal_regulatory.fact_building_violations
    primary_key: [violation_id]
    partition_by: [year]
    schema: inherited

  v_all_business_licenses:
    type: fact
    description: "All business licenses across federated municipalities"
    union_of:
      - municipal_regulatory.fact_business_licenses
    primary_key: [license_id]
    partition_by: [year]
    schema: inherited

storage:
  format: delta
  silver:
    root: storage/silver/_base/regulatory/

metadata:
  domain: _base
  subdomain: regulatory
status: active
---

## Regulatory Federation

Unifies inspection, violation, and license data across municipalities. Currently Chicago only; ready for multi-city federation.
