# Domain Models

Domain models are the core abstraction in de_Funk. Each model is a markdown file with YAML frontmatter that defines a dimensional snowflake schema -- facts, dimensions, measures, graph edges, and build instructions. The build system reads these configs, loads raw data from Bronze (Delta Lake tables ingested from external APIs), transforms it through source alias mappings, and writes typed Silver tables.

This document uses **Chicago municipal data** as the primary example because it demonstrates every pattern in the system: multiple source providers, multi-source UNION tables, cross-domain edges, dimension enrichment, and federation. The `county.property` domain provides a second example where the source provider is Cook County rather than Chicago.

---

## 1. Directory Layout

Every domain model lives under `domains/models/` in a directory that mirrors its canonical name. The directory contains three kinds of files:

| File | `type:` value | Purpose |
|------|---------------|---------|
| `model.md` | `domain-model` | Main config: graph, build phases, measures, dependencies |
| `tables/*.md` | `domain-model-table` | One file per Silver table: schema, PK, measures |
| `sources/**/*.md` | `domain-model-source` | One file per Bronze-to-Silver mapping |

The loader auto-discovers `tables/*.md` relative to each subdomain directory and `sources/**/*.md` at the domain-group level (e.g., `municipal/sources/`). You never list them explicitly.

### Municipal Domain Tree

The `municipal` top-level directory contains six subdomains. Each subdomain has its own `model.md` and `tables/`, but all sources are grouped together under `municipal/sources/chicago/` — organized by subdomain:

```
domains/models/municipal/
├── entity/
│   ├── model.md
│   └── tables/
│       └── ...
├── finance/
│   ├── model.md
│   └── tables/
│       ├── fact_budget_events.md
│       ├── fact_ledger_entries.md
│       ├── fact_property_tax.md
│       ├── dim_department.md
│       ├── dim_vendor.md
│       ├── dim_contract.md
│       ├── dim_fund.md
│       └── dim_chart_of_accounts.md
├── geospatial/
│   ├── model.md
│   └── tables/
│       ├── dim_community_area.md
│       ├── dim_ward.md
│       ├── dim_patrol_district.md
│       └── dim_patrol_area.md
├── public_safety/
│   ├── model.md
│   └── tables/
│       ├── fact_crimes.md
│       └── fact_arrests.md
├── regulatory/
│   ├── model.md
│   └── tables/
│       ├── fact_food_inspections.md
│       ├── fact_building_violations.md
│       ├── fact_business_licenses.md
│       └── dim_facility.md
├── operations/
│   ├── model.md
│   └── tables/
│       └── fact_service_requests.md
├── housing/
│   ├── model.md
│   └── tables/
│       └── fact_building_permits.md
├── transportation/
│   ├── model.md
│   └── tables/
│       ├── fact_bus_ridership.md
│       ├── fact_rail_ridership.md
│       └── fact_traffic.md
└── sources/                                   ← All sources grouped here
    └── chicago/                               ← Entity: City of Chicago
        ├── finance/
        │   ├── payments.md                    ← Socrata: vendor payments
        │   ├── contracts.md                   ← Socrata: city contracts
        │   ├── budget_appropriations.md       ← Socrata: annual budget
        │   ├── budget_revenue.md              ← Socrata: revenue estimates
        │   └── budget_positions.md            ← Socrata: budgeted salaries
        ├── geospatial/
        │   ├── community_areas.md             ← Socrata: 77 boundaries
        │   ├── wards.md                       ← Socrata: 50 wards
        │   ├── police_districts.md            ← Socrata: 22 districts
        │   └── police_beats.md               ← Socrata: ~280 beats
        ├── public_safety/
        │   ├── crimes.md                      ← Socrata: incidents 2001-present
        │   ├── arrests.md                     ← Socrata: arrest records
        │   └── iucr_codes.md                  ← Socrata: crime classification
        ├── regulatory/
        │   ├── food_inspections.md
        │   ├── building_violations.md
        │   └── business_licenses.md
        ├── operations/
        │   └── 311_requests.md
        ├── housing/
        │   ├── building_permits.md
        │   └── zoning_districts.md
        └── transportation/
            ├── cta_bus_ridership.md
            ├── cta_l_ridership.md
            ├── cta_l_stops.md
            └── traffic.md
```

### Why Sources Are Grouped Under `sources/{entity}/`

Sources live at the top level of each domain group (e.g., `municipal/sources/`, `county/sources/`), not under individual subdomains. Within `sources/`, they're organized by entity — the data provider or municipality. Today, Chicago is the only municipal entity, so all municipal sources live under `sources/chicago/{subdomain}/`. If Detroit were onboarded, its sources would go in `sources/detroit/` with different Bronze table references but the same `maps_to` targets. The `domain_source` discriminator column tracks which entity produced each row.

The county domain uses the same pattern with `cook_county` as the entity:

