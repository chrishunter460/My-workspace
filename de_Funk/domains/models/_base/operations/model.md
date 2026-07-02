---
type: domain-model
model: operations_federation
version: 1.0
description: "Federated union of 311 service request data across municipalities"

extends: [_base.operations.service_request]
depends_on: [municipal_operations]

federation:
  union_key: domain_source
  children:
    - {model: municipal_operations, domain_source: chicago}

tables:
  v_all_service_requests:
    type: fact
    description: "All 311 service requests across federated municipalities"
    union_of:
      - municipal_operations.fact_service_requests
    primary_key: [request_id]
    partition_by: [year]
    schema: inherited

storage:
  format: delta
  silver:
    root: storage/silver/_base/operations/

metadata:
  domain: _base
  subdomain: operations
status: active
---

## Operations Federation

Unifies 311 service request data across municipalities. Currently Chicago only; ready for multi-city federation.
