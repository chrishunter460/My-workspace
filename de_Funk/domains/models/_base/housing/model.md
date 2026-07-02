---
type: domain-model
model: housing_federation
version: 1.0
description: "Federated union of building permit data across municipalities"

extends: [_base.housing.permit]
depends_on: [municipal_housing]

federation:
  union_key: domain_source
  children:
    - {model: municipal_housing, domain_source: chicago}

tables:
  v_all_building_permits:
    type: fact
    description: "All building permits across federated municipalities"
    union_of:
      - municipal_housing.fact_building_permits
    primary_key: [permit_id]
    partition_by: [year]
    schema: inherited

storage:
  format: delta
  silver:
    root: storage/silver/_base/housing/

metadata:
  domain: _base
  subdomain: housing
status: active
---

## Housing Federation

Unifies building permit data across municipalities. Currently Chicago only; ready for multi-city federation.