```
domains/models/county/
├── property/
│   ├── model.md
│   ├── tables/
│   │   ├── dim_parcel.md
│   │   ├── fact_assessed_values.md
│   │   └── fact_parcel_sales.md
│   └── views/
│       └── ...
├── geospatial/
│   ├── model.md
│   └── tables/
│       └── ...
└── sources/                               ← All county sources grouped here
    └── cook_county/                       ← Entity: Cook County
        ├── parcel_universe.md             ← Cook County Open Data
        ├── parcel_sales.md                ← Cook County Open Data
        ├── assessed_values.md             ← Cook County Open Data
        ├── municipalities.md              ← Cook County Open Data
        ├── neighborhoods.md               ← Cook County Open Data
        └── townships.md                   ← Cook County Open Data
```

Different providers, different APIs, different column names — but the same dimensional model on the Silver side. This separation keeps source mappings from cluttering subdomain directories and makes it easy to see all sources for an entity at a glance.

---

## 2. The model.md File

The `model.md` file is the main config for a domain model. Here is the actual frontmatter from `municipal.finance`, annotated key by key:

```yaml
---
type: domain-model                          # File role identifier
model: municipal.finance                    # Canonical name (used in depends_on, edges, storage)
version: 3.1
description: "Municipal payments, contracts, and budget data"

extends:                                    # Inherit base schemas
  - _base.accounting.ledger_entry
  - _base.accounting.financial_statement
  - _base.accounting.fund
  - _base.accounting.chart_of_accounts
  - _base.property.tax_district

depends_on: [temporal, municipal.entity, county.property]   # Build order

storage:
  format: delta
  sources_from: sources/{entity}/           # Where to find source files
  silver:
    root: storage/silver/municipal/{entity}/finance/    # Where Silver writes

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [entry_to_vendor, fact_ledger_entries, dim_vendor, [vendor_id=vendor_id], many_to_one, null]
    - [budget_to_calendar, fact_budget_events, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]
    - [budget_to_municipality, fact_budget_events, municipal.entity.dim_municipality, [legal_entity_id=municipality_id], many_to_one, municipal.entity]
    - [property_tax_to_parcel, fact_property_tax, county.property.dim_parcel, [parcel_id=parcel_id], many_to_one, county.property]
    # ... more edges omitted for brevity

  paths:
    payment_to_contract_vendor:
      description: "Drill from payment -> contract -> vendor"
      steps:
        - {from: fact_ledger_entries, to: dim_contract, via: contract_id}
        - {from: dim_contract, to: dim_vendor, via: vendor_id}

build:
  partitions: [date_id]
  optimize: true
  phases:
    1:
      description: "Build fact tables from source unions"
      tables: [fact_ledger_entries, fact_budget_events, fact_property_tax]
      persist: true
    2:
      description: "Build dimensions from facts (+ bronze for dim_contract)"
      tables: [dim_vendor, dim_department, dim_contract, dim_fund, dim_chart_of_accounts, dim_tax_district]
      persist: true
      enrich: true

measures:
  simple:
    - [total_payments, sum, fact_ledger_entries.transaction_amount, "Total payment amount", {format: "$#,##0.00"}]
    - [vendor_count, count_distinct, dim_vendor.vendor_id, "Unique vendors", {format: "#,##0"}]
    - [total_budget, sum, fact_budget_events.amount, "Total budget amount", {format: "$#,##0.00"}]
  computed:
    - [budget_surplus, expression, "SUM(CASE WHEN fact_budget_events.event_type = 'REVENUE' THEN fact_budget_events.amount ELSE 0 END) - SUM(CASE WHEN fact_budget_events.event_type = 'APPROPRIATION' THEN fact_budget_events.amount ELSE 0 END)", "Revenue minus appropriations", {format: "$#,##0.00"}]

federation:
  enabled: true
  union_key: domain_source

metadata:
  domain: municipal
  subdomain: finance
status: active
---
```

### Key-by-Key Reference

**`model:`** -- The canonical dotted name. This is how other models reference you in `depends_on`, how edge declarations find your tables (e.g., `municipal.finance.dim_vendor`), and how storage paths are resolved.

**`extends:`** -- Base templates from `domains/_base/`. The loader resolves each reference to a config dict and deep-merges it with this model. `_base.accounting.ledger_entry` provides the `_fact_ledger_entries` schema, standard date edges, and accounting measures. Multiple bases merge left-to-right.

**`depends_on:`** -- Models that must be built before this one. The build system topologically sorts all models by their dependencies. `municipal.finance` depends on `temporal` (calendar dimension), `municipal.entity` (municipality dimension), and `county.property` (parcel dimension for property tax joins).

**`storage:`** -- `sources_from` tells the loader where to find source mapping files. `silver.root` is where built tables are written. The `{entity}` placeholder is resolved at build time (e.g., `chicago`).

**`graph.edges:`** -- Join relationships. Each edge is a list: `[name, from_table, to_table, [join_keys], cardinality, cross_domain]`. When `cross_domain` is not `null`, the target table lives in another model (e.g., `temporal.dim_calendar`).

