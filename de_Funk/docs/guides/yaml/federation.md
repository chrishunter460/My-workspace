---

type: reference
description: "Guide for federation — cross-model union queries via models/_base/"
status: planned
---

> **Implementation Status**: **PLANNED**. Federation participation flags are parsed and recognized. However, `union_of` tables are NOT synthesized into SQL UNIONs during build. Federation models exist in `domains/models/_base/` but are not built.


## federation Guide

### Implementation Status

| Feature | Status |
|---------|--------|
| `federation.enabled` | **PARSED ONLY** -- read by config loader, not acted on by build pipeline |
| `federation.union_key` | **PARSED ONLY** -- read by config loader, not acted on by build pipeline |
| `federation.children` | **PARSED ONLY** -- read by config loader, not acted on by build pipeline |
| `tables.*.union_of` | **PARSED ONLY** -- read by config loader, never synthesized into UNION nodes |
| `domain_source` column injection | **IMPLEMENTED** -- sources inject `domain_source` as a literal column |
| Federation UNION view materialization | **PLANNED** -- not built yet |

> **PLANNED** — Config parsing is implemented (`config/domain/federation.py`),
> but the build pipeline does not yet execute federation. `federation.enabled`,
> `children`, `union_key`, and `union_of` are parsed but never built into Silver
> tables. Note: `DomainModel._build_union_node()` unions multiple Bronze sources
> into one Silver fact -- that is source-level union, not federation.

Federation enables querying across multiple domain-models that share the same base template by creating UNION views of their fact tables.

---


### Architecture

Federation is separated into three layers:

| Layer | Location | Responsibility |
|-------|----------|---------------|
| **Base templates** | `_base/` | Define canonical schema contract. No federation config — bases stay pure. |
| **Domain models** | `models/{domain}/` | Produce data. Declare `federation: {enabled: true}` to signal participation. |
| **Federation models** | `models/_base/` | Own the UNION. Declare `children:` and `union_of:` tables. |

```
_base/accounting/ledger_entry.md           ← Schema contract (no federation block)
  ↑ extends
models/municipal/finance/model.md          ← Produces fact_ledger_entries (domain_source: 'chicago')
models/corporate/finance/model.md          ← Produces fact_financial_statements
  ↑ depends_on
models/_base/accounting/model.md           ← Creates v_all_ledger_entries (UNION)
```

---


### Federation Model Config (models/_base/)

```yaml
type: domain-model
model: accounting_federation
extends: [_base.accounting.ledger_entry, _base.accounting.financial_event]
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
    schema: inherited

  v_all_financial_events:
    type: fact
    union_of:
      - municipal_finance.fact_budget_events
      - municipal_finance.fact_property_tax
      - corporate_finance.fact_financial_statements
    primary_key: [event_id]
    schema: inherited
```

### Federation Model Keys

| Key | Required | Description |
|-----|----------|-------------|
| `federation.union_key` | Yes | Column identifying source: `domain_source` |
| `federation.children` | Yes | List of `{model, domain_source}` objects |
| `tables.*.union_of` | Yes | List of `model.table` references to UNION |
| `tables.*.schema` | No | `inherited` = use canonical schema from base |
| `depends_on` | Yes | All child models must build before federation |

---


### Domain Model Config (participation signal)

Domain models that participate in federation declare a simple block:

```yaml
# models/municipal/finance/model.md
federation:
  enabled: true
  union_key: domain_source
```

This signals the model produces federated data. The `domain_source` column value comes from each source file's `domain_source:` key.

---


### domain_source Column

The `domain_source` column is defined on the root event base (`_base._base_.event`) and carried into every fact table. This column is `nullable: false` — every fact row must identify its origin.

Sources declare it as a top-level key:

```yaml
---

type: domain-model-source
source: payments
maps_to: fact_ledger_entries
from: bronze.payments
domain_source: "'chicago'"
---

```

The loader injects it as a literal column value in the SELECT.

---


### Query Pattern

```sql
-- Federation view (auto-generated from union_of)
SELECT * FROM _base.accounting.v_all_financial_events
WHERE domain_source = 'chicago'    -- filter to one city
-- or
SELECT * FROM _base.accounting.v_all_financial_events
-- see all cities/providers side by side
```

---


### Adding a New City

When onboarding a second municipality (e.g., Detroit):

1. Create `models/municipal_detroit/finance/` extending the same bases
2. Each source file declares `domain_source: "'detroit'"`
3. Update the federation model:
   ```yaml
   # models/_base/accounting/model.md
   federation:
     children:
       - {model: municipal_finance, domain_source: chicago}
       - {model: municipal_detroit_finance, domain_source: detroit}   # NEW

   tables:
     v_all_ledger_entries:
       union_of:
         - municipal_finance.fact_ledger_entries
         - municipal_detroit_finance.fact_ledger_entries              # NEW
   ```

---


### Current Federation Models

| Federation Model | Location | Children | Union Tables |
|-----------------|----------|----------|-------------|
| `accounting_federation` | `models/_base/accounting/` | municipal_finance, corporate_finance | v_all_ledger_entries, v_all_financial_events |
| `public_safety_federation` | `models/_base/public_safety/` | municipal_public_safety | v_all_crimes, v_all_arrests |
| `operations_federation` | `models/_base/operations/` | municipal_operations | v_all_service_requests |
| `regulatory_federation` | `models/_base/regulatory/` | municipal_regulatory | v_all_inspections, v_all_building_violations, v_all_business_licenses |
| `housing_federation` | `models/_base/housing/` | municipal_housing | v_all_building_permits |
| `transportation_federation` | `models/_base/transportation/` | municipal_transportation | v_all_ridership, v_all_traffic |
| `corporate_federation` | `models/_base/corporate/` | corporate_finance | v_all_earnings |
| `finance_federation` | `models/_base/finance/` | securities_stocks | v_all_dividends, v_all_splits |

---


### Build Order

Federation models are the highest tier — they depend on all child domain models:

```
Tier 0: temporal, geospatial          (foundation)
Tier 1: entity models                  (corporate.entity, municipal_entity)
Tier 2: geo subdivisions              (municipal_geospatial, county_geospatial)
Tier 3: domain models                 (municipal_finance, corporate_finance, ...)
Tier 4: federation models             (models/_base/accounting, ...)
```
