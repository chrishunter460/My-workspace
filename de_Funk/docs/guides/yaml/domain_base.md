---

type: reference
description: "Complete YAML reference for domain-base template files"
---

> **Implementation Status**: All features fully implemented.


## domain-base Guide

A `domain-base` is a reusable template that defines canonical schemas, measures, and graph patterns. It is never materialized — only inherited by concrete `domain-model` files via `extends:`.

---


### All Top-Level Keys

#### Required

| Key | Type | Description |
|-----|------|-------------|
| `type` | string | Always `domain-base` |
| `model` | string | Template identifier (e.g., `ledger_entry`, `crime`, `calendar`) |
| `version` | string | Semantic version |
| `description` | string | What this template provides |

#### Optional — Inheritance

| Key | Type | Description |
|-----|------|-------------|
| `extends` | string | Parent base template: `_base._base_.event` or `_base.property.parcel` |
| `subset_of` | string | Parent template this is a subset of: `_base.property.parcel` |
| `subset_value` | string | Which subset value this represents: `RESIDENTIAL` |

#### Optional — Schema Contract

| Key | Type | Description |
|-----|------|-------------|
| `canonical_fields` | list | Semantic field definitions — the contract that models must fulfill |
| `tables` | object | Template table definitions with leading underscore names (`_fact_*`, `_dim_*`) |

#### Optional — Graph & Edges

| Key | Type | Description |
|-----|------|-------------|
| `auto_edges` | list | FK patterns auto-applied to every fact table with matching columns |
| `graph` | object | Template-level edge definitions |
| `graph.edges` | list | Edge tuples (same format as model edges) |

#### Optional — Behaviors & Classification

| Key | Type | Description |
|-----|------|-------------|
| `behaviors` | list | Capability tags: `[temporal, geo_locatable, subsettable]` |
| `subsets` | object | Declarative data slicing by dimension discriminator |
| `views` | object | Template view definitions with leading underscore names (`_view_*`) |

#### Optional — Generation (temporal only)

| Key | Type | Description |
|-----|------|-------------|
| `generation` | object | Self-generation config for seeded dimensions |
| `generation.params` | object | Generation parameters with type, default, description |

#### Optional — Metadata

| Key | Type | Description |
|-----|------|-------------|
| `domain` | string | Domain classification: `_base`, `property`, `accounting`, `temporal` |
| `tags` | list | Classification tags: `[base, template, event, root]` |
| `status` | string | `active`, `deprecated`, `draft` |

---


### canonical_fields

The semantic contract that domain-models must fulfill. Format:

```yaml
canonical_fields:
  # [field_name, type, nullable: bool, description: "meaning"]
  - [event_id, integer, nullable: false, description: "Surrogate primary key"]
  - [legal_entity_id, integer, nullable: true, description: "FK to owning legal entity"]
  - [event_date, date, nullable: false, description: "When the event occurred"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar (YYYYMMDD)"]
  - [location_id, integer, nullable: true, description: "FK to geo_location (nullable)"]
```

**Rules:**
- `nullable: false` fields MUST have a real alias in every source (not `null` or `TBD`)
- `nullable: true` fields MAY be null if the source lacks the data
- Inherited through `extends:` chain — child adds fields, doesn't remove parent's

**Used by:** All 28 files in `_base/` (exclusively a base template feature).

---


### Template Tables

Tables in base templates use underscore prefixes to indicate they are templates:

```yaml
tables:
  _fact_ledger_entries:
    type: fact
    primary_key: [entry_id]
    partition_by: [date_id]
    schema:
      - [entry_id, integer, false, "PK", {derived: "ABS(HASH(...))"}]
      - [date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
```

Concrete models reference these via `extends:` on their table definitions:

```yaml
# models/municipal/finance/tables/fact_ledger_entries.md
extends: _base.accounting.ledger_entry._fact_ledger_entries
```

---


### auto_edges

FK patterns applied automatically to every fact table whose schema contains the matching column. Declared on base templates, inherited through the chain.

```yaml
auto_edges:
  # [fk_column, target, on, type, cross_model]
  - [date_id, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
  - [location_id, geo_location._dim_location, [location_id=location_id], many_to_one, geo_location, optional: true]
```

**Which bases declare auto_edges:**

| Base | auto_edges | Inherited By |
|------|-----------|-------------|
| `_base._base_.event` | `date_id`, `location_id` | All event-chain bases |
| `_base.finance.securities` | `date_id` | securities, stocks |
| `_base.property.parcel` | `date_id` | county_property |

---


