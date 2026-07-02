---

type: reference
description: "Complete YAML reference for domain-model files"
---

> **Implementation Status**: Core fields (type, model, version, extends, depends_on, graph, build, hooks, storage, measures) are fully implemented. `ml_models:` is **parsed only** (dataclass exists but build pipeline does not use it). `views:` is **not implemented**.


## domain-model Guide

A `domain-model` is a concrete implementation that maps source data to a canonical schema defined by a `domain-base`. It produces materialized tables in Silver.

---


### File Types

| Type | File | Purpose |
|------|------|---------|
| `domain-model` | `model.md` | Model metadata, graph, build, measures |
| `domain-model-table` | `tables/*.md` | Table definitions (fact, dimension) |
| `domain-model-source` | `sources/*.md` | Bronze-to-canonical alias mapping |
| `domain-model-view` | `views/*.md` | Derived or rollup view definitions |

---


### Directory Structure

```
models/{domain}/{subdomain}/
├── model.md                    # domain-model
├── tables/
│   ├── fact_*.md               # domain-model-table (fact)
│   ├── dim_*.md                # domain-model-table (dimension)
│   └── _int_*.md               # domain-model-table (intermediate)
├── sources/
│   └── {entity}/
│       └── {subdomain}/
│           ├── source_a.md     # domain-model-source
│           └── source_b.md
└── views/
    └── view_*.md               # domain-model-view
```

**Auto-discovery:** The loader reads `model.md` first, then discovers all `sources/*.md` and `tables/*.md` automatically. No wiring needed.

---


### model.md — All Top-Level Keys

#### Required

| Key | Type | Description |
|-----|------|-------------|
| `type` | string | Always `domain-model` |
| `model` | string | Model identifier (e.g., `municipal_finance`) |
| `version` | string | Semantic version (e.g., `3.1`) |
| `description` | string | What this model provides |
| `extends` | string or list | Parent base template(s): `_base.accounting.ledger_entry` or `[_base.accounting.ledger_entry, _base.accounting.fund]` |

#### Optional — Dependencies & Storage

| Key | Type | Description |
|-----|------|-------------|
| `depends_on` | list | Models that must build first: `[temporal, municipal_entity]` |
| `sources_from` | string | Directory of source files: `sources/` or `sources/{entity}/` |
| `storage` | object | Storage configuration (see storage.md) |
| `storage.format` | string | Always `delta` |
| `storage.sources_from` | string | Alternative location for `sources_from` |
| `storage.silver.root` | string | Output path: `storage/silver/municipal/{entity}/finance/` |

#### Optional — Graph

| Key | Type | Description |
|-----|------|-------------|
| `graph` | object | Edge and path definitions (see graph.md) |
| `graph.edges` | list | `[edge_name, from, to, on, type, cross_model]` tuples |
| `graph.paths` | object | Named multi-hop traversals with `steps:` |

#### Optional — Build

| Key | Type | Description |
|-----|------|-------------|
| `build` | object | Build configuration |
| `build.partitions` | list | Delta partition columns: `[date_id]` or `[year]` |
| `build.sort_by` | list | Z-order columns: `[security_id, date_id]` |
| `build.optimize` | boolean | Enable Delta optimization: `true` |
| `build.phases` | object | Multi-phase build ordering (see materialization.md) |

#### Optional — Measures

| Key | Type | Description |
|-----|------|-------------|
| `measures` | object | Model-level measures (see measures.md) |
| `measures.simple` | list | `[name, aggregation, column, description, {options}]` |
| `measures.computed` | list | `[name, expression, SQL, description, {options}]` |

#### Optional — Federation & Views

| Key | Type | Description |
|-----|------|-------------|
| `federation` | object | Federation config: `{enabled: true, union_key: domain_source}` |
| `views` | object | View definitions that extend base template views |

#### Optional — Metadata

| Key | Type | Description |
|-----|------|-------------|
| `metadata` | object | Model metadata |
| `metadata.domain` | string | Domain classification: `municipal`, `corporate`, `securities` |
| `metadata.subdomain` | string | Sub-classification: `finance`, `public_safety` |
| `metadata.owner` | string | Owning team: `data_engineering` |
| `status` | string | `active`, `deprecated`, `draft` |

#### Special-Purpose Keys

| Key | Type | Used By | Description |
|-----|------|---------|-------------|
| `calendar_config` | object | temporal only | Generation params: `{start_date, end_date, fiscal_year_start_month}` |
| `ml_models` | object | forecast only | ML model definitions: `{arima_7d: {type: arima, ...}}` |
| `tables` | object | temporal only | Inline table defs (normally in separate files) |

---