**`graph.paths:`** -- Named multi-hop traversals for the query engine. The `payment_to_contract_vendor` path chains two joins so a query can drill from a payment through its contract to the vendor.

**`build.phases:`** -- Intra-model build order. In municipal.finance, facts are built first (phase 1), then dimensions are extracted from those facts (phase 2). This is the reverse of models where dimensions come from Bronze directly.

**`measures:`** -- Pre-defined analytics. Simple measures are aggregations (`sum`, `count_distinct`, `avg`). Computed measures are SQL expressions. Both reference columns as `table.column`.

**`federation:`** -- Signals that this model participates in cross-domain UNION views. The `domain_source` column discriminates rows by provider.

---

## 3. Table Definitions

Each Silver table gets its own markdown file in `tables/`. Tables come in two flavors: fact tables (event data, partitioned by time) and dimension tables (reference data, typically smaller).

### Fact Table: fact_budget_events.md

This table demonstrates several patterns: base schema inheritance, additional model-specific columns, nullable columns that vary by source, and table-level measures.

```yaml
---
type: domain-model-table
table: fact_budget_events
extends: _base.accounting.financial_statement._fact_financial_statements
table_type: fact
primary_key: [statement_entry_id]
partition_by: [period_end_date_id]
persist: true

# Base financial_statement fields (inherited from extends)
schema:
  - [statement_entry_id, integer, false, "PK", {}]
  - [legal_entity_id, integer, false, "FK to reporting entity"]
  - [account_id, integer, false, "FK to chart of accounts", {fk: dim_chart_of_accounts.account_id}]
  - [period_end_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
  - [report_type, string, false, "budget"]
  - [amount, double, false, "Line item value", {format: $}]

# Budget-specific columns beyond base financial_statement schema
additional_schema:
  - [event_type, string, false, "APPROPRIATION, REVENUE, POSITION"]
  - [fiscal_year, integer, false, "Budget year", {derived: "YEAR(period_end_date_id)"}]
  - [department_code, string, true, "Department code (nullable for revenue sources)"]
  - [fund_code, string, true, "Fund code (nullable for position sources)"]
  - [department_id, integer, true, "FK to dim_department", {fk: dim_department.org_unit_id, derived: "CASE WHEN department_code IS NOT NULL THEN ABS(HASH(department_code)) ELSE null END"}]

measures:
  - [total_budget, sum, amount, "Total budgeted amount", {format: "$#,##0.00"}]
  - [appropriation_total, expression, "SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount ELSE 0 END)", "Total appropriations", {format: "$#,##0.00"}]
  - [budget_surplus, expression, "SUM(CASE WHEN event_type = 'REVENUE' THEN amount ELSE 0 END) - SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount ELSE 0 END)", "Revenue minus appropriations", {format: "$#,##0.00"}]
---
```

**Key patterns:**

- `extends:` inherits the base financial statement schema. The `schema:` block lists inherited columns for resolver indexing; `additional_schema:` adds budget-specific columns.
- `{derived: "..."}` in column options specifies SQL expressions computed at build time. The `department_id` FK is derived from a hash of `department_code`, but only when non-null.
- `{fk: dim_department.org_unit_id}` documents (but does not enforce) the foreign key relationship.
- Three different sources (appropriations, revenue, positions) UNION into this single table, distinguished by `event_type`. Some columns are nullable because not all source types have them (revenue sources have no department).

### Dimension Table: dim_department.md

This dimension demonstrates the "dimensions from facts" pattern and build-time enrichment:

```yaml
---
type: domain-model-table
table: dim_department
extends: _base.entity.organizational_entity._dim_org_unit
table_type: dimension
transform: distinct
from: fact_ledger_entries
union_from: [fact_ledger_entries, fact_budget_events]
group_by: [organizational_unit]
primary_key: [org_unit_id]
unique_key: [org_unit_code]

schema:
  - [org_unit_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(organizational_unit, 'UNKNOWN')))"}]
  - [org_unit_code, string, false, "Natural key", {derived: "COALESCE(organizational_unit, 'UNKNOWN')"}]
  - [org_unit_name, string, false, "Display name", {derived: "COALESCE(organizational_unit, 'UNKNOWN')"}]
  - [org_unit_type, string, false, "Type", {derived: "'DEPARTMENT'"}]
  - [legal_entity_id, integer, false, "City of Chicago", {derived: "ABS(HASH(CONCAT('CITY_', 'Chicago')))"}]

enrich:
  - from: fact_ledger_entries
    join: [organizational_unit = org_unit_code]
    columns:
      - [total_paid, "decimal(18,2)", true, "Total actual spending", {derived: "SUM(transaction_amount)", format: $}]
      - [payment_count, integer, true, "Number of payments", {derived: "COUNT(DISTINCT entry_id)", format: number}]

  - from: fact_budget_events
    join: [department_description = org_unit_code]
    filter: "event_type = 'APPROPRIATION'"
    columns:
      - [total_appropriated, "decimal(18,2)", true, "Total budgeted", {derived: "SUM(amount)", format: $}]

  - derived:
      - [budget_variance, "decimal(18,2)", true, "Budget minus actual", {derived: "COALESCE(total_appropriated, 0) - COALESCE(total_paid, 0)", format: $}]
      - [budget_utilization_pct, "decimal(5,4)", true, "% of budget used", {derived: "COALESCE(total_paid, 0) / NULLIF(total_appropriated, 0)", format: "%"}]
---
```

