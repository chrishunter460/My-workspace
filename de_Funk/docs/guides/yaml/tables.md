---

type: reference
description: "Complete YAML reference for domain-model-table files"
---

> **Implementation Status**: Core features (schema, primary_key, table_type, seed, distinct, union, enrich, unpivot) are fully implemented. `derivations:` is **not implemented**. `unique_key` is **parsed but not enforced** during build.


## tables Guide

A `domain-model-table` defines one materialized table in the Silver layer. Tables are the single source of truth for column definitions. Data sourcing is handled by source files (`maps_to:` links sources to tables); tables do not declare `from:`.

---


### All Table Keys

#### Required

| Key | Type | Description |
|-----|------|-------------|
| `type` | string | Always `domain-model-table` |
| `table` | string | Table name: `fact_ledger_entries`, `dim_vendor` |
| `table_type` | string | `fact` or `dimension` |
| `primary_key` | list | PK columns: `[entry_id]`, `[parcel_id, year]` |
| `schema` | list | Column definitions (required unless inherited via `extends:`) |

#### Optional — Inheritance

| Key | Type | Description |
|-----|------|-------------|
| `extends` | string | Base template table: `_base.accounting.ledger_entry._fact_ledger_entries` |
| `additional_schema` | list | Extra columns beyond what `extends:` provides |
| `derivations` | map | Source-specific column expressions — overrides `derived:` on inherited columns |

#### Optional — Natural Key

| Key | Type | Description |
|-----|------|-------------|
| `unique_key` | list | Business/natural key columns that must be unique (distinct from surrogate PK) |

> **Note:** `unique_key` is parsed but **not enforced** during build — no dedup
> or uniqueness validation occurs. Duplicate rows are allowed. It serves as
> documentation of the intended natural key.

`unique_key` is used on 18+ dimension tables. It declares the natural key that identifies a real-world entity, while `primary_key` is the surrogate hash-based key.

```yaml
# Single-column natural key
primary_key: [company_id]
unique_key: [ticker]

# Compound natural key
primary_key: [geography_id]
unique_key: [geography_type, geography_code]

# Another compound example
primary_key: [crime_type_id]
unique_key: [iucr_code, fbi_code]
```

#### Optional — Build Control

| Key | Type | Description |
|-----|------|-------------|
| `partition_by` | list | Delta partition columns: `[date_id]`, `[year]` |
| `transform` | string | `aggregate`, `distinct`, or `unpivot` |
| `group_by` | list | Grouping columns (required if `transform: aggregate` or `distinct`) |
| `filters` | list | SQL WHERE predicates applied to source data during build |
| `persist` | boolean | `true` = write to Silver storage (default), `false` = intermediate only |
| `generated` | boolean | `true` = computed post-build, not loaded from bronze sources |
| `static` | boolean | `true` = seeded from inline `data:` block, not built from sources |
| `seed` | boolean | `true` = seeded dimension (synonym for `static`) |
| `data` | list | Inline seed rows (used with `static: true` or `seed: true`) |

#### Optional — Enrichment

| Key | Type | Description |
|-----|------|-------------|
| `enrich` | list | Post-build enrichment — joins related tables to add aggregate columns |

#### Optional — Measures

| Key | Type | Description |
|-----|------|-------------|
| `measures` | list | Table-level measures: `[name, aggregation, column, description, {options}]` |

---


### Schema Column Format

```yaml
# [column, type, nullable, description, {options}]
schema:
  - [entry_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(entry_type, '_', source_id)))"}]
  - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
  - [amount, "decimal(18,2)", false, "Transaction amount"]
  - [department, string, true, "Nullable field"]
  - [status, string, false, "Status code", {enum: [OPEN, CLOSED, PENDING]}]
```

### Schema Column Options

| Option | Description | Example |
|--------|-------------|---------|
| `derived` | SQL expression to compute value | `{derived: "ABS(HASH(ticker))"}` |
| `fk` | Foreign key reference | `{fk: temporal.dim_calendar.date_id}` |
| `enum` | Allowed values | `{enum: [EXPENSE, REVENUE, TRANSFER]}` |
| `default` | Default value | `{default: true}` |
| `unique` | Unique constraint on column | `{unique: true}` |
| `format` | Display format | `{format: "$#,##0.00"}` |

---


### Fact Table (extends base, schema inherited)

Facts typically `extends:` a base template table, inheriting its schema. Use `additional_schema:` to add model-specific columns.

```yaml
---

type: domain-model-table
table: fact_ledger_entries
extends: _base.accounting.ledger_entry._fact_ledger_entries
table_type: fact
primary_key: [entry_id]
partition_by: [date_id]
persist: true

additional_schema:
  - [vendor_id, integer, true, "FK to dim_vendor"]
  - [department_id, integer, true, "FK to dim_department"]
  - [contract_id, integer, true, "FK to dim_contract"]
---

```

