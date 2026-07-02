---

type: reference
description: "Guide for graph definitions - edges only in v5.0"
---

> **Implementation Status**: Explicit `graph.edges` are fully implemented. `auto_edges` and `paths` are **parsed only** — the config loader reads them but the build pipeline does not use them.


## graph Guide

### Implementation Status

| Feature | Status |
|---------|--------|
| `graph.edges` (explicit edges) | **IMPLEMENTED** |
| Cross-model edges | **IMPLEMENTED** |
| Optional edges (left joins) | **IMPLEMENTED** |
| `auto_edges` (inherited FK edges) | **PARSED ONLY** -- config loader reads these from base templates, but they are never auto-injected into the build or query pipeline |
| `graph.paths` (multi-hop traversals) | **PARSED ONLY** -- config loader reads these, but no traversal API exists to use them |

---


In v5.0, graph only contains `edges`. Source/filter/derive are defined in table definitions.

### auto_edges (Inherited FK Edges)

> **PARSED ONLY** — Config parsing reads `auto_edges` from base templates
> (`config/domain/graph.py`), but the build pipeline and query API do not
> auto-inject these edges. All edges must be explicitly declared in `graph.edges`.

Base templates can declare `auto_edges` — FK patterns applied automatically to every fact table whose schema contains the matching column. Any base template can declare `auto_edges`, not just the event root — entity-chain bases (securities, parcel) use them too.

```yaml
# _base/_base_/event.md — event chain (date_id + location_id)
auto_edges:
  - [date_id, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
  - [location_id, geo_location._dim_location, [location_id=location_id], many_to_one, geo_location]

# _base/finance/securities.md — entity chain (date_id only)
auto_edges:
  - [date_id, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]

# _base/property/parcel.md — entity chain (date_id only)
auto_edges:
  - [date_id, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
```

**How it works:**
1. Loader collects `auto_edges` from the base inheritance chain
2. For each fact table, checks if schema contains the `fk_column`
3. If match → generates edge: `{fact_name}_to_{target_short_name}`
4. If no match → no edge (safe)

**Which bases declare auto_edges:**

| Base | auto_edges | Inherited By |
|------|-----------|-------------|
| `_base._base_.event` | `date_id`, `location_id` | All event-chain bases (crime, inspection, permit, service_request, transit, traffic, financial_event) |
| `_base.finance.securities` | `date_id` | securities, stocks, options, etfs, futures |
| `_base.property.parcel` | `date_id` | county_property (and any future property models) |

**What still needs explicit edges:**

| Pattern | Example | Why |
|---------|---------|-----|
| Non-standard FK column names | `sale_date_id`, `report_date_id`, `period_end_date_id` | Column name doesn't match auto_edge pattern |
| Natural key joins | `community_area=area_number` | Not a FK column |
| Fact-to-fact | `arrest_to_crime` via `incident_id` | Business relationship |
| Domain-specific dim FKs | `inspection_to_facility` | Unique to the domain |

### Edge Format (Tabular)

```yaml
graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [prices_to_stock, fact_stock_prices, dim_stock, [security_id=security_id], many_to_one, null]
```

### Edge Columns

| Position | Name | Required | Description |
|----------|------|----------|-------------|
| 0 | edge_name | Yes | Unique edge identifier |
| 1 | from | Yes | Source table (in this model) |
| 2 | to | Yes | Target table (can be `model.table` for cross-model) |
| 3 | on | Yes | Join conditions `[col1=col2]` |
| 4 | type | Yes | `many_to_one`, `one_to_one`, `one_to_many` |
| 5 | cross_model | No | Target model name (null for same-model) |

### Cross-Model Edges

When `to` references another model, set `cross_model`:

```yaml
- [stock_to_company, dim_stock, company.dim_company, [company_id=company_id], many_to_one, company]
```

### Optional Edges (Left Joins)

For nullable FKs, append `optional: true` as a 7th element:

```yaml
- [entry_to_chart, fact_entries, dim_chart, [expense_category=account_code], many_to_one, null, optional: true]
```

### Paths (Multi-Hop Traversals)

> **PARSED ONLY** — Config parsing reads `graph.paths` (`config/domain/graph.py`),
> but neither the build pipeline nor the FastAPI query API uses them. The old
> `models/api/graph.py` had path traversal code, but that's dead code from the
> pre-FastAPI query layer.

Named multi-hop join sequences. Declare in `graph.paths:` on model files to document common analysis chains.

```yaml
graph:
  paths:
    assessment_to_tax_district:
      description: "Property tax calculation chain"
      steps:
        - {from: fact_assessed_values, to: dim_parcel, via: parcel_id}
        - {from: dim_parcel, to: dim_tax_district, via: tax_code}
```

Each step uses an existing edge. Steps can cross model boundaries:

```yaml
    sale_to_township:
      steps:
        - {from: fact_parcel_sales, to: dim_parcel, via: parcel_id}
        - {from: dim_parcel, to: county_geospatial.dim_township, via: township_code}
```

**Models with paths**: securities/stocks, securities/master, county/property, municipal/finance, municipal/public_safety, corporate/finance.

### v5.0 Change

Graph `nodes:` with `select:`, `derive:`, `drop:` are **deprecated**. Those are now in table schema.