### domain-model-source — All Keys

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `type` | string | Yes | Always `domain-model-source` |
| `source` | string | Yes | Source identifier (e.g., `payments`) |
| `extends` | string | Yes | Base template: `_base.accounting.ledger_entry` |
| `maps_to` | string | Yes | Target table: `fact_ledger_entries` |
| `from` | string | Yes | Bronze table: `bronze.chicago_payments` |
| `domain_source` | string | Yes | Origin literal: `"'chicago'"` |
| `aliases` | list | Yes | `[canonical_field, source_expression]` pairs |
| `entry_type` | string | No | Ledger discriminator: `VENDOR_PAYMENT`, `PAYROLL` |
| `event_type` | string | No | Event discriminator: `APPROPRIATION`, `REVENUE` |
| `transform` | string | No | `unpivot` for wide-to-long |
| `unpivot_aliases` | list | No | Column-to-account mappings for unpivot |

See sources.md for alias conventions, hashing patterns, and worked examples.
See source_onboarding.md for the 5-phase onboarding workflow.

---


### domain-model-table — All Keys

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `type` | string | Yes | Always `domain-model-table` |
| `table` | string | Yes | Table name: `dim_vendor`, `fact_ledger_entries` |
| `extends` | string | No | Base template table: `_base.accounting.ledger_entry._fact_ledger_entries` |
| `table_type` | string | Yes | `dimension` or `fact` |
| `primary_key` | list | Yes | PK columns: `[entry_id]` |
| `unique_key` | list | No | Natural key columns: `[account_code]`, `[ticker]` |
| `schema` | list | Yes* | `[column, type, nullable, description, {options}]` |
| `additional_schema` | list | No | Extra columns beyond inherited base |
| `partition_by` | list | No | Delta partition columns: `[date_id]` |
| `transform` | string | No | `aggregate`, `distinct`, or `unpivot` |
| `group_by` | list | No | Grouping columns (if transform = aggregate/distinct) |
| `enrich` | list | No | Post-build enrichment from related tables |
| `measures` | list | No | Table-level measures |
| `static` | boolean | No | `true` = seeded from `data:` block, not built from sources |
| `seed` | boolean | No | `true` = seeded dimension (alternative to `static`) |
| `data` | list | No | Seed data rows (used with `static: true` or `seed: true`) |
| `generated` | boolean | No | `true` = computed post-build, not from bronze sources |
| `filters` | list | No | SQL WHERE predicates on source data |
| `persist` | boolean | No | `false` = intermediate, not written to storage |

*Facts that extend a base inherit schema; dimensions typically need explicit schema.

See tables.md for schema column format and options.

---


### domain-model-view — All Keys

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `type` | string | Yes | Always `domain-model-view` |
| `view` | string | Yes | View name: `view_equalized_values` |
| `extends` | string | No | Base template view: `_base.property.parcel._view_equalized_values` |
| `view_type` | string | Yes | `derived` or `rollup` |
| `assumptions` | object | No | Override assumption sources and join conditions |
| `schema` | list | No | Output columns |
| `measures` | list | No | View-level measures |

See views.md for derived vs rollup patterns and assumption binding.

---


### Complete Example

```yaml
---

type: domain-model
model: municipal_finance
version: 3.1
description: "Municipal payments, contracts, and budget data"

extends:
  - _base.accounting.ledger_entry
  - _base.accounting.financial_statement
  - _base.accounting.fund

depends_on: [temporal, municipal_entity, county_property]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/finance/

graph:
  edges:
    - [entry_to_vendor, fact_ledger_entries, dim_vendor, [vendor_id=vendor_id], many_to_one, null]
    - [entry_to_contract, fact_ledger_entries, dim_contract, [contract_id=contract_id], many_to_one, null, optional: true]
  paths:
    payment_to_contract_vendor:
      description: "Drill from payment to contract to vendor"
      steps:
        - {from: fact_ledger_entries, to: dim_contract, via: contract_id}
        - {from: dim_contract, to: dim_vendor, via: vendor_id}

build:
  partitions: [date_id]
  optimize: true
  phases:
    1: { tables: [fact_ledger_entries, fact_budget_events], persist: true }
    2: { tables: [dim_vendor, dim_department], persist: true, enrich: true }

measures:
  simple:
    - [total_payments, sum, fact_ledger_entries.transaction_amount, "Total payments", {format: "$#,##0.00"}]
  computed:
    - [payments_per_vendor, expression, "SUM(amount) / NULLIF(COUNT(DISTINCT vendor_id), 0)", "Avg per vendor", {format: "$#,##0.00"}]

federation:
  enabled: true
  union_key: domain_source

metadata:
  domain: municipal
  subdomain: finance
status: active
---

```