Data flows into fact tables via source files that declare `maps_to: fact_ledger_entries`. Multiple sources are unioned automatically.

---


### Fact Table with Filters

Use `filters:` when a fact table reads from a shared bronze source and needs to select a subset. Common for models that share a unified bronze table (e.g., securities).

```yaml
---

type: domain-model-table
table: fact_stock_prices
extends: _base.finance.securities._fact_prices
table_type: fact
primary_key: [price_id]
partition_by: [date_id]
filters:
  - "asset_type = 'stocks'"
---

```

---


### Dimension Table (schema explicit)

Dimensions built from source data typically need explicit `schema:` and often use `transform: aggregate` or `distinct` to deduplicate.

```yaml
---

type: domain-model-table
table: dim_vendor
table_type: dimension
transform: aggregate
group_by: [payee]
primary_key: [vendor_id]
unique_key: [vendor_name]

schema:
  - [vendor_id, integer, false, "PK", {derived: "ABS(HASH(payee))"}]
  - [vendor_name, string, false, "Vendor name"]
  - [total_payments, "decimal(18,2)", true, "Lifetime total", {derived: "SUM(transaction_amount)"}]
  - [payment_count, integer, true, "Number of payments", {derived: "COUNT(DISTINCT entry_id)"}]
---

```

---


### Generated Table

`generated: true` marks tables that are computed post-build from other Silver tables, not loaded from bronze sources. Typically used for technical indicators and ML outputs.

```yaml
---

type: domain-model-table
table: fact_stock_technicals
extends: _base.finance.securities._fact_technicals
table_type: fact
generated: true
primary_key: [technical_id]
partition_by: [date_id]
---

```

The base template `_fact_technicals` declares `generated: true` and defines the schema (SMA, EMA, MACD, RSI, ATR, Bollinger bands). The concrete table inherits everything.

**Where used:** `fact_stock_technicals` (computed from prices), `fact_forecast_price`, `fact_forecast_metrics`, `dim_model_registry` (ML outputs).

---


### Static / Seeded Dimension

`static: true` (or `seed: true`) marks dimensions populated from an inline `data:` block rather than bronze sources. Used for reference data that doesn't change with ingestion.

**Compact row format** (many rows):

```yaml
---

type: domain-model-table
table: dim_financial_account
extends: _base.accounting.chart_of_accounts._dim_chart_of_accounts
table_type: dimension
static: true
primary_key: [account_id]
unique_key: [account_code]

data:
  # Income Statement
  - {account_code: TOTAL_REVENUE, account_name: "Total Revenue", account_type: REVENUE, statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 1}
  - {account_code: COST_OF_REVENUE, account_name: "Cost of Revenue", account_type: EXPENSE, statement_section: INCOME_STATEMENT, normal_balance: DEBIT, is_rollup: false, format_type: CURRENCY, level: 2, display_order: 2}
---

```

**Expanded row format** (few rows, more readable):

```yaml
---

type: domain-model-table
table: dim_municipality
extends: _base.entity.municipality._dim_municipality
table_type: dimension
primary_key: [municipality_id]
unique_key: [municipality_name, municipality_type]
seed: true

data:
  - municipality_id: "ABS(HASH(CONCAT('CITY_', 'Chicago')))"
    municipality_name: "Chicago"
    municipality_type: CITY
    fips_code: "1714000"
    state: IL
    population: 2746388
---

```

`static` and `seed` are synonyms — use whichever reads best. Both signal "no bronze source; populate from `data:` block."

---


### Enrichment

`enrich:` adds pre-computed aggregate columns to a dimension by joining related fact tables back after initial build. This runs during build phase 2 (after facts are persisted in phase 1).

**Simple enrichment** (one source):

```yaml
enrich:
  - from: fact_ledger_entries
    join: [contract_id = contract_id]
    columns:
      - [total_paid, "decimal(18,2)", true, "Total payments", {derived: "SUM(transaction_amount)"}]
      - [payment_count, integer, true, "Payment count", {derived: "COUNT(DISTINCT entry_id)"}]
      - [first_payment_date, date, true, "First payment", {derived: "MIN(transaction_date)"}]
      - [last_payment_date, date, true, "Most recent payment", {derived: "MAX(transaction_date)"}]
```

**Multi-source enrichment with filters** (different slices of the same fact):

