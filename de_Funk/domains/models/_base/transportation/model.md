---
type: domain-model
model: transportation_federation
version: 1.0
description: "Federated union of transit ridership and traffic data across municipalities"

extends: [_base.transportation.transit, _base.transportation.traffic]
depends_on: [municipal_transportation]

federation:
  union_key: domain_source
  children:
    - {model: municipal_transportation, domain_source: chicago}

tables:
  v_all_ridership:
    type: fact
    description: "All transit ridership across federated municipalities"
    union_of:
      - municipal_transportation.fact_ridership
    primary_key: [ridership_id]
    partition_by: [year]
    schema: inherited

  v_all_traffic:
    type: fact
    description: "All traffic observations across federated municipalities"
    union_of:
      - municipal_transportation.fact_traffic_observations
    primary_key: [observation_id]
    partition_by: [year]
    schema: inherited

storage:
  format: delta
  silver:
    root: storage/silver/_base/transportation/

metadata:
  domain: _base
  subdomain: transportation
status: active
---

## Transportation Federation

Unifies transit ridership and traffic data across municipalities. Currently Chicago only; ready for multi-city federation.
