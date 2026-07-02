---

type: reference
description: "Guide for storage and source discovery configuration"
---

> **Implementation Status**: All features fully implemented.


## storage Guide

Storage configuration defines where Silver output is written and how source files are discovered. Bronze input is handled by source files (see source_onboarding.md), not by the storage block.

---


### Storage Block

Every `model.md` declares a `storage:` block:

```yaml
storage:
  format: delta
  silver:
    root: storage/silver/temporal/
```

#### Storage Keys

| Key | Required | Description |
|-----|----------|-------------|
| `format` | Yes | Always `delta` (Delta Lake) |
| `silver.root` | Yes | Output directory path for materialized tables |
| `sources_from` | No | Directory containing source files (alternative placement — see below) |

---


### sources_from

Tells the loader where to discover `domain-model-source` files. Can be placed in two locations:

**Top-level key** (corporate / securities models):

```yaml
# models/corporate/entity/model.md
sources_from: sources/entity/
storage:
  format: delta
  silver:
    root: storage/silver/corporate/entity/
```

**Inside storage block** (municipal / county models):

```yaml
# models/municipal/finance/model.md
storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/finance/
```

Both placements are equivalent. The loader discovers all `*.md` files in the directory and its subdirectories automatically.

---


### Entity Placeholder

Municipal and county models use `{entity}` as a placeholder for city/county-specific paths:

```yaml
storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/finance/
```

At build time, `{entity}` is replaced with the concrete entity name (e.g., `chicago`, `cook_county`). This enables the same model definition to serve multiple municipalities.

**Models using `{entity}`:**
- All `models/municipal/*/model.md` files
- All `models/county/*/model.md` files

**Models NOT using `{entity}`:**
- `models/temporal/model.md` — no sources, self-generated
- `models/corporate/*/model.md` — use literal paths like `sources/entity/`
- `models/securities/*/model.md` — use literal paths like `sources/`
- `models/geospatial/model.md` — uses `sources/{entity}/`

---


### Silver Output Paths

Silver tables are written to subdirectories under `silver.root`:

```
storage/silver/{model}/
├── fact_ledger_entries/     # Delta Lake table directory
├── dim_vendor/
├── dim_department/
└── ...
```

Each table becomes a Delta Lake directory with `_delta_log/` and Parquet data files.

---


### Source Discovery

When `sources_from:` is set, the loader auto-discovers source files:

```
sources/{entity}/finance/
├── payments.md              # domain-model-source
├── payroll.md
├── contracts.md
└── budget.md
```

Each source file declares:
- `from:` — bronze table path (e.g., `bronze.chicago_payments`)
- `maps_to:` — target Silver table (e.g., `fact_ledger_entries`)
- `aliases:` — column mappings from bronze to canonical schema

No wiring is needed in `model.md`. The loader reads `model.md` first, then discovers all source files, and links them to tables via `maps_to:`.

---


### Models Without Sources

Two patterns produce tables without bronze sources:

1. **Self-generated** (temporal): Uses `from: self` + `calendar_config:` to generate rows
2. **Static/seeded** dimensions: Uses `static: true` + inline `data:` block

Neither requires `sources_from:`.

---


### Complete Examples

**Simple (no entity placeholder):**

```yaml
storage:
  format: delta
  silver:
    root: storage/silver/temporal/
```

**Corporate (top-level sources_from):**

```yaml
sources_from: sources/finance/
storage:
  format: delta
  silver:
    root: storage/silver/corporate/finance/
```

**Municipal (entity-parameterized):**

```yaml
storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/finance/
```
