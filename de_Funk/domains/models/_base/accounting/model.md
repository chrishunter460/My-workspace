---
type: domain-model
model: accounting_federation
version: 1.0
description: "Federated union of all accounting data — ledger entries, financial events, and statements across municipal and corporate domains"

extends:
  - _base.accounting.ledger_entry
  - _base.accounting.financial_event
  - _base.accounting.financial_statement

depends_on: [municipal_finance, corporate_finance]

federation:
  union_key: domain_source
  children:
    - {model: municipal_finance, domain_source: chicago}
    - {model: corporate_finance, domain_source: alpha_vantage}

tables:
  v_all_ledger_entries:
    type: fact
    description: "All ledger entries across federated domains"
    union_of:
      - municipal_finance.fact_ledger_entries
    primary_key: [entry_id]
    partition_by: [date_id]
    schema: inherited

  v_all_financial_events:
    type: fact
    description: "All financial events — budget events and corporate statements"
    union_of:
      - municipal_finance.fact_budget_events
      - corporate_finance.fact_financial_statements
    primary_key: [event_id]
    partition_by: [date_id]
    schema: inherited

storage:
  format: delta
  silver:
    root: storage/silver/_base/accounting/

metadata:
  domain: _base
  subdomain: accounting
status: active
---

## Accounting Federation

Unifies accounting data across municipal and corporate domains. Each child model builds its own fact tables independently; this model creates UNION views across them using the `domain_source` column to identify origin.

### Union Tables

| View | Sources | Schema From |
|------|---------|-------------|
| `v_all_ledger_entries` | municipal/finance | `_base.accounting.ledger_entry` |
| `v_all_financial_events` | municipal/finance + corporate/finance | `_base.accounting.financial_event` |

### Adding a New City

When onboarding a second municipality (e.g., Detroit):

1. Create `models/municipal_detroit/finance/` extending the same bases
2. Add to `children:` list above
3. Add `municipal_detroit_finance.fact_ledger_entries` to `v_all_ledger_entries.union_of:`
