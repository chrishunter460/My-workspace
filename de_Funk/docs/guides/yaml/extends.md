---

type: reference
description: "Complete guide for extends keyword — inheritance across all file types"
---

> **Implementation Status**: All features fully implemented.


## extends Guide

The `extends` keyword links child definitions to parent templates, inheriting schema, measures, edges, and behaviors. It is used at four levels: model, table, source, and view.

---


### Model-Level Extends

In `model.md`, `extends:` links the model to one or more base templates.

**Single base (scalar):**

```yaml
extends: _base.public_safety.crime
```

**Single base (inline list):**

```yaml
extends: [_base.operations.service_request]
```

**Multiple bases (inline list):**

```yaml
extends: [_base.transportation.transit, _base.transportation.traffic]
```

**Multiple bases (block list — for 3+ bases):**

```yaml
extends:
  - _base.accounting.ledger_entry
  - _base.accounting.financial_statement
  - _base.accounting.fund
  - _base.accounting.chart_of_accounts
  - _base.property.tax_district
```

All three formats are equivalent. Use block list for readability when extending 3+ bases.

---


### What Gets Inherited (Model-Level)

| From Base | Behavior |
|-----------|----------|
| `canonical_fields` | Defines the target schema contract — child sources must map to these fields |
| `tables._*` | Template table schemas available for child tables to `extends:` individually |
| `auto_edges` | FK patterns auto-applied to all fact tables with matching columns |
| `python_measures` | Complex calculations inherited (child can override `params`) |
| `federation` | Federation config inherited if `enabled: true` |
| `behaviors` | Capability tags inherited |
| `graph.edges` | Template-level edge patterns |

**Important:** Model-level `extends:` makes the base's resources *available*. Individual tables still need their own `extends:` to inherit a specific base table's schema (see Table-Level Extends below).

---


### Table-Level Extends

Tables in `tables/*.md` use `extends:` with a dotted path that includes the specific table name:

```yaml
---

type: domain-model-table
table: fact_ledger_entries
extends: _base.accounting.ledger_entry._fact_ledger_entries
table_type: fact
primary_key: [entry_id]
---

```

**Path format:** `_base.{domain}.{template}._{table_name}`

Examples:
```
_base.accounting.ledger_entry._fact_ledger_entries
_base.finance.securities._fact_prices
_base.finance.securities._dim_security
_base.geography.geo_spatial._dim_boundary
_base.transportation.transit._dim_transit_station
```

**What's inherited:** Schema columns, measures, `generated:` flag, `partition_by:`. The child can add `additional_schema:` columns beyond the inherited base.

---


### Source-Level Extends

Source files in `sources/*.md` use `extends:` to reference the base template (not a specific table):

```yaml
---

type: domain-model-source
source: payments
extends: _base.accounting.ledger_entry
maps_to: fact_ledger_entries
from: bronze.chicago_payments
---

```

**Path format:** `_base.{domain}.{template}`

Examples:
```
_base.accounting.ledger_entry
_base.accounting.financial_statement
_base.public_safety.crime
_base.finance.securities
_base.finance.corporate_action
```

Source-level `extends:` tells the loader which `canonical_fields` contract to validate against — every non-nullable canonical field must have a real alias (not `null` or `TBD`).

---


### View-Level Extends

View files in `views/*.md` use `extends:` to reference a base template view:

```yaml
---

type: domain-model-view
view: view_equalized_values
extends: _base.property.parcel._view_equalized_values
view_type: derived
---

```

**Path format:** `_base.{domain}.{template}._{view_name}`

The child view inherits the base view's schema, assumptions, and measures, and can override `assumptions:` to bind to concrete data sources.

---


### Schema Merge Rules

When a child `extends:` a parent:

1. Child inherits **all** parent columns
2. Child can **add** new columns via `additional_schema:`
3. Child can **override** column options (nullable, default, derived)
4. Child **cannot** change a column's type
5. Child **cannot** remove parent columns
6. `additional_schema:` columns are appended after inherited columns

---


### Inheritance Chain

