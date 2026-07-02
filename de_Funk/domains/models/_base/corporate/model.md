---
type: domain-model
model: corporate_federation
version: 1.0
description: "Federated union of corporate earnings data across providers"

extends: [_base.corporate.earnings]
depends_on: [corporate_finance]

federation:
  union_key: domain_source
  children:
    - {model: corporate_finance, domain_source: alpha_vantage}

tables:
  v_all_earnings:
    type: fact
    description: "All corporate earnings reports across federated providers"
    union_of:
      - corporate_finance.fact_earnings
    primary_key: [earnings_id]
    schema: inherited

storage:
  format: delta
  silver:
    root: storage/silver/_base/corporate/

metadata:
  domain: _base
  subdomain: corporate
status: active
---

## Corporate Federation

Unifies corporate earnings data across providers. Currently Alpha Vantage only; ready for additional SEC/EDGAR or Bloomberg providers.
