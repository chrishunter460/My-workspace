---
type: domain-model
model: finance_federation
version: 1.0
description: "Federated union of corporate action data (dividends, splits) across providers"

extends: [_base.finance.corporate_action]
depends_on: [securities_stocks]

federation:
  union_key: domain_source
  children:
    - {model: securities_stocks, domain_source: alpha_vantage}

tables:
  v_all_dividends:
    type: fact
    description: "All dividend payments across federated providers"
    union_of:
      - securities_stocks.fact_dividends
    primary_key: [action_id]
    schema: inherited

  v_all_splits:
    type: fact
    description: "All stock splits across federated providers"
    union_of:
      - securities_stocks.fact_splits
    primary_key: [action_id]
    schema: inherited

storage:
  format: delta
  silver:
    root: storage/silver/_base/finance/

metadata:
  domain: _base
  subdomain: finance
status: active
---

## Finance Federation

Unifies corporate action data (dividends, splits) across securities data providers. Currently Alpha Vantage only; ready for additional providers.