Base templates can extend other base templates, forming a chain:

```
_base._base_.event                          # Root event: event_id, date_id, location_id
  └── _base.accounting.financial_event      # Adds: amount, event_type, legal_entity_id
        └── _base.accounting.ledger_entry   # Adds: entry_id, entry_type, payee, transaction_amount
```

Each level adds `canonical_fields` and table columns. The child inherits the full chain.

The complete inheritance tree is documented in `domain_base.md`.

---


### subset_of and subset_value

Used on child base templates that define the **field contract** for a typed subset of a parent template. The child's `canonical_fields` and `measures` are **auto-absorbed** into the parent's wide dimension table as nullable columns with `{subset: VALUE}` metadata.

```yaml
# _base/property/residential.md — single source of truth for residential fields
type: domain-base
model: residential_parcel
extends: _base.property.parcel
subset_of: _base.property.parcel
subset_value: RESIDENTIAL

canonical_fields:
  - [bedrooms, integer, nullable: true, description: "Number of bedrooms"]
  - [bathrooms, double, nullable: true, description: "Number of bathrooms"]
  - [stories, double, nullable: true, description: "Number of stories"]

measures:
  - [avg_bedrooms, avg, bedrooms, "Average bedrooms", {format: "#,##0.0"}]
```

| Key | Description |
|-----|-------------|
| `subset_of` | Parent base template this is a subset of |
| `subset_value` | Discriminator value that selects this subset |

**Auto-absorption (v3.0):** The parent template declares `subsets.pattern: wide_table` with `target_table: _dim_parcel`. The loader discovers child templates by `subset_of` (or explicit `subsets.values.*.extends` references) and automatically:

1. Appends child `canonical_fields` to `target_table.schema` as nullable columns with `{subset: VALUE}`
2. Appends child `measures` to `target_table.measures` with `{subset: VALUE}`
3. Updates parent `canonical_fields` with the unioned set

**Adding a field**: Define it in the child template's `canonical_fields` — it auto-propagates to the parent's wide table. No need to edit the parent template.

**Current subsets:**

| Parent | Subset | subset_value | Fields |
|--------|--------|-------------|--------|
| `_base.property.parcel` | `_base.property.residential` | `RESIDENTIAL` | bedrooms, bathrooms, stories, garage_spaces, basement, exterior_wall |
| `_base.property.parcel` | `_base.property.commercial` | `COMMERCIAL` | commercial_sqft, commercial_units, residential_units, space_type, floors |
| `_base.property.parcel` | `_base.property.industrial` | `INDUSTRIAL` | industrial_sqft, loading_docks, ceiling_height, zoning_class |

The securities domain uses a different pattern (separate models) — see `subsets.md`.

---


### Multi-Extends Resolution

When a model extends multiple bases, the loader merges them in order:

```yaml
extends:
  - _base.accounting.ledger_entry        # 1st: canonical_fields + tables
  - _base.accounting.financial_statement  # 2nd: additional canonical_fields + tables
  - _base.accounting.fund                # 3rd: additional tables
```

**Merge rules:**
- `canonical_fields` are unioned (no duplicates by field name)
- `tables` are unioned (each base contributes different template tables)
- `auto_edges` are unioned
- `python_measures` are unioned (child override wins on name collision)
- `behaviors` are unioned
- `federation` uses last-wins (most specific base's config)

This enables models like `municipal_finance` to combine ledger entries, budget statements, fund accounting, and chart of accounts — each from a separate base template — into one model.

---


### Quick Reference

| Level | extends Format | What's Inherited |
|-------|---------------|-----------------|
| Model (`model.md`) | `_base.{domain}.{template}` | canonical_fields, auto_edges, python_measures, federation, behaviors |
| Table (`tables/*.md`) | `_base.{domain}.{template}._{table}` | Schema columns, measures, generated flag, partition_by |
| Source (`sources/*.md`) | `_base.{domain}.{template}` | canonical_fields contract for alias validation |
| View (`views/*.md`) | `_base.{domain}.{template}._{view}` | Schema, assumptions, measures |
