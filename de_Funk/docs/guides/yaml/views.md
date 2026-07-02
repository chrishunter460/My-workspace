---

type: reference
description: "Guide for the views convention — layered calculations and rollup aggregations"
status: planned
---

> **Implementation Status**: **PLANNED**. Config parsing infrastructure exists (`config/domain/views.py`) but views are NOT materialized as Silver tables. All documentation below describes the intended design.


## views Guide

### Implementation Status

| Feature | Status |
|---------|--------|
| `views:` block parsing | **PARSED ONLY** -- config loader reads and validates views, but the build pipeline never materializes them |
| Derived views | **PARSED ONLY** |
| Rollup views | **PARSED ONLY** |
| View assumptions | **PARSED ONLY** |
| View layering (view-on-view) | **PARSED ONLY** |
| View-level measures | **PARSED ONLY** |

> **PARSED ONLY** — Config parsing is implemented (`config/domain/views.py`), but
> the build pipeline does not yet materialize views. Views declared in model configs
> are parsed and validated but never built into Silver tables.

A `views:` block declares named views that layer calculations onto physical tables. Views separate assumption-driven business logic from raw data storage.

### Two View Types

| Type | Purpose | Example |
|------|---------|---------|
| `derived` | Apply configurable assumptions to compute new columns | assessed_value_total × equalization_factor = equalized_value_total |
| `rollup` | Pre-aggregate to a different (coarser) grain | Parcel-level → township-level summary |

### Derived View Syntax (Base Template)

```yaml
views:
  _view_equalized_values:
    type: derived
    from: _fact_assessed_values
    join: [{table: _dim_tax_district, on: [tax_code=tax_code], fields: [equalization_factor]}]
    description: "Assessed values with equalization factor applied"
    assumptions:
      equalization_factor:
        type: "decimal(10,6)"
        default: 1.0
        description: "State equalization factor"
        source: "Joined from dim_tax_district"
    schema:
      - [parcel_id, string, false, "FK to dim_parcel"]
      - [equalized_value_total, "decimal(18,2)", false, "Equalized value", {derived: "assessed_value_total * equalization_factor"}]
    measures:
      - [total_equalized_value, sum, equalized_value_total, "Total equalized value", {format: "$#,##0.00"}]
```

### Rollup View Syntax

```yaml
views:
  _view_township_summary:
    type: rollup
    from: _fact_assessed_values
    grain: [township_code, year, assessment_stage]
    description: "Township-level assessment summary"
    schema:
      - [township_code, string, false, "Township"]
      - [parcel_count, integer, false, "Parcels", {derived: "COUNT(DISTINCT parcel_id)"}]
      - [total_assessed_value, "decimal(18,2)", false, "Total assessed value", {derived: "SUM(assessed_value_total)"}]
```

### Key Properties

| Property | Derived | Rollup | Description |
|----------|---------|--------|-------------|
| `type` | `derived` | `rollup` | View classification |
| `from` | Required | Required | Source table or another view |
| `join` | Optional | Not used | Dimension joins for assumption values |
| `grain` | Same as source | Required | New grouping columns |
| `assumptions` | Optional | Not used | Named parameters with type, default, source |
| `schema` | Required | Required | Output columns with `{derived:}` expressions |
| `measures` | Optional | Optional | Aggregations on view columns |

### Assumptions

Assumptions are named, typed, overridable parameters:

```yaml
assumptions:
  equalization_factor:
    type: "decimal(10,6)"     # SQL type
    default: 1.0              # Fallback if no join match
    description: "..."        # Human-readable
    source: "Joined from..."  # Where value comes from
```

Models override assumptions at implementation time to bind to specific data sources.

### View Layering

Views can reference other views in their `from:` field, creating calculation chains:

```
_fact_assessed_values (physical table)
     ↓ join equalization_factor
_view_equalized_values (equalized_value_total = assessed_value_total × factor)
     ↓ join total_rate
_view_estimated_tax (estimated_tax = equalized_value_total × rate)
```

The loader resolves the dependency chain and builds views in order.

### Model-Level Implementation

Models implement base view templates either inline or as separate files:

**Inline in model.md:**
```yaml
views:
  view_equalized_values:
    extends: _base.property.parcel._view_equalized_values
    assumptions:
      equalization_factor:
        source: dim_tax_district.equalization_factor
        join_on: [township_code=township_code, year=tax_year]
```

**Separate file** (`models/{model}/views/view_name.md`):
```yaml
---

type: domain-model-view
view: view_equalized_values
extends: _base.property.parcel._view_equalized_values
view_type: derived

assumptions:
  equalization_factor:
    source: dim_tax_district.equalization_factor
    join_on: [township_code=township_code, year=tax_year]
---

```

### Naming Convention

- Base templates: `_view_*` (underscore prefix, like `_dim_*` and `_fact_*`)
- Model implementations: `view_*` (no underscore prefix, like `dim_*` and `fact_*`)

### Current View Assignments

| Base Template | Views | Type |
|--------------|-------|------|
| `_base.property.parcel` | `_view_equalized_values` | derived |
| `_base.property.parcel` | `_view_estimated_tax` | derived (layers on equalized_values) |
| `_base.property.parcel` | `_view_township_summary` | rollup |

### Views vs Python Measures

| Aspect | Views | Python Measures |
|--------|-------|----------------|
| **Output** | New table/columns | New columns on existing table |
| **Grain** | Can change grain (rollup) | Same grain as source |
| **Assumptions** | Named, typed, overridable | Params in YAML |
| **Joins** | Can join dimension data | Operate on single table |
| **When to use** | Business logic with external assumptions | Complex math on existing columns |