**Key patterns:**

- `transform: distinct` + `group_by: [organizational_unit]` means this dimension is built by taking distinct values from fact tables, not from a dedicated Bronze source.
- `union_from: [fact_ledger_entries, fact_budget_events]` unions two tables before applying DISTINCT, capturing departments that appear in either.
- `enrich:` blocks are materialized at build time. The builder LEFT JOINs aggregated fact data back onto the dimension, producing pre-computed columns like `total_paid` and `total_appropriated`.
- `derived:` entries in the enrich block compute columns from already-enriched columns (e.g., `budget_variance = total_appropriated - total_paid`).

### Dimension Table: dim_vendor.md

A simpler dimension built via aggregation from a single fact table:

```yaml
---
type: domain-model-table
table: dim_vendor
table_type: dimension
transform: aggregate
from: fact_ledger_entries
group_by: [payee]
primary_key: [vendor_id]
unique_key: [payee]

schema:
  - [vendor_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(payee, 'UNKNOWN')))"}]
  - [vendor_name, string, false, "Display name", {derived: "payee"}]
  - [total_payments, "decimal(18,2)", false, "Lifetime total", {derived: "SUM(transaction_amount)", format: $}]
  - [payment_count, integer, false, "Number of ledger entries", {derived: "COUNT(*)", format: number}]
  - [is_active, boolean, false, "Recent activity", {derived: "MAX(transaction_date) >= CURRENT_DATE - INTERVAL 2 YEAR"}]
---
```

Here `transform: aggregate` tells the builder to GROUP BY `payee` and compute the aggregate expressions in `{derived:}`. The result is a vendor profile with lifetime payment totals computed directly from the fact table.

### Schema Column Format

Every column is a list:

```yaml
# [name, type, nullable, description]              -- basic
# [name, type, nullable, description, {options}]    -- with options
```

Supported option keys:

| Key | Purpose | Example |
|-----|---------|---------|
| `derived` | SQL expression computed at build time | `"ABS(HASH(ticker))"` |
| `fk` | Documents foreign key target | `dim_department.org_unit_id` |
| `format` | Display format hint | `$`, `date`, `"#,##0"` |
| `enum` | Allowed values | `[common, preferred, adr]` |
| `default` | Default for nullable columns | `true`, `false` |

---

## 4. Source Attachments

Source files are the bridge between external APIs and the dimensional model. Each source file declares:
- Which Bronze table it reads from (`from:`)
- Which Silver table it writes to (`maps_to:`)
- How external API columns map to canonical schema columns (`aliases:`)

This is the most important pattern in the system. The source layer is where provider-specific column names, data formats, and quirks are absorbed, producing a clean canonical schema on the Silver side.

### Anatomy of a Source File

Here is the actual `budget_appropriations.md` that maps Chicago Data Portal (Socrata) budget data to `fact_budget_events`:

```yaml
---
type: domain-model-source
source: budget_appropriations
extends: _base.accounting.financial_statement
maps_to: fact_budget_events                     # Target Silver table
from: bronze.chicago_budget_appropriations      # Bronze source table
event_type: APPROPRIATION                       # Discriminator injected as literal column
domain_source: "'chicago'"                      # Entity discriminator

aliases:
  # Maps to financial_statement base schema
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [statement_entry_id, "ABS(HASH(CONCAT('APPROPRIATION', '_', CAST(year AS INT), '_', COALESCE(department_number,''), '_', COALESCE(appropriation_account,''))))"]
  - [account_id, "ABS(HASH(COALESCE(appropriation_account, 'UNCLASSIFIED')))"]
  - [period_end_date_id, "CAST(CONCAT(CAST(CAST(year AS INT) AS STRING), '1231') AS INT)"]
  - [report_type, "'budget'"]
  - [amount, "COALESCE(amount, CAST(ordinance_amount AS DOUBLE), CAST(appropriation_ordinance AS DOUBLE))"]
  - [reported_currency, "'USD'"]
  # Budget-specific columns
  - [fiscal_year, "CAST(year AS INT)"]
  - [department_code, department_number]
  - [department_description, department_description]
  - [fund_code, fund_code]
  - [fund_description, fund_description]
  - [account_code, appropriation_account]
  - [account_description, appropriation_account_description]
---
```

**How aliases work:**

Each alias is a pair: `[canonical_column_name, source_expression]`.