### python_measures (Base-Level)

Complex calculations defined on base templates, inherited by all extending models:

```yaml
python_measures:
  net_present_value:
    function: "accounting.measures.calculate_npv"
    description: "Net present value of cash flows"
    params:
      discount_rate: 0.10
      cash_flow_col: "amount"
      period_col: "period_end_date_id"
    returns: [legal_entity_id, npv_value, irr_value]
```

**Used by:** 7 base templates (financial_event, financial_statement, ledger_entry, earnings, corporate_action, securities, inspection).

---


### Template Table Measures

Measures defined inside template table schemas:

```yaml
tables:
  _dim_chart_of_accounts:
    measures:
      - [account_count, count_distinct, account_id, "Number of accounts", {format: "#,##0"}]
```

---


### behaviors

Informational tags documenting which cross-cutting capabilities the template supports:

```yaml
behaviors:
  - temporal        # auto_edges: date_id → calendar
  - geo_locatable   # auto_edges: location_id → geo_location
  - subsettable     # subsets: block present
```

**Note:** `federable` was removed — federation is now owned by `models/_base/` federation models. See federation.md.

See behaviors.md for full assignment table.

---


### generation (temporal only)

Declares that this is a self-generating dimension with configurable parameters:

```yaml
generation:
  description: "Self-generating dimension — no bronze source"
  params:
    start_date: {type: date, default: "2000-01-01", description: "First calendar date"}
    end_date: {type: date, default: "2050-12-31", description: "Last calendar date"}
    fiscal_year_start_month: {type: integer, default: 1, description: "Fiscal year start month"}
    holidays: {type: string, default: "US_FEDERAL", description: "Holiday calendar"}
```

Models override via `calendar_config:` in their model.md.

---


### Inheritance Chain

```
_base._base_.entity                    Pure entity (no time)
  ├── _base.entity.legal               Legal entities
  │   ├── _base.entity.company         Corporations
  │   └── _base.entity.municipality    Cities/counties
  ├── _base.entity.organizational_entity   Departments
  ├── _base.geography.geo_location     Point locations
  ├── _base.geography.geo_spatial      Boundaries
  ├── _base.finance.securities         Tradable instruments
  ├── _base.property.parcel            Land records
  │   ├── _base.property.residential   (subset)
  │   ├── _base.property.commercial    (subset)
  │   └── _base.property.industrial    (subset)
  ├── _base.property.tax_district      Tax zones
  ├── _base.accounting.chart_of_accounts  Account classification
  └── _base.accounting.fund            Fiscal pools

_base._base_.event                     Timestamped occurrence
  ├── _base.accounting.financial_event  Financial events (NPV, velocity)
  │   ├── _base.accounting.ledger_entry    Payments/payroll
  │   │   └── _base.accounting.financial_statement  Periodic reports
  │   └── (fact_property_tax inherits financial_event)
  ├── _base.corporate.earnings         EPS reports
  ├── _base.finance.corporate_action   Dividends/splits
  ├── _base.public_safety.crime        Crime incidents
  ├── _base.regulatory.inspection      Inspections
  ├── _base.operations.service_request  311 requests
  ├── _base.housing.permit             Building permits
  ├── _base.transportation.transit     Public transit
  └── _base.transportation.traffic     Road traffic

_base.temporal.calendar                Calendar dimension (standalone)
```

---


### Complete Example

```yaml
---

type: domain-base
model: ledger_entry
version: 3.0
description: "Single financial transaction — payment, payroll, contract"
extends: _base.accounting.financial_event

canonical_fields:
  - [entry_id, integer, nullable: false, description: "Surrogate PK"]
  - [entry_type, string, nullable: false, description: "Discriminator"]
  - [payee, string, nullable: true, description: "Who got paid"]
  - [transaction_amount, "decimal(18,2)", nullable: false, description: "Amount"]

tables:
  _fact_ledger_entries:
    type: fact
    primary_key: [entry_id]
    partition_by: [date_id]
    schema:
      - [entry_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(entry_type, '_', source_id)))"}]
      - [entry_type, string, false, "Discriminator"]
      - [transaction_amount, "decimal(18,2)", false, "Amount"]
    measures:
      - [total_amount, sum, transaction_amount, "Total", {format: "$#,##0.00"}]

python_measures:
  spending_velocity:
    function: "accounting.measures.calculate_spending_velocity"
    params: {window_days: 30, amount_col: "transaction_amount"}

graph:
  edges: []

behaviors:
  - temporal

domain: accounting
tags: [base, template, accounting, ledger]
status: active
---

```
