---
type: domain-model
model: public_safety_federation
version: 1.0
description: "Federated union of crime and arrest data across municipalities"

extends: [_base.public_safety.crime]
depends_on: [municipal_public_safety]

federation:
  union_key: domain_source
  children:
    - {model: municipal_public_safety, domain_source: chicago}

tables:
  v_all_crimes:
    type: fact
    description: "All crime incidents across federated municipalities"
    union_of:
      - municipal_public_safety.fact_crimes
    primary_key: [incident_id]
    partition_by: [year]
    schema: inherited

  v_all_arrests:
    type: fact
    description: "All arrests across federated municipalities"
    union_of:
      - municipal_public_safety.fact_arrests
    primary_key: [arrest_id]
    partition_by: [year]
    schema: inherited

storage:
  format: delta
  silver:
    root: storage/silver/_base/public_safety/

metadata:
  domain: _base
  subdomain: public_safety
status: active
---

## Public Safety Federation

Unifies crime and arrest data across municipalities. Currently Chicago only; ready for multi-city federation.