- **Simple pass-through**: `[fund_code, fund_code]` -- the Bronze column maps directly.
- **SQL expression**: `[statement_entry_id, "ABS(HASH(CONCAT('APPROPRIATION', '_', ...)))"]` -- computes a surrogate PK from a combination of source columns.
- **Literal value**: `[report_type, "'budget'"]` -- injects a constant string.
- **Coalesce**: `[amount, "COALESCE(amount, CAST(ordinance_amount AS DOUBLE), ...)"]` -- handles column name changes across API versions.

### Multi-Source UNION: Three Sources into One Fact Table

`fact_budget_events` has three source files that all declare `maps_to: fact_budget_events`:

| Source File | `from:` | `event_type` | `account_code` derived from |
|-------------|---------|--------------|----------------------------|
| `budget_appropriations.md` | `bronze.chicago_budget_appropriations` | APPROPRIATION | `appropriation_account` |
| `budget_revenue.md` | `bronze.chicago_budget_revenue` | REVENUE | `revenue_source` |
| `budget_positions.md` | `bronze.chicago_budget_positions_salaries` | POSITION | `title_code` |

Each source has completely different Bronze column names, but they all map to the same canonical schema. The config translator groups them by `maps_to` target and synthesizes a UNION node. At build time, `DomainModel._build_union_node()` loads each Bronze table, applies its aliases, injects discriminator columns (`event_type`, `domain_source`), and UNIONs the results.

The revenue source maps its account code from a different Bronze column than appropriations:

```yaml
# budget_revenue.md
aliases:
  - [account_id, "ABS(HASH(COALESCE(revenue_source, 'UNCLASSIFIED')))"]
  - [amount, "COALESCE(CAST(estimated_revenue AS DECIMAL(18,2)), CAST(ordinance_amount AS DOUBLE))"]
  - [account_code, revenue_source]          # Different Bronze column name
  - [department_code, department_number]     # Same as appropriations
```

The positions source has no fund information at all:

```yaml
# budget_positions.md
aliases:
  - [amount, total_budgeted_amount]
  - [account_code, title_code]              # Yet another Bronze column name
  - [fund_code, "null"]                     # Positions don't have funds
  - [fund_description, "null"]
```

This is why `fund_code` and `department_code` are nullable in the fact table schema -- not all source types populate them.

### Same Domain, Two Sources for One Fact Table

`fact_ledger_entries` demonstrates the same UNION pattern for a different reason -- payments and contracts are separate Socrata datasets but both represent financial transactions:

```yaml
# payments.md
from: bronze.chicago_payments
entry_type: VENDOR_PAYMENT
aliases:
  - [payee, vendor_name]
  - [transaction_amount, amount]
  - [transaction_date, check_date]
  - [contract_number, contract_number]

# contracts.md
from: bronze.chicago_contracts
entry_type: CONTRACT
aliases:
  - [payee, vendor_name]
  - [transaction_amount, award_amount]      # Different Bronze column for "amount"
  - [transaction_date, start_date]          # Different date column
  - [contract_number, contract_number]
```

Both produce rows with `payee`, `transaction_amount`, `transaction_date` -- the canonical ledger entry schema -- but they read from different Bronze tables with different column names.

### Cross-Provider Example: Cook County Sources

The `county.property` domain uses Cook County Open Data as its provider instead of Chicago Socrata. The source pattern is identical, only the Bronze table names and column names differ:

```yaml
# county/sources/cook_county/parcel_sales.md
type: domain-model-source
source: parcel_sales
extends: _base.property.parcel
maps_to: fact_parcel_sales
from: bronze.cook_county_parcel_sales           # Different provider prefix
domain_source: "'cook_county'"                  # Different entity

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('COUNTY_', 'Cook County')))"]
  - [parcel_id, "LPAD(CAST(pin AS STRING), 14, '0')"]   # Cook County uses "pin" for parcel ID
  - [sale_date, sale_date]
  - [sale_price, sale_price]
  - [sale_type, deed_type]                      # Cook County calls it "deed_type"
  - [property_class, class]                     # Cook County calls it "class"
  - [township_code, township_code]
```

And the assessed values source from the same provider:

```yaml
# county/sources/cook_county/assessed_values.md
from: bronze.cook_county_assessed_values
domain_source: "'cook_county'"
aliases:
  - [parcel_id, "LPAD(CAST(pin AS STRING), 14, '0')"]
  - [assessment_stage, stage_name]              # Cook County calls it "stage_name"
  - [assessed_value_land, av_land]              # Abbreviated column names
  - [assessed_value_building, av_bldg]
  - [assessed_value_total, av_tot]
```

The Bronze columns are provider-specific (`pin`, `av_land`, `av_bldg`), but the Silver columns are canonical (`parcel_id`, `assessed_value_land`). Any future provider (e.g., Will County) would write its own source files mapping its column names to the same canonical schema.

### How the Config Translator Processes Sources

The `config_translator.py` module converts source configs into `graph.nodes` entries:

