---

type: reference
description: "Guide for materialization — what gets built, in what order, and how"
---

> **Implementation Status**: All features fully implemented.


## materialization Guide

Materialization controls which tables are written to Delta Lake storage, the order they are built, and which are kept as intermediates.

---


### What Gets Materialized

| Type | Location | Materialized? | Description |
|------|----------|---------------|-------------|
| `domain-base` | `_base/` | Never | Template only — defines contracts for children |
| `domain-model` | `models/` | Yes | Concrete model — writes to Silver |
| Template table | `_base/*.md` → `_fact_*`, `_dim_*` | Never | Inherited by children via `extends:` |
| Concrete table | `tables/*.md` → `fact_*`, `dim_*` | Yes | Written to `storage/silver/{model}/{table}/` |
| Intermediate table | `tables/*.md` → `_int_*` | Configurable | Use `persist: false` to skip writing |
| Generated table | `tables/*.md` → `generated: true` | Yes (post-build) | Computed from other Silver tables, not from bronze |
| Static/seeded dimension | `tables/*.md` → `static: true` | Yes | Populated from inline `data:` block |

---


### Build Phases

Build phases control the order tables are materialized. Defined in `model.md`:

```yaml
build:
  partitions: [date_id]
  optimize: true
  phases:
    1:
      description: "Build fact tables from source unions"
      tables: [fact_ledger_entries, fact_budget_events, fact_property_tax]
      persist: true
    2:
      description: "Build dimensions from facts (+ bronze)"
      tables: [dim_vendor, dim_department, dim_contract, dim_fund]
      persist: true
      enrich: true
```

#### Build Block Keys

| Key | Required | Description |
|-----|----------|-------------|
| `partitions` | No | Delta partition columns applied to all fact tables: `[date_id]`, `[year]` |
| `sort_by` | No | Z-order columns for optimized reads: `[security_id, date_id]` |
| `optimize` | No | Enable Delta optimization: `true` |
| `phases` | No | Ordered build phases (see below) |

#### Phase Keys

| Key | Required | Description |
|-----|----------|-------------|
| `tables` | Yes | Tables to build in this phase |
| `persist` | No | `true` = write to Silver (default), `false` = intermediate only |
| `enrich` | No | `true` = run enrich blocks on dimension tables in this phase |
| `description` | No | Human-readable phase description |

---


### Phase Ordering

Typical phase pattern:

| Phase | Tables | Why |
|-------|--------|-----|
| 1 | Fact tables | Facts load directly from source unions — no dependencies |
| 2 | Dimension tables | Dimensions aggregate from facts (or bronze) and run `enrich:` |
| 3 | Generated tables | Technical indicators, forecasts — computed from phase 1-2 output |

**Example with 3 phases:**

```yaml
build:
  phases:
    1: { tables: [fact_stock_prices], persist: true }
    2: { tables: [dim_stock, dim_exchange], persist: true }
    3: { tables: [fact_stock_technicals], persist: true }
```

Phase 3 runs after phases 1-2 because `fact_stock_technicals` is `generated: true` — it computes indicators from `fact_stock_prices` data.

---


### Persist Control

`persist` works at two levels:

**Model-level** (build phase):

```yaml
build:
  phases:
    1: { tables: [_int_staging], persist: false }
    2: { tables: [fact_final], persist: true }
```

**Table-level** (individual table):

```yaml
---

type: domain-model-table
table: fact_ledger_entries
table_type: fact
persist: true
---

```

Table-level `persist` overrides phase-level `persist`. If neither is set, the default is `true` (write to Silver).

---


### Generated Tables

Tables marked `generated: true` are not loaded from bronze sources. Instead, they are computed from other Silver tables during a later build phase.

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

The builder knows to compute these tables from the model's existing Silver data (e.g., computing SMA/EMA/RSI from `fact_stock_prices`).

**Current generated tables:**
- `fact_stock_technicals` — technical indicators from price data
- `fact_forecast_price` — ML-generated price predictions
- `fact_forecast_metrics` — model accuracy metrics
- `dim_model_registry` — ML model tracking

---


### Static/Seeded Tables

Tables marked `static: true` or `seed: true` are populated from inline `data:` blocks, not from bronze or other Silver tables:

```yaml
---

type: domain-model-table
table: dim_municipality
table_type: dimension
seed: true
data:
  - municipality_id: "ABS(HASH(...))"
    municipality_name: "Chicago"
    municipality_type: CITY
---

```

These are built before any phase (or as phase 0) since they have no dependencies.

---


### Self-Generated Models

The temporal model is unique — it generates its own data:

```yaml
# models/temporal/model.md
from: self
calendar_config:
  start_date: "2000-01-01"
  end_date: "2050-12-31"
  fiscal_year_start_month: 1
```

`from: self` signals the builder to generate rows algorithmically rather than reading from bronze. The base template `_base/temporal/calendar.md` defines a `generation:` block with default parameters; the model overrides them via `calendar_config:`.

---


### Storage Format

All materialized tables use Delta Lake:

| Feature | Description |
|---------|-------------|
| ACID transactions | Concurrent reads/writes are safe |
| Time travel | Query historical versions |
| Schema evolution | New columns handled automatically |
| Merge/upsert | Incremental updates without full rewrites |

### Output Paths

```
storage/silver/{model}/{table}/
├── _delta_log/              # Transaction log
├── part-00000-*.parquet     # Data files
└── ...
```

Example: `storage/silver/municipal/chicago/finance/fact_ledger_entries/`