```yaml
enrich:
  - from: fact_ledger_entries
    join: [department_id = org_unit_id]
    columns:
      - [total_paid, "decimal(18,2)", true, "Total actual spending", {derived: "SUM(transaction_amount)"}]
      - [payment_count, integer, true, "Number of payments", {derived: "COUNT(DISTINCT entry_id)"}]

  - from: fact_budget_events
    join: [department_id = org_unit_id]
    filter: "event_type = 'APPROPRIATION'"
    columns:
      - [total_appropriated, "decimal(18,2)", true, "Total budgeted", {derived: "SUM(amount)"}]

  - from: fact_budget_events
    join: [department_id = org_unit_id]
    filter: "event_type = 'POSITION'"
    columns:
      - [total_personnel_budget, "decimal(18,2)", true, "Personnel costs", {derived: "SUM(amount)"}]
```

**Derived columns** (computed from enriched columns, no additional join):

```yaml
  - derived:
      - [budget_variance, "decimal(18,2)", true, "Budget minus actual", {derived: "COALESCE(total_appropriated, 0) - COALESCE(total_paid, 0)"}]
      - [budget_utilization_pct, "decimal(5,4)", true, "% of budget used", {derived: "COALESCE(total_paid, 0) / NULLIF(total_appropriated, 0)"}]
```

**Enrich block structure:**

| Element | Description |
|---------|-------------|
| `from:` | Source table to aggregate from |
| `join:` | Join condition: `[dim_col = fact_col]` |
| `filter:` | Optional SQL WHERE on the source rows |
| `columns:` | Aggregate columns to add, same `[name, type, nullable, desc, {derived}]` format |
| `derived:` | Computed columns using previously enriched values (no join needed) |

---


### Derivations (Source-Specific Column Mapping)

`derivations:` is a flat map that overrides the `derived:` option on inherited columns without repeating the full schema. Use it when a model table `extends:` a base table and needs to map canonical column names to source-specific expressions.

**Without derivations** (old pattern — full schema repeated):

```yaml
extends: _base.property.parcel._dim_parcel
schema:
  - [parcel_id, string, false, "PK", {derived: "LPAD(pin, 14, '0')"}]
  - [parcel_code, string, false, "Natural key", {derived: "pin"}]
  - [property_class, string, true, "Classification code", {derived: "class"}]
  - [bedrooms, integer, true, "Number of bedrooms", {subset: RESIDENTIAL, derived: "bdrm"}]
  # ... every column repeated just to set derived: ...
```

**With derivations** (new pattern — only the differences):

```yaml
extends: _base.property.parcel._dim_parcel

derivations:
  parcel_id: "LPAD(pin, 14, '0')"
  parcel_code: "pin"
  property_class: "class"
  neighborhood_code: "nbhd"
  bedrooms: "bdrm"
  bathrooms: "COALESCE(fbath, 0) + COALESCE(hbath, 0) * 0.5"
  commercial_sqft: "comm_sqft"
```

**Behavior:**
- Full schema (types, nullable, descriptions, `{subset}` metadata) inherited from base
- `derivations:` sets `derived:` on named columns — only those columns need to be listed
- Columns **not** in `derivations:` use the canonical name as-is (passthrough from source)
- Can be combined with `additional_schema:` for model-specific columns not in the base

**When to use**: Any table that `extends:` a base template and needs source-specific column transformations. Eliminates repeating the entire schema just to map column names.

---


### Table-Level Measures

Tables can declare measures directly. Format matches model-level `measures.simple`:

```yaml
measures:
  # [name, aggregation, column, description, {options}]
  - [total_rides, sum, rides, "Total ridership", {format: "#,##0"}]
  - [avg_daily_rides, avg, rides, "Average daily ridership", {format: "#,##0"}]
  - [station_count, count_distinct, station_id, "Number of stations", {format: "#,##0"}]
```

Expression measures embed SQL as the third element:

```yaml
measures:
  - [avg_tax_per_parcel, expression, "SUM(transaction_amount) / NULLIF(COUNT(DISTINCT parcel_id), 0)", "Average tax per parcel", {format: "$#,##0.00"}]
```

Aggregation types: `count`, `count_distinct`, `sum`, `avg`, `min`, `max`, `expression`.

---


### Naming Conventions

| Prefix | Type | Materialized | Description |
|--------|------|-------------|-------------|
| `fact_*` | fact | Yes | Event/transaction tables |
| `dim_*` | dimension | Yes | Reference/lookup tables |
| `_int_*` | intermediate | Configurable | Staging tables, use `persist: false` |
| `_fact_*` | template fact | Never | Base template table (inherited) |
| `_dim_*` | template dimension | Never | Base template table (inherited) |

Template tables (underscore prefix) live in `_base/` files. Concrete tables (no prefix) live in `models/*/tables/` files. The naming maps 1:1: `_fact_ledger_entries` → `fact_ledger_entries`.