1. **Group by target**: Sources are grouped by their `maps_to` value. All sources targeting `fact_budget_events` are collected together.
2. **Convert aliases**: The `aliases` list becomes a `select` dict: `{canonical_name: expression}`.
3. **Normalize `from`**: Provider-underscore notation is converted to dot notation for StorageRouter: `bronze.chicago_budget_appropriations` becomes `bronze.chicago.budget_appropriations`.
4. **Inject discriminators**: `event_type`, `entry_type`, and `domain_source` are added as literal columns.
5. **Single source**: Produces a standard node with `from`, `select`, and `derive`.
6. **Multiple sources**: Produces a `__union__` node that `DomainModel.custom_node_loading()` handles at build time.

---

## 5. Base Model Design Standard

The build machinery is implemented in three Python classes that form a composition hierarchy.

### BaseModel (`src/de_funk/models/base/model.py`)

The generic model class that all domain models inherit from. It provides:

- **Graph building**: Delegates to `GraphBuilder` to load Bronze tables, apply transforms, and materialize Silver tables.
- **Table access**: `get_table()`, `get_denormalized()`, `list_tables()` -- runtime access to built tables.
- **Measure calculation**: Delegates to `MeasureCalculator` for computing pre-defined analytics.
- **Persistence**: Delegates to `ModelWriter` for writing to Delta Lake.
- **Backend detection**: Auto-detects Spark vs DuckDB from the connection object.

Key lifecycle methods:

```python
class BaseModel:
    def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """Build model tables from Bronze layer."""
        self._graph_builder = GraphBuilder(self)
        self._dims, self._facts = self._graph_builder.build()
        return self._dims, self._facts

    def ensure_built(self):
        """Lazy build -- try Silver first, fall back to Bronze."""
        if not self._is_built:
            if self._load_from_silver():
                self._is_built = True
                return
            self.build()

    def custom_node_loading(self, node_id, node_config) -> Optional[DataFrame]:
        """Override point for domain-specific loading. Returns None to use default."""
        return None
```

### DomainModel (`src/de_funk/models/base/domain_model.py`)

Subclass of BaseModel that handles domain-config-specific build behaviors:

- **Seed tables**: Inline data blocks materialized as DataFrames.
- **UNION tables**: Multiple source files merged into one table.
- **Distinct/aggregate transforms**: Dimensions extracted from fact tables via GROUP BY.
- **Enrichment**: Aggregate columns from fact tables joined back onto dimensions.

The `custom_node_loading()` method intercepts special node types:

```python
class DomainModel(BaseModel):
    def custom_node_loading(self, node_id, node_config) -> Optional[DataFrame]:
        from_spec = node_config.get("from", "")

        if from_spec == "__seed__":
            return self._build_seed_node(node_id, node_config)
        if from_spec == "__union__":
            return self._build_union_node(node_id, node_config)
        if from_spec == "__distinct__":
            return self._build_distinct_node(node_id, node_config)

        return None  # Let GraphBuilder handle standard nodes
```

The UNION builder loads each source Bronze table, applies aliases as a SELECT, injects discriminator columns, and UNIONs all DataFrames:

```python
def _build_union_node(self, node_id, node_config) -> DataFrame:
    sources = node_config.get("_union_sources", [])
    dfs = []
    for source in sources:
        df = self.graph_builder._load_bronze_table(table)
        # Apply aliases as column selection
        df = self._select_columns(df, select_dict)
        # Inject discriminators
        df = self._apply_derive(df, "domain_source", source["domain_source"], node_id)
        df = self._apply_derive(df, "event_type", f"'{source['event_type']}'", node_id)
        dfs.append(df)
    # UNION all
    result = dfs[0]
    for df in dfs[1:]:
        result = result.unionByName(df, allowMissingColumns=True)
    return result
```

The distinct/aggregate builder handles dimensions extracted from facts:

```python
def _build_distinct_node(self, node_id, node_config) -> DataFrame:
    # Load source tables (possibly UNION multiple)
    # Apply GROUP BY or DISTINCT
    # Apply derived column expressions
    # Apply enrichment JOINs (aggregate columns from fact tables)
    df = self._apply_distinct_enrichments(df, enrich_specs, node_id)
    return df
```

### DomainBuilderFactory (`src/de_funk/models/base/domain_builder.py`)

The factory that bridges domain configs to the build pipeline:

1. Scans `domains/models/` for all `model.md` files.
2. For each model, creates a dynamic builder class with `type()`.
3. Each builder knows how to: load the raw domain config via `DomainConfigLoaderV4`, translate it via `translate_domain_config()`, and instantiate the appropriate model class.
4. Registers all builders with `BuilderRegistry` so the build script can discover them.

Most models use the generic `DomainModel`. Three models have custom classes:

| Model | Custom Class | Why |
|-------|-------------|-----|
| `temporal` | `TemporalModel` | Generates calendar dimension from date range, no Bronze source |
| `corporate.entity` | `CompanyModel` | Custom SEC CIK deduplication logic |
| `securities.stocks` | `StocksModel` | Technical indicator computation |

### Build Lifecycle

```
1. DomainBuilderFactory.create_builders()
   → Scans domains/, creates builder per model, registers with BuilderRegistry

2. build_models.py resolves topological order from depends_on
   → [temporal, geospatial, municipal.entity, municipal.geospatial, municipal.finance, ...]

3. For each model:
   a. Builder.get_model_config()
      → DomainConfigLoaderV4 reads model.md + tables/*.md + sources/**/*.md
      → translate_domain_config() synthesizes graph.nodes from tables + sources

   b. Builder instantiates DomainModel(connection, storage_cfg, translated_config)

   c. DomainModel.build()
      → GraphBuilder iterates build phases
      → Phase 1: fact tables (loaded from Bronze via UNION, aliases applied)
      → Phase 2: dimensions (DISTINCT/AGGREGATE from facts, enriched)
      → Each table: custom_node_loading() intercepts special types
      → ModelWriter.write_tables() persists to Delta Lake

   d. Builder.post_build()
      → Runs post_build enrichments (cross-domain computed columns)
```

---

## 6. Graph Edges and Dependencies

### Edge Format

Each edge is a list with 6-7 elements:

```yaml
# [name, from_table, to_table, [join_keys], cardinality, cross_domain, optional?]
- [entry_to_vendor, fact_ledger_entries, dim_vendor, [vendor_id=vendor_id], many_to_one, null]
- [budget_to_calendar, fact_budget_events, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]
```

| Position | Field | Description |
|----------|-------|-------------|
| 0 | `name` | Unique edge identifier |
| 1 | `from_table` | Source table (local or fully qualified) |
| 2 | `to_table` | Target table (local or fully qualified) |
| 3 | `[join_keys]` | List of `left_col=right_col` pairs |
| 4 | `cardinality` | `many_to_one`, `one_to_many`, `one_to_one` |
| 5 | `cross_domain` | Target model name if cross-domain, else `null` |
| 6 | `optional: true` | (Optional) Edge may not resolve if dependency missing |

Cross-domain edges use fully qualified table names: `municipal.entity.dim_municipality`, `county.property.dim_parcel`, `temporal.dim_calendar`.

### Named Paths

Paths define multi-hop traversals for complex queries:

```yaml
paths:
  payment_to_contract_vendor:
    description: "Drill from payment -> contract -> vendor"
    steps:
      - {from: fact_ledger_entries, to: dim_contract, via: contract_id}
      - {from: dim_contract, to: dim_vendor, via: vendor_id}
  property_tax_chain:
    description: "Property tax -> parcel -> tax district"
    steps:
      - {from: fact_property_tax, to: county.property.dim_parcel, via: parcel_id}
      - {from: fact_property_tax, to: dim_tax_district, via: tax_district_id}
```

### Build Order (depends_on)

Models declare dependencies that determine build order:

```
Tier 0 (Foundation -- no dependencies):
  temporal              depends_on: []
  geospatial            depends_on: []

Tier 1 (Entity -- foundation only):
  corporate.entity      depends_on: [temporal]
  municipal.entity      depends_on: [temporal, geospatial]

Tier 2 (Geospatial subdivisions):
  municipal.geospatial  depends_on: [geospatial, municipal.entity]
  county.geospatial     depends_on: [geospatial, municipal.entity]

Tier 3 (Domain models):
  county.property       depends_on: [temporal, county.geospatial]
  municipal.finance     depends_on: [temporal, municipal.entity, county.property]
  municipal.*           depends_on: [temporal, municipal.geospatial]
```

Rules:
1. No circular dependencies.
2. Base templates (`_base.*`) are NOT listed -- they are schema contracts, not built models.
3. Only list direct dependencies, not transitive ones.

### auto_edges

Base templates declare automatic edges for common FK patterns. When a fact table has a `date_id` column, it automatically gets an edge to `temporal.dim_calendar`. When it has a `location_id`, it gets an edge to `geospatial.dim_location`. These are declared once in the root event base (`_base._base_.event`) and inherited by all fact tables.

---

## 7. Measures and Computed Columns

Measures are pre-defined analytics declared in both `model.md` (model-level) and individual table files (table-level).

### Simple Measures

Compact list format: `[name, aggregation, table.column, description, {options}]`

```yaml
measures:
  simple:
    - [total_payments, sum, fact_ledger_entries.transaction_amount, "Total payment amount", {format: "$#,##0.00"}]
    - [vendor_count, count_distinct, dim_vendor.vendor_id, "Unique vendors", {format: "#,##0"}]
    - [department_count, count_distinct, dim_department.org_unit_id, "City departments", {format: "#,##0"}]
```

Supported aggregations: `sum`, `avg`, `count`, `count_distinct`, `min`, `max`.

### Computed Measures

SQL expressions for calculations that span multiple columns or use CASE logic:

```yaml
measures:
  computed:
    - [budget_surplus, expression, "SUM(CASE WHEN fact_budget_events.event_type = 'REVENUE' THEN fact_budget_events.amount ELSE 0 END) - SUM(CASE WHEN fact_budget_events.event_type = 'APPROPRIATION' THEN fact_budget_events.amount ELSE 0 END)", "Revenue minus appropriations", {format: "$#,##0.00"}]
    - [vendor_payment_pct, expression, "SUM(CASE WHEN fact_ledger_entries.entry_type = 'VENDOR_PAYMENT' THEN fact_ledger_entries.transaction_amount ELSE 0 END) / NULLIF(SUM(fact_ledger_entries.transaction_amount), 0)", "Vendor payments as % of total", {format: "0.00%"}]
```

### Table-Level Measures

Individual table files can also declare measures that operate only on that table's columns:

```yaml
# dim_department.md
measures:
  - [department_count, count_distinct, org_unit_id, "Number of departments", {format: "#,##0"}]
  - [over_budget_count, expression, "SUM(CASE WHEN budget_variance < 0 THEN 1 ELSE 0 END)", "Departments over budget", {format: "#,##0"}]
  - [avg_utilization, avg, budget_utilization_pct, "Avg budget utilization", {format: "0.0%"}]
```

### Build-Time Enrichment vs. Query-Time Measures

There is an important distinction between enrichment (materialized at build time) and measures (computed at query time):

- **Enrichment** (`enrich:` blocks on dimension tables): Pre-computed aggregates stored as physical columns. Example: `dim_department.total_paid` is the sum of all ledger entries for that department, computed once during the build and stored in the Delta table.
- **Measures** (`measures:` blocks): Computed on the fly at query time by the measure executor. Example: `total_payments` sums `transaction_amount` across whatever rows match the current filters.

Enriched columns enable fast lookups ("which departments are over budget?") without joining at query time. Measures enable flexible analytics with arbitrary filters.

---

## 8. Domain Catalog

All 17 registered domain models:

| Canonical Name | Description | Key Tables |
|---------------|-------------|------------|
| **Foundation** | | |
| `temporal` | Master calendar (2000-2050) | dim_calendar |
| `geospatial` | US geographic reference | dim_geography, dim_location |
| **Corporate** | | |
| `corporate.entity` | SEC-registered companies | dim_company |
| `corporate.finance` | Financial statements, earnings | fact_financial_statements |
| **Securities** | | |
| `securities.master` | Unified securities + prices | dim_security, fact_security_prices |
| `securities.stocks` | Stock equities | dim_stock, fact_stock_prices, fact_dividends |
| `securities.forecast` | Price/volume forecasting | fact_forecasts |
| **Municipal** | | |
| `municipal.entity` | Cities, counties, townships | dim_municipality |
| `municipal.finance` | Budget, contracts, payments | fact_ledger_entries, fact_budget_events, dim_vendor, dim_department |
| `municipal.geospatial` | Community areas, wards, beats | dim_community_area, dim_ward, dim_patrol_district |
| `municipal.housing` | Building permits | fact_building_permits |
| `municipal.operations` | 311 service requests | fact_service_requests |
| `municipal.public_safety` | Crimes, arrests | fact_crimes, fact_arrests |
| `municipal.regulatory` | Inspections, violations, licenses | fact_food_inspections, fact_building_violations, dim_facility |
| `municipal.transportation` | Bus/rail ridership, traffic | fact_bus_ridership, fact_rail_ridership, fact_traffic |
| **County** | | |
| `county.geospatial` | Cook County boundaries | dim_township, dim_municipality_boundary |
| `county.property` | Assessed values, parcels, sales | dim_parcel, fact_assessed_values, fact_parcel_sales |

---

## Reference

### YAML Syntax Guides

Detailed reference files in `docs/guides/yaml/`:

| Guide | Topic |
|-------|-------|
| `domain_model.md` | Top-level model keys |
| `tables.md` | Table and column definitions |
| `graph.md` | Edges, paths, auto_edges |
| `depends_on.md` | Dependency specification |
| `extends.md` | Inheritance resolution |
| `sources.md` | Bronze source mapping |
| `measures.md` | Measure definitions |
| `federation.md` | Cross-domain UNION views |
| `views.md` | SQL view definitions |
| `materialization.md` | Build phases and optimization |
| `storage.md` | Storage routing rules |
| `source_onboarding.md` | Adding a new data source end-to-end |

### Key Source Files

| File | Purpose |
|------|---------|
| `src/de_funk/config/domain/__init__.py` | `DomainConfigLoaderV4` and `get_domain_loader()` |
| `src/de_funk/config/domain/config_translator.py` | `translate_domain_config()` -- source-to-node synthesis |
| `src/de_funk/config/domain/extends.py` | `resolve_extends_reference()` and `deep_merge()` |
| `src/de_funk/models/base/model.py` | `BaseModel` -- generic model with graph building |
| `src/de_funk/models/base/domain_model.py` | `DomainModel` -- UNION, seed, distinct, enrich |
| `src/de_funk/models/base/domain_builder.py` | `DomainBuilderFactory` -- dynamic builder registration |
| `src/de_funk/models/base/graph_builder.py` | `GraphBuilder` -- node loading and edge validation |
| `configs/storage.json` | Storage roots and domain_roots overrides |
